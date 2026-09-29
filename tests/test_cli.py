import os
import shutil
import subprocess
import sys

import pytest

from plain_parser import cli


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
