import pytest

from plain_parser import plain_spec


def _tree(*frids):
    return {"functional specs": [{"id": f, "markdown": f, "linked_resources": []} for f in frids]}


def test_next_previous_in_middle():
    tree = _tree("a", "b", "c")
    assert plain_spec.get_next_frid(tree, "b") == "c"
    assert plain_spec.get_previous_frid(tree, "b") == "a"


def test_frids_before_unknown_returns_all():
    assert plain_spec.get_frids_before(_tree("a", "b"), "zz") == ["a", "b"]


def test_range_start_equals_end():
    assert plain_spec.get_frids_range(_tree("a", "b"), "b", "b") == ["b"]


def test_code_variable_conflict():
    tree = {
        "definitions": [{"markdown": "- {{ x }}", "code_variables": [{"name": "x", "value": "1"}]}],
        "functional specs": [
            {"id": "a", "markdown": "{{ x }}", "linked_resources": [], "code_variables": [{"name": "x", "value": "2"}]}
        ],
    }
    with pytest.raises(Exception, match="^Code variable x has multiple values: 1 and 2$"):
        plain_spec.get_specifications_for_frid(tree, "a")


def test_same_target_other_text():
    tree = {
        "definitions": [
            {"markdown": "- a", "linked_resources": [{"text": "one", "target": "x.md"}]},
            {"markdown": "- b", "linked_resources": [{"text": "two", "target": "x.md"}]},
        ]
    }
    with pytest.raises(Exception, match="^The linked resource two is linked to multiple files: x.md$"):
        plain_spec.collect_linked_resources(tree, [], None, False)


def test_section_filter():
    tree = {
        "definitions": [{"markdown": "- a", "linked_resources": [{"text": "d", "target": "d.md"}]}],
        "test reqs": [{"markdown": "- b", "linked_resources": [{"text": "t", "target": "t.md"}]}],
    }
    registry: list = []
    plain_spec.collect_linked_resources(tree, registry, ["test reqs"], False)
    assert [r["target"] for r in registry] == ["t.md"]
