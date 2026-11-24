"""Conformance tests of module spec_tree."""

import hashlib
import json

import pytest
from plain_parser import exceptions, plain_spec
from plain_parser.exceptions import InvalidFridArgument


def _func(frid, markdown="", conformance=None, acceptance=None, links=None, **extra):
    item = {
        "id": frid,
        "markdown": markdown,
        "linked_resources": links or [],
        "conformance_tests": conformance or [],
        "acceptance_tests": acceptance or [],
    }
    item.update(extra)
    return item


def _tree(*frids):
    return {"functional specs": [_func(f, f"{f} body") for f in frids]}


def _link(target, text=None):
    return {"text": text if text is not None else target, "target": target}


SIMPLE_TREE = {
    "implementation reqs": [{"markdown": "- Simple implementation requirement"}],
    "functional specs": [_func("simple-functionality", "Simple functionality")],
}


# define-error-classes


def test_define_error_classes__error_classes_are_exceptions():
    for name in [
        "PlainSyntaxError",
        "UnsupportedBase64Content",
        "UnsupportedResourceType",
        "InvalidFridArgument",
        "InvalidLiquidVariableName",
        "ModuleDoesNotExistError",
        "MissingFunctionalitiesError",
        "ImportedModuleWithFunctionalitiesError",
        "MissingTestPlainFileError",
    ]:
        assert issubclass(getattr(exceptions, name), Exception)


# check-semantic-id


def test_check_semantic_id__accepts_hyphen_joined_segments():
    for text in ["a", "add-task", "add-task-2", "2", "a-b-c", "x1-y2"]:
        assert plain_spec.is_semantic_id(text), text


def test_check_semantic_id__rejects_other_shapes():
    for text in [
        "",
        "-",
        "---",
        "-add-task",
        "add-task-",
        "add--task",
        "add_task",
        "Add-task",
        "add task",
        "add.task",
        "ädd",
    ]:
        assert not plain_spec.is_semantic_id(text), text


# walk-func-ids


def test_walk_func_ids__func_ids_in_file_order():
    assert list(plain_spec.get_frids(_tree("f1", "f2", "f3", "f4"))) == ["f1", "f2", "f3", "f4"]


def test_walk_func_ids__first_func_id():
    assert plain_spec.get_first_frid(_tree("f1", "f2")) == "f1"
    assert plain_spec.get_first_frid({"definitions": []}) is None


def test_walk_func_ids__next_and_previous():
    tree = _tree("simple-functionality")
    assert plain_spec.get_next_frid(tree, "simple-functionality") is None
    assert plain_spec.get_previous_frid(tree, "simple-functionality") is None


def test_walk_func_ids__func_ids_before():
    assert plain_spec.get_frids_before(_tree("f1", "f2", "f3", "f4"), "f3") == ["f1", "f2"]


def test_walk_func_ids__has_acceptance_tests():
    tree = {
        "functional specs": [
            _func("f1", "one"),
            _func("f2", "two", acceptance=[{"id": "x", "text": "y", "linked_resources": []}]),
        ]
    }
    assert plain_spec.has_acceptance_tests(tree)
    assert not plain_spec.has_acceptance_tests(_tree("f1", "f2"))
    assert not plain_spec.has_acceptance_tests({})


def test_walk_func_ids__unknown_func_id():
    tree = _tree("simple-functionality")
    with pytest.raises(Exception, match="^Functionality missing does not exist.$"):
        plain_spec.get_next_frid(tree, "missing")
    with pytest.raises(Exception, match="^Functionality missing does not exist.$"):
        plain_spec.get_previous_frid(tree, "missing")


# select-func-id-range


def test_select_func_id_range__start_and_end_inclusive():
    assert plain_spec.get_frids_range(_tree("f1", "f2", "f3", "f4"), "f2", "f3") == ["f2", "f3"]


def test_select_func_id_range__without_end():
    assert plain_spec.get_frids_range(_tree("f1", "f2", "f3", "f4"), "f3") == ["f3", "f4"]


def test_select_func_id_range__unknown_start():
    with pytest.raises(InvalidFridArgument, match="Invalid start functionality ID: f9"):
        plain_spec.get_frids_range(_tree("f1", "f2", "f3", "f4"), "f9")


def test_select_func_id_range__unknown_end():
    with pytest.raises(InvalidFridArgument, match="Invalid end functionality ID: f9"):
        plain_spec.get_frids_range(_tree("f1", "f2", "f3", "f4"), "f1", "f9")


def test_select_func_id_range__start_after_end():
    with pytest.raises(InvalidFridArgument, match="must be before"):
        plain_spec.get_frids_range(_tree("f1", "f2", "f3", "f4"), "f3", "f2")


# collect-specifications-for-func-id


def test_collect_specifications_for_func_id__specifications_up_to_the_func_id():
    tree = {
        "definitions": [{"markdown": "- a thing is a thing."}],
        "functional specs": [
            _func(
                f"f{i}",
                f"Functionality {i}.",
                conformance=[{"id": f"f{i}-works", "text": f"Functionality {i} works.", "linked_resources": []}],
                acceptance=[{"id": f"f{i}-flow", "text": f"Functionality {i} flows.", "linked_resources": []}],
            )
            for i in range(1, 5)
        ],
    }
    specifications, code_variables = plain_spec.get_specifications_for_frid(tree, "f2")
    assert specifications == {
        "definitions": ["- a thing is a thing."],
        "implementation reqs": [],
        "test reqs": [],
        "functional specs": ["Functionality 1.", "Functionality 2."],
        "conformance_tests": [{"id": "f2-works", "text": "Functionality 2 works."}],
        "acceptance_tests": [{"id": "f2-flow", "text": "Functionality 2 flows."}],
    }
    assert list(specifications) == [
        "definitions",
        "implementation reqs",
        "test reqs",
        "functional specs",
        "conformance_tests",
        "acceptance_tests",
    ]
    assert code_variables is None


def test_collect_specifications_for_func_id__single_functionality():
    specifications, _ = plain_spec.get_specifications_for_frid(SIMPLE_TREE, "simple-functionality")
    assert specifications == {
        "definitions": [],
        "implementation reqs": ["- Simple implementation requirement"],
        "test reqs": [],
        "functional specs": ["Simple functionality"],
        "conformance_tests": [],
        "acceptance_tests": [],
    }


def test_collect_specifications_for_func_id__unknown_func_id():
    with pytest.raises(Exception, match="^Functionality a does not exist.$"):
        plain_spec.get_specifications_for_frid(SIMPLE_TREE, "a")


# replace-code-variables


def _code_variable_tree():
    scenario = {
        "id": "greets",
        "text": "It prints {{ greeting }}.",
        "linked_resources": [],
        "code_variables": [{"name": "greeting", "value": "hello"}],
    }
    return {"functional specs": [_func("f1", "Greets.", conformance=[scenario])]}


def test_replace_code_variables__replace_in_scenario():
    specifications, code_variables = plain_spec.get_specifications_for_frid(_code_variable_tree(), "f1")
    assert specifications["conformance_tests"] == [{"id": "greets", "text": "It prints hello."}]
    assert code_variables == {"greeting": "hello"}


def test_replace_code_variables__replacement_off():
    specifications, code_variables = plain_spec.get_specifications_for_frid(
        _code_variable_tree(), "f1", replace_code_variables=False
    )
    assert specifications["conformance_tests"] == [{"id": "greets", "text": "It prints {{ greeting }}."}]
    assert code_variables == {"greeting": "hello"}


# collect-linked-resources


def _linked_tree():
    return {
        "functional specs": [
            _func(
                f"f{i}",
                f"Functionality {i}.",
                links=[_link(f"r{i}.md")],
                conformance=[{"id": f"c{i}", "text": "c", "linked_resources": [_link(f"c{i}.md")]}],
                acceptance=[{"id": f"a{i}", "text": "a", "linked_resources": [_link(f"a{i}.md")]}],
            )
            for i in range(1, 5)
        ]
    }


def test_collect_linked_resources__stops_at_the_func_id():
    registry: list = []
    assert plain_spec.collect_linked_resources(_linked_tree(), registry, None, True, "f2") is True
    assert [r["target"] for r in registry] == ["a2.md", "c2.md", "r1.md", "r2.md"]


def test_collect_linked_resources__every_functionality_and_scenario():
    registry: list = []
    assert plain_spec.collect_linked_resources(_linked_tree(), registry, None, True) is False
    expected = sorted([f"{p}{i}.md" for p in "acr" for i in range(1, 5)])
    assert [r["target"] for r in registry] == expected


def test_collect_linked_resources__without_scenarios():
    registry: list = []
    plain_spec.collect_linked_resources(_linked_tree(), registry, None, False)
    assert [r["target"] for r in registry] == ["r1.md", "r2.md", "r3.md", "r4.md"]


def test_collect_linked_resources__same_link_twice_records_both_sections():
    tree = {
        "implementation reqs": [{"markdown": "- req", "linked_resources": [_link("notes.md", "notes")]}],
        "functional specs": [_func("f1", "body", links=[_link("notes.md", "notes")])],
    }
    registry: list = []
    plain_spec.collect_linked_resources(tree, registry, None, False)
    assert registry == [
        {"text": "notes", "target": "notes.md", "sections": ["implementation reqs", "functional specs"]}
    ]


def test_collect_linked_resources__tree_is_not_a_mapping():
    with pytest.raises(ValueError, match="^plain_source_tree must be a dictionary.$"):
        plain_spec.collect_linked_resources([], [], None, False)


def test_collect_linked_resources__unknown_func_id():
    with pytest.raises(ValueError, match="^frid f9 does not exist.$"):
        plain_spec.collect_linked_resources(_linked_tree(), [], None, True, "f9")


def test_collect_linked_resources__same_text_other_target():
    tree = {
        "implementation reqs": [
            {"markdown": "- a", "linked_resources": [_link("a.md", "notes")]},
            {"markdown": "- b", "linked_resources": [_link("b.md", "notes")]},
        ]
    }
    with pytest.raises(Exception) as error:
        plain_spec.collect_linked_resources(tree, [], None, False)
    assert str(error.value) == "The file b.md is linked to multiple linked resources with the same text: notes"


# hash-specifications


def test_hash_specifications__hash_text():
    assert plain_spec.hash_text("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_hash_specifications__hash_specifications_value():
    value = {"a": [1]}
    expected = hashlib.sha256(json.dumps(value, indent=4).encode("utf-8")).hexdigest()
    assert plain_spec.get_hash_value(value) == expected
