import pytest

from plain_parser import test_plain_file as tpf
from plain_parser.exceptions import PlainSyntaxError

HEAD = "---\nmodule: m\nfunc_id: f\n---\n\n"


def test_scenarios_property_order(tmp_path):
    text = HEAD + "***conformance tests***\n\n# a\nA.\n\n***acceptance tests***\n\n# b\nB.\n"
    parsed = tpf.parse_test_plain_file_source(text, "f.plain", [str(tmp_path)], {})
    assert [s.id for s in parsed.scenarios] == ["a", "b"]


def test_missing_conformance_section(tmp_path):
    with pytest.raises(PlainSyntaxError, match="has no `\\*\\*\\*conformance tests\\*\\*\\*` section"):
        tpf.parse_test_plain_file_source(HEAD, "f.plain", [str(tmp_path)], {})


def test_empty_module_value(tmp_path):
    with pytest.raises(PlainSyntaxError, match="must be a non-empty string"):
        tpf.parse_test_plain_file_source("---\nmodule: ''\nfunc_id: f\n---\n", "f.plain", [str(tmp_path)], {})


def test_concept_reported_once_per_scenario(tmp_path):
    text = HEAD + "***conformance tests***\n\n# a\n:X: and :X:.\n\n***acceptance tests***\n"
    parsed = tpf.parse_test_plain_file_source(text, "f.plain", [str(tmp_path)], {})
    assert len(tpf.validate_scenario_concepts(parsed, set())) == 1
