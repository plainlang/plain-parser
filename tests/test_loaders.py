import os
import tempfile

import pytest

from plain_parser.exceptions import UnsupportedBase64Content, UnsupportedResourceType
from plain_parser.loaders import MAX_BASE64_BLOB_LENGTH, load_linked_resources, resolve_linked_resource


@pytest.fixture
def template_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def test_load_linked_resources_text_file(template_dir):
    file_path = os.path.join(template_dir, "notes.md")
    with open(file_path, "w") as f:
        f.write("# hello")

    result = load_linked_resources([template_dir], [{"text": "Notes", "target": "notes.md"}], "my_thing")

    assert result == {"notes.md": "# hello"}


def test_load_linked_resources_binary_file_raises_unsupported_resource_type(template_dir):
    file_path = os.path.join(template_dir, "icon.png")
    with open(file_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe\xfd")

    with pytest.raises(UnsupportedResourceType) as exc_info:
        load_linked_resources([template_dir], [{"text": "Icon", "target": "icon.png"}], "my_thing")

    assert "icon.png" in str(exc_info.value)
    assert "binary file" in str(exc_info.value)
    assert "my_thing" in str(exc_info.value)


def test_load_linked_resources_missing_file_raises_file_not_found(template_dir):
    with pytest.raises(FileNotFoundError) as exc_info:
        load_linked_resources([template_dir], [{"text": "Missing", "target": "missing.md"}], "my_thing")

    message = str(exc_info.value)
    assert "missing.md" in message
    assert "my_thing" in message
    assert "--template-dir" not in message


def test_load_linked_resources_base64_blob_raises(template_dir):
    file_path = os.path.join(template_dir, "request.txt")
    with open(file_path, "w") as f:
        f.write("curl -d 'selfie_image=" + "A" * (MAX_BASE64_BLOB_LENGTH + 100) + "'")

    with pytest.raises(UnsupportedBase64Content) as exc_info:
        load_linked_resources([template_dir], [{"text": "Request", "target": "request.txt"}], "my_thing")

    assert "request.txt" in str(exc_info.value)
    assert "my_thing" in str(exc_info.value)


def test_load_linked_resources_small_base64_allowed(template_dir):
    file_path = os.path.join(template_dir, "token.txt")
    with open(file_path, "w") as f:
        f.write("token=" + "A" * (MAX_BASE64_BLOB_LENGTH - 100))

    result = load_linked_resources([template_dir], [{"text": "Token", "target": "token.txt"}], "my_thing")

    assert "token.txt" in result


def test_load_linked_resources_real_base64_image_raises(template_dir):
    # Real base64-encoded JPEG that made Gemini 3 fail, inlined into a curl example resource.
    sample_path = os.path.join(os.path.dirname(__file__), "data", "sample_base64_image.txt")
    with open(sample_path) as f:
        blob = f.read()

    file_path = os.path.join(template_dir, "face_match_request.txt")
    with open(file_path, "w") as f:
        f.write(f"curl -d 'selfie_image={blob}' https://example.com/face-match")

    with pytest.raises(UnsupportedBase64Content) as exc_info:
        load_linked_resources([template_dir], [{"text": "Request", "target": "face_match_request.txt"}], "face_match")

    assert "face_match_request.txt" in str(exc_info.value)
    assert str(len(blob)) in str(exc_info.value)


def test_get_loaded_templates_missing_include_names_template(template_dir):
    from liquid2 import TemplateNotFoundError

    from plain_parser.loaders import get_loaded_templates

    with pytest.raises(TemplateNotFoundError) as exc_info:
        get_loaded_templates([template_dir], "{% include 'nope.plain' %}")

    message = str(exc_info.value)
    assert "nope.plain" in message
    assert "--template-dir" not in message


def test_resolve_linked_resource_returns_none_when_missing(template_dir):
    assert resolve_linked_resource([template_dir], "missing.md") is None


def test_resolve_linked_resource_first_dir_wins():
    with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
        for d in (first, second):
            with open(os.path.join(d, "notes.md"), "w") as f:
                f.write("x")

        assert resolve_linked_resource([first, second], "notes.md") == os.path.join(first, "notes.md")


def test_resolve_linked_resource_falls_back_to_later_dir():
    with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
        with open(os.path.join(second, "notes.md"), "w") as f:
            f.write("x")

        assert resolve_linked_resource([first, second], "notes.md") == os.path.join(second, "notes.md")


def test_resolve_linked_resource_parent_relative_path():
    with tempfile.TemporaryDirectory() as root:
        spec_dir = os.path.join(root, "plain")
        os.mkdir(spec_dir)
        with open(os.path.join(root, "shared.md"), "w") as f:
            f.write("x")

        assert resolve_linked_resource([spec_dir], "../shared.md") == os.path.join(spec_dir, "../shared.md")


def test_resolve_linked_resource_directory_in_first_dir_shadows_file_in_second():
    # Parity with codeplain: existence, not file-ness, decides the match.
    with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
        os.mkdir(os.path.join(first, "notes.md"))
        with open(os.path.join(second, "notes.md"), "w") as f:
            f.write("x")

        assert resolve_linked_resource([first, second], "notes.md") == os.path.join(first, "notes.md")
