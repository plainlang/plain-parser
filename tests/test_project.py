import pytest

from plain_parser import plain_spec, project
from plain_parser.exceptions import MissingConformanceScenariosError, PlainSyntaxError

MODULE = (
    "***definitions***\n\n- :Task: is a thing to do.\n\n***implementation reqs***\n\n- A req.\n\n"
    "***functional specs***\n\n# add-task\nA :Task: can be added.\n\n# list-tasks\nEvery :Task: is listed.\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def scenario_file(module, func_id, conformance="", acceptance=""):
    return (
        f"---\nmodule: {module}\nfunc_id: {func_id}\n---\n\n***conformance tests***\n\n{conformance}"
        f"\n***acceptance tests***\n\n{acceptance}"
    )


def parse(tmp_path, require_conformance_scenarios=False, test_dirs=None):
    test_dirs = [str(tmp_path / "tests")] if test_dirs is None else test_dirs
    return project.parse_project("todo.plain", [str(tmp_path)], test_dirs, require_conformance_scenarios)


def functionalities(result, module="todo"):
    return {item["id"]: item for item in dict(result.chain)[module][plain_spec.FUNCTIONAL_REQUIREMENTS]}


def scenario_ids(functionality, key):
    return [scenario["id"] for scenario in functionality[key]]


def test_scenarios_are_merged_into_the_bound_functionality(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(
        tmp_path / "tests" / "todo" / "add-task.plain",
        scenario_file(
            "todo", "add-task", "# add-one\nAdding one :Task: shows it.\n", "# add-then-list\nAdd, then list.\n"
        ),
    )

    result = parse(tmp_path)

    assert [(bound.name, bound.parsed.module, bound.parsed.func_id) for bound in result.test_plain_files] == [
        ("tests/todo/add-task.plain", "todo", "add-task")
    ]
    assert functionalities(result)["add-task"][plain_spec.CONFORMANCE_TESTS] == [
        {"id": "add-one", "text": "Adding one :Task: shows it.", "linked_resources": []}
    ]
    assert functionalities(result)["add-task"][plain_spec.ACCEPTANCE_TESTS] == [
        {"id": "add-then-list", "text": "Add, then list.", "linked_resources": []}
    ]
    assert functionalities(result)["list-tasks"][plain_spec.CONFORMANCE_TESTS] == []


def test_location_and_name_of_a_test_plain_file_are_convention_only(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(tmp_path / "tests" / "anything.plain", scenario_file("todo", "list-tasks", "# lists\nIt lists.\n"))

    result = parse(tmp_path)

    assert scenario_ids(functionalities(result)["list-tasks"], plain_spec.CONFORMANCE_TESTS) == ["lists"]


def test_files_bound_to_one_functionality_merge_in_path_order(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(tmp_path / "tests" / "b.plain", scenario_file("todo", "add-task", "# from-b\nFrom b.\n"))
    write(tmp_path / "tests" / "a.plain", scenario_file("todo", "add-task", "# from-a\nFrom a.\n"))
    write(tmp_path / "tests" / "sub" / "c.plain", scenario_file("todo", "add-task", "# from-c\nFrom c.\n"))

    result = parse(tmp_path)

    assert scenario_ids(functionalities(result)["add-task"], plain_spec.CONFORMANCE_TESTS) == [
        "from-a",
        "from-b",
        "from-c",
    ]
    assert [bound.name for bound in result.test_plain_files] == [
        "tests/a.plain",
        "tests/b.plain",
        "tests/sub/c.plain",
    ]


def test_test_dirs_are_read_in_the_given_order(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(tmp_path / "more" / "b.plain", scenario_file("todo", "add-task", "# from-b\nFrom b.\n"))
    write(tmp_path / "tests" / "a.plain", scenario_file("todo", "add-task", "# from-a\nFrom a.\n"))

    result = parse(tmp_path, test_dirs=[str(tmp_path / "more"), str(tmp_path / "tests")])

    assert scenario_ids(functionalities(result)["add-task"], plain_spec.CONFORMANCE_TESTS) == ["from-b", "from-a"]
    assert [bound.name for bound in result.test_plain_files] == ["more/b.plain", "tests/a.plain"]


def test_missing_test_dir_is_not_an_error(tmp_path):
    write(tmp_path / "todo.plain", MODULE)

    result = parse(tmp_path)

    assert result.test_plain_files == []


def test_duplicate_scenario_id_across_files_is_rejected(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(tmp_path / "tests" / "a.plain", scenario_file("todo", "add-task", "# works\nIt works.\n"))
    write(tmp_path / "tests" / "b.plain", scenario_file("todo", "add-task", "", "# works\nIt works again.\n"))

    with pytest.raises(PlainSyntaxError) as exc_info:
        parse(tmp_path)

    assert str(exc_info.value) == (
        "Plain syntax error: Syntax error at line 11 in test plain file 'tests/b.plain': Duplicate scenario-id "
        "`works` for functionality 'todo:add-task'; it is first used at line 8 in test plain file 'tests/a.plain'."
    )


def test_same_scenario_id_for_two_functionalities_is_allowed(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(tmp_path / "tests" / "a.plain", scenario_file("todo", "add-task", "# works\nIt works.\n"))
    write(tmp_path / "tests" / "b.plain", scenario_file("todo", "list-tasks", "# works\nIt works.\n"))

    parse(tmp_path)


def test_unknown_module_is_rejected(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(tmp_path / "tests" / "a.plain", scenario_file("tasks", "add-task", "# works\nIt works.\n"))

    with pytest.raises(PlainSyntaxError) as exc_info:
        parse(tmp_path)

    assert str(exc_info.value) == (
        "Plain syntax error: Test plain file 'tests/a.plain' binds to module 'tasks', which is not the entry "
        "module or one of its required modules (todo)."
    )


def test_unknown_func_id_is_rejected(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(tmp_path / "tests" / "a.plain", scenario_file("todo", "delete-task", "# works\nIt works.\n"))

    with pytest.raises(PlainSyntaxError) as exc_info:
        parse(tmp_path)

    assert str(exc_info.value) == (
        "Plain syntax error: Test plain file 'tests/a.plain' binds to functionality 'todo:delete-task', which "
        "module 'todo' does not have."
    )


def test_plain_file_under_test_dir_without_binding_keys_is_rejected(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(tmp_path / "tests" / "helper.plain", "***definitions***\n\n- :Helper: helps.\n")

    with pytest.raises(PlainSyntaxError) as exc_info:
        parse(tmp_path)

    assert str(exc_info.value) == (
        "Plain syntax error: File 'tests/helper.plain' is under a test folder but is not a test plain file: its "
        "frontmatter needs the keys `module:` and `func_id:`."
    )


def test_file_under_test_dir_with_invalid_frontmatter_is_rejected(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(tmp_path / "tests" / "broken.plain", "---\nmodule: [\n---\n")

    with pytest.raises(PlainSyntaxError, match="File 'tests/broken.plain' under a test folder has invalid frontmatter"):
        parse(tmp_path)


def test_test_plain_file_errors_name_their_file(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(tmp_path / "tests" / "a.plain", "---\nmodule: todo\nfunc_id: add-task\n---\n\n***conformance tests***\n")

    with pytest.raises(PlainSyntaxError, match="Test plain file 'tests/a.plain' has no `\\*\\*\\*acceptance tests"):
        parse(tmp_path)


def test_scenario_concepts_are_checked_against_the_bound_module(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(
        tmp_path / "tests" / "a.plain", scenario_file("todo", "add-task", "# works\nA :Task: and a :Note: are added.\n")
    )

    with pytest.raises(PlainSyntaxError) as exc_info:
        parse(tmp_path)

    assert str(exc_info.value) == (
        "Plain syntax error: Found 1 errors in test plain file 'tests/a.plain':\n"
        "Syntax error at line 8 in test plain file 'tests/a.plain': Concept :Note: used in scenario `works` is not "
        "defined in module 'todo'."
    )


def test_scenarios_see_imported_and_exported_concepts(tmp_path):
    write(tmp_path / "shared.plain", "***definitions***\n\n- :Clock: tells the time.\n")
    write(
        tmp_path / "core.plain",
        '---\nexported_concepts: [":Task:"]\n---\n\n***definitions***\n\n- :Task: is a thing to do.\n\n'
        "***implementation reqs***\n\n- A req.\n\n***functional specs***\n\n# store-task\nA :Task: is stored.\n",
    )
    write(
        tmp_path / "todo.plain",
        "---\nrequires:\n  - core\nimport:\n  - shared\n---\n\n***implementation reqs***\n\n- A req.\n\n"
        "***functional specs***\n\n# add-task\nA :Task: can be added at a :Clock: time.\n",
    )
    write(
        tmp_path / "tests" / "todo" / "add-task.plain",
        scenario_file("todo", "add-task", "# works\nA :Task: at :Clock:.\n"),
    )
    write(
        tmp_path / "tests" / "core" / "store-task.plain",
        scenario_file("core", "store-task", "# stores\nA :Task: is kept.\n"),
    )

    result = parse(tmp_path)

    assert scenario_ids(functionalities(result, "core")["store-task"], plain_spec.CONFORMANCE_TESTS) == ["stores"]
    assert scenario_ids(functionalities(result)["add-task"], plain_spec.CONFORMANCE_TESTS) == ["works"]


def test_required_module_scenarios_do_not_see_the_top_modules_concepts(tmp_path):
    write(
        tmp_path / "core.plain",
        "***implementation reqs***\n\n- A req.\n\n***functional specs***\n\n# store-task\nIt stores.\n",
    )
    write(tmp_path / "todo.plain", "---\nrequires:\n  - core\n---\n\n" + MODULE)
    write(
        tmp_path / "tests" / "core" / "store-task.plain",
        scenario_file("core", "store-task", "# stores\nA :Task: is kept.\n"),
    )

    with pytest.raises(
        PlainSyntaxError, match="Concept :Task: used in scenario `stores` is not defined in module 'core'"
    ):
        parse(tmp_path)


def test_every_functionality_needs_a_conformance_scenario_when_required(tmp_path):
    write(tmp_path / "todo.plain", MODULE)
    write(tmp_path / "tests" / "a.plain", scenario_file("todo", "add-task", "# works\nIt works.\n"))
    write(tmp_path / "tests" / "b.plain", scenario_file("todo", "list-tasks", "", "# flows\nIt flows.\n"))

    parse(tmp_path)
    with pytest.raises(MissingConformanceScenariosError) as exc_info:
        parse(tmp_path, require_conformance_scenarios=True)

    assert str(exc_info.value) == (
        "Functionality todo:list-tasks has no conformance scenario. Add one in a test plain file (by convention "
        "tests/todo/list-tasks.plain) with the add-test-scenarios skill."
    )


def test_completeness_covers_the_required_modules_first(tmp_path):
    write(
        tmp_path / "core.plain",
        "***implementation reqs***\n\n- A req.\n\n***functional specs***\n\n# store-task\nIt stores.\n",
    )
    write(tmp_path / "todo.plain", "---\nrequires:\n  - core\n---\n\n" + MODULE)

    with pytest.raises(MissingConformanceScenariosError, match="Functionality core:store-task has no conformance"):
        parse(tmp_path, require_conformance_scenarios=True)
