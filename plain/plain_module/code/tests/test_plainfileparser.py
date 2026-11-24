import pytest

from plain_parser import plain_file
from plain_parser.exceptions import PlainSyntaxError


def test_simple_module(get_test_data_path):
    name, tree, requires = plain_file.plain_file_parser("simple.plain", [get_test_data_path("data")])
    assert name == "simple"
    assert requires == []
    assert tree["functional specs"][0]["markdown"] == "Simple functionality"


def test_restore_stripped_lines():
    text = "---\na: 1\n---\n\nbody\n"
    assert plain_file.restore_stripped_lines(text, "body") == "\n\n\n\nbody\n"


def test_parse_result_fields(tmp_path):
    result = plain_file.parse_plain_source(
        "---\nrequires:\n  - base\n---\n***implementation reqs***\n\n- A req.\n", {}, [str(tmp_path)], [], []
    )
    assert result.required_modules == ["base"]
    assert result.required_concepts == []
    assert list(result.plain_source) == ["implementation reqs"]


def test_marshall_list_item_with_link(tmp_path):
    (tmp_path / "a.md").write_text("x")
    result = plain_file.parse_plain_source("***definitions***\n\n- :A: see [a](a.md).\n", {}, [str(tmp_path)], [], [])
    tree = plain_file.marshall_plain_source(result.plain_source)
    assert tree == {
        "definitions": [{"markdown": "- :A: see `[resource]a`.", "linked_resources": [{"text": "a", "target": "a.md"}]}]
    }


def test_link_to_directory(tmp_path):
    (tmp_path / "dir").mkdir()
    text = "***implementation reqs***\n\n- req\n\n***functional specs***\n\n# f\nSee [d](dir).\n"
    (tmp_path / "m.plain").write_text(text)
    with pytest.raises(PlainSyntaxError, match="must be a file"):
        plain_file.plain_file_parser("m.plain", [str(tmp_path)])


def test_link_to_plain_file(tmp_path):
    text = "***implementation reqs***\n\n- req\n\n***functional specs***\n\n# f\nSee [d](other.plain).\n"
    (tmp_path / "m.plain").write_text(text)
    with pytest.raises(PlainSyntaxError, match="is a .plain file"):
        plain_file.plain_file_parser("m.plain", [str(tmp_path)])


def test_process_section_code_variables():
    section = [{"markdown": "x TOKEN y"}]
    plain_file.process_section_code_variables(section, {"TOKEN": {"v": "1"}})
    assert section == [{"markdown": "x {{ v }} y", "code_variables": [{"name": "v", "value": "1"}]}]
