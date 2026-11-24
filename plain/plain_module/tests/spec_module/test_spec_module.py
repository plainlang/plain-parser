"""Conformance tests of module spec_module."""

import os
import re

import pytest
from plain_parser import plain_file
from plain_parser.exceptions import (
    ImportedModuleWithFunctionalitiesError,
    MissingFunctionalitiesError,
    ModuleDoesNotExistError,
    PlainSyntaxError,
    UnsupportedBase64Content,
)
from spec_module_helpers import PREFIX, c, prefix_of

IMPL = f"***implementation reqs***\n\n- {c('Implementation')} is written in Python.\n"


def raises(exception, call, *args, **kwargs):
    with pytest.raises(exception) as error:
        call(*args, **kwargs)
    return str(error.value)


def module(definitions=None, impl=None, functional=None, frontmatter=None):
    parts = []
    if frontmatter is not None:
        parts.append("---\n" + frontmatter + "---\n")
    if definitions is not None:
        parts.append("***definitions***\n\n" + "".join(f"{d}\n" for d in definitions))
    if impl is not None:
        parts.append("***implementation reqs***\n\n" + "".join(f"{d}\n" for d in impl))
    if functional is not None:
        parts.append("***functional specs***\n\n" + functional)
    return "\n".join(parts)


SIMPLE = "***implementation reqs***\n\n- Simple implementation requirement\n\n***functional specs***\n\n# simple-functionality\nSimple functionality\n"

REGULAR = """***definitions***

***implementation reqs***

- First implementation requirement.
- Second implementation requirement.

***functional specs***

# display-hello-world
Display "hello, world"
"""

REGULAR_TREE = {
    "definitions": [],
    "implementation reqs": [
        {"markdown": "- First implementation requirement."},
        {"markdown": "- Second implementation requirement."},
    ],
    "functional specs": [
        {
            "id": "display-hello-world",
            "markdown": 'Display "hello, world"',
            "linked_resources": [],
            "conformance_tests": [],
            "acceptance_tests": [],
        }
    ],
}


# name-module-files


def test_name_module_files__file_name_of_module():
    assert plain_file.get_filename_from_module_name("sub/todo") == "sub/todo.plain"
    assert plain_file.get_module_name_from_filename("sub/todo.plain") == "sub/todo"


# normalize-line-endings


def test_normalize_line_endings__mixed_line_endings():
    assert plain_file.normalize_line_endings("a\r\nb\rc\nd") == "a\nb\nc\nd"


# read-list-sections


def test_read_list_sections__regular_module(project):
    _, tree, _ = project.parse("regular_plain_source.plain", REGULAR)
    assert tree == REGULAR_TREE


def test_read_list_sections__comment_lines_are_dropped(project):
    text = "> A comment before the definitions.\n" + REGULAR.replace(
        "- First implementation requirement.", "> First implementation requirement is a comment."
    )
    _, tree, _ = project.parse("regular_plain_source.plain", text)
    assert tree["implementation reqs"] == [{"markdown": "- Second implementation requirement."}]


def test_read_list_sections__indented_comment_lines_are_dropped(project):
    text = REGULAR.replace(
        "- First implementation requirement.\n", "- First implementation requirement.\n  > a comment\n"
    )
    _, tree, _ = project.parse("regular_plain_source.plain", text)
    assert tree == REGULAR_TREE


def test_read_list_sections__invalid_frontmatter(project):
    message = raises(PlainSyntaxError, project.parse_text, "---\nmodule: [\n---\n" + REGULAR)
    assert message.startswith("Plain syntax error: Invalid frontmatter: ")


# reject-invalid-sections

UNKNOWN = "\n***definitions***\n\n***Unknown Section:***\n"
UNKNOWN_MESSAGE = (
    "Invalid specification heading (`Unknown Section:`). Allowed headings: definitions, implementation reqs, "
    "test reqs, functional specs"
)


def test_reject_invalid_sections__unknown_section(project):
    message = raises(Exception, project.parse_text, UNKNOWN)
    assert f"Syntax error at line 4: {UNKNOWN_MESSAGE}" in message


def test_reject_invalid_sections__line_number_counts_frontmatter(project):
    message = raises(Exception, project.parse_text, "---\ndescription: 'x'\n---\n" + UNKNOWN)
    assert f"Syntax error at line 7: {UNKNOWN_MESSAGE}" in message


def test_reject_invalid_sections__line_number_with_windows_line_endings(project):
    text = ("---\ndescription: 'x'\n---\n" + UNKNOWN).replace("\n", "\r\n")
    message = raises(Exception, project.parse_text, text)
    assert f"Syntax error at line 7: {UNKNOWN_MESSAGE}" in message


def test_reject_invalid_sections__duplicate_section(project):
    message = raises(Exception, project.parse_text, "\n***definitions***\n\n***definitions***\n")
    assert "Syntax error at line 4: Duplicate specification heading (`definitions`)" in message


def test_reject_invalid_sections__duplicate_section_names_the_module(project):
    text = f"***definitions***\n\n- {c('A')} is a.\n\n\n***definitions***\n"
    project.write("duplicate_specification_heading.plain", text)
    message = raises(Exception, project.parse, "duplicate_specification_heading.plain")
    assert (
        "Syntax error at line 6 in module 'duplicate_specification_heading': Duplicate specification heading "
        "(`definitions`)" in message
    )


def test_reject_invalid_sections__definitions_not_first(project):
    text = "***implementation reqs***\n\n- A req.\n\n\n***definitions***\n"
    project.write("invalid_specification_order.plain", text)
    message = raises(Exception, project.parse, "invalid_specification_order.plain")
    assert (
        "Syntax error at line 6 in module 'invalid_specification_order': Definitions specification must be the "
        "first specification in the section (`definitions`)" in message
    )


def test_reject_invalid_sections__code_block_in_list_section(project):
    message = raises(Exception, project.parse_text, "\n***definitions***\n```\ncode block\n```\n")
    assert "Syntax error at line 3: Invalid source structure (`code block`)" in message


def test_reject_invalid_sections__block_after_list_items(project):
    message = raises(PlainSyntaxError, project.parse_text, "***implementation reqs***\n\n- A req.\n\n```\ncode\n```\n")
    assert "Syntax error at line 5: Invalid source structure" in message


def test_reject_invalid_sections__test_section_in_spec_file(project):
    for heading in ("acceptance tests", "conformance tests"):
        text = f"***definitions***\n\n- {c('Task')} is a thing to do.\n\n***{heading}***\n\n# add\nAdding works.\n"
        message = raises(PlainSyntaxError, project.parse_text, text)
        assert message == (
            f"Plain syntax error: Syntax error at line 5: The `{heading}` section is not allowed in a spec plain "
            "file; test scenarios live in test plain files."
        )


def test_reject_invalid_sections__nested_test_section(project):
    text = PREFIX + f"# add-task\nA {c('Task')} can be added.\n\n    ***acceptance tests***\n"
    assert text.split("\n")[13] == "    ***acceptance tests***"
    message = raises(PlainSyntaxError, project.parse_text, text)
    assert "Syntax error at line 14: The `acceptance tests` section" in message


# read-functionalities


def _functional(project, body, name="m"):
    _, tree, _ = project.parse(f"{name}.plain", PREFIX + body)
    return tree["functional specs"]


def test_read_functionalities__heading_and_body(project):
    body = (
        f"# add-task\nA {c('Task')} can be added.\nIt gets an id.\n  - Only a {c('Task')} with a name is added.\n"
        f"    - The name is trimmed.\n\n# list-tasks\n> A comment between the heading and the body.\n\n"
        f"Every {c('Task')} is listed.\n"
    )
    functionalities = _functional(project, body)
    empty = {"linked_resources": [], "conformance_tests": [], "acceptance_tests": []}
    assert functionalities == [
        {
            "id": "add-task",
            "markdown": f"A {c('Task')} can be added.\nIt gets an id.\n  - Only a {c('Task')} with a name is added.\n"
            "    - The name is trimmed.",
            **empty,
        },
        {"id": "list-tasks", "markdown": f"Every {c('Task')} is listed.", **empty},
    ]


def test_read_functionalities__body_starts_with_a_list(project):
    functionalities = _functional(project, f"# add-task\n  - A {c('Task')} can be added.\n")
    assert functionalities[0]["markdown"] == f"  - A {c('Task')} can be added."


def test_read_functionalities__flush_left_list_is_body(project):
    markdown = f"A {c('Task')} can be added.\n\n- A {c('Task')} has a name.\n    - Deeper, four spaces in."
    functionalities = _functional(project, f"# add-task\n{markdown}\n")
    assert functionalities[0]["markdown"] == markdown


def test_read_functionalities__any_block_is_body(project):
    body = (
        f"# add-task\nA {c('Task')} can be added.\n\n```\ntodo add\n```\n\n| id | name |\n|---|---|\n| 1 | Buy milk |\n"
        f"# list-tasks\nEvery {c('Task')} is listed.\n"
    )
    functionalities = _functional(project, body)
    assert functionalities[0]["markdown"] == (
        f"A {c('Task')} can be added.\n\n```\ntodo add\n```\n\n| id  | name     |\n| --- | -------- |\n| 1   | Buy milk |"
    )
    assert functionalities[1]["markdown"] == f"Every {c('Task')} is listed."


# reject-invalid-functionalities


def test_reject_invalid_functionalities__heading_outside_functional_specs(project):
    message = raises(PlainSyntaxError, project.parse_text, "***implementation reqs***\n\n# add-task\n- A req.\n")
    assert (
        "Syntax error at line 3: A `# <func-id>` heading is allowed only in the functional specs section (`add-task`)."
        in message
    )


def test_reject_invalid_functionalities__heading_of_level_two(project):
    message = raises(PlainSyntaxError, project.parse_text, PREFIX + "## add-task\nBody.\n")
    assert (
        "Syntax error at line 11: Invalid heading level 2 (`add-task`). A functionality heading is `# <func-id>`."
        in message
    )


def test_reject_invalid_functionalities__invalid_func_id(project):
    for heading in [
        "#",
        "# ",
        "# add_task",
        "# add-task!",
        "# Ädd",
        "# -add-task",
        "# add-task-",
        "# add--task",
        "# -",
        "# ---",
    ]:
        message = raises(PlainSyntaxError, project.parse_text, PREFIX + heading + "\nBody.\n")
        assert "Syntax error at line 11: Invalid func-id" in message, heading


def test_reject_invalid_functionalities__invalid_func_id_message(project):
    project.write("func_id_invalid.plain", prefix_of(9) + "# Add Task 2\nBody.\n")
    message = raises(PlainSyntaxError, project.parse, "func_id_invalid.plain")
    assert message == (
        "Plain syntax error: Syntax error at line 10 in module 'func_id_invalid': Invalid func-id (`Add Task 2`). "
        "A func-id is lowercase letters and digits, with single hyphens between them."
    )


def test_reject_invalid_functionalities__duplicate_func_id(project):
    text = IMPL + "\n***functional specs***\n\n# add-task\nOne.\n\n\n\n\n# add-task\nTwo.\n"
    assert text.split("\n")[6] == "# add-task" and text.split("\n")[12] == "# add-task"
    project.write("func_id_duplicate.plain", text)
    message = raises(PlainSyntaxError, project.parse, "func_id_duplicate.plain")
    assert message == (
        "Plain syntax error: Syntax error at line 13 in module 'func_id_duplicate': Duplicate func-id `add-task`; "
        "it is first used at line 7."
    )


def test_reject_invalid_functionalities__content_before_first_heading(project):
    for first in (f"A {c('Task')} can be added.", f"  - A {c('Task')} can be added."):
        message = raises(PlainSyntaxError, project.parse_text, PREFIX + first + "\n\n# add-task\nBody.\n")
        assert (
            f"Syntax error at line 11: Content before the first `# <func-id>` heading in the functional specs "
            f"section (`A {c('Task')} can be added.`). A functionality is a `# <func-id>` heading followed by its "
            "body; the previous syntax is not supported." in message
        )


def test_reject_invalid_functionalities__previous_syntax(project):
    project.write("old_syntax_functional_specs.plain", PREFIX + '- Display "hello, world"\n')
    message = raises(PlainSyntaxError, project.parse, "old_syntax_functional_specs.plain")
    assert message == (
        "Plain syntax error: Syntax error at line 11 in module 'old_syntax_functional_specs': Content before the "
        'first `# <func-id>` heading in the functional specs section (`Display "hello, world"`). A functionality is '
        "a `# <func-id>` heading followed by its body; the previous syntax is not supported."
    )


def test_reject_invalid_functionalities__functionality_without_body(project):
    for rest in ["# list-tasks\nBody.\n", "***test reqs***\n\n- A test req.\n", "", "> only a comment\n"]:
        message = raises(PlainSyntaxError, project.parse_text, PREFIX + "# add-task\n" + rest)
        assert "Syntax error at line 11: Functionality `add-task` has no body." in message, rest


# marshall-plain-source


def _linked_yaml_module(project):
    project.write("task_list_ui_specification.yaml", "ui: list\n")
    project.write("add_new_task_modal_specification.yaml", "ui: modal\n")
    body = (
        f"# add-task\nA {c('Task')} can be added.\n\n"
        "# show-list\nShow the list as in [task_list_ui_specification.yaml](task_list_ui_specification.yaml).\n\n"
        "# show-modal\nShow the modal as in "
        "[add_new_task_modal_specification.yaml](add_new_task_modal_specification.yaml).\n"
    )
    project.write("linked.plain", PREFIX + body)


def test_marshall_plain_source__links_are_rendered_as_resources(project):
    _linked_yaml_module(project)
    _, tree, _ = project.parse("linked.plain")
    functionalities = tree["functional specs"]
    assert functionalities[1]["linked_resources"] == [
        {"text": "task_list_ui_specification.yaml", "target": "task_list_ui_specification.yaml"}
    ]
    assert functionalities[2]["linked_resources"] == [
        {"text": "add_new_task_modal_specification.yaml", "target": "add_new_task_modal_specification.yaml"}
    ]
    assert "`[resource]task_list_ui_specification.yaml`" in functionalities[1]["markdown"]
    assert "`[resource]add_new_task_modal_specification.yaml`" in functionalities[2]["markdown"]


def _diamond(project):
    def import_module(name, concept, imports=()):
        frontmatter = ""
        if imports:
            frontmatter = "---\nimport:\n" + "".join(f"  - {i}\n" for i in imports) + "---\n"
        return frontmatter + (
            f"***definitions***\n\n- {c(concept)} is a concept of {name}.\n\n"
            f"***implementation reqs***\n\n- {c(concept)} is implemented.\n\n"
            f"***test reqs***\n\n- {c(concept)} is tested.\n"
        )

    project.write("diamond_import_common.plain", import_module("diamond_import_common", "App"))
    project.write("diamond_import_1.plain", import_module("diamond_import_1", "One", ["diamond_import_common"]))
    project.write("diamond_import_2.plain", import_module("diamond_import_2", "Two", ["diamond_import_common"]))
    project.write(
        "diamond_imports_main.plain",
        "---\nimport:\n  - diamond_import_1\n  - diamond_import_2\n---\n\n"
        f"***definitions***\n\n- {c('MainExecutableFile')} is the main file.\n\n"
        f'***implementation reqs***\n\n- {c("MainExecutableFile")} of {c("App")} should be called "hello_world.py".\n\n'
        f"***functional specs***\n\n# display-hello-world\n{c('App')} displays hello world.\n",
    )


def test_marshall_plain_source__imports_merge_in_order(project):
    _diamond(project)
    project.write(
        "diamond_imports_main.plain",
        "---\nimport:\n  - diamond_import_1\n  - diamond_import_2\n---\n\n"
        f"***definitions***\n\n- {c('MainExecutableFile')} is the main file.\n\n"
        f'***implementation reqs***\n\n- {c("MainExecutableFile")} of {c("App")} should be called "hello_world.py".\n\n'
        f"***functional specs***\n\n# display-hello-world\n{c('App')} displays hello world.\n",
    )
    _, tree, _ = project.parse("diamond_imports_main.plain")
    assert [d["markdown"] for d in tree["definitions"]] == [
        f"- {c('App')} is a concept of diamond_import_common.",
        f"- {c('One')} is a concept of diamond_import_1.",
        f"- {c('Two')} is a concept of diamond_import_2.",
        f"- {c('MainExecutableFile')} is the main file.",
    ]
    assert [d["markdown"] for d in tree["implementation reqs"]] == [
        f"- {c('App')} is implemented.",
        f"- {c('One')} is implemented.",
        f"- {c('Two')} is implemented.",
        f'- {c("MainExecutableFile")} of {c("App")} should be called "hello_world.py".',
    ]
    assert [d["markdown"] for d in tree["test reqs"]] == [
        f"- {c('App')} is tested.",
        f"- {c('One')} is tested.",
        f"- {c('Two')} is tested.",
    ]


# find-linked-resources


def test_find_linked_resources__independent_of_working_directory(project, tmp_path, monkeypatch):
    _linked_yaml_module(project)
    _, first, _ = project.parse("linked.plain")
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    _, second, _ = plain_file.plain_file_parser("linked.plain", [project.root])
    assert [f["linked_resources"] for f in first["functional specs"]] == [
        f["linked_resources"] for f in second["functional specs"]
    ]


def test_find_linked_resources__url_link(project):
    text = PREFIX + "# add-task\nSee [spec](https://example.com/spec.yaml).\n"
    message = raises(Exception, project.parse, "m.plain", text)
    assert "Only relative links are allowed" in message


def test_find_linked_resources__absolute_link(project):
    path = project.write("abs.yaml", "x: 1\n")
    text = PREFIX + f"# add-task\nSee [spec]({path}).\n"
    message = raises(Exception, project.parse, "m.plain", text)
    assert "Only relative links are allowed" in message


def test_find_linked_resources__missing_link_lists_directories(project):
    text = PREFIX + "# add-task\nSee [spec](resources/missing_resource.yaml).\n"
    message = raises(PlainSyntaxError, project.parse, "m.plain", text)
    assert "resources/missing_resource.yaml does not exist" in message
    assert "highest to lowest precedence" in message
    assert os.path.abspath(project.root) in message


# import-modules


def test_import_modules__diamond_import_merged_once(project):
    _diamond(project)
    _, tree, _ = project.parse("diamond_imports_main.plain")
    markdowns = [d["markdown"] for d in tree["definitions"]]
    assert markdowns.count(f"- {c('App')} is a concept of diamond_import_common.") == 1


def test_import_modules__imported_module_with_functionalities(project):
    project.write("import_with_functionalities.plain", IMPL + "\n***functional specs***\n\n# f\nBody.\n")
    text = "---\nimport:\n  - import_with_functionalities\n---\n" + PREFIX + "# add-task\nBody.\n"
    message = raises(ImportedModuleWithFunctionalitiesError, project.parse, "m.plain", text)
    assert "use 'requires' instead of 'import'" in message


def test_import_modules__non_existent_import(project):
    text = "---\nimport:\n  - non_existent_module\n---\n" + PREFIX + "# add-task\nBody.\n"
    message = raises(Exception, project.parse, "m.plain", text)
    assert "Module does not exist" in message


def test_import_modules__circular_imports(project):
    project.write("circular_imports_1.plain", "---\nimport:\n  - circular_imports_2\n---\n" + IMPL)
    project.write("circular_imports_2.plain", "---\nimport:\n  - circular_imports_1\n---\n" + IMPL)
    text = "---\nimport:\n  - circular_imports_1\n---\n" + PREFIX + "# add-task\nBody.\n"
    message = raises(Exception, project.parse, "circular_imports_main.plain", text)
    assert "Circular import detected" in message


# read-module-file


def test_read_module_file__first_directory_wins(project, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "m.plain").write_text(PREFIX + "# from-first\nBody.\n")
    (second / "m.plain").write_text(PREFIX + "# from-second\nBody.\n")
    _, tree, _ = plain_file.plain_file_parser("m.plain", [str(first), str(second)])
    assert tree["functional specs"][0]["id"] == "from-first"


def test_read_module_file__missing_module(project):
    message = raises(ModuleDoesNotExistError, project.parse, "does_not_exist.plain")
    assert message == "Module does not exist (does_not_exist)."


def test_read_module_file__base64_in_module(project):
    message = raises(UnsupportedBase64Content, project.parse, "m.plain", PREFIX + "# add-task\n" + "A" * 8292 + "\n")
    assert "contains a base64-encoded blob (8292 characters)" in message


# require-imported-concepts

REQUIRED = (
    "---\nrequired_concepts:\n"
    f"  - '{c('Concept')} is a required concept and needs to be defined in the module that imports this one.'\n---\n"
    f"***definitions***\n\n- {c('DependantConcept')} is a concept that depends on the {c('Concept')} concept.\n"
)


def _importing(imports, definitions):
    frontmatter = "---\nimport:\n" + "".join(f"  - {i}\n" for i in imports) + "---\n"
    defs = ("***definitions***\n\n" + "".join(f"{d}\n" for d in definitions) + "\n") if definitions else ""
    return frontmatter + defs + IMPL + "\n***functional specs***\n\n# main\nBody.\n"


def test_require_imported_concepts__required_concept_defined(project):
    project.write("required_concepts.plain", REQUIRED)
    project.parse("m.plain", _importing(["required_concepts"], [f"- {c('Concept')} is a concept."]))


def test_require_imported_concepts__required_concept_defined_by_another_import(project):
    project.write("required_concepts.plain", REQUIRED)
    project.write("required_concepts_defs.plain", f"***definitions***\n\n- {c('Concept')} is a concept.\n")
    _, tree, _ = project.parse("m.plain", _importing(["required_concepts", "required_concepts_defs"], []))
    assert tree["definitions"] == [
        {"markdown": f"- {c('Concept')} is a concept."},
        {"markdown": f"- {c('DependantConcept')} is a concept that depends on the {c('Concept')} concept."},
    ]


def _nested_required(project):
    project.write(
        "required_concepts_l2.plain",
        f"---\nrequired_concepts:\n  - '{c('Concept1')} is needed.'\n  - '{c('Concept2')} is needed.'\n---\n"
        f"***implementation reqs***\n\n- Uses {c('Concept1')} and {c('Concept2')}.\n",
    )
    project.write(
        "required_concepts_l1.plain",
        f"---\nimport:\n  - required_concepts_l2\n---\n***definitions***\n\n- {c('Concept1')} is the first concept.\n",
    )


def test_require_imported_concepts__nested_required_concepts(project):
    _nested_required(project)
    project.parse("m.plain", _importing(["required_concepts_l1"], [f"- {c('Concept2')} is the second concept."]))


def test_require_imported_concepts__required_concept_missing(project):
    project.write("required_concepts.plain", REQUIRED)
    message = raises(PlainSyntaxError, project.parse, "m.plain", _importing(["required_concepts"], []))
    assert f"Not all required concepts were defined. Missing required concepts: {c('Concept')}." in message


def test_require_imported_concepts__required_concept_defined_twice(project):
    _nested_required(project)
    text = _importing(
        ["required_concepts_l1"], [f"- {c('Concept1')} is mine.", f"- {c('Concept2')} is the second concept."]
    )
    message = raises(PlainSyntaxError, project.parse, "m.plain", text)
    assert "Concepts were defined multiple times" in message


# normalize-concept-lists


def test_normalize_concept_lists__string_entries(project):
    text = f"---\nexported_concepts:\n  - '{c('Concept')} is a concept.'\n---\n***definitions***\n\n- {c('Concept')} is a concept.\n"
    result = project.parse_text(text)
    assert result.plain_source_obj.metadata["exported_concepts"] == [f"- {c('Concept')} is a concept."]


def test_normalize_concept_lists__entry_of_another_type(project):
    message = raises(PlainSyntaxError, project.parse_text, "---\nexported_concepts:\n  - 5\n---\n" + IMPL)
    assert message == "Plain syntax error: Invalid exported_concepts metadata. Expected a dictionary or a string."


# check-exported-concepts


def _exporting(exports, definitions, extra_frontmatter=""):
    frontmatter = (
        "---\n" + extra_frontmatter + "exported_concepts:\n" + "".join(f"  - '{e}'\n" for e in exports) + "---\n"
    )
    defs = ("***definitions***\n\n" + "".join(f"{d}\n" for d in definitions) + "\n") if definitions else ""
    return frontmatter + defs + IMPL + "\n***functional specs***\n\n# main\nBody.\n"


def test_check_exported_concepts__export_own_concept(project):
    project.parse("exported_concepts.plain", _exporting([c("Concept")], [f"- {c('Concept')} is a concept."]))


def test_check_exported_concepts__export_imported_concept(project):
    project.write("exported_concepts_base.plain", f"***definitions***\n\n- {c('Concept')} is a concept.\n")
    project.parse("m.plain", _exporting([c("Concept")], [], "import:\n  - exported_concepts_base\n"))


def test_check_exported_concepts__several_per_entry(project):
    text = _exporting(
        [f"{c('NewConcept')}, {c('OtherConcept')}"],
        [f"- {c('NewConcept')} is new.", f"- {c('OtherConcept')} is other."],
    )
    project.parse("m.plain", text)


def test_check_exported_concepts__export_predefined_concept(project):
    message = raises(PlainSyntaxError, project.parse, "m.plain", _exporting([c("Implementation")], []))
    assert "cannot export default concept" in message


def test_check_exported_concepts__export_inherited_concept(project):
    project.write("exported_concepts.plain", _exporting([c("Concept")], [f"- {c('Concept')} is a concept."]))
    text = (
        f"---\nrequires:\n  - exported_concepts\nexported_concepts:\n  - '{c('Concept')}'\n---\n"
        + IMPL
        + f"\n***functional specs***\n\n# uses\nUses {c('Concept')}.\n"
    )
    message = raises(PlainSyntaxError, project.parse, "m.plain", text)
    assert "cannot be re-exported" in message


def test_check_exported_concepts__export_malformed(project):
    message = raises(PlainSyntaxError, project.parse, "m.plain", _exporting(["Concept"], []))
    assert "exports an invalid concept" in message


def test_check_exported_concepts__export_undefined_names_module(project):
    project.write(
        "exported_concepts_missing_definition.plain", _exporting([c("Concept")], [f"- {c('Other')} is other."])
    )
    message = raises(PlainSyntaxError, project.parse, "exported_concepts_missing_definition.plain")
    assert "'exported_concepts_missing_definition' exports" in message
    assert "exports undefined concept" in message
    text = (
        "---\nrequires:\n  - exported_concepts_missing_definition\n---\n"
        + IMPL
        + "\n***functional specs***\n\n# m\nBody.\n"
    )
    message = raises(PlainSyntaxError, project.parse, "dependent.plain", text)
    assert "'exported_concepts_missing_definition' exports" in message
    assert "exports undefined concept" in message


def test_check_exported_concepts__export_undefined_in_multi_entry(project):
    text = _exporting([f"{c('NewConcept')}, {c('OtherConcept')}"], [f"- {c('NewConcept')} is new."])
    message = raises(PlainSyntaxError, project.parse, "m.plain", text)
    assert "exports undefined concept" in message


def test_check_exported_concepts__export_without_definitions(project):
    message = raises(PlainSyntaxError, project.parse, "m.plain", _exporting([c("Concept")], []))
    assert "exports undefined concept" in message


# mark-code-variables


def test_mark_code_variables__token_is_recorded():
    code_variables: dict = {}
    output = plain_file.render_plain_source(
        "{% include 't', a: 'A', b: 'B' %}", {"t": "{{ b | code_variable }}"}, code_variables
    )
    assert re.fullmatch(r"[0-9a-f]{32}", output)
    assert code_variables == {output: {"a": "B"}}


def test_mark_code_variables__outside_include():
    code_variables: dict = {}
    output = plain_file.render_plain_source("a {{ 'x' | code_variable }}", {}, code_variables)
    assert output.startswith("a ")
    token = output[2:]
    assert re.fullmatch(r"[0-9a-f]{32}", token)
    assert code_variables == {token: {"code_variables": "x"}}


# record-code-variables


def test_record_code_variables__functionality_code_variable(project):
    project.write(
        "implement.plain",
        "something nice and useful\n  - the nice thing should be really {{ variable_name | code_variable }}\n"
        "  - the useful thing should be really useful\n",
    )
    text = (
        f"***definitions***\n\n- {c('concept')} is a concept.\n\n"
        + IMPL
        + '\n***functional specs***\n\n# implement\nImplement {% include "implement.plain", variable_name: "nice" %}\n'
    )
    _, tree, _ = project.parse("code_variables.plain", text)
    functionality = tree["functional specs"][0]
    assert functionality["markdown"] == (
        "Implement something nice and useful\n  - the nice thing should be really {{ variable_name }}\n"
        "  - the useful thing should be really useful"
    )
    assert functionality["code_variables"] == [{"name": "variable_name", "value": "nice"}]
    assert tree["definitions"] == [{"markdown": f"- {c('concept')} is a concept."}]


def test_record_code_variables__list_items_and_first_argument_name(project):
    project.write(
        "header.plain",
        "- Use {{ variable_name_1 | code_variable }} first.\n- Use {{ variable_name_2 | code_variable }} second.\n",
    )
    text = (
        '***implementation reqs***\n\n{% include "header.plain", variable_name_1: "nice_1", variable_name_2: "nice_2" %}\n\n'
        "***functional specs***\n\n# main\nBody.\n"
    )
    _, tree, _ = project.parse("template_include.plain", text)
    assert tree["implementation reqs"] == [
        {
            "markdown": "- Use {{ variable_name_1 }} first.",
            "code_variables": [{"name": "variable_name_1", "value": "nice_1"}],
        },
        {
            "markdown": "- Use {{ variable_name_1 }} second.",
            "code_variables": [{"name": "variable_name_1", "value": "nice_2"}],
        },
    ]


def test_record_code_variables__same_include_two_values(project):
    project.write("value.plain", "{{ variable_name | code_variable }}")
    text = PREFIX + (
        '# first\nUse {% include "value.plain", variable_name: "first" %}.\n\n'
        '# second\nUse {% include "value.plain", variable_name: "second" %}.\n'
    )
    _, tree, _ = project.parse("m.plain", text)
    assert tree["functional specs"][0]["code_variables"] == [{"name": "variable_name", "value": "first"}]
    assert tree["functional specs"][1]["code_variables"] == [{"name": "variable_name", "value": "second"}]


# check-module-shape


def test_check_module_shape__no_implementation_reqs(project):
    for text in [
        "***implementation reqs***\n\n***functional specs***\n\n# main\nBody.\n",
        "***functional specs***\n\n# main\nBody.\n",
    ]:
        message = raises(Exception, project.parse, "m.plain", text)
        assert "defines functionalities but specifies no implementation reqs" in message
        assert "requires" not in message


def test_check_module_shape__no_implementation_reqs_with_requires(project):
    project.write("base.plain", IMPL + "\n***functional specs***\n\n# base\nBody.\n")
    text = "---\nrequires:\n  - base\n---\n***functional specs***\n\n# main\nBody.\n"
    message = raises(PlainSyntaxError, project.parse, "m.plain", text)
    assert "not inherited through 'requires'" in message


def test_check_module_shape__no_functional_specs_section(project):
    message = raises(MissingFunctionalitiesError, project.parse, "m.plain", IMPL)
    assert "does not have any functionality specified" in message


def test_check_module_shape__empty_functional_specs_section(project):
    message = raises(PlainSyntaxError, project.parse, "m.plain", IMPL + "\n***functional specs***\n")
    assert (
        "has a 'functional specs' section without a `# <func-id>` heading. A functionality is a `# <func-id>` "
        "heading followed by its body; the previous syntax is not supported." in message
    )


# parse-single-module


def test_parse_single_module__simple_module(project):
    assert project.parse("simple.plain", SIMPLE) == (
        "simple",
        {
            "implementation reqs": [{"markdown": "- Simple implementation requirement"}],
            "functional specs": [
                {
                    "id": "simple-functionality",
                    "markdown": "Simple functionality",
                    "linked_resources": [],
                    "conformance_tests": [],
                    "acceptance_tests": [],
                }
            ],
        },
        [],
    )


def test_parse_single_module__nested_module_name(project):
    project.write("sub/m.plain", SIMPLE)
    name, _, _ = plain_file.plain_file_parser("sub/m.plain", [project.root])
    assert name == "sub/m"


def test_parse_single_module__valid_concepts(project):
    text = module(
        definitions=[f"- {c('Task')} is a thing to do.", f"- {c('User')}, {c('Admin')} are people."],
        impl=[f"- {c('Implementation')} stores every {c('Task')}."],
        functional=f"# add-task\nA {c('User')} or an {c('Admin')} adds a {c('Task')}.\n",
    )
    project.parse("m.plain", text)


def test_parse_single_module__sorted_definitions(project):
    text = module(
        definitions=[
            f"- {c('Concept3')} is built from {c('Concept1')} and {c('Concept2')}.",
            f"- {c('Concept2')} is built from {c('Concept1')}.",
            f"- {c('Concept1')} is a concept.",
        ],
        impl=["- A req."],
        functional="# main\nBody.\n",
    )
    _, tree, _ = project.parse("m.plain", text)
    assert [d["markdown"].split(":")[1] for d in tree["definitions"]] == ["Concept1", "Concept2", "Concept3"]


def test_parse_single_module__wrong_extension(project):
    project.write("test.txt", SIMPLE)
    raises(PlainSyntaxError, project.parse, "test.txt")


def test_parse_single_module__undefined_concept(project):
    raises(PlainSyntaxError, project.parse, "a.plain", module(impl=["- A req."], functional=f"# f\nA {c('User')}.\n"))
    text = module(
        definitions=[f"- {c('Task')} is a thing."],
        impl=["- A req."],
        functional=f"# f\nA {c('Task')} is seen by a {c('Visitor')}.\n",
    )
    raises(PlainSyntaxError, project.parse, "b.plain", text)


def test_parse_single_module__definition_without_concept(project):
    text = module(definitions=["- A plain sentence."], impl=["- A req."], functional="# f\nBody.\n")
    message = raises(PlainSyntaxError, project.parse, "m.plain", text)
    assert "Invalid definition specification text" in message


def test_parse_single_module__concept_defined_twice(project):
    text = module(
        definitions=[f"- {c('Task')} is x.", f"- {c('Task')} is y."], impl=["- A req."], functional="# f\nBody.\n"
    )
    message = raises(PlainSyntaxError, project.parse, "m.plain", text)
    assert "Concepts were defined multiple times" in message


def test_parse_single_module__cyclic_definitions(project):
    text = module(
        definitions=[f"- {c('A')} uses {c('B')}.", f"- {c('B')} uses {c('A')}."],
        impl=["- A req."],
        functional="# f\nBody.\n",
    )
    message = raises(PlainSyntaxError, project.parse, "m.plain", text)
    assert "cycle(s) in concept definitions" in message


def test_parse_single_module__cyclic_definitions_across_import(project):
    project.write("required_concepts.plain", REQUIRED)
    own = f"- {c('Concept')} is the concept that {c('DependantConcept')} builds on."
    message = raises(PlainSyntaxError, project.parse, "m.plain", _importing(["required_concepts"], [own]))
    assert "Found 1 cycle" in message
    assert own in message
    assert f"- {c('DependantConcept')} is a concept that depends on the {c('Concept')} concept." in message


def test_parse_single_module__cyclic_definitions_through_sub_item(project):
    order = f"- {c('Order')} is a purchase.\n  - It is placed by a {c('Customer')}."
    text = module(
        definitions=[order, f"- {c('Customer')} has {c('Order')} items.", f"- {c('Receipt')} is for an {c('Order')}."],
        impl=["- A req."],
        functional="# f\nBody.\n",
    )
    message = raises(PlainSyntaxError, project.parse, "m.plain", text)
    assert f"Cycle 1: {c('Order')} -> {c('Customer')} -> {c('Order')}" in message
    assert order in message
    assert c("Receipt") not in message


def test_parse_single_module__liquid_error_names_module(project):
    text = "***functional specs***\n\n# a-user-can-add-a\nA user can add a {{ task_name\n"
    message = raises(PlainSyntaxError, project.parse, "unterminated_output.plain", text)
    assert message.startswith("Plain syntax error: Invalid Liquid at unterminated_output:5:0")


def test_parse_single_module__include_ending_in_newline(project):
    project.write("detail.plain", "the detail\n")
    text = PREFIX + '# add-task\nA thing.\n  - With {% include "detail.plain" %}\n> a comment\n'
    project.parse("m.plain", text)
