"""Command-line entry point: ``plain-parser {check,parse} <file.plain> [--template-dir DIR] [--tests-folder DIR]...
[--config-name NAME]``."""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field

import yaml

from plain_parser import loaders, plain_spec, project

DEFAULT_CONFIG_NAME = "config.yaml"
TEMPLATE_DIR_CONFIG_KEYS = ("template_dir", "template-dir")
TESTS_FOLDER_CONFIG_KEYS = ("tests_folder", "tests-folder")
CONFORMANCE_TESTS_SCRIPT_CONFIG_KEYS = ("conformance_tests_script", "conformance-tests-script")
PARSE_FORMAT_VERSION = 2


class AmbiguousConfigFileError(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plain-parser", description="Tools for ***plain specification files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check",
        help="Validate a .plain module, its requires chain and its test plain files, and read every linked file: "
        "binary files and large base64 blobs are rejected.",
    )
    parse_parser = subparsers.add_parser(
        "parse",
        help="Print the parse result of a .plain module, its requires chain and its test plain files as JSON. "
        "Linked files are located but never read.",
    )
    for subparser in (check_parser, parse_parser):
        subparser.add_argument("plain_file", help="Path to the .plain module.")
        subparser.add_argument(
            "--template-dir",
            help="Directory searched for modules and templates after the .plain file's own directory. "
            "Overrides the template-dir value of the config file.",
        )
        subparser.add_argument(
            "--tests-folder",
            action="append",
            metavar="DIR",
            help="Directory scanned for test plain files; repeat the option for more than one. Overrides the "
            "tests-folder value of the config file. Without both, no test plain files are read.",
        )
        subparser.add_argument(
            "--config-name",
            default=DEFAULT_CONFIG_NAME,
            help="Name of the config file to read template-dir, tests-folder and conformance-tests-script from. "
            "Looked up in the .plain file's directory and the current working directory. Defaults to %(default)s.",
        )
    return parser


def resolve_config_file(config_name: str, plain_file_path: str) -> str | None:
    """The config file next to the .plain file, else the one in the working directory, else None."""
    plain_file_dir = os.path.dirname(os.path.abspath(plain_file_path))
    plain_dir_config = os.path.normpath(os.path.join(plain_file_dir, config_name))
    cwd_config = os.path.normpath(os.path.join(os.getcwd(), config_name))

    in_plain_dir = os.path.exists(plain_dir_config)
    in_cwd = os.path.exists(cwd_config)
    if in_plain_dir and in_cwd and plain_dir_config != cwd_config:
        raise AmbiguousConfigFileError(
            f"Config file '{config_name}' was found in two locations:\n"
            f"  - Plain file directory: {plain_file_dir}\n"
            f"  - Current working directory: {os.getcwd()}\n"
            f"Remove the config file from one of these locations to resolve the ambiguity."
        )
    if in_plain_dir:
        return plain_dir_config
    if in_cwd:
        return cwd_config
    return None


@dataclass
class Config:
    template_dir: str | None = None
    tests_folders: list[str] | None = None  # None when the config does not set tests-folder.
    conformance_tests_enabled: bool = False  # Whether the config names a conformance-tests-script.


def _config_value(config: dict, keys: tuple[str, ...]):
    """The first value set under one of the key spellings, or None."""
    return next((config[key] for key in keys if config.get(key)), None)


def read_config(config_file: str) -> Config:
    """The values plain-parser reads from the config file, paths resolved against the file's directory. Other keys
    are ignored."""
    with open(config_file) as f:
        config = yaml.safe_load(f) or {}

    def resolve(value) -> str:
        value = os.path.expanduser(str(value))
        return value if os.path.isabs(value) else os.path.join(os.path.dirname(config_file), value)

    result = Config()
    template_dir = _config_value(config, TEMPLATE_DIR_CONFIG_KEYS)
    if template_dir:
        result.template_dir = resolve(template_dir)
    tests_folder = _config_value(config, TESTS_FOLDER_CONFIG_KEYS)
    if tests_folder:
        result.tests_folders = [
            resolve(value) for value in (tests_folder if isinstance(tests_folder, list) else [tests_folder])
        ]
    result.conformance_tests_enabled = bool(_config_value(config, CONFORMANCE_TESTS_SCRIPT_CONFIG_KEYS))
    return result


@dataclass
class ParseResult:
    modules: list[
        tuple[str, dict]
    ]  # (module name, plain source tree) for the chain, deepest ancestor first, entry last.
    # Each link target in the chain, as written, to the path it resolves to, relative to the entry module's dir
    # with `/` as separator (loaders.relative_resource_path).
    resources: dict[str, str]
    # Each test plain file, by its path relative to the entry module's dir with `/`, to the functionality it binds to.
    test_plain_files: dict[str, dict] = field(default_factory=dict)


def parse_spec(
    plain_file_path: str,
    template_dir: str | None,
    load_resources: bool,
    tests_folders: list[str] | None = None,
    require_test_plain_files: bool = False,
) -> ParseResult:
    """Parse the module, its requires chain and its test plain files, resolve the links, and walk the entry's
    FRIDs; raise on the first error.

    Without ``tests_folders`` no test plain files are read. With ``require_test_plain_files``, every functionality needs a
    test plain file bound to it. With ``load_resources``, each module's linked files are
    also read and checked (text only, no large base64 blob) right after that module's links are collected, so a
    resource error is reported before a FRID-walk error.
    """
    # Absolute, so the chain parse and the resource paths below search the same directories.
    entry_dir = os.path.dirname(os.path.abspath(plain_file_path))
    template_dirs = [entry_dir]
    if template_dir:
        template_dirs.append(os.path.abspath(template_dir))
    tests_folders = [os.path.abspath(tests_folder) for tests_folder in tests_folders or []]

    parsed = project.parse_project(
        os.path.basename(plain_file_path), template_dirs, tests_folders, require_test_plain_files
    )
    chain = parsed.chain

    # The target joined as written onto its template dir (`..` kept, symlinks not resolved), made relative to the
    # entry module's dir so the result does not depend on where the project sits on the machine.
    resources: dict[str, str] = {}
    for module_name, plain_source_tree in chain:
        resources_list: list[dict] = []
        plain_spec.collect_linked_resources(plain_source_tree, resources_list, None, True)
        if load_resources:
            loaders.load_linked_resources(template_dirs, resources_list, module_name)
        for resource in resources_list:
            target = resource["target"]
            resource_dir = loaders.find_resource_dir(template_dirs, target)
            resources[target] = loaders.relative_resource_path(template_dirs[0], resource_dir, target)

    _, top_plain_source_tree = chain[-1]
    for frid in plain_spec.get_frids(top_plain_source_tree):
        plain_spec.get_specifications_for_frid(top_plain_source_tree, frid)

    test_plain_files = {
        bound.name: {"module": bound.parsed.module, "func_id": bound.parsed.func_id}
        for bound in parsed.test_plain_files
    }
    return ParseResult(chain, resources, test_plain_files)


def check(
    plain_file_path: str,
    template_dir: str | None,
    tests_folders: list[str] | None = None,
    require_test_plain_files: bool = False,
) -> None:
    """Raise if the module, its requires chain, its test plain files, or its linked resources are invalid."""
    parse_spec(plain_file_path, template_dir, True, tests_folders, require_test_plain_files)


def _error_output(type_name: str, message: str) -> dict:
    return {"format_version": PARSE_FORMAT_VERSION, "type": type_name, "message": message}


def _escape(text: str) -> str:
    """The text with every non-ASCII character as a backslash escape, so it always encodes."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _encode_output(output: dict) -> bytes:
    """The output as UTF-8 JSON; raise if it is not JSON-serialisable or holds text that is not valid UTF-8."""
    return (json.dumps(output, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def parse(
    plain_file_path: str,
    template_dir: str | None,
    tests_folders: list[str] | None = None,
    require_test_plain_files: bool = False,
) -> int:
    """Print the parse result, or the parser error, as one UTF-8 JSON document on stdout; return the exit code."""
    output: dict
    try:
        result = parse_spec(plain_file_path, template_dir, False, tests_folders, require_test_plain_files)
        output = {
            "format_version": PARSE_FORMAT_VERSION,
            "modules": [{"module": module_name, "tree": tree} for module_name, tree in result.modules],
            "resources": result.resources,
            "test_plain_files": result.test_plain_files,
        }
        exit_code = 0
    except Exception as e:
        output = _error_output(type(e).__name__, str(e))
        exit_code = 1

    try:
        data = _encode_output(output)
    except UnicodeEncodeError as e:
        # A file or directory name that is not valid UTF-8, which is allowed on Linux.
        if exit_code == 1:
            # A parser error whose message names such a file. Keep its type and escape the name.
            output = _error_output(output["type"], _escape(output["message"]))
        else:
            # A valid result that contains such a name. Report the output line that contains it.
            line_start = e.object.rfind("\n", 0, e.start) + 1
            line_end = e.object.find("\n", e.end)
            line = e.object[line_start : line_end if line_end != -1 else None].strip().rstrip(",")
            output = _error_output(
                type(e).__name__, f"The parse result holds text that is not valid UTF-8: {_escape(line)}"
            )
        data = _encode_output(output)
        exit_code = 1
    except Exception as e:
        # A value in the result that JSON cannot represent. Report it as a JSON error.
        data = _encode_output(_error_output(type(e).__name__, _escape(str(e))))
        exit_code = 1

    # Write the UTF-8 bytes to stdout's byte stream, because sys.stdout encodes text with the system encoding, which
    # may not be UTF-8.
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        # A Python caller replaced stdout with a stream that takes only text.
        sys.stdout.write(data.decode("utf-8"))
        return exit_code

    try:
        sys.stdout.flush()  # Send out anything already written to sys.stdout first.
        buffer.write(data)
        buffer.flush()
    except BrokenPipeError:
        # The reader closed the pipe early. Send stdout to /dev/null, so Python's flush at exit does not fail again,
        # and keep the exit code.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        # The config file is resolved even when --template-dir is given, so an ambiguous config is always an error.
        config = _read_config(parser, args)
        template_dir = args.template_dir or config.template_dir
        tests_folders = args.tests_folder or config.tests_folders
        if config.conformance_tests_enabled and not tests_folders:
            parser.error(
                "conformance-tests-script is set in the config file, but no tests folder is given. "
                "Pass --tests-folder or set tests-folder in the config file."
            )
        if args.command == "parse":
            return parse(args.plain_file, template_dir, tests_folders, config.conformance_tests_enabled)
        check(args.plain_file, template_dir, tests_folders, config.conformance_tests_enabled)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"{args.plain_file}: OK")
    return 0


def _read_config(parser: argparse.ArgumentParser, args: argparse.Namespace) -> Config:
    try:
        config_file = resolve_config_file(args.config_name, args.plain_file)
        return read_config(config_file) if config_file is not None else Config()
    except AmbiguousConfigFileError as e:
        parser.error(str(e))
    except Exception as e:
        parser.error(f"Error reading config file: {e}")
