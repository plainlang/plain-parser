import os
import shutil
import subprocess
import sys

import pytest

from plain_parser import cli


@pytest.fixture
def cli_data_dir(get_test_data_path):
    return get_test_data_path("data/cli")


def test_check_valid_module_exits_zero_and_prints_nothing(cli_data_dir, capsys):
    exit_code = cli.main(["check", os.path.join(cli_data_dir, "valid.plain")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
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


def test_console_script_is_installed_and_exits_zero(cli_data_dir):
    # The venv's script dir may not be on PATH when pytest is run through an absolute interpreter path.
    search_path = os.pathsep.join([os.path.dirname(sys.executable), os.environ.get("PATH", "")])
    script = shutil.which("plain-parser", path=search_path)
    if script is None:
        pytest.skip("plain-parser console script not installed; run: uv pip install -e '.[dev]'")

    result = subprocess.run(
        [script, "check", os.path.join(cli_data_dir, "valid.plain")], capture_output=True, text=True
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
