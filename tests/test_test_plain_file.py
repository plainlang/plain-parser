import os
import re

import pytest

from plain_parser import test_plain_file
from plain_parser.exceptions import PlainSyntaxError


@pytest.fixture
def fixtures_dir(get_test_data_path):
    return get_test_data_path("data/testplainfile")


def _parse(fixtures_dir, file_name, code_variables=None):
    with open(os.path.join(fixtures_dir, file_name)) as f:
        text = f.read()
    return test_plain_file.parse_test_plain_file_source(text, file_name, [fixtures_dir], code_variables or {})


def test_valid_file_binds_to_its_functionality_and_keeps_the_scenarios_verbatim(fixtures_dir):
    parsed = _parse(fixtures_dir, "valid.plain")

    assert (parsed.name, parsed.module, parsed.func_id) == ("valid.plain", "task-manager", "add-task")
    assert [scenario.to_dict() for scenario in parsed.conformance_tests] == [
        {
            "id": "add-first-task",
            "text": 'Adding a :Task: named "Buy milk" to an empty :TaskList: shows one :Task: named "Buy milk".\n'
            "  - :App: prints `Added task 1: Buy milk`.",
            "linked_resources": [],
        },
        {
            "id": "add-without-name",
            "text": "given:\n  - an empty :TaskList:\nwhen:\n  - :User: runs `todo add`\nthen:\n"
            "  - stderr is `Error: name is required`\n  - exit status is 1",
            "linked_resources": [],
        },
        {
            "id": "gherkin-shape",
            "text": 'Scenario: adding a task with a note\n  Given an empty :TaskList:\n  When :User: adds "Buy milk"\n\n'
            "  Then :TaskList: shows it",
            "linked_resources": [],
        },
        {
            "id": "links-the-notes",
            "text": "The output matches [the notes](notes.md).",
            "linked_resources": [{"text": "the notes", "target": "notes.md"}],
        },
    ]
    assert [scenario.to_dict() for scenario in parsed.acceptance_tests] == [
        {
            "id": "add-then-list",
            "text": '- :User: adds a :Task: named "Buy milk".\n- `todo list` shows `1 Buy milk`.',
            "linked_resources": [],
        }
    ]
    assert [scenario.line_number for scenario in parsed.scenarios] == [10, 14, 26, 33, 38]


def test_both_sections_may_be_empty(fixtures_dir):
    parsed = _parse(fixtures_dir, "empty_sections.plain")

    assert (parsed.conformance_tests, parsed.acceptance_tests) == ([], [])


@pytest.mark.parametrize(
    ("file_name", "message"),
    [
        (
            "missing_acceptance_section.plain",
            "Plain syntax error: Test plain file 'missing_acceptance_section.plain' has no `***acceptance tests***` "
            "section.",
        ),
        (
            "sections_out_of_order.plain",
            "Plain syntax error: Syntax error at line 6 in test plain file 'sections_out_of_order.plain': The "
            "`***acceptance tests***` section must come after `***conformance tests***`.",
        ),
        (
            "duplicate_section.plain",
            "Plain syntax error: Syntax error at line 11 in test plain file 'duplicate_section.plain': Duplicate "
            "section `***conformance tests***`.",
        ),
        (
            "unknown_section.plain",
            "Plain syntax error: Syntax error at line 11 in test plain file 'unknown_section.plain': Invalid section "
            "(`***definitions***`). A test plain file has the sections `***conformance tests***` and "
            "`***acceptance tests***`, in this order.",
        ),
        (
            "extra_frontmatter_key.plain",
            "Plain syntax error: Test plain file 'extra_frontmatter_key.plain' has the frontmatter key "
            "`description:`; only `module:` and `func_id:` are allowed.",
        ),
        (
            "missing_func_id.plain",
            "Plain syntax error: Test plain file 'missing_func_id.plain' has no `func_id:` key in its frontmatter.",
        ),
        (
            "module_not_a_string.plain",
            "Plain syntax error: Test plain file 'module_not_a_string.plain': the frontmatter key `module:` must be "
            "a non-empty string.",
        ),
        (
            "duplicate_scenario_id.plain",
            "Plain syntax error: Syntax error at line 13 in test plain file 'duplicate_scenario_id.plain': Duplicate "
            "scenario-id `works`; it is first used at line 8.",
        ),
        (
            "invalid_scenario_id.plain",
            "Plain syntax error: Syntax error at line 8 in test plain file 'invalid_scenario_id.plain': Invalid "
            "scenario-id (`Works Well`). A scenario-id is lowercase letters and digits, with single hyphens between "
            "them.",
        ),
        (
            "content_before_section.plain",
            "Plain syntax error: Syntax error at line 6 in test plain file 'content_before_section.plain': Content "
            "before the first section (`It works.`); a test plain file starts with `***conformance tests***`.",
        ),
        (
            "content_before_scenario.plain",
            "Plain syntax error: Syntax error at line 8 in test plain file 'content_before_scenario.plain': Content "
            "before the first `# <scenario-id>` heading in the `conformance tests` section (`It works.`).",
        ),
        (
            "scenario_before_section.plain",
            "Plain syntax error: Syntax error at line 6 in test plain file 'scenario_before_section.plain': Scenario "
            "`works` comes before the first section; a test plain file starts with `***conformance tests***`.",
        ),
        (
            "empty_scenario.plain",
            "Plain syntax error: Syntax error at line 8 in test plain file 'empty_scenario.plain': Scenario `works` "
            "has no text.",
        ),
    ],
)
def test_invalid_file_is_rejected_with_its_place(fixtures_dir, file_name, message):
    with pytest.raises(PlainSyntaxError) as exc_info:
        _parse(fixtures_dir, file_name)

    assert str(exc_info.value) == message


def test_missing_link_names_the_file_and_the_scenario(fixtures_dir):
    with pytest.raises(PlainSyntaxError) as exc_info:
        _parse(fixtures_dir, "missing_link.plain")

    assert str(exc_info.value).startswith(
        "Plain syntax error: Link missing.md in test plain file 'missing_link.plain', scenario `works` does not "
        "exist. Linked resources are looked up relative to the following directories"
    )


def test_link_to_a_plain_file_is_rejected(fixtures_dir):
    with pytest.raises(PlainSyntaxError, match=re.escape("Referenced resource 'valid.plain' in test plain file")):
        _parse(fixtures_dir, "link_to_plain_file.plain")


@pytest.mark.parametrize("scenario_id", ["-works", "works-", "works--well", "-", "--", "works_well", "Works"])
def test_scenario_id_syntax_is_checked(scenario_id):
    text = f"---\nmodule: m\nfunc_id: f\n---\n\n***conformance tests***\n\n# {scenario_id}\nIt works.\n\n***acceptance tests***\n"

    with pytest.raises(PlainSyntaxError, match=re.escape(f"Invalid scenario-id (`{scenario_id}`)")):
        test_plain_file.parse_test_plain_file_source(text, "f.plain", [], {})


def test_invalid_frontmatter_is_rejected():
    with pytest.raises(PlainSyntaxError, match="Test plain file 'broken.plain' has invalid frontmatter"):
        test_plain_file.parse_test_plain_file_source("---\nmodule: [\n---\n", "broken.plain", [], {})


def test_liquid_runs_with_the_template_directories(tmp_path):
    (tmp_path / "shape.plain").write_text("  - exit status is {{ status | code_variable }}")
    text = (
        "---\nmodule: m\nfunc_id: f\n---\n\n***conformance tests***\n\n# works\n"
        'It works.\n{% include "shape.plain", status: "0" %}\n\n***acceptance tests***\n'
    )
    code_variables = {}

    parsed = test_plain_file.parse_test_plain_file_source(text, "f.plain", [str(tmp_path)], code_variables)

    assert parsed.conformance_tests[0].to_dict() == {
        "id": "works",
        "text": "It works.\n  - exit status is {{ status }}",
        "linked_resources": [],
        "code_variables": [{"name": "status", "value": "0"}],
    }


def test_liquid_error_names_the_file():
    text = "---\nmodule: m\nfunc_id: f\n---\n\n***conformance tests***\n\n# works\nIt {{ works\n"

    with pytest.raises(PlainSyntaxError, match=re.escape("Invalid Liquid at f.plain:")):
        test_plain_file.parse_test_plain_file_source(text, "f.plain", [], {})


def test_scenario_concepts_are_checked_against_the_visible_concepts(fixtures_dir):
    parsed = _parse(fixtures_dir, "valid.plain")

    assert test_plain_file.validate_scenario_concepts(parsed, {":Task:", ":TaskList:", ":App:", ":User:"}) == []
    assert test_plain_file.validate_scenario_concepts(parsed, {":Task:", ":App:", ":User:"}) == [
        "Syntax error at line 10 in test plain file 'valid.plain': Concept :TaskList: used in scenario "
        "`add-first-task` is not defined in module 'task-manager'.",
        "Syntax error at line 14 in test plain file 'valid.plain': Concept :TaskList: used in scenario "
        "`add-without-name` is not defined in module 'task-manager'.",
        "Syntax error at line 26 in test plain file 'valid.plain': Concept :TaskList: used in scenario "
        "`gherkin-shape` is not defined in module 'task-manager'.",
    ]


def test_predefined_concepts_need_no_definition():
    scenario = test_plain_file.Scenario("works", 8, ":ConformanceTests: start :Implementation:.")
    parsed = test_plain_file.TestPlainFile("f.plain", "m", "f", [scenario], [])

    assert test_plain_file.validate_scenario_concepts(parsed, set()) == []


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [({"module": "m", "func_id": "f"}, True), ({"module": "m"}, False), ({}, False), ({"description": "x"}, False)],
)
def test_is_test_plain_file(metadata, expected):
    assert test_plain_file.is_test_plain_file(metadata) is expected
