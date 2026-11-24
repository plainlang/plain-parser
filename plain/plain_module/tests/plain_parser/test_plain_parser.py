"""Conformance tests of module plain_parser."""

import io
import json
import os
import subprocess
import sys

import plain_parser
from plain_parser import cli
from plain_parser.exceptions import PlainSyntaxError
from plain_parser_helpers import LIST_TWO_TEXT, VALID, c

OK = ": OK\n"
API_ALL = [
    "PlainFileParseResult",
    "concept_utils",
    "exceptions",
    "get_filename_from_module_name",
    "get_module_name_from_filename",
    "loaders",
    "marshall_plain_source",
    "parse_module_chain",
    "parse_plain_file",
    "parse_plain_source",
    "plain_file",
    "plain_file_parser",
    "plain_spec",
    "project",
    "test_plain_file",
]
IMPL = "***implementation reqs***\n\n- It is written in Python.\n\n"


def simple_module(body="It works.", impl=IMPL, front="", definitions=""):
    return front + definitions + impl + f"***functional specs***\n\n# main\n{body}\n"


def doc(result):
    assert result.stdout.endswith("\n") and not result.stdout.endswith("\n\n")
    return json.loads(result.stdout)


def chain_of(path, dirs):
    return plain_parser.parse_module_chain(os.path.basename(path), dirs)


# export-package-api


def test_export_package_api__package_names(ws):
    assert plain_parser.__all__ == API_ALL
    for name in API_ALL:
        assert hasattr(plain_parser, name)
    ws.valid()
    name, tree, requires = plain_parser.plain_file_parser("valid.plain", [ws.root])
    assert name == "valid" and requires == [] and tree["functional specs"][0]["id"] == "app-prints-hello-world"


def test_export_package_api__console_script(ws):
    ws.valid()
    result = ws.run("check", "valid.plain")
    assert result.returncode == 0
    assert result.stdout.endswith(OK)
    assert result.stderr == ""


# accept-command-line


def test_accept_command_line__check_without_file(ws):
    result = ws.run("check")
    assert result.returncode == 2 and "usage:" in result.stderr


def test_accept_command_line__parse_without_file(ws):
    result = ws.run("parse")
    assert result.returncode == 2 and "usage:" in result.stderr and result.stdout == ""


def test_accept_command_line__without_subcommand(ws):
    assert ws.run().returncode == 2


# find-config-file


def test_find_config_file__config_next_to_spec(ws):
    ws.top_project(config="template-dir: template\n")
    assert ws.run("check", "project/top.plain").stdout == "project/top.plain" + OK


def test_find_config_file__config_in_working_directory(ws):
    ws.top_project()
    ws.write("config.yaml", "template-dir: project/template\n")
    assert ws.run("check", "project/top.plain").stdout == "project/top.plain" + OK


def test_find_config_file__config_name_option(ws):
    ws.top_project()
    ws.write("project/web.config.yaml", "template-dir: template\n")
    assert ws.run("check", "project/top.plain", "--config-name", "web.config.yaml").stdout == "project/top.plain" + OK
    assert ws.run("check", "project/top.plain").returncode == 1


def test_find_config_file__no_config(ws):
    ws.top_project()
    result = ws.run("check", "project/top.plain")
    assert result.returncode == 1
    assert result.stderr == "Error: Module does not exist (helper).\n"


def test_find_config_file__config_in_both_places(ws):
    ws.top_project(config="template-dir: template\n")
    ws.write("config.yaml", "template-dir: project/template\n")
    for args in (["check", "project/top.plain"], ["check", "project/top.plain", "--template-dir", "project/template"]):
        result = ws.run(*args)
        assert result.returncode == 2 and "found in two locations" in result.stderr
    result = ws.run("parse", "project/top.plain")
    assert result.returncode == 2 and "found in two locations" in result.stderr and result.stdout == ""


def test_find_config_file__unreadable_config(ws):
    ws.top_project(config="template-dir: [unclosed\n")
    result = ws.run("check", "project/top.plain")
    assert result.returncode == 2 and "Error reading config file" in result.stderr


# read-config-values


def test_read_config_values__underscore_key(ws):
    ws.top_project(config="template_dir: template\n")
    assert ws.run("check", "project/top.plain").stdout == "project/top.plain" + OK


def test_read_config_values__other_keys_ignored(ws):
    ws.top_project(config="unittests-script: scripts/x.sh\nbuild-dest: dist\ntemplate-dir: template\nverbose: true\n")
    assert ws.run("check", "project/top.plain").stdout == "project/top.plain" + OK


def test_read_config_values__template_dir_option_wins(ws):
    ws.top_project(config="template-dir: does_not_exist\n")
    result = ws.run("check", "project/top.plain", "--template-dir", "project/template")
    assert result.stdout == "project/top.plain" + OK


def test_read_config_values__project_with_test_plain_files(ws):
    ws.todo_project()
    assert ws.run("check", "todo.plain", cwd=ws.path("project")).stdout == "todo.plain: OK\n"


def _rename_tests(ws, to="scenarios"):
    os.rename(ws.path("project", "tests"), ws.path("project", to))


def test_read_config_values__tests_folder_from_config(ws):
    for config in [
        "conformance-tests-script: run.sh\ntests-folder: scenarios\n",
        "conformance_tests_script: run.sh\ntests_folder: scenarios\n",
        "conformance-tests-script: run.sh\ntests-folder:\n  - scenarios\n  - more\n",
    ]:
        ws.todo_project(config=config)
        if os.path.isdir(ws.path("project", "scenarios")):
            import shutil

            shutil.rmtree(ws.path("project", "scenarios"))
        _rename_tests(ws)
        assert ws.run("check", "project/todo.plain").stdout == "project/todo.plain" + OK, config
        ws.remove("project/scenarios/todo/add-task.plain")
        result = ws.run("check", "project/todo.plain")
        assert "todo:add-task has no test plain file" in result.stderr, config


def test_read_config_values__config_tests_folder_only(ws):
    ws.todo_project(config="conformance-tests-script: test_scripts/run_conformance_tests.sh\ntests-folder: scenarios\n")
    result = ws.run("check", "project/todo.plain")
    assert result.returncode == 1
    assert "todo:add-task has no test plain file" in result.stderr


def test_read_config_values__tests_folder_option_wins(ws):
    ws.todo_project(
        config="conformance-tests-script: test_scripts/run_conformance_tests.sh\ntests-folder: does_not_exist\n"
    )
    _rename_tests(ws)
    assert "todo:add-task has no test plain file" in ws.run("check", "project/todo.plain").stderr
    result = ws.run("check", "project/todo.plain", "--tests-folder", "project/scenarios")
    assert result.stdout == "project/todo.plain" + OK


def test_read_config_values__tests_folder_option_repeated(ws):
    ws.todo_project()
    os.makedirs(ws.path("project", "more"))
    os.rename(ws.path("project", "tests", "todo", "list-tasks.plain"), ws.path("project", "more", "list-tasks.plain"))
    assert "todo:list-tasks has no test plain file" in ws.run("check", "project/todo.plain").stderr
    result = ws.run("check", "project/todo.plain", "--tests-folder", "project/tests", "--tests-folder", "project/more")
    assert result.stdout == "project/todo.plain" + OK


def test_read_config_values__without_conformance_script(ws):
    import shutil

    ws.todo_project(config="unittests-script: test_scripts/run_unittests.sh\n")
    shutil.rmtree(ws.path("project", "tests"))
    assert ws.run("check", "project/todo.plain").stdout == "project/todo.plain" + OK


def test_read_config_values__without_tests_folder(ws):
    ws.todo_project(config=None)
    ws.write("project/tests/todo/add-task.plain", "not a test plain file")
    assert ws.run("check", "project/todo.plain").stdout == "project/todo.plain" + OK
    assert doc(ws.run("parse", "project/todo.plain"))["test_plain_files"] == {}


def test_read_config_values__conformance_without_tests_folder(ws):
    ws.todo_project(config="conformance-tests-script: run.sh\n")
    message = "no tests folder is given. Pass --tests-folder or set tests-folder in the config file."
    for command in ("check", "parse"):
        result = ws.run(command, "project/todo.plain")
        assert result.returncode == 2 and result.stdout == "" and message in result.stderr
    result = ws.run("check", "project/todo.plain", "--tests-folder", "project/tests")
    assert result.stdout == "project/todo.plain" + OK


# parse-spec


def _template_link(ws):
    ws.write("template_link/spec/top.plain", simple_module("See [notes](notes.md)."))
    ws.write("template_link/tpl/notes.md", "notes")


def test_parse_spec__resource_from_template_dir(ws):
    _template_link(ws)
    result = doc(ws.run("parse", "template_link/spec/top.plain", "--template-dir", "template_link/tpl"))
    assert result["resources"] == {"notes.md": "../tpl/notes.md"}
    joined = os.path.normpath(os.path.join(ws.path("template_link", "spec"), result["resources"]["notes.md"]))
    assert joined == os.path.normpath(
        plain_parser.loaders.resolve_linked_resource([ws.path("template_link", "tpl")], "notes.md")
    )


def test_parse_spec__parent_relative_target(ws):
    ws.write("parent_link/a/spec/top.plain", simple_module("See [notes](../shared/notes.md)."))
    ws.write("parent_link/b/shared/notes.md", "notes")
    os.makedirs(ws.path("parent_link", "b", "tpl"))
    result = ws.run("parse", "a/spec/top.plain", "--template-dir", "b/tpl", cwd=ws.path("parent_link"))
    assert doc(result)["resources"] == {"../shared/notes.md": "../../b/tpl/../shared/notes.md"}


def test_parse_spec__symlink_not_resolved(ws):
    ws.write("top.plain", simple_module("See [x](lnk/../x.md)."))
    ws.write("sub/x.md", "read through the symlink")
    os.makedirs(ws.path("sub", "real"))
    ws.write("x.md", "next to the spec")
    os.symlink(ws.path("sub", "real"), ws.path("lnk"))
    resources = doc(ws.run("parse", "top.plain"))["resources"]
    assert resources == {"lnk/../x.md": "lnk/../x.md"}
    with open(os.path.join(ws.root, resources["lnk/../x.md"]), encoding="utf-8") as file:
        assert file.read() == "read through the symlink"


def test_parse_spec__target_from_two_modules(ws):
    ws.write("notes.md", "notes")
    ws.write("shared_link_helper.plain", simple_module("See [notes](notes.md)."))
    ws.write(
        "shared_link_top.plain",
        simple_module("See [notes](notes.md).", front="---\nrequires:\n  - shared_link_helper\n---\n"),
    )
    result = doc(ws.run("parse", "shared_link_top.plain"))
    assert [m["module"] for m in result["modules"]] == ["shared_link_helper", "shared_link_top"]
    assert result["resources"] == {"notes.md": "notes.md"}


def test_parse_spec__scenario_links(ws):
    ws.todo_project()
    ws.write("project/listing.txt", "1 Buy milk\n")
    ws.write(
        "project/tests/todo/list-tasks.plain",
        "---\nmodule: todo\nfunc_id: list-tasks\n---\n\n***conformance tests***\n\n"
        "# lists\nThe output matches [the listing](listing.txt).\n\n***acceptance tests***\n",
    )
    result = doc(ws.run("parse", "todo.plain", cwd=ws.path("project")))
    assert result["resources"] == {"listing.txt": "listing.txt"}


def test_parse_spec__relative_entry_path(ws):
    ws.write("subdir/nested.plain", VALID)
    assert ws.run("check", "subdir/nested.plain").stdout == "subdir/nested.plain" + OK


def test_parse_spec__empty_template_dir_is_ignored(ws):
    ws.write("spec/top.plain", simple_module(front="---\nrequires:\n  - helper\n---\n"))
    ws.write("helper.plain", simple_module())
    result = ws.run("check", "spec/top.plain", "--template-dir", "")
    assert result.returncode == 1
    assert result.stderr == "Error: Module does not exist (helper).\n"


def test_parse_spec__missing_template_dir_is_ignored(ws):
    ws.valid()
    assert ws.run("check", "valid.plain", "--template-dir", "nope").stdout == "valid.plain" + OK


def test_parse_spec__no_relative_path(ws, monkeypatch):
    _template_link(ws)

    def no_relative_path(*args, **kwargs):
        raise ValueError("path is on mount 'C:', start on mount 'D:'")

    monkeypatch.setattr(os.path, "relpath", no_relative_path)
    result = cli.parse_spec(ws.path("template_link", "spec", "top.plain"), ws.path("template_link", "tpl"), False)
    expected = os.path.join(ws.path("template_link", "tpl"), "notes.md").replace(os.sep, "/")
    assert result.resources == {"notes.md": expected}


def _code_variable_conflict(ws, directory=""):
    ws.write(os.path.join(directory, "code_variable_template.plain"), "{{ variable_name | code_variable }}")
    body = (
        '# implement-first\nUse {% include "code_variable_template.plain", variable_name: "first" %}.\n\n'
        '# implement-second\nUse {% include "code_variable_template.plain", variable_name: "second" %}.\n'
    )
    return IMPL + "***functional specs***\n\n" + body


def test_parse_spec__ancestor_resource_before_func_id_walk(ws):
    ws.write("binary.bin", b"\x89PNG\r\n\x1a\n\xff\xfe\x00\x80")
    ws.write("resource_before_frid_walk/base.plain", simple_module("See [binary](../binary.bin)."))
    text = "---\nrequires:\n  - base\n---\n" + _code_variable_conflict(ws, "resource_before_frid_walk")
    ws.write("resource_before_frid_walk/top.plain", text)
    result = ws.run("check", "resource_before_frid_walk/top.plain")
    assert result.stderr.startswith("Error: Referenced resource '../binary.bin' in module 'base' is a binary file.")


def test_parse_spec__code_variable_with_two_values(ws):
    ws.write("code_variable_conflict.plain", _code_variable_conflict(ws))
    message = "Code variable variable_name has multiple values: first and second"
    result = ws.run("check", "code_variable_conflict.plain")
    assert result.returncode == 1
    assert result.stderr == f"Error: {message}\n"
    assert doc(ws.run("parse", "code_variable_conflict.plain"))["message"] == message


# check-command


def test_check_command__valid_module(ws):
    ws.valid()
    result = ws.run("check", "valid.plain")
    assert (result.returncode, result.stdout, result.stderr) == (0, "valid.plain: OK\n", "")


def test_check_command__probe_module(ws):
    ws.write(
        "probe.plain",
        f"***implementation reqs***\n\n- {c('Implementation')} is written in Python 3.12.\n\n"
        f"***functional specs***\n\n# probe\n{c('Implementation')} starts.\n",
    )
    result = ws.run("check", "probe.plain")
    assert (result.returncode, result.stdout, result.stderr) == (0, "probe.plain: OK\n", "")


def test_check_command__minimal_test_plain_file(ws):
    ws.todo_project()
    ws.write(
        "project/tests/todo/list-tasks.plain",
        "---\nmodule: todo\nfunc_id: list-tasks\n---\n***conformance tests***\n***acceptance tests***\n",
    )
    assert ws.run("check", "todo.plain", cwd=ws.path("project")).stdout == "todo.plain: OK\n"


def _undefined(ws):
    ws.write("undefined_concept.plain", simple_module(f"A {c('User')} meets a {c('Visitor')}."))


def test_check_command__undefined_concepts(ws):
    _undefined(ws)
    result = ws.run("check", "undefined_concept.plain")
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.startswith("Error: Plain syntax error: Found 2 errors in the plain file:\n")
    assert c("User") in result.stderr and c("Visitor") in result.stderr
    assert "Traceback" not in result.stderr


MISSING_LINK = (
    "Error: Plain syntax error: Link does_not_exist.md does not exist. Linked resources are looked up relative to the "
    "following directories (highest to lowest precedence):\n"
)


def test_check_command__missing_linked_resource(ws):
    path = ws.write("specs/missing_resource.plain", simple_module("See [it](does_not_exist.md)."))
    os.makedirs(ws.path("elsewhere"))
    result = ws.run("check", path, cwd=ws.path("elsewhere"))
    assert result.stderr == MISSING_LINK + f"  1. {os.path.dirname(path)}\n"


def test_check_command__relative_template_dir_listed_absolute(ws):
    path = ws.write("specs/missing_resource.plain", simple_module("See [it](does_not_exist.md)."))
    os.makedirs(ws.path("elsewhere", "tpl"))
    result = ws.run("check", path, "--template-dir", "tpl", cwd=ws.path("elsewhere"))
    assert result.stderr == MISSING_LINK + f"  1. {os.path.dirname(path)}\n  2. {ws.path('elsewhere', 'tpl')}\n"


def _binary(ws):
    ws.write("binary.bin", b"\x89PNG\r\n\x1a\n\xff\xfe\x00\x80")
    ws.write("binary_resource.plain", simple_module("See [binary](binary.bin)."))
    ws.write("requires_binary_resource_base.plain", simple_module("See [binary](binary.bin)."))
    ws.write(
        "requires_binary_resource_top.plain",
        simple_module(front="---\nrequires:\n  - requires_binary_resource_base\n---\n"),
    )


def test_check_command__binary_resource(ws):
    _binary(ws)
    assert ws.run("check", "binary_resource.plain").stderr.startswith(
        "Error: Referenced resource 'binary.bin' in module 'binary_resource' is a binary file."
    )
    assert ws.run("check", "requires_binary_resource_top.plain").stderr.startswith(
        "Error: Referenced resource 'binary.bin' in module 'requires_binary_resource_base' is a binary file."
    )


def test_check_command__base64_resource(ws):
    ws.write("sample_base64_image.txt", "data:image/png;base64," + "iVBORw0KGgo" * 1000 + "==")
    ws.write("specs/base64_resource.plain", simple_module("See [image](../sample_base64_image.txt)."))
    result = ws.run("check", "specs/base64_resource.plain")
    assert result.stderr.startswith(
        "Error: Referenced resource '../sample_base64_image.txt' in module 'base64_resource' contains a large "
        "base64-encoded blob"
    )


def test_check_command__binary_scenario_resource(ws):
    ws.todo_project()
    ws.write("project/listing.bin", b"\x00\xff\xfe\x80")
    ws.write(
        "project/tests/todo/list-tasks.plain",
        "---\nmodule: todo\nfunc_id: list-tasks\n---\n\n***conformance tests***\n\n"
        "# lists\nThe output matches [the listing](listing.bin).\n\n***acceptance tests***\n",
    )
    result = ws.run("check", "todo.plain", cwd=ws.path("project"))
    assert result.stderr.startswith("Error: Referenced resource 'listing.bin' in module 'todo' is a binary file.")


def test_check_command__missing_module(ws):
    result = ws.run("check", "does_not_exist.plain")
    assert (result.returncode, result.stderr) == (1, "Error: Module does not exist (does_not_exist).\n")


def test_check_command__wrong_extension(ws):
    ws.write("not_plain.md", "# hello\n")
    result = ws.run("check", "not_plain.md")
    assert result.returncode == 1
    assert result.stderr == "Error: Plain syntax error: Invalid plain file extension: .md. Expected: .plain.\n"


MISSING_LIST_TASKS = (
    "Functionality todo:list-tasks has no test plain file. Add one, by convention tests/todo/list-tasks.plain, with "
    "the add-test-scenarios skill."
)


def test_check_command__missing_test_plain_file(ws):
    ws.todo_project()
    ws.remove("project/tests/todo/list-tasks.plain")
    result = ws.run("check", "todo.plain", cwd=ws.path("project"))
    assert (result.returncode, result.stdout, result.stderr) == (1, "", f"Error: {MISSING_LIST_TASKS}\n")


def test_check_command__test_plain_file_error(ws):
    ws.todo_project()
    ws.write(
        "project/tests/todo/list-tasks.plain",
        "---\nmodule: todo\nfunc_id: list-tasks\n---\n\n***conformance tests***\n\n"
        f"# lists\nEvery {c('Note')} is listed.\n\n***acceptance tests***\n",
    )
    result = ws.run("check", "todo.plain", cwd=ws.path("project"))
    assert result.stderr == (
        "Error: Plain syntax error: Found 1 errors in test plain file 'tests/todo/list-tasks.plain':\n"
        f"Syntax error at line 8 in test plain file 'tests/todo/list-tasks.plain': Concept {c('Note')} used in "
        "scenario `lists` is not defined in module 'todo'.\n"
    )


def _interrupt(*args, **kwargs):
    raise KeyboardInterrupt


def test_check_command__interrupted(ws, monkeypatch, capsys):
    ws.valid()
    monkeypatch.chdir(ws.root)
    for target in ("check", "resolve_config_file"):
        with monkeypatch.context() as patch:
            patch.setattr(cli, target, _interrupt)
            assert cli.main(["check", "valid.plain"]) == 130
        captured = capsys.readouterr()
        assert captured.out == "" and "Traceback" not in captured.err


# parse-command


def test_parse_command__valid_module(ws):
    ws.valid()
    result = ws.run("parse", "valid.plain")
    assert result.returncode == 0 and result.stderr == ""
    document = doc(result)
    assert document["format_version"] == 2
    assert document["modules"] == [{"module": "valid", "tree": chain_of("valid.plain", [ws.root])[-1][1]}]
    assert document["resources"] == {} and document["test_plain_files"] == {}


def _chain(ws, name, requires=()):
    front = ("---\nrequires:\n" + "".join(f"  - {r}\n" for r in requires) + "---\n") if requires else ""
    ws.write(f"{name}.plain", simple_module(f"{name} works.", front=front))


def test_parse_command__chain_deepest_first(ws):
    _chain(ws, "chain_base")
    _chain(ws, "chain_middle", ["chain_base"])
    _chain(ws, "chain_top", ["chain_middle"])
    _chain(ws, "chain_fork_top", ["chain_base", "chain_middle"])
    for top, names in [
        ("chain_top", ["chain_base", "chain_middle", "chain_top"]),
        ("chain_fork_top", ["chain_base", "chain_middle", "chain_fork_top"]),
    ]:
        document = doc(ws.run("parse", f"{top}.plain"))
        assert [(m["module"], m["tree"]) for m in document["modules"]] == [
            (n, t) for n, t in chain_of(f"{top}.plain", [ws.root])
        ]
        assert [m["module"] for m in document["modules"]] == names


def test_parse_command__test_plain_files_and_scenarios(ws):
    ws.todo_project()
    document = doc(ws.run("parse", "todo.plain", cwd=ws.path("project")))
    assert document["test_plain_files"] == {
        "tests/todo/add-task.plain": {"module": "todo", "func_id": "add-task"},
        "tests/todo/list-tasks.plain": {"module": "todo", "func_id": "list-tasks"},
    }
    add_task, list_tasks = document["modules"][-1]["tree"]["functional specs"]
    assert [s["id"] for s in add_task["conformance_tests"]] == ["add-first-task", "add-without-name"]
    assert [s["id"] for s in add_task["acceptance_tests"]] == ["add-then-list"]
    assert list_tasks["conformance_tests"][0]["text"] == LIST_TWO_TEXT


def test_parse_command__template_dir_from_config(ws):
    ws.top_project(config="template-dir: template\n")
    result = ws.run("parse", "project/top.plain")
    assert result.stderr == ""
    assert [m["module"] for m in doc(result)["modules"]] == ["helper", "top"]


def test_parse_command__binary_resource_is_not_read(ws):
    _binary(ws)
    for name in ("binary_resource.plain", "requires_binary_resource_top.plain"):
        result = ws.run("parse", name)
        assert result.returncode == 0
        assert doc(result)["resources"] == {"binary.bin": "binary.bin"}
        error = ws.run("check", name).stderr
        assert "'binary.bin'" in error and "is a binary file" in error


def test_parse_command__stdout_without_byte_buffer(ws, monkeypatch):
    ws.valid()
    monkeypatch.chdir(ws.root)
    buffer = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buffer)
    assert cli.main(["parse", "valid.plain"]) == 0
    assert json.loads(buffer.getvalue())["modules"][0]["module"] == "valid"


def test_parse_command__invalid_module(ws):
    _undefined(ws)
    result = ws.run("parse", "undefined_concept.plain")
    assert result.returncode == 1 and result.stderr == ""
    document = doc(result)
    assert sorted(document) == ["format_version", "message", "type"]
    assert document["format_version"] == 2 and document["type"] == "PlainSyntaxError"
    assert ws.run("check", "undefined_concept.plain").stderr == f"Error: {document['message']}\n"


def test_parse_command__diverging_requires(ws):
    _chain(ws, "diamond_requires_base")
    _chain(ws, "diamond_requires_left", ["diamond_requires_base"])
    _chain(ws, "diamond_requires_right", ["diamond_requires_base"])
    _chain(ws, "diamond_requires_main", ["diamond_requires_left", "diamond_requires_right"])
    result = ws.run("parse", "diamond_requires_main.plain")
    assert result.returncode == 1 and doc(result)["type"] == "PlainSyntaxError"


def test_parse_command__missing_test_plain_file(ws):
    ws.todo_project()
    ws.remove("project/tests/todo/list-tasks.plain")
    result = ws.run("parse", "todo.plain", cwd=ws.path("project"))
    document = doc(result)
    assert result.returncode == 1
    assert document["type"] == "MissingTestPlainFileError" and "add-test-scenarios" in document["message"]


def test_parse_command__missing_or_non_plain_entry(ws):
    ws.write("not_plain.md", "# hello\n")
    for name in ("does_not_exist.plain", "not_plain.md"):
        result = ws.run("parse", name)
        assert result.returncode == 1 and result.stderr == ""
        assert sorted(doc(result)) == ["format_version", "message", "type"]


def test_parse_command__interrupted(ws, monkeypatch, capsys):
    ws.valid()
    monkeypatch.chdir(ws.root)
    for target in ("parse_spec", "resolve_config_file"):
        with monkeypatch.context() as patch:
            patch.setattr(cli, target, _interrupt)
            assert cli.main(["parse", "valid.plain"]) == 130
        assert capsys.readouterr().out == ""


# write-parse-output


def test_write_parse_output__utf8_whatever_the_encoding(ws):
    ws.write("greet.plain", simple_module("Greets. It greets “Zoë” with ✓."))
    result = subprocess.run(
        ["plain-parser", "parse", "greet.plain"],
        cwd=ws.root,
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "ascii"},
    )
    assert result.returncode == 0 and result.stderr == b""
    assert "“Zoë” with ✓" in json.dumps(json.loads(result.stdout.decode("utf-8")), ensure_ascii=False)


def test_write_parse_output__closed_pipe(ws):
    ws.valid()
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        result = subprocess.run(
            ["plain-parser", "parse", "valid.plain"], cwd=ws.root, stdout=write_end, stderr=subprocess.PIPE
        )
    finally:
        os.close(write_end)
    assert result.returncode == 0
    assert result.stderr == b""


def _non_utf8_dir(ws):
    """Create a directory whose name holds the byte 0xff, when the file system allows it."""
    path = os.path.join(os.fsencode(ws.root), b"bad\xffname")
    try:
        os.mkdir(path)
    except OSError:
        return None
    return path


def test_write_parse_output__non_utf8_directory_stays_out(ws):
    path = _non_utf8_dir(ws)
    if path is None:  # the file system rejects such names (e.g. APFS): use a non-ASCII directory name instead
        path = os.fsencode(ws.path("badÿname"))
        os.mkdir(path)
    with open(os.path.join(path, b"notes.md"), "w", encoding="utf-8") as file:
        file.write("notes")
    with open(os.path.join(path, b"m.plain"), "w", encoding="utf-8") as file:
        file.write(simple_module("See [notes](notes.md)."))
    result = subprocess.run(
        [b"plain-parser", b"parse", os.path.join(os.path.basename(path), b"m.plain")], cwd=ws.root, capture_output=True
    )
    assert result.returncode == 0
    assert json.loads(result.stdout.decode("utf-8"))["resources"] == {"notes.md": "notes.md"}


def test_write_parse_output__non_utf8_module_name(ws, monkeypatch, capsys):
    expected = 'The parse result holds text that is not valid UTF-8: "module": "bad\\udcffname"'
    try:
        with open(os.path.join(os.fsencode(ws.root), b"bad\xffname.plain"), "w", encoding="utf-8") as file:
            file.write(VALID)
    except OSError:  # the file system rejects such names: give the parse result the same decoded name
        tree = chain_of("valid.plain", [ws.write("valid.plain", VALID) and ws.root])[-1][1]
        monkeypatch.chdir(ws.root)
        monkeypatch.setattr(cli, "parse_spec", lambda *a, **k: cli.ParseResult([("bad\udcffname", tree)], {}, {}))
        assert cli.main(["parse", "valid.plain"]) == 1
        captured = capsys.readouterr()
        assert captured.err == ""
        assert json.loads(captured.out)["message"] == expected
        return
    result = subprocess.run([b"plain-parser", b"parse", b"bad\xffname.plain"], cwd=ws.root, capture_output=True)
    assert result.returncode == 1 and result.stderr == b""
    assert json.loads(result.stdout.decode("utf-8"))["message"] == expected


def test_write_parse_output__non_utf8_path_in_error(ws, monkeypatch, capsys):
    path = _non_utf8_dir(ws)
    if path is None:  # the file system rejects such names: raise the error a missing link in it gives
        monkeypatch.chdir(ws.root)
        ws.valid()
        message = f"Plain syntax error: Link missing.md does not exist. ...\n  1. {ws.root}/bad\udcffname"

        def fail(*args, **kwargs):
            raise PlainSyntaxError(message)

        monkeypatch.setattr(cli, "parse_spec", fail)
        assert cli.main(["parse", "valid.plain"]) == 1
        document = json.loads(capsys.readouterr().out)
        assert document["type"] == "PlainSyntaxError" and "bad\udcffname" in document["message"]
        return
    with open(os.path.join(path, b"m.plain"), "w", encoding="utf-8") as file:
        file.write(simple_module("See [missing](missing.md)."))
    result = subprocess.run([b"plain-parser", b"parse", b"bad\xffname/m.plain"], cwd=ws.root, capture_output=True)
    document = json.loads(result.stdout.decode("utf-8"))
    assert document["type"] == "PlainSyntaxError" and "bad\udcffname" in document["message"]


def test_write_parse_output__result_not_json(ws, monkeypatch, capsys):
    ws.valid()
    monkeypatch.chdir(ws.root)
    monkeypatch.setattr(cli, "parse_spec", lambda *a, **k: cli.ParseResult([("valid", {"x": object()})], {}, {}))
    assert cli.main(["parse", "valid.plain"]) == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["type"] == "TypeError"
