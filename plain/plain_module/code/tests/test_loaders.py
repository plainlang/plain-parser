import pytest

from plain_parser import loaders


def test_blob_padding_is_limited_to_two():
    blob = loaders.find_large_base64_blob("A" * 8192 + "===")
    assert blob == "A" * 8192 + "=="


def test_exact_limit_is_a_blob():
    assert loaders.find_large_base64_blob("A" * 8192) == "A" * 8192
    assert loaders.find_large_base64_blob("A" * 8191) is None


def test_open_from_invalid_utf8_raises(tmp_path):
    (tmp_path / "b.bin").write_bytes(b"\xff\xfe")
    with pytest.raises(UnicodeDecodeError):
        loaders.open_from([str(tmp_path)], "b.bin")


def test_open_from_skips_directory(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.md").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "x.md").write_text("ok")
    assert loaders.open_from([str(tmp_path / "a"), str(tmp_path / "b")], "x.md") == "ok"


def test_target_read_once(tmp_path):
    (tmp_path / "n.md").write_text("x")
    result = loaders.load_linked_resources(
        [str(tmp_path)], [{"text": "a", "target": "n.md"}, {"text": "a", "target": "n.md"}], "m"
    )
    assert result == {"n.md": "x"}


def test_code_variable_outputs_value_without_mapping(tmp_path):
    (tmp_path / "t.plain").write_text("{{ v | code_variable }}")
    rendered, _ = loaders.get_loaded_templates([str(tmp_path)], "{% include 't.plain', v: 'x' %}")
    assert rendered == "x"


def test_filter_with_empty_scope(tmp_path):
    with pytest.raises(Exception, match="^Invalid use of prohibited_chars filter!$"):
        loaders.get_loaded_templates([str(tmp_path)], "{{ 'a' | prohibited_chars: '#' }}")
