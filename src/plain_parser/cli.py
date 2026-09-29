"""Command-line entry point: ``plain-parser check <file.plain> [--template-dir DIR]``."""

import argparse
import os
import sys

from plain_parser import loaders, plain_file, plain_spec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plain-parser", description="Tools for ***plain specification files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Validate a .plain module and its requires chain.")
    check_parser.add_argument("plain_file", help="Path to the .plain module.")
    check_parser.add_argument(
        "--template-dir",
        help="Directory searched for modules and templates after the .plain file's own directory.",
    )
    return parser


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
    args = build_parser().parse_args(argv)

    try:
        check(args.plain_file, args.template_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0
