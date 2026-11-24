import json

import pytest

from plain_parser import cli


def test_read_config_dashed_key_first(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("template-dir: a\ntemplate_dir: b\ntests-folder: ''\ntests_folder: t\n")
    result = cli.read_config(str(config))
    assert result.template_dir == str(tmp_path / "a")
    assert result.tests_folders == [str(tmp_path / "t")]
    assert result.conformance_tests_enabled is False


def test_read_config_empty_file(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("")
    assert cli.read_config(str(config)) == cli.Config()


def test_resolve_config_same_directory(tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text("x: 1\n")
    monkeypatch.chdir(tmp_path)
    assert cli.resolve_config_file("config.yaml", "m.plain") == str(tmp_path / "config.yaml")


def test_parser_requires_subcommand():
    with pytest.raises(SystemExit) as error:
        cli.build_parser().parse_args([])
    assert error.value.code == 2


def test_parse_error_document(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["parse", "missing.plain"]) == 1
    document = json.loads(capsys.readouterr().out)
    assert document == {
        "format_version": 2,
        "type": "ModuleDoesNotExistError",
        "message": "Module does not exist (missing).",
    }


def test_simple_module_check(get_test_data_path, monkeypatch, capsys):
    monkeypatch.chdir(get_test_data_path("data"))
    assert cli.main(["check", "simple.plain"]) == 0
    assert capsys.readouterr().out == "simple.plain: OK\n"
