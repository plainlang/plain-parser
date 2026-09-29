"""Command-line entry point: ``plain-parser check <file.plain> [--template-dir DIR] [--config-name NAME]``."""

import argparse
import os
import sys

import yaml

from plain_parser import loaders, plain_file, plain_spec

DEFAULT_CONFIG_NAME = "config.yaml"
TEMPLATE_DIR_CONFIG_KEYS = ("template_dir", "template-dir")


class AmbiguousConfigFileError(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plain-parser", description="Tools for ***plain specification files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Validate a .plain module and its requires chain.")
    check_parser.add_argument("plain_file", help="Path to the .plain module.")
    check_parser.add_argument(
        "--template-dir",
        help="Directory searched for modules and templates after the .plain file's own directory. "
        "Overrides the template-dir value of the config file.",
    )
    check_parser.add_argument(
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


def check(plain_file_path: str, template_dir: str | None) -> None:
    """Raise if the module, its requires chain, or its linked resources are invalid."""
    template_dirs = [os.path.dirname(os.path.abspath(plain_file_path))]
    if template_dir:
        template_dirs.append(template_dir)

    chain = plain_file.parse_module_chain(os.path.basename(plain_file_path), template_dirs)

    for module_name, plain_source_tree in chain:
        resources_list: list[dict] = []
        plain_spec.collect_linked_resources(plain_source_tree, resources_list, None, True)
        loaders.load_linked_resources(template_dirs, resources_list, module_name)

    _, top_plain_source_tree = chain[-1]
    for frid in plain_spec.get_frids(top_plain_source_tree):
        plain_spec.get_specifications_for_frid(top_plain_source_tree, frid)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        template_dir = args.template_dir or _template_dir_from_config(parser, args)
        check(args.plain_file, template_dir)
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
