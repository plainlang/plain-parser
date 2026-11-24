"""Conformance tests of module project."""

import os

import pytest
from plain_parser import project
from plain_parser.exceptions import MissingTestPlainFileError, PlainSyntaxError


def c(name):
    return f":{name}:"


TODO = (
    f"***definitions***\n\n- {c('Task')} is a thing to do.\n\n"
    "***implementation reqs***\n\n- The app is written in Python.\n\n"
    f"***functional specs***\n\n# add-task\nA {c('Task')} can be added.\n\n# list-tasks\nEvery {c('Task')} is listed.\n"
)


class Fixture:
    def __init__(self, root):
        self.root = str(root)
        self.write("todo.plain", TODO)

    def write(self, name, text):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mode = "wb" if isinstance(text, bytes) else "w"
        with open(path, mode, **({} if isinstance(text, bytes) else {"encoding": "utf-8"})) as file:
            file.write(text)

    def test_file(self, name, module, func_id, conformance=(), acceptance=(), with_acceptance=True):
        """``conformance`` and ``acceptance`` hold (scenario-id, text) pairs."""
        text = f"---\nmodule: {module}\nfunc_id: {func_id}\n---\n\n***conformance tests***\n\n"
        text += "".join(f"# {sid}\n{body}\n\n" for sid, body in conformance)
        if with_acceptance:
            text += "***acceptance tests***\n\n" + "".join(f"# {sid}\n{body}\n\n" for sid, body in acceptance)
        self.write(name, text)

    def parse(self, entry="todo.plain", tests=("tests",), require=False):
        return project.parse_project(entry, [self.root], list(tests), require)


@pytest.fixture
def fx(tmp_path):
    return Fixture(tmp_path)


def raises(exception, call, *args, **kwargs):
    with pytest.raises(exception) as error:
        call(*args, **kwargs)
    return str(error.value)


def functionality(result, module, func_id):
    tree = dict(result.chain)[module]
    return next(f for f in tree["functional specs"] if f["id"] == func_id)


# discover-test-plain-files


def test_discover_test_plain_files__path_order(fx):
    for name in ["tests/b.plain", "tests/a.plain", "tests/sub/c.plain"]:
        fx.test_file(name, "todo", "add-task", [(f"s-{name[6]}", "Works.")])
    result = fx.parse()
    assert [b.name for b in result.test_plain_files] == ["tests/a.plain", "tests/b.plain", "tests/sub/c.plain"]


def test_discover_test_plain_files__folder_order(fx):
    fx.test_file("more/b.plain", "todo", "add-task", [("from-b", "Works.")])
    fx.test_file("tests/a.plain", "todo", "add-task", [("from-a", "Works.")])
    result = fx.parse(tests=["more", "tests"])
    assert [b.name for b in result.test_plain_files] == ["more/b.plain", "tests/a.plain"]


def test_discover_test_plain_files__missing_folder(fx):
    assert fx.parse().test_plain_files == []


# bind-test-plain-files


def test_bind_test_plain_files__scenarios_are_merged(fx):
    fx.test_file(
        "tests/todo/add-task.plain",
        "todo",
        "add-task",
        [("add-one", f"Adding one {c('Task')} shows it.")],
        [("add-then-list", "Add, then list.")],
    )
    result = fx.parse()
    assert [(b.name, b.parsed.module, b.parsed.func_id) for b in result.test_plain_files] == [
        ("tests/todo/add-task.plain", "todo", "add-task")
    ]
    add_task = functionality(result, "todo", "add-task")
    assert add_task["conformance_tests"] == [
        {"id": "add-one", "text": f"Adding one {c('Task')} shows it.", "linked_resources": []}
    ]
    assert add_task["acceptance_tests"] == [{"id": "add-then-list", "text": "Add, then list.", "linked_resources": []}]
    assert functionality(result, "todo", "list-tasks")["conformance_tests"] == []


def test_bind_test_plain_files__name_is_convention_only(fx):
    fx.test_file("tests/anything.plain", "todo", "list-tasks", [("lists", "Lists.")])
    result = fx.parse()
    assert [s["id"] for s in functionality(result, "todo", "list-tasks")["conformance_tests"]] == ["lists"]


def test_bind_test_plain_files__merge_in_discovery_order(fx):
    fx.test_file("tests/b.plain", "todo", "add-task", [("from-b", "B.")])
    fx.test_file("tests/a.plain", "todo", "add-task", [("from-a", "A.")])
    fx.test_file("tests/sub/c.plain", "todo", "add-task", [("from-c", "C.")])
    result = fx.parse()
    assert [s["id"] for s in functionality(result, "todo", "add-task")["conformance_tests"]] == [
        "from-a",
        "from-b",
        "from-c",
    ]


def test_bind_test_plain_files__folders_in_given_order(fx):
    fx.test_file("more/b.plain", "todo", "add-task", [("from-b", "B.")])
    fx.test_file("tests/a.plain", "todo", "add-task", [("from-a", "A.")])
    result = fx.parse(tests=["more", "tests"])
    assert [s["id"] for s in functionality(result, "todo", "add-task")["conformance_tests"]] == ["from-b", "from-a"]


def test_bind_test_plain_files__file_of_another_module_is_passed_over(fx):
    fx.test_file("tests/todo/add-task.plain", "todo", "add-task", [("works", "Works.")])
    fx.test_file("tests/notes/add-note.plain", "notes", "add-note", [("noted", "Noted.")])
    result = fx.parse()
    assert [b.name for b in result.test_plain_files] == ["tests/todo/add-task.plain"]
    assert [s["id"] for s in functionality(result, "todo", "add-task")["conformance_tests"]] == ["works"]


def test_bind_test_plain_files__file_of_another_module_is_not_read(fx):
    fx.test_file(
        "tests/notes/add-note.plain",
        "notes",
        "add-note",
        [("noted", f"A {c('Note')} is added.")],
        with_acceptance=False,
    )
    assert fx.parse().test_plain_files == []


def _core_and_todo(fx, core_definitions=True, todo_extra=""):
    core = "---\nexported_concepts:\n  - ':Task:'\n---\n" if core_definitions else ""
    if core_definitions:
        core += f"***definitions***\n\n- {c('Task')} is a thing to do.\n\n"
    core += "***implementation reqs***\n\n- Core is a library.\n\n***functional specs***\n\n# store-task\nIt stores.\n"
    fx.write("core.plain", core)
    fx.write("shared.plain", f"***definitions***\n\n- {c('Clock')} tells the time.\n")
    todo = "---\nrequires:\n  - core\nimport:\n  - shared\n---\n"
    todo += todo_extra
    todo += "***implementation reqs***\n\n- Todo is an app.\n\n"
    todo += f"***functional specs***\n\n# add-task\nA {c('Task')} at {c('Clock')}.\n"
    fx.write("todo.plain", todo)


def test_bind_test_plain_files__required_module_files(fx):
    _core_and_todo(fx)
    fx.test_file("tests/core/store-task.plain", "core", "store-task", [("stores", f"A {c('Task')} is kept.")])
    fx.test_file("tests/todo/add-task.plain", "todo", "add-task", [("works", f"A {c('Task')} at {c('Clock')}.")])
    result = fx.parse()
    assert [(b.parsed.module, b.parsed.func_id) for b in result.test_plain_files] == [
        ("core", "store-task"),
        ("todo", "add-task"),
    ]


# reject-invalid-test-plain-files


def test_reject_invalid_test_plain_files__unknown_func_id(fx):
    fx.test_file("tests/a.plain", "todo", "delete-task", [("works", "Works.")])
    assert raises(PlainSyntaxError, fx.parse) == (
        "Plain syntax error: Test plain file 'tests/a.plain' binds to functionality 'todo:delete-task', which module "
        "'todo' does not have."
    )


def test_reject_invalid_test_plain_files__no_binding_keys(fx):
    fx.write("tests/helper.plain", f"***definitions***\n\n- {c('Helper')} helps.\n")
    assert raises(PlainSyntaxError, fx.parse) == (
        "Plain syntax error: File 'tests/helper.plain' is under a tests folder but is not a test plain file: its "
        "frontmatter needs the keys `module:` and `func_id:`."
    )


def test_reject_invalid_test_plain_files__invalid_frontmatter(fx):
    fx.write("tests/broken.plain", "---\nmodule: [\n---\n")
    assert "File 'tests/broken.plain' under a tests folder has invalid frontmatter" in raises(
        PlainSyntaxError, fx.parse
    )


def test_reject_invalid_test_plain_files__file_errors_name_the_file(fx):
    fx.test_file("tests/a.plain", "todo", "add-task", [("works", "Works.")], with_acceptance=False)
    assert "Test plain file 'tests/a.plain' has no `***acceptance tests***`" in raises(PlainSyntaxError, fx.parse)


def test_reject_invalid_test_plain_files__not_a_text_file(fx):
    fx.write("tests/bin.plain", b"\x00\xff\xfe")
    assert "File 'tests/bin.plain' under a tests folder is not a text file." in raises(PlainSyntaxError, fx.parse)


# check-bound-scenarios


def test_check_bound_scenarios__same_id_in_two_functionalities(fx):
    fx.test_file("tests/a.plain", "todo", "add-task", [("works", "Works.")])
    fx.test_file("tests/b.plain", "todo", "list-tasks", [("works", "Works.")])
    fx.parse()


def test_check_bound_scenarios__undefined_concept(fx):
    fx.test_file("tests/a.plain", "todo", "add-task", [("works", f"A {c('Task')} and a {c('Note')} are added.")])
    message = raises(PlainSyntaxError, fx.parse)
    assert message == (
        "Plain syntax error: Found 1 errors in test plain file 'tests/a.plain':\n"
        f"Syntax error at line 8 in test plain file 'tests/a.plain': Concept {c('Note')} used in scenario `works` is "
        "not defined in module 'todo'."
    )


def test_check_bound_scenarios__required_module_does_not_see_entry_concepts(fx):
    fx.write(
        "core.plain", "***implementation reqs***\n\n- Core.\n\n***functional specs***\n\n# store-task\nIt stores.\n"
    )
    fx.write(
        "todo.plain",
        "---\nrequires:\n  - core\n---\n"
        + f"***definitions***\n\n- {c('Task')} is a thing.\n\n***implementation reqs***\n\n- Todo.\n\n"
        + f"***functional specs***\n\n# add-task\nA {c('Task')}.\n",
    )
    fx.test_file("tests/core/store-task.plain", "core", "store-task", [("stores", f"A {c('Task')} is kept.")])
    message = raises(PlainSyntaxError, fx.parse)
    assert f"Concept {c('Task')} used in scenario `stores` is not defined in module 'core'" in message


def test_check_bound_scenarios__duplicate_id_across_files(fx):
    fx.test_file("tests/a.plain", "todo", "add-task", [("works", "Works.")])
    fx.write(
        "tests/b.plain",
        "---\nmodule: todo\nfunc_id: add-task\n---\n\n***conformance tests***\n\n\n***acceptance tests***\n\n"
        "# works\nWorks too.\n",
    )
    message = raises(PlainSyntaxError, fx.parse)
    assert message == (
        "Plain syntax error: Syntax error at line 11 in test plain file 'tests/b.plain': Duplicate scenario-id `works` "
        "for functionality 'todo:add-task'; it is first used at line 8 in test plain file 'tests/a.plain'."
    )


# require-test-plain-files


def test_require_test_plain_files__empty_sections_satisfy_the_check(fx):
    fx.test_file("tests/a.plain", "todo", "add-task", [("works", "Works.")])
    for text in [
        "---\nmodule: todo\nfunc_id: list-tasks\n---\n***conformance tests***\n***acceptance tests***\n",
        "---\nmodule: todo\nfunc_id: list-tasks\n---\n\n***conformance tests***\n\n"
        "> add conformance test scenarios here\n\n***acceptance tests***\n",
    ]:
        fx.write("tests/b.plain", text)
        result = fx.parse(require=True)
        assert functionality(result, "todo", "list-tasks")["conformance_tests"] == []


def test_require_test_plain_files__check_off_by_default(fx):
    fx.test_file("tests/a.plain", "todo", "add-task", [("works", "Works.")])
    fx.parse()


def test_require_test_plain_files__missing_file(fx):
    fx.test_file("tests/a.plain", "todo", "add-task", [("works", "Works.")])
    assert raises(MissingTestPlainFileError, fx.parse, require=True) == (
        "Functionality todo:list-tasks has no test plain file. Add one, by convention tests/todo/list-tasks.plain, "
        "with the add-test-scenarios skill."
    )


def test_require_test_plain_files__misspelled_module(fx):
    fx.test_file("tests/a.plain", "tasks", "add-task", [("works", "Works.")])
    assert "todo:add-task" in raises(MissingTestPlainFileError, fx.parse, require=True)


def test_require_test_plain_files__required_modules_first(fx):
    fx.write(
        "core.plain", "***implementation reqs***\n\n- Core.\n\n***functional specs***\n\n# store-task\nIt stores.\n"
    )
    fx.write(
        "todo.plain",
        "---\nrequires:\n  - core\n---\n"
        + f"***definitions***\n\n- {c('Task')} is a thing.\n\n***implementation reqs***\n\n- Todo.\n\n"
        + f"***functional specs***\n\n# add-task\nA {c('Task')}.\n",
    )
    message = raises(MissingTestPlainFileError, fx.parse, require=True)
    assert "Functionality core:store-task has no test plain file" in message
