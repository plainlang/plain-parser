"""Command-line entry point: ``plain-parser {check,parse} <file.plain> [--template-dir DIR] [--config-name NAME]``."""

import argparse
import json
import os
import sys
from dataclasses import dataclass

import yaml

from plain_parser import loaders, plain_file, plain_spec

DEFAULT_CONFIG_NAME = "config.yaml"
TEMPLATE_DIR_CONFIG_KEYS = ("template_dir", "template-dir")
PARSE_FORMAT_VERSION = 1


class AmbiguousConfigFileError(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plain-parser", description="Tools for ***plain specification files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check",
        help="Validate a .plain module and its requires chain, and read every linked file: "
        "binary files and large base64 blobs are rejected, as codeplain requires.",
    )
    parse_parser = subparsers.add_parser(
        "parse",
        help="Print the parse result of a .plain module and its requires chain as JSON. Linked files are "
        "located but never read.",
    )
    for subparser in (check_parser, parse_parser):
        subparser.add_argument("plain_file", help="Path to the .plain module.")
        subparser.add_argument(
            "--template-dir",
            help="Directory searched for modules and templates after the .plain file's own directory. "
            "Overrides the template-dir value of the config file.",
        )
        subparser.add_argument(
            "--config-name",
            default=DEFAULT_CONFIG_NAME,
            help="Name of the config file to read template-dir from. Looked up in the .plain file's directory "
            "and the current working directory. Defaults to %(default)s.",
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


def template_dir_from_config(config_file: str) -> str | None:
    """The template-dir value of the config file, resolved against the file's directory. Other keys are ignored."""
    with open(config_file) as f:
        config = yaml.safe_load(f) or {}

    for key in TEMPLATE_DIR_CONFIG_KEYS:
        value = config.get(key)
        if value:
            value = os.path.expanduser(str(value))
            return value if os.path.isabs(value) else os.path.join(os.path.dirname(config_file), value)
    return None


@dataclass
class ParseResult:
    modules: list[
        tuple[str, dict]
    ]  # (module name, plain source tree) for the chain, deepest ancestor first, entry last.
    resources: dict[str, str]  # Each link target in the chain, as written, to the absolute path it resolves to.


def parse_spec(plain_file_path: str, template_dir: str | None, load_resources: bool) -> ParseResult:
    """Parse the module and its requires chain, resolve its links, and walk the entry's FRIDs; raise on the first error.

    With ``load_resources``, each module's linked files are also read and checked (text only, no large base64 blob) right
    after that module's links are collected, so a resource error is reported before a FRID-walk error.
    """
    template_dirs = [os.path.dirname(os.path.abspath(plain_file_path))]
    if template_dir:
        template_dirs.append(template_dir)

    chain = plain_file.parse_module_chain(os.path.basename(plain_file_path), template_dirs)

    # Each template dir made absolute, the target joined as written (`..` kept, symlinks not resolved).
    absolute_template_dirs = [os.path.abspath(dir) for dir in template_dirs]
    resources: dict[str, str] = {}
    for module_name, plain_source_tree in chain:
        resources_list: list[dict] = []
        plain_spec.collect_linked_resources(plain_source_tree, resources_list, None, True)
        if load_resources:
            loaders.load_linked_resources(template_dirs, resources_list, module_name)
        for resource in resources_list:
            target = resource["target"]
            resources[target] = loaders.resolve_linked_resource(absolute_template_dirs, target)

    _, top_plain_source_tree = chain[-1]
    for frid in plain_spec.get_frids(top_plain_source_tree):
        plain_spec.get_specifications_for_frid(top_plain_source_tree, frid)

    return ParseResult(chain, resources)


def check(plain_file_path: str, template_dir: str | None) -> None:
    """Raise if the module, its requires chain, or its linked resources are invalid."""
    parse_spec(plain_file_path, template_dir, load_resources=True)


def _error_output(type_name: str, message: str) -> dict:
    return {"format_version": PARSE_FORMAT_VERSION, "type": type_name, "message": message}


def _escape(text: str) -> str:
    """The text with every non-ASCII character as a backslash escape, so it always encodes."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _encode_output(output: dict) -> bytes:
    """The output as UTF-8 JSON; raise if it is not JSON-serialisable or holds text that is not valid UTF-8."""
    return (json.dumps(output, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def parse(plain_file_path: str, template_dir: str | None) -> int:
    """Print the parse result, or the parser error, as one UTF-8 JSON document on stdout; return the exit code."""
    output: dict
    try:
        result = parse_spec(plain_file_path, template_dir, load_resources=False)
        output = {
            "format_version": PARSE_FORMAT_VERSION,
            "modules": [{"module": module_name, "tree": tree} for module_name, tree in result.modules],
            "resources": result.resources,
        }
        exit_code = 0
    except Exception as e:
        output = _error_output(type(e).__name__, str(e))
        exit_code = 1

    try:
        data = _encode_output(output)
    except UnicodeEncodeError as e:
        # A file or directory name that is not valid UTF-8 (the OS hands it over as surrogate escapes).
        if exit_code == 1:
            # Already a parser error naming the path: keep its type, escape its message.
            output = _error_output(output["type"], _escape(output["message"]))
        else:
            line_start = e.object.rfind("\n", 0, e.start) + 1
            line_end = e.object.find("\n", e.end)
            line = e.object[line_start : line_end if line_end != -1 else None].strip()
            output = _error_output(type(e).__name__, f"A path in the parse result is not valid UTF-8: {_escape(line)}")
        data = _encode_output(output)
        exit_code = 1
    except Exception as e:
        data = _encode_output(_error_output(type(e).__name__, _escape(str(e))))
        exit_code = 1

    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        # A text-only stream, e.g. stdout redirected to a StringIO by an in-process caller.
        sys.stdout.write(data.decode("utf-8"))
        return exit_code

    # UTF-8 whatever the locale's encoding, so non-ASCII spec text cannot fail the write.
    sys.stdout.flush()
    buffer.write(data)
    buffer.flush()
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        # The config file is resolved even when --template-dir is given, so an ambiguous config is always an error.
        config_template_dir = _template_dir_from_config(parser, args)
        if args.command == "parse":
            return parse(args.plain_file, args.template_dir or config_template_dir)
        check(args.plain_file, args.template_dir or config_template_dir)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"{args.plain_file}: OK")
    return 0


def _template_dir_from_config(parser: argparse.ArgumentParser, args: argparse.Namespace) -> str | None:
    try:
        config_file = resolve_config_file(args.config_name, args.plain_file)
        return template_dir_from_config(config_file) if config_file is not None else None
    except AmbiguousConfigFileError as e:
        parser.error(str(e))
    except Exception as e:
        parser.error(f"Error reading config file: {e}")
