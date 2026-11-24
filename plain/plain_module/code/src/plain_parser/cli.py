"""The plain-parser command line tool: check and parse a module with its requires chain and test plain files."""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field

import yaml

from plain_parser import loaders, plain_spec
from plain_parser.project import parse_project

DEFAULT_CONFIG_NAME = "config.yaml"
PARSE_FORMAT_VERSION = 2

_TEMPLATE_DIR_KEYS = ("template-dir", "template_dir")
_TESTS_FOLDER_KEYS = ("tests-folder", "tests_folder")
_CONFORMANCE_SCRIPT_KEYS = ("conformance-tests-script", "conformance_tests_script")
_NO_TESTS_FOLDER = (
    "conformance-tests-script is set in the config file, but no tests folder is given. Pass --tests-folder or set "
    "tests-folder in the config file."
)
_INTERRUPTED = 130


class AmbiguousConfigFileError(Exception):
    pass


@dataclass
class Config:
    template_dir: str | None = None
    tests_folders: list[str] | None = None
    conformance_tests_enabled: bool = False


@dataclass
class ParseResult:
    modules: list[tuple[str, dict]]
    resources: dict[str, str]
    test_plain_files: dict[str, dict] = field(default_factory=dict)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plain-parser", description="Check and parse ***plain specification files.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("check", "validate a module with its requires chain and test plain files"),
        ("parse", "print the parsed module with its requires chain as JSON"),
    ):
        subparser = subparsers.add_parser(command, help=help_text)
        subparser.add_argument("plain_file", help="path of the module's .plain file")
        subparser.add_argument("--template-dir", dest="template_dir", default=None, metavar="DIR")
        subparser.add_argument("--tests-folder", dest="tests_folder", action="append", default=None, metavar="DIR")
        subparser.add_argument("--config-name", dest="config_name", default=DEFAULT_CONFIG_NAME, metavar="NAME")
    return parser


def resolve_config_file(config_name: str, plain_file_path: str) -> str | None:
    """Return the config file next to the module or in the working directory, or None."""
    plain_dir = os.path.dirname(os.path.abspath(plain_file_path))
    cwd = os.getcwd()
    next_to_module = os.path.join(plain_dir, config_name)
    in_working_dir = os.path.join(cwd, config_name)
    found_next = os.path.isfile(next_to_module)
    found_cwd = os.path.isfile(in_working_dir)
    if found_next and found_cwd and os.path.realpath(next_to_module) != os.path.realpath(in_working_dir):
        raise AmbiguousConfigFileError(
            f"Config file '{config_name}' was found in two locations:\n"
            f"  - Plain file directory: {plain_dir}\n"
            f"  - Current working directory: {cwd}\n"
            "Remove the config file from one of these locations to resolve the ambiguity."
        )
    if found_next:
        return next_to_module
    if found_cwd:
        return in_working_dir
    return None


def _config_value(data: dict, keys: tuple[str, str]):
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            return value
    return None


def _resolve(config_dir: str, path) -> str:
    return os.path.join(config_dir, os.path.expanduser(str(path)))


def read_config(config_file: str) -> Config:
    """Read the template directory, the tests folders and the conformance switch from a config file."""
    with open(config_file, encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        data = {}
    config_dir = os.path.dirname(os.path.abspath(config_file))
    config = Config()

    template_dir = _config_value(data, _TEMPLATE_DIR_KEYS)
    if template_dir is not None:
        config.template_dir = _resolve(config_dir, template_dir)

    tests_folder = _config_value(data, _TESTS_FOLDER_KEYS)
    if tests_folder is not None:
        folders = tests_folder if isinstance(tests_folder, list) else [tests_folder]
        config.tests_folders = [_resolve(config_dir, folder) for folder in folders]

    config.conformance_tests_enabled = _config_value(data, _CONFORMANCE_SCRIPT_KEYS) is not None
    return config


def _posix(path: str) -> str:
    return path.replace(os.sep, "/") if os.sep != "/" else path


def parse_spec(
    plain_file_path: str,
    template_dir: str | None,
    load_resources: bool,
    tests_folders: list[str] | None = None,
    require_test_plain_files: bool = False,
) -> ParseResult:
    """Parse an entry module file with its requires chain, resources and test plain files."""
    entry_path = os.path.abspath(plain_file_path)
    entry_dir = os.path.dirname(entry_path)
    template_dirs = [entry_dir]
    if template_dir:
        template_dirs.append(os.path.abspath(template_dir))

    result = parse_project(entry_path, template_dirs, tests_folders or [], require_test_plain_files)

    resources: dict[str, str] = {}
    for module_name, tree in result.chain:
        registry: list[dict] = []
        plain_spec.collect_linked_resources(tree, registry, None, True)
        for resource in registry:
            target = resource["target"]
            if target not in resources:
                resource_dir = loaders.find_resource_dir(template_dirs, target)
                if resource_dir is None:
                    raise FileNotFoundError(f"Resource file '{target}' referenced in module '{module_name}' not found.")
                resources[target] = loaders.relative_resource_path(entry_dir, resource_dir, target)
        if load_resources:
            loaders.load_linked_resources(template_dirs, registry, module_name)

    test_plain_files = {
        bound.name: {"module": bound.parsed.module, "func_id": bound.parsed.func_id}
        for bound in result.test_plain_files
    }

    entry_tree = result.chain[-1][1]
    for frid in plain_spec.get_frids(entry_tree):
        plain_spec.get_specifications_for_frid(entry_tree, frid)

    return ParseResult(modules=list(result.chain), resources=resources, test_plain_files=test_plain_files)


def check(
    plain_file_path: str,
    template_dir: str | None,
    tests_folders: list[str] | None = None,
    require_test_plain_files: bool = False,
) -> None:
    """Validate a module, loading its linked files; raise the first error found."""
    parse_spec(plain_file_path, template_dir, True, tests_folders, require_test_plain_files)


def _error_document(error: BaseException) -> dict:
    return {"format_version": PARSE_FORMAT_VERSION, "type": type(error).__name__, "message": str(error)}


def _not_utf8_line(text: str) -> str:
    for line in text.split("\n"):
        try:
            line.encode("utf-8")
        except UnicodeEncodeError:
            stripped = line.strip()
            if stripped.endswith(","):
                stripped = stripped[:-1]
            return stripped.encode("utf-8", "backslashreplace").decode("utf-8")
    return ""


def _dump(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _encode_output(document: dict, is_error: bool) -> tuple[bytes, int]:
    exit_code = 1 if is_error else 0
    try:
        text = _dump(document)
    except Exception as error:  # a value JSON cannot represent
        text = _dump(_error_document(error))
        is_error, exit_code = True, 1
    if is_error:
        return text.encode("utf-8", "backslashreplace"), exit_code
    try:
        return text.encode("utf-8"), exit_code
    except UnicodeEncodeError as error:
        message = f"The parse result holds text that is not valid UTF-8: {_not_utf8_line(text)}"
        document = {"format_version": PARSE_FORMAT_VERSION, "type": type(error).__name__, "message": message}
        return _dump(document).encode("utf-8", "backslashreplace"), 1


def _write_stdout(data: bytes) -> None:
    try:
        sys.stdout.flush()
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is not None:
            buffer.write(data)
            buffer.flush()
        else:
            sys.stdout.write(data.decode("utf-8"))
            sys.stdout.flush()
    except BrokenPipeError:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except (OSError, ValueError, AttributeError):
            pass


def parse(
    plain_file_path: str,
    template_dir: str | None,
    tests_folders: list[str] | None = None,
    require_test_plain_files: bool = False,
) -> int:
    """Print the parse result of a module as one JSON document; return the exit code."""
    try:
        result = parse_spec(plain_file_path, template_dir, False, tests_folders, require_test_plain_files)
        document = {
            "format_version": PARSE_FORMAT_VERSION,
            "modules": [{"module": name, "tree": tree} for name, tree in result.modules],
            "resources": result.resources,
            "test_plain_files": result.test_plain_files,
        }
        is_error = False
    except Exception as error:
        document = _error_document(error)
        is_error = True
    data, exit_code = _encode_output(document, is_error)
    _write_stdout(data)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        try:
            config_file = resolve_config_file(args.config_name, args.plain_file)
        except AmbiguousConfigFileError as error:
            parser.error(str(error))
        config = Config()
        if config_file is not None:
            try:
                config = read_config(config_file)
            except (OSError, yaml.YAMLError, UnicodeDecodeError) as error:
                parser.error(f"Error reading config file: {error}")

        template_dir = config.template_dir
        if args.template_dir is not None:
            template_dir = os.path.abspath(args.template_dir) if args.template_dir else None

        tests_folders = config.tests_folders
        if args.tests_folder:
            tests_folders = [os.path.abspath(folder) for folder in args.tests_folder]

        if config.conformance_tests_enabled and not tests_folders:
            parser.error(_NO_TESTS_FOLDER)
        require = config.conformance_tests_enabled

        if args.command == "parse":
            return parse(args.plain_file, template_dir, tests_folders, require)

        try:
            check(args.plain_file, template_dir, tests_folders, require)
        except Exception as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        print(f"{args.plain_file}: OK")
        return 0
    except KeyboardInterrupt:
        return _INTERRUPTED


if __name__ == "__main__":
    sys.exit(main())
