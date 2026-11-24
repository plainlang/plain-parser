"""Conformance tests of module test_plain_file."""

import pytest
from plain_parser import test_plain_file as tpf
from plain_parser.exceptions import PlainSyntaxError


def c(name):
    return f":{name}:"


HEAD = "---\nmodule: task-manager\nfunc_id: add-task\n---\n\n"  # lines 1-5


def parse(text, name, dirs, code_variables=None):
    return tpf.parse_test_plain_file_source(text, name, dirs, {} if code_variables is None else code_variables)


def error_of(text, name, dirs):
    with pytest.raises(PlainSyntaxError) as error:
        parse(text, name, dirs)
    return str(error.value)


@pytest.fixture
def dirs(tmp_path):
    return [str(tmp_path)]


VALID = f"""---
module: task-manager
func_id: add-task
---

> A comment before the first section.

***conformance tests***

# add-first-task
Adding a {c('Task')} named "Buy milk" to an empty {c('TaskList')} shows one {c('Task')} named "Buy milk".
  - {c('App')} prints `Added task 1: Buy milk`.

# add-without-name

given:
  - an empty {c('TaskList')}
when:
  - {c('User')} runs `todo add`
then:
  - stderr is `Error: name is required`
> A comment inside a body is dropped.
  - exit status is 1


# gherkin-shape
Scenario: adding a task with a note
  Given an empty {c('TaskList')}
  When {c('User')} adds "Buy milk"

  Then {c('TaskList')} shows it

# links-the-notes
The output matches [the notes](notes.md).

***acceptance tests***

# add-then-list
- {c('User')} adds a {c('Task')} named "Buy milk".
- `todo list` shows `1 Buy milk`.
"""


def parse_valid(tmp_path):
    (tmp_path / "notes.md").write_text("notes")
    return parse(VALID, "valid.plain", [str(tmp_path)])


# recognize-test-plain-file


def test_recognize_test_plain_file__binding_keys():
    assert tpf.is_test_plain_file({"module": "m", "func_id": "f"})
    assert not tpf.is_test_plain_file({"module": "m"})
    assert not tpf.is_test_plain_file({})
    assert not tpf.is_test_plain_file({"description": "x"})


# read-test-frontmatter

SECTIONS = "***conformance tests***\n\n***acceptance tests***\n"


def test_read_test_frontmatter__extra_key(dirs):
    text = "---\nmodule: task-manager\nfunc_id: add-task\ndescription: x\n---\n\n" + SECTIONS
    assert error_of(text, "extra_frontmatter_key.plain", dirs) == (
        "Plain syntax error: Test plain file 'extra_frontmatter_key.plain' has the frontmatter key `description:`; "
        "only `module:` and `func_id:` are allowed."
    )


def test_read_test_frontmatter__missing_func_id(dirs):
    text = "---\nmodule: task-manager\n---\n\n" + SECTIONS
    assert error_of(text, "missing_func_id.plain", dirs) == (
        "Plain syntax error: Test plain file 'missing_func_id.plain' has no `func_id:` key in its frontmatter."
    )


def test_read_test_frontmatter__module_not_a_string(dirs):
    text = "---\nmodule: [a, b]\nfunc_id: add-task\n---\n\n" + SECTIONS
    assert error_of(text, "module_not_a_string.plain", dirs) == (
        "Plain syntax error: Test plain file 'module_not_a_string.plain': the frontmatter key `module:` must be a "
        "non-empty string."
    )


def test_read_test_frontmatter__invalid_yaml(dirs):
    assert "Test plain file 'broken.plain' has invalid frontmatter" in error_of(
        "---\nmodule: [\n---\n", "broken.plain", dirs
    )


# read-scenarios


def test_read_scenarios__valid_file(tmp_path):
    parsed = parse_valid(tmp_path)
    assert (parsed.name, parsed.module, parsed.func_id) == ("valid.plain", "task-manager", "add-task")
    conformance = {s.id: s for s in parsed.conformance_tests}
    assert list(conformance) == ["add-first-task", "add-without-name", "gherkin-shape", "links-the-notes"]
    assert conformance["add-first-task"].text == (
        f'Adding a {c("Task")} named "Buy milk" to an empty {c("TaskList")} shows one {c("Task")} named "Buy milk".\n'
        f"  - {c('App')} prints `Added task 1: Buy milk`."
    )
    assert conformance["add-without-name"].text == (
        f"given:\n  - an empty {c('TaskList')}\nwhen:\n  - {c('User')} runs `todo add`\nthen:\n"
        "  - stderr is `Error: name is required`\n  - exit status is 1"
    )
    assert conformance["gherkin-shape"].text == (
        f"Scenario: adding a task with a note\n  Given an empty {c('TaskList')}\n  When {c('User')} adds \"Buy milk\"\n"
        f"\n  Then {c('TaskList')} shows it"
    )
    assert conformance["links-the-notes"].linked_resources == [{"text": "the notes", "target": "notes.md"}]
    assert [s.id for s in parsed.acceptance_tests] == ["add-then-list"]
    assert parsed.acceptance_tests[0].text == (
        f'- {c("User")} adds a {c("Task")} named "Buy milk".\n- `todo list` shows `1 Buy milk`.'
    )
    assert [s.line_number for s in parsed.scenarios] == [10, 14, 26, 33, 38]
    for scenario in parsed.scenarios:
        as_dict = scenario.to_dict()
        assert "code_variables" not in as_dict
        if scenario.id != "links-the-notes":
            assert as_dict["linked_resources"] == []


def test_read_scenarios__empty_sections(dirs):
    for text in [
        HEAD + "***conformance tests***\n\n***acceptance tests***\n",
        "---\nmodule: m\nfunc_id: f\n---\n***conformance tests***\n***acceptance tests***\n",
        HEAD + "***conformance tests***\n\n> add conformance test scenarios here\n\n***acceptance tests***\n",
    ]:
        assert parse(text, "add-task.plain", dirs).scenarios == []


def test_read_scenarios__liquid_and_code_variables(tmp_path):
    (tmp_path / "shape.plain").write_text("  - exit status is {{ status | code_variable }}")
    text = (
        HEAD
        + '***conformance tests***\n\n# works\nIt works.\n{% include "shape.plain", status: "0" %}\n\n***acceptance tests***\n'
    )
    parsed = parse(text, "add-task.plain", [str(tmp_path)])
    assert parsed.conformance_tests[0].to_dict() == {
        "id": "works",
        "text": "It works.\n  - exit status is {{ status }}",
        "linked_resources": [],
        "code_variables": [{"name": "status", "value": "0"}],
    }


def test_read_scenarios__liquid_error_names_the_file(dirs):
    text = HEAD + "***conformance tests***\n\n# works\nIt {{ works\n\n***acceptance tests***\n"
    assert "Invalid Liquid at f.plain" in error_of(text, "f.plain", dirs)


# reject-invalid-scenarios


def test_reject_invalid_scenarios__missing_acceptance_section(dirs):
    text = HEAD + "***conformance tests***\n\n# works\nIt works.\n"
    assert error_of(text, "missing_acceptance_section.plain", dirs) == (
        "Plain syntax error: Test plain file 'missing_acceptance_section.plain' has no `***acceptance tests***` section."
    )


def test_reject_invalid_scenarios__sections_out_of_order(dirs):
    text = HEAD + "***acceptance tests***\n\n***conformance tests***\n"
    assert error_of(text, "sections_out_of_order.plain", dirs) == (
        "Plain syntax error: Syntax error at line 6 in test plain file 'sections_out_of_order.plain': The "
        "`***acceptance tests***` section must come after `***conformance tests***`."
    )


def test_reject_invalid_scenarios__duplicate_section(dirs):
    text = HEAD + "***conformance tests***\n\n# works\nIt works.\n\n***conformance tests***\n"
    assert text.split("\n")[10] == "***conformance tests***"
    assert error_of(text, "duplicate_section.plain", dirs) == (
        "Plain syntax error: Syntax error at line 11 in test plain file 'duplicate_section.plain': Duplicate section "
        "`***conformance tests***`."
    )


def test_reject_invalid_scenarios__unknown_section(dirs):
    text = HEAD + "***conformance tests***\n\n# works\nIt works.\n\n***definitions***\n"
    assert error_of(text, "unknown_section.plain", dirs) == (
        "Plain syntax error: Syntax error at line 11 in test plain file 'unknown_section.plain': Invalid section "
        "(`***definitions***`). A test plain file has the sections `***conformance tests***` and "
        "`***acceptance tests***`, in this order."
    )


def test_reject_invalid_scenarios__duplicate_scenario_id(dirs):
    text = HEAD + "***conformance tests***\n\n# works\nIt works.\n\n\n\n# works\nAgain.\n\n***acceptance tests***\n"
    assert text.split("\n")[7] == "# works" and text.split("\n")[12] == "# works"
    assert error_of(text, "duplicate_scenario_id.plain", dirs) == (
        "Plain syntax error: Syntax error at line 13 in test plain file 'duplicate_scenario_id.plain': Duplicate "
        "scenario-id `works`; it is first used at line 8."
    )


def test_reject_invalid_scenarios__invalid_scenario_id(dirs):
    text = HEAD + "***conformance tests***\n\n# Works Well\nIt works.\n\n***acceptance tests***\n"
    assert error_of(text, "invalid_scenario_id.plain", dirs) == (
        "Plain syntax error: Syntax error at line 8 in test plain file 'invalid_scenario_id.plain': Invalid "
        "scenario-id (`Works Well`). A scenario-id is lowercase letters and digits, with single hyphens between them."
    )


def test_reject_invalid_scenarios__scenario_id_shapes(dirs):
    for scenario_id in ["-works", "works-", "works--well", "-", "--", "works_well", "Works"]:
        text = HEAD + f"***conformance tests***\n\n# {scenario_id}\nIt works.\n\n***acceptance tests***\n"
        assert f"Invalid scenario-id (`{scenario_id}`)" in error_of(text, "add-task.plain", dirs)


def test_reject_invalid_scenarios__content_before_section(dirs):
    text = HEAD + "It works.\n\n***conformance tests***\n\n***acceptance tests***\n"
    assert error_of(text, "content_before_section.plain", dirs) == (
        "Plain syntax error: Syntax error at line 6 in test plain file 'content_before_section.plain': Content "
        "before the first section (`It works.`); a test plain file starts with `***conformance tests***`."
    )


def test_reject_invalid_scenarios__content_before_scenario(dirs):
    text = HEAD + "***conformance tests***\n\nIt works.\n\n***acceptance tests***\n"
    assert error_of(text, "content_before_scenario.plain", dirs) == (
        "Plain syntax error: Syntax error at line 8 in test plain file 'content_before_scenario.plain': Content "
        "before the first `# <scenario-id>` heading in the `conformance tests` section (`It works.`)."
    )


def test_reject_invalid_scenarios__scenario_before_section(dirs):
    text = HEAD + "# works\nIt works.\n\n***conformance tests***\n\n***acceptance tests***\n"
    assert error_of(text, "scenario_before_section.plain", dirs) == (
        "Plain syntax error: Syntax error at line 6 in test plain file 'scenario_before_section.plain': Scenario "
        "`works` comes before the first section; a test plain file starts with `***conformance tests***`."
    )


def test_reject_invalid_scenarios__empty_scenario(dirs):
    text = HEAD + "***conformance tests***\n\n# works\n***acceptance tests***\n"
    assert error_of(text, "empty_scenario.plain", dirs) == (
        "Plain syntax error: Syntax error at line 8 in test plain file 'empty_scenario.plain': Scenario `works` has no "
        "text."
    )


# keep-code-fences


def fence_file(scenario):
    return f"---\nmodule: todo\nfunc_id: add-task\n---\n\n***conformance tests***\n\n{scenario}\n\n***acceptance tests***\n"


def test_keep_code_fences__fenced_lines_are_text(dirs):
    fences = [
        '```bash\n# create an empty list, then add a task\n# add-first-task\ntodo add "Buy milk"\n```',
        "```\n***\ntodo 1.0\n***\n```",
        "```\n> todo add Buy milk\nAdded task 1: Buy milk\n> todo list\n```",
        "  ~~~\n  # not a heading\n  ```\n  ~~~",
    ]
    for fence in fences:
        text = f"The commands below add a task.\n\n{fence}\nThe task is listed."
        parsed = parse(fence_file(f"# add-first-task\n{text}"), "add-task.plain", dirs)
        assert [s.id for s in parsed.scenarios] == ["add-first-task"]
        assert parsed.scenarios[0].text == text


def test_keep_code_fences__heading_after_closed_fence(dirs):
    scenario = "# first\n```\n# not a heading\n```\n\n# second\nIt works."
    parsed = parse(fence_file(scenario), "add-task.plain", dirs)
    assert [s.id for s in parsed.scenarios] == ["first", "second"]


def test_keep_code_fences__fence_not_closed(dirs):
    text = fence_file("# first\nIt works:\n```\ntodo add")
    assert text.split("\n")[7] == "# first"
    assert error_of(text, "add-task.plain", dirs) == (
        "Plain syntax error: Syntax error at line 8 in test plain file 'add-task.plain': Scenario `first` has a code "
        "fence that is not closed."
    )


def test_keep_code_fences__fence_before_first_scenario(dirs):
    text = fence_file("```\n# not a heading\n```\n# first\nIt works.")
    message = error_of(text, "add-task.plain", dirs)
    assert (
        "Syntax error at line 8 in test plain file 'add-task.plain': Content before the first `# <scenario-id>` heading"
        in message
    )


# resolve-scenario-links


def test_resolve_scenario_links__missing_link(dirs):
    text = HEAD + "***conformance tests***\n\n# works\nSee [missing](missing.md).\n\n***acceptance tests***\n"
    message = error_of(text, "missing_link.plain", dirs)
    assert message.startswith(
        "Plain syntax error: Link missing.md in test plain file 'missing_link.plain', scenario `works` does not exist. "
        "Linked resources are looked up relative to the following directories"
    )


def test_resolve_scenario_links__link_to_plain_file(tmp_path):
    (tmp_path / "valid.plain").write_text(VALID)
    text = HEAD + "***conformance tests***\n\n# works\nSee [valid](valid.plain).\n\n***acceptance tests***\n"
    assert "Referenced resource 'valid.plain' in test plain file" in error_of(
        text, "link_to_plain_file.plain", [str(tmp_path)]
    )


# check-scenario-concepts


def test_check_scenario_concepts__all_concepts_visible(tmp_path):
    parsed = parse_valid(tmp_path)
    assert tpf.validate_scenario_concepts(parsed, {c("Task"), c("TaskList"), c("App"), c("User")}) == []


def test_check_scenario_concepts__missing_concept(tmp_path):
    parsed = parse_valid(tmp_path)
    errors = tpf.validate_scenario_concepts(parsed, {c("Task"), c("App"), c("User")})
    assert errors == [
        f"Syntax error at line {line} in test plain file 'valid.plain': Concept {c('TaskList')} used in scenario "
        f"`{scenario}` is not defined in module 'task-manager'."
        for line, scenario in [(10, "add-first-task"), (14, "add-without-name"), (26, "gherkin-shape")]
    ]


def test_check_scenario_concepts__predefined_concepts(dirs):
    text = (
        HEAD
        + f"***conformance tests***\n\n# works\n{c('ConformanceTests')} start {c('Implementation')}.\n\n***acceptance tests***\n"
    )
    parsed = parse(text, "add-task.plain", dirs)
    assert parsed.scenarios[0].line_number == 8
    assert tpf.validate_scenario_concepts(parsed, set()) == []
