"""Conformance tests of module resource_loading."""

import os

import pytest
from liquid2.exceptions import TemplateNotFoundError
from plain_parser import loaders
from plain_parser.exceptions import (
    InvalidLiquidVariableName,
    PlainSyntaxError,
    UnsupportedBase64Content,
    UnsupportedResourceType,
)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(text)


# find-base64-blob


def test_find_base64_blob__long_run_is_a_blob():
    blob = loaders.find_large_base64_blob("curl -d 'img=" + "A" * 8292 + "'")
    assert blob is not None and len(blob) == 8292


def test_find_base64_blob__short_run_is_not_a_blob():
    assert loaders.find_large_base64_blob("token=" + "A" * 8092) is None


def test_find_base64_blob__data_uri_header_is_included():
    blob = loaders.find_large_base64_blob("x data:image/png;base64," + "A" * 8192 + "==")
    assert blob is not None
    assert len(blob) == 8216
    assert blob.startswith("data:image/png;base64,")


# look-up-files


def test_look_up_files__first_dir_wins(tmp_path):
    first, second = str(tmp_path / "first"), str(tmp_path / "second")
    _write(os.path.join(first, "notes.md"), "1")
    _write(os.path.join(second, "notes.md"), "2")
    assert loaders.resolve_linked_resource([first, second], "notes.md") == os.path.join(first, "notes.md")


def test_look_up_files__later_dir_is_searched(tmp_path):
    first, second = str(tmp_path / "first"), str(tmp_path / "second")
    os.makedirs(first)
    _write(os.path.join(second, "notes.md"), "2")
    assert loaders.resolve_linked_resource([first, second], "notes.md") == os.path.join(second, "notes.md")
    assert loaders.find_resource_dir([first, second], "notes.md") == second


def test_look_up_files__missing_file(tmp_path):
    directory = str(tmp_path)
    assert loaders.resolve_linked_resource([directory], "missing.md") is None
    assert loaders.find_resource_dir([directory], "missing.md") is None
    assert loaders.open_from([directory], "missing.md") is None


def test_look_up_files__parent_relative_path(tmp_path):
    root = tmp_path / "root"
    _write(str(root / "shared.md"), "shared")
    os.makedirs(root / "plain")
    plain_dir = str(root / "plain")
    assert loaders.resolve_linked_resource([plain_dir], "../shared.md") == os.path.join(plain_dir, "../shared.md")


def test_look_up_files__directory_hides_later_file(tmp_path):
    first, second = str(tmp_path / "first"), str(tmp_path / "second")
    os.makedirs(os.path.join(first, "notes.md"))
    _write(os.path.join(second, "notes.md"), "2")
    assert loaders.resolve_linked_resource([first, second], "notes.md") == os.path.join(first, "notes.md")


def test_look_up_files__read_text(tmp_path):
    first, second = str(tmp_path / "first"), str(tmp_path / "second")
    os.makedirs(first)
    _write(os.path.join(second, "notes.md"), "# hello")
    assert loaders.open_from([first, second], "notes.md") == "# hello"


# relative-resource-path


def test_relative_resource_path__same_directory():
    assert loaders.relative_resource_path("/p/spec", "/p/spec", "notes.md") == "notes.md"
    assert loaders.relative_resource_path("/p/spec", "/p/spec", "../shared.md") == "../shared.md"


def test_relative_resource_path__other_directory():
    assert loaders.relative_resource_path("/p/app/python", "/p/tpl", "notes.md") == "../../tpl/notes.md"
    assert loaders.relative_resource_path("/p/app/python", "/p/tpl", "../sub.md") == "../../tpl/../sub.md"


def test_relative_resource_path__subdirectory():
    assert loaders.relative_resource_path("/p/spec", "/p/spec/tpl/sub", "deep.md") == "tpl/sub/deep.md"


def test_relative_resource_path__no_relative_path(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("path is on mount 'Q:', start on mount 'P:'")

    monkeypatch.setattr(os.path, "relpath", fail)
    assert loaders.relative_resource_path("/p/spec", "/q/tpl", "notes.md") == "/q/tpl/notes.md"


# load-linked-files


def test_load_linked_files__text_file(tmp_path):
    _write(str(tmp_path / "notes.md"), "# hello")
    result = loaders.load_linked_resources([str(tmp_path)], [{"text": "Notes", "target": "notes.md"}], "my_thing")
    assert result == {"notes.md": "# hello"}


def test_load_linked_files__small_base64_is_allowed(tmp_path):
    text = "token=" + "A" * 8092
    _write(str(tmp_path / "token.txt"), text)
    result = loaders.load_linked_resources([str(tmp_path)], [{"text": "t", "target": "token.txt"}], "my_thing")
    assert result == {"token.txt": text}


def test_load_linked_files__binary_file(tmp_path):
    (tmp_path / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe\x80")
    with pytest.raises(UnsupportedResourceType) as error:
        loaders.load_linked_resources([str(tmp_path)], [{"text": "Icon", "target": "icon.png"}], "my_thing")
    message = str(error.value)
    assert "icon.png" in message and "binary file" in message and "my_thing" in message


def test_load_linked_files__missing_file(tmp_path):
    with pytest.raises(FileNotFoundError) as error:
        loaders.load_linked_resources([str(tmp_path)], [{"text": "m", "target": "missing.md"}], "my_thing")
    message = str(error.value)
    assert "missing.md" in message and "my_thing" in message and "--template-dir" not in message


def test_load_linked_files__base64_blob(tmp_path):
    _write(str(tmp_path / "request.txt"), "curl -d 'selfie_image=" + "A" * 8292)
    with pytest.raises(UnsupportedBase64Content) as error:
        loaders.load_linked_resources([str(tmp_path)], [{"text": "r", "target": "request.txt"}], "my_thing")
    message = str(error.value)
    assert "request.txt" in message and "my_thing" in message and "8292" in message


# render-liquid


def test_render_liquid__include_is_loaded_and_recorded(tmp_path):
    _write(str(tmp_path / "t.plain"), "B")
    rendered, loaded = loaders.get_loaded_templates([str(tmp_path)], "A {% include 't.plain' %}")
    assert rendered == "A B"
    assert loaded == {"t.plain": "B"}


def test_render_liquid__missing_include(tmp_path):
    with pytest.raises(TemplateNotFoundError) as error:
        loaders.get_loaded_templates([str(tmp_path)], "{% include 'nope.plain' %}")
    message = str(error.value)
    assert "nope.plain" in message and "--template-dir" not in message


def test_render_liquid__malformed_tag(tmp_path):
    with pytest.raises(PlainSyntaxError) as error:
        loaders.get_loaded_templates([str(tmp_path)], "***functional specs***\n\n{% if %}", "malformed_tag")
    assert str(error.value).startswith("Plain syntax error: Invalid Liquid at malformed_tag:3:0: ")


def test_render_liquid__unterminated_output(tmp_path):
    source = "***functional specs***\n\n# a-user-can-add-a\nA user can add a {{ task_name\n"
    with pytest.raises(PlainSyntaxError) as error:
        loaders.get_loaded_templates([str(tmp_path)], source, "unterminated_output")
    assert str(error.value).startswith("Plain syntax error: Invalid Liquid at unterminated_output:5:0: ")


def test_render_liquid__undefined_variable(tmp_path):
    with pytest.raises(Exception) as error:
        loaders.get_loaded_templates([str(tmp_path)], "{{ missing }}")
    assert str(error.value).startswith("Undefined liquid variable: ")


def test_render_liquid__error_message_without_position():
    from liquid2.exceptions import LiquidSyntaxError

    error = LiquidSyntaxError("missing expression", token=None, template_name="header")
    assert loaders.liquid_error_message(error) == "Plain syntax error: Invalid Liquid in header: missing expression"
    error = LiquidSyntaxError("missing expression", token=None)
    assert loaders.liquid_error_message(error) == "Plain syntax error: Invalid Liquid: missing expression"


# indent-included-templates


def test_indent_included_templates__indented_includes(tmp_path):
    implement = (
        "something nice and useful\n"
        "    - the nice thing should be really nice\n"
        "    - the useful thing should be really useful"
    )
    template = "- This is a functionality inside a template."
    _write(str(tmp_path / "implement.plain"), implement)
    _write(str(tmp_path / "template.plain"), template)
    source = (
        '- Implement {% include "implement.plain" %}\n'
        '{% include "template.plain" %}\n'
        '    {% include "template.plain" %}\n'
        '    - Implement {% include "implement.plain" %}'
    )
    rendered, loaded = loaders.get_loaded_templates([str(tmp_path)], source)
    assert rendered == (
        "- Implement something nice and useful\n"
        "    - the nice thing should be really nice\n"
        "    - the useful thing should be really useful\n"
        "- This is a functionality inside a template.\n"
        "    - This is a functionality inside a template.\n"
        "    - Implement something nice and useful\n"
        "        - the nice thing should be really nice\n"
        "        - the useful thing should be really useful"
    )
    assert loaded == {"implement.plain": implement, "template.plain": template}


def test_indent_included_templates__include_in_comment_is_kept(tmp_path):
    rendered, _ = loaders.get_loaded_templates(
        [str(tmp_path)], '> This is a with an include tag {% include "template.plain" %}'
    )
    assert rendered == "> This is a with an include tag {% include 'template.plain' %}"


def test_indent_included_templates__arguments_are_variables(tmp_path):
    _write(str(tmp_path / "t.plain"), "Hello {{ name }}")
    rendered, _ = loaders.get_loaded_templates([str(tmp_path)], "{% include 't.plain', name: 'Ann' %}")
    assert rendered == "Hello Ann"


# reject-prohibited-characters


def test_reject_prohibited_characters__clean_value_passes(tmp_path):
    _write(str(tmp_path / "t.plain"), "{{ v | prohibited_chars: '#' }}")
    rendered, _ = loaders.get_loaded_templates([str(tmp_path)], "{% include 't.plain', v: 5 %}")
    assert rendered == "5"


def test_reject_prohibited_characters__prohibited_character(tmp_path):
    _write(str(tmp_path / "t.plain"), "{{ v | prohibited_chars: '#' }}")
    with pytest.raises(InvalidLiquidVariableName) as error:
        loaders.get_loaded_templates([str(tmp_path)], "{% include 't.plain', v: 'a#b' %}")
    assert str(error.value) == "'#' is not a valid character for variable 'v' (value: 'a#b')."
