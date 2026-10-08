import contextlib
import io
import json
import os
import shutil
import subprocess
import sys

import pytest

from plain_parser import cli, plain_file
from plain_parser.exceptions import PlainSyntaxError, UnsupportedResourceType


@pytest.fixture
def cli_specs_dir(get_test_data_path):
    return get_test_data_path("data/cli")


def test_check_valid_module_exits_zero(cli_specs_dir, capsys):
    exit_code = cli.main(["check", os.path.join(cli_specs_dir, "valid.plain")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""


def test_check_without_file_argument_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["check"])

    assert exc_info.value.code == 2
    assert "usage:" in capsys.readouterr().err


def test_without_subcommand_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2


def test_console_script_is_installed_and_exits_zero(cli_specs_dir):
    # The venv's script dir may not be on PATH when pytest is run through an absolute interpreter path.
    search_path = os.pathsep.join([os.path.dirname(sys.executable), os.environ.get("PATH", "")])
    script = shutil.which("plain-parser", path=search_path)
    if script is None:
        message = "plain-parser console script not installed; run: uv pip install -e '.[dev]'"
        # CI installs the package, so a missing script there means [project.scripts] is broken.
        pytest.fail(message) if os.environ.get("CI") else pytest.skip(message)

    result = subprocess.run(
        [script, "check", os.path.join(cli_specs_dir, "valid.plain")], capture_output=True, text=True
    )

    assert result.returncode == 0
    assert result.stdout.endswith(": OK\n")
    assert result.stderr == ""


def _run_check(capsys, *argv):
    exit_code = cli.main(["check", *argv])
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def _assert_ok(result):
    exit_code, out, err = result
    assert (exit_code, err) == (0, "")
    assert out.endswith(": OK\n"), out


def test_check_valid_module_in_subdirectory_from_parent(cli_specs_dir, capsys, monkeypatch):
    monkeypatch.chdir(cli_specs_dir)

    exit_code, out, err = _run_check(capsys, os.path.join("subdir", "nested.plain"))

    _assert_ok((exit_code, out, err))


def test_check_valid_module_with_linked_resource_in_acceptance_test(cli_specs_dir, capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    exit_code, out, err = _run_check(capsys, os.path.join(cli_specs_dir, "acceptance_test_resource.plain"))

    _assert_ok((exit_code, out, err))


def test_check_nonexistent_template_dir_is_ignored(cli_specs_dir, capsys):
    exit_code, out, err = _run_check(
        capsys, os.path.join(cli_specs_dir, "valid.plain"), "--template-dir", os.path.join(cli_specs_dir, "nope")
    )

    _assert_ok((exit_code, out, err))


def test_check_undefined_concept(cli_specs_dir, capsys):
    exit_code, out, err = _run_check(capsys, os.path.join(cli_specs_dir, "undefined_concept.plain"))

    assert exit_code == 1
    assert out == ""
    assert err.startswith("Error: Plain syntax error: Found 2 errors in the plain file:\n")
    assert ":User:" in err
    assert ":Visitor:" in err
    assert "Traceback" not in err


def test_check_missing_linked_resource(cli_specs_dir, capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    exit_code, out, err = _run_check(capsys, os.path.join(cli_specs_dir, "missing_resource.plain"))

    assert exit_code == 1
    assert out == ""
    assert err == (
        "Error: Plain syntax error: Link does_not_exist.md does not exist. "
        "Linked resources are looked up relative to the following directories (highest to lowest precedence):\n"
        f"  1. {cli_specs_dir}\n"
    )


def test_check_binary_linked_resource(cli_specs_dir, capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    exit_code, out, err = _run_check(capsys, os.path.join(cli_specs_dir, "binary_resource.plain"))

    assert exit_code == 1
    assert out == ""
    assert err.startswith("Error: Referenced resource 'binary.bin' in module 'binary_resource' is a binary file.")


def test_check_base64_blob_linked_resource(cli_specs_dir, capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    exit_code, out, err = _run_check(capsys, os.path.join(cli_specs_dir, "base64_resource.plain"))

    assert exit_code == 1
    assert out == ""
    assert err.startswith(
        "Error: Referenced resource '../sample_base64_image.txt' in module 'base64_resource' "
        "contains a large base64-encoded blob"
    )


def test_check_invalid_linked_resource_in_required_module(cli_specs_dir, capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    exit_code, out, err = _run_check(capsys, os.path.join(cli_specs_dir, "requires_binary_resource_top.plain"))

    assert exit_code == 1
    assert out == ""
    assert err.startswith(
        "Error: Referenced resource 'binary.bin' in module 'requires_binary_resource_base' is a binary file."
    )


def test_check_code_variable_with_two_values(cli_specs_dir, capsys):
    exit_code, out, err = _run_check(capsys, os.path.join(cli_specs_dir, "code_variable_conflict.plain"))

    assert exit_code == 1
    assert out == ""
    assert err == "Error: Code variable variable_name has multiple values: first and second\n"


def test_check_missing_plain_file(cli_specs_dir, capsys):
    exit_code, out, err = _run_check(capsys, os.path.join(cli_specs_dir, "does_not_exist.plain"))

    assert exit_code == 1
    assert out == ""
    assert err == "Error: Module does not exist (does_not_exist).\n"


def test_check_wrong_extension(cli_specs_dir, capsys):
    exit_code, out, err = _run_check(capsys, os.path.join(cli_specs_dir, "not_plain.md"))

    assert exit_code == 1
    assert out == ""
    assert err == "Error: Plain syntax error: Invalid plain file extension: .md. Expected: .plain.\n"


def test_check_empty_template_dir_is_ignored(tmp_path, capsys, monkeypatch):
    # An empty --template-dir must not add the working directory to the search path (codeplain ignores it).
    (tmp_path / "helper.plain").write_text(
        "***implementation reqs***\n\n- A req.\n\n***functional specs***\n\n- A functionality.\n"
    )
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    (spec_dir / "top.plain").write_text(
        "---\nrequires:\n  - helper\n---\n\n***implementation reqs***\n\n- A req.\n\n***functional specs***\n\n- A functionality.\n"
    )
    monkeypatch.chdir(tmp_path)

    exit_code, out, err = _run_check(capsys, os.path.join("spec", "top.plain"), "--template-dir", "")

    assert exit_code == 1
    assert out == ""
    assert err == "Error: Module does not exist (helper).\n"


def test_check_binary_linked_resource_in_acceptance_test(cli_specs_dir, capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    exit_code, out, err = _run_check(capsys, os.path.join(cli_specs_dir, "acceptance_test_binary_resource.plain"))

    assert exit_code == 1
    assert out == ""
    assert err.startswith(
        "Error: Referenced resource 'binary.bin' in module 'acceptance_test_binary_resource' is a binary file."
    )


@pytest.mark.parametrize("interrupted_function", ["check", "resolve_config_file"])
def test_check_interrupted_exits_130_without_traceback(cli_specs_dir, capsys, monkeypatch, interrupted_function):
    def interrupt(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, interrupted_function, interrupt)

    exit_code = cli.main(["check", os.path.join(cli_specs_dir, "valid.plain")])

    captured = capsys.readouterr()
    assert exit_code == 130
    assert captured.out == ""
    assert "Traceback" not in captured.err


_MODULE = "***implementation reqs***\n\n- A req.\n\n***functional specs***\n\n- A functionality.\n"
_TOP = "---\nrequires:\n  - helper\n---\n\n" + _MODULE


def _project(tmp_path, config_name=None, config_text=None, template_subdir="template"):
    """A spec requiring ``helper``, which lives only in ``<spec dir>/<template_subdir>/``."""
    spec_dir = tmp_path / "project"
    (spec_dir / template_subdir).mkdir(parents=True)
    (spec_dir / "top.plain").write_text(_TOP)
    (spec_dir / template_subdir / "helper.plain").write_text(_MODULE)
    if config_name is not None:
        (spec_dir / config_name).write_text(config_text)
    return spec_dir


def test_check_reads_template_dir_from_config_next_to_spec(tmp_path, capsys, monkeypatch):
    spec_dir = _project(tmp_path, "config.yaml", "template-dir: template\n")
    monkeypatch.chdir(tmp_path)  # not the spec dir: the relative value must resolve against the config file

    _assert_ok(_run_check(capsys, str(spec_dir / "top.plain")))


def test_check_accepts_template_dir_key_with_underscore(tmp_path, capsys):
    spec_dir = _project(tmp_path, "config.yaml", "template_dir: template\n")

    _assert_ok(_run_check(capsys, str(spec_dir / "top.plain")))


def test_check_ignores_other_config_keys(tmp_path, capsys):
    spec_dir = _project(
        tmp_path,
        "config.yaml",
        "unittests-script: scripts/x.sh\nbuild-dest: dist\ntemplate-dir: template\nverbose: true\n",
    )

    _assert_ok(_run_check(capsys, str(spec_dir / "top.plain")))


def test_check_without_config_does_not_search_template_dir(tmp_path, capsys):
    spec_dir = _project(tmp_path)

    exit_code, out, err = _run_check(capsys, str(spec_dir / "top.plain"))

    assert (exit_code, out, err) == (1, "", "Error: Module does not exist (helper).\n")


def test_check_config_name_selects_config_file(tmp_path, capsys):
    spec_dir = _project(tmp_path, "web.config.yaml", "template-dir: template\n")

    _assert_ok(_run_check(capsys, str(spec_dir / "top.plain"), "--config-name", "web.config.yaml"))
    assert _run_check(capsys, str(spec_dir / "top.plain"))[0] == 1


def test_check_explicit_template_dir_overrides_config(tmp_path, capsys):
    spec_dir = _project(tmp_path, "config.yaml", "template-dir: does_not_exist\n")

    _assert_ok(_run_check(capsys, str(spec_dir / "top.plain"), "--template-dir", str(spec_dir / "template")))


def test_check_reads_config_from_working_directory(tmp_path, capsys, monkeypatch):
    spec_dir = _project(tmp_path)
    (tmp_path / "config.yaml").write_text("template-dir: project/template\n")
    monkeypatch.chdir(tmp_path)

    _assert_ok(_run_check(capsys, os.path.join("project", "top.plain")))


def test_check_config_in_both_locations_is_usage_error(tmp_path, capsys, monkeypatch):
    spec_dir = _project(tmp_path, "config.yaml", "template-dir: template\n")
    (tmp_path / "config.yaml").write_text("template-dir: project/template\n")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["check", str(spec_dir / "top.plain")])

    assert exc_info.value.code == 2
    assert "found in two locations" in capsys.readouterr().err


def test_check_config_in_both_locations_is_usage_error_even_with_explicit_template_dir(tmp_path, capsys, monkeypatch):
    spec_dir = _project(tmp_path, "config.yaml", "template-dir: template\n")
    (tmp_path / "config.yaml").write_text("template-dir: project/template\n")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["check", str(spec_dir / "top.plain"), "--template-dir", str(spec_dir / "template")])

    assert exc_info.value.code == 2
    assert "found in two locations" in capsys.readouterr().err


def test_check_unreadable_config_is_usage_error(tmp_path, capsys):
    spec_dir = _project(tmp_path, "config.yaml", "template-dir: [unclosed\n")

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["check", str(spec_dir / "top.plain")])

    assert exc_info.value.code == 2
    assert "Error reading config file" in capsys.readouterr().err


def test_check_valid_module_prints_ok_line_with_file_as_given(cli_specs_dir, capsys, monkeypatch):
    monkeypatch.chdir(cli_specs_dir)

    exit_code, out, err = _run_check(capsys, "valid.plain")

    assert (exit_code, out, err) == (0, "valid.plain: OK\n", "")


def test_check_reports_ancestor_resource_before_frid_walk_error(cli_specs_dir, capsys):
    # base.plain links a binary file; top.plain also has a code-variable conflict only the FRID walk finds.
    spec = os.path.join(cli_specs_dir, "resource_before_frid_walk", "top.plain")

    exit_code, out, err = _run_check(capsys, spec)

    assert (exit_code, out) == (1, "")
    assert err.startswith("Error: Referenced resource '../binary.bin' in module 'base' is a binary file.")


@pytest.fixture
def requires_specs_dir(get_test_data_path):
    return get_test_data_path("data/requires")


@pytest.mark.parametrize(
    "entry, expected_chain",
    [
        ("chain_top.plain", ["chain_base", "chain_middle", "chain_top"]),
        # chain_fork_top requires chain_base and chain_middle, which itself requires chain_base.
        ("chain_fork_top.plain", ["chain_base", "chain_middle", "chain_fork_top"]),
    ],
)
def test_parse_spec_modules_are_deepest_ancestor_first(requires_specs_dir, entry, expected_chain):
    result = cli.parse_spec(os.path.join(requires_specs_dir, entry), None, load_resources=False)

    assert [module_name for module_name, _ in result.modules] == expected_chain


def test_parse_spec_modules_carry_every_tree_in_the_chain(requires_specs_dir):
    result = cli.parse_spec(os.path.join(requires_specs_dir, "chain_top.plain"), None, load_resources=False)

    assert result.modules == plain_file.parse_module_chain("chain_top.plain", [requires_specs_dir])


def test_parse_spec_raises_on_diverging_requires(requires_specs_dir):
    with pytest.raises(PlainSyntaxError, match="There must be a fixed order how required modules are dependent"):
        cli.parse_spec(os.path.join(requires_specs_dir, "diamond_requires_main.plain"), None, load_resources=False)


def test_parse_spec_loads_resources_only_when_asked(cli_specs_dir):
    spec = os.path.join(cli_specs_dir, "binary_resource.plain")

    with pytest.raises(UnsupportedResourceType):
        cli.parse_spec(spec, None, load_resources=True)

    result = cli.parse_spec(spec, None, load_resources=False)
    assert result.resources == {"binary.bin": os.path.join(os.path.abspath(cli_specs_dir), "binary.bin")}


def _run_parse(capsys, *argv):
    exit_code = cli.main(["parse", *argv])
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def _parse_output(out):
    # The whole of stdout must be one JSON document followed by one newline.
    assert out.endswith("\n") and not out.endswith("\n\n"), repr(out[-20:])
    return json.loads(out)


def _module_names(result: dict) -> list[str]:
    return [module["module"] for module in result["modules"]]


def test_parse_valid_module_prints_success_json(cli_specs_dir, capsys):
    exit_code, out, err = _run_parse(capsys, os.path.join(cli_specs_dir, "valid.plain"))

    assert (exit_code, err) == (0, "")
    result = _parse_output(out)
    assert set(result) == {"format_version", "modules", "resources"}
    assert result["format_version"] == 1
    assert result["resources"] == {}
    _, tree = plain_file.parse_module_chain("valid.plain", [cli_specs_dir])[-1]
    assert result["modules"] == [{"module": "valid", "tree": json.loads(json.dumps(tree))}]


def test_parse_invalid_module_prints_error_json(cli_specs_dir, capsys):
    spec = os.path.join(cli_specs_dir, "undefined_concept.plain")

    exit_code, out, err = _run_parse(capsys, spec)

    assert (exit_code, err) == (1, "")
    result = _parse_output(out)
    assert set(result) == {"format_version", "type", "message"}
    assert result["format_version"] == 1
    assert result["type"] == "PlainSyntaxError"
    _, _, check_err = _run_check(capsys, spec)
    assert check_err == f"Error: {result['message']}\n"


@pytest.mark.parametrize(
    "entry, expected_chain",
    [
        ("chain_top.plain", ["chain_base", "chain_middle", "chain_top"]),
        ("chain_fork_top.plain", ["chain_base", "chain_middle", "chain_fork_top"]),
    ],
)
def test_parse_prints_every_module_of_the_chain_deepest_ancestor_first(
    requires_specs_dir, capsys, entry, expected_chain
):
    exit_code, out, _ = _run_parse(capsys, os.path.join(requires_specs_dir, entry))

    assert exit_code == 0
    chain = plain_file.parse_module_chain(entry, [requires_specs_dir])
    expected_modules = [{"module": name, "tree": json.loads(json.dumps(tree))} for name, tree in chain]
    assert [module["module"] for module in expected_modules] == expected_chain
    assert _parse_output(out)["modules"] == expected_modules


def test_parse_diverging_requires_is_parser_error(requires_specs_dir, capsys):
    exit_code, out, _ = _run_parse(capsys, os.path.join(requires_specs_dir, "diamond_requires_main.plain"))

    assert exit_code == 1
    assert _parse_output(out)["type"] == "PlainSyntaxError"


def _write_module(path, body="", requires=None):
    front = "---\nrequires:\n" + "".join(f"  - {name}\n" for name in requires) + "---\n\n" if requires else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        front + "***implementation reqs***\n\n- A req.\n\n***functional specs***\n\n- A functionality." + body
    )


def test_parse_resolves_link_from_template_dir(cli_specs_dir, capsys):
    # template_link/spec/top.plain links notes.md, which exists only in template_link/tpl.
    template_dir = os.path.join(cli_specs_dir, "template_link", "tpl")

    exit_code, out, _ = _run_parse(
        capsys, os.path.join(cli_specs_dir, "template_link", "spec", "top.plain"), "--template-dir", template_dir
    )

    assert exit_code == 0
    assert _parse_output(out)["resources"] == {"notes.md": os.path.join(os.path.abspath(template_dir), "notes.md")}


@pytest.mark.parametrize("entry", ["binary_resource.plain", "requires_binary_resource_top.plain"])
def test_parse_accepts_binary_resource_that_check_rejects(cli_specs_dir, capsys, entry):
    spec = os.path.join(cli_specs_dir, entry)

    exit_code, out, _ = _run_parse(capsys, spec)
    assert exit_code == 0
    assert _parse_output(out)["resources"] == {"binary.bin": os.path.join(os.path.abspath(cli_specs_dir), "binary.bin")}

    check_exit_code, _, check_err = _run_check(capsys, spec)
    assert check_exit_code == 1
    assert "'binary.bin'" in check_err and "is a binary file" in check_err


def test_parse_lists_a_target_linked_from_two_modules_once(cli_specs_dir, capsys):
    # shared_link_top.plain and the shared_link_helper.plain it requires both link notes.md.
    exit_code, out, _ = _run_parse(capsys, os.path.join(cli_specs_dir, "shared_link_top.plain"))

    assert exit_code == 0
    result = _parse_output(out)
    assert _module_names(result) == ["shared_link_helper", "shared_link_top"]
    assert result["resources"] == {"notes.md": os.path.join(os.path.abspath(cli_specs_dir), "notes.md")}


def test_parse_without_file_argument_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["parse"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert captured.out == ""
    assert "usage:" in captured.err


def test_parse_config_in_both_locations_is_usage_error(tmp_path, capsys, monkeypatch):
    spec_dir = _project(tmp_path, "config.yaml", "template-dir: template\n")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("template-dir: template\n")

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["parse", str(spec_dir / "top.plain")])

    assert exc_info.value.code == 2
    assert capsys.readouterr().out == ""


def test_parse_writes_utf8_json_whatever_the_stdout_encoding(tmp_path):
    _write_module(tmp_path / "unicode.plain", " It greets “Zoë” with ✓.\n")

    result = subprocess.run(
        [sys.executable, "-c", "import sys; from plain_parser import cli; sys.exit(cli.main(sys.argv[1:]))"]
        + ["parse", str(tmp_path / "unicode.plain")],
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "ascii"},
    )

    assert (result.returncode, result.stderr) == (0, b"")
    assert "“Zoë” with ✓" in json.dumps(json.loads(result.stdout.decode("utf-8")), ensure_ascii=False)


def test_parse_resource_path_is_the_absolute_template_dir_joined_with_the_target(cli_specs_dir, capsys, monkeypatch):
    # The template dir made absolute against the working directory, the target joined as written.
    # parent_link/a/spec/top.plain links ../shared/notes.md, which exists only next to the empty parent_link/b/tpl.
    parent_link = os.path.join(cli_specs_dir, "parent_link")
    monkeypatch.chdir(parent_link)

    exit_code, out, _ = _run_parse(capsys, os.path.join("a", "spec", "top.plain"), "--template-dir", "b/tpl")

    assert exit_code == 0
    template_dir = os.path.join(os.path.realpath(parent_link), "b", "tpl")  # getcwd() is the real path
    assert _parse_output(out)["resources"] == {"../shared/notes.md": os.path.join(template_dir, "../shared/notes.md")}


def test_parse_resource_path_keeps_a_symlink_unresolved(tmp_path, capsys):
    # The OS follows `lnk` before applying `..`, so removing `..` as text would name x.md in the spec dir.
    _write_module(tmp_path / "top.plain", " See [x](lnk/../x.md).\n")
    (tmp_path / "sub" / "real").mkdir(parents=True)
    (tmp_path / "sub" / "x.md").write_text("read through the symlink\n")
    (tmp_path / "x.md").write_text("next to the spec\n")
    try:
        os.symlink(os.path.join("sub", "real"), tmp_path / "lnk")
    except OSError:
        pytest.skip("symlinks are not available")

    exit_code, out, _ = _run_parse(capsys, str(tmp_path / "top.plain"))

    assert exit_code == 0
    path = _parse_output(out)["resources"]["lnk/../x.md"]
    assert path == os.path.join(str(tmp_path), "lnk/../x.md")
    with open(path) as f:
        assert f.read() == "read through the symlink\n"


def test_parse_with_template_dir_from_config_prints_only_json(tmp_path, capsys):
    spec_dir = _project(tmp_path, "config.yaml", "template-dir: template\n")

    exit_code, out, err = _run_parse(capsys, str(spec_dir / "top.plain"))

    assert (exit_code, err) == (0, "")
    assert _module_names(_parse_output(out)) == ["helper", "top"]


@pytest.mark.parametrize("interrupted_function", ["parse_spec", "resolve_config_file"])
def test_parse_interrupted_exits_130_with_empty_stdout(cli_specs_dir, capsys, monkeypatch, interrupted_function):
    def interrupt(*_, **__):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, interrupted_function, interrupt)

    exit_code = cli.main(["parse", os.path.join(cli_specs_dir, "valid.plain")])

    captured = capsys.readouterr()
    assert exit_code == 130
    assert captured.out == ""
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("entry", ["does_not_exist.plain", "not_plain.md"])
def test_parse_missing_or_non_plain_entry_is_parser_error(cli_specs_dir, capsys, entry):
    exit_code, out, err = _run_parse(capsys, os.path.join(cli_specs_dir, entry))

    assert (exit_code, err) == (1, "")
    assert set(_parse_output(out)) == {"format_version", "type", "message"}


def test_parse_path_that_is_not_utf8_is_reported_as_json_error(tmp_path, capsys):
    spec_dir = os.path.join(os.fsencode(tmp_path), b"bad\xffname")
    try:
        os.mkdir(spec_dir)
    except OSError:
        pytest.skip("the file system rejects names that are not UTF-8")
    spec_dir_str = os.fsdecode(spec_dir)
    _write_module(tmp_path / spec_dir_str / "top.plain", " See [the notes](notes.md).\n")
    (tmp_path / spec_dir_str / "notes.md").write_text("notes\n")

    exit_code, out, err = _run_parse(capsys, os.path.join(spec_dir_str, "top.plain"))

    assert (exit_code, err) == (1, "")
    result = _parse_output(out)
    assert result["type"] == "UnicodeEncodeError"
    assert result["message"].startswith("A path in the parse result is not valid UTF-8: ")
    assert "bad\\udcffname" in result["message"]


def test_parse_error_naming_a_path_that_is_not_utf8_keeps_its_type(tmp_path, capsys):
    spec_dir = os.path.join(os.fsencode(tmp_path), b"bad\xffname")
    try:
        os.mkdir(spec_dir)
    except OSError:
        pytest.skip("the file system rejects names that are not UTF-8")
    spec_dir_str = os.fsdecode(spec_dir)
    _write_module(tmp_path / spec_dir_str / "top.plain", " See [the notes](missing.md).\n")

    exit_code, out, err = _run_parse(capsys, os.path.join(spec_dir_str, "top.plain"))

    assert (exit_code, err) == (1, "")
    result = _parse_output(out)
    assert result["type"] == "PlainSyntaxError"
    assert "bad\\udcffname" in result["message"]


def test_parse_result_that_is_not_json_is_reported_as_json_error(cli_specs_dir, capsys, monkeypatch):
    monkeypatch.setattr(cli, "parse_spec", lambda *_, **__: cli.ParseResult([("valid", {"x": object()})], {}))

    exit_code, out, err = _run_parse(capsys, os.path.join(cli_specs_dir, "valid.plain"))

    assert (exit_code, err) == (1, "")
    assert _parse_output(out)["type"] == "TypeError"


def test_parse_writes_to_a_stdout_without_byte_buffer(cli_specs_dir):
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        exit_code = cli.main(["parse", os.path.join(cli_specs_dir, "valid.plain")])

    assert exit_code == 0
    assert _module_names(_parse_output(stdout.getvalue())) == ["valid"]
