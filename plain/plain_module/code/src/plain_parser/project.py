"""A module with its requires chain and the test plain files bound to its functionalities."""

import os
from dataclasses import dataclass

import frontmatter
import yaml

from plain_parser import concept_utils, loaders, plain_spec
from plain_parser.exceptions import MissingTestPlainFileError, PlainSyntaxError, UnsupportedBase64Content
from plain_parser.plain_file import PLAIN_SOURCE_FILE_EXTENSION, normalize_line_endings, parse_module_chain
from plain_parser.test_plain_file import (
    TestPlainFile,
    is_test_plain_file,
    parse_test_plain_file_source,
    validate_scenario_concepts,
)


@dataclass
class BoundTestPlainFile:
    path: str
    name: str
    parsed: TestPlainFile


@dataclass
class ProjectParseResult:
    chain: list[tuple[str, dict]]
    test_plain_files: list[BoundTestPlainFile]


def _posix(path: str) -> str:
    return path.replace(os.sep, "/") if os.sep != "/" else path


def discover_test_plain_files(tests_folders: list[str], entry_dir: str) -> list[tuple[str, str]]:
    """List every ``.plain`` file under the tests folders, as its path and its name relative to ``entry_dir``."""
    found: list[tuple[str, str]] = []
    for folder in tests_folders:
        root = folder if os.path.isabs(folder) else os.path.join(entry_dir, folder)
        if not os.path.isdir(root):
            continue
        for directory, subdirectories, files in os.walk(root):
            subdirectories.sort()
            for file_name in sorted(files):
                if not file_name.endswith(PLAIN_SOURCE_FILE_EXTENSION):
                    continue
                path = os.path.join(directory, file_name)
                found.append((path, _posix(os.path.relpath(path, entry_dir))))
    return found


def _read_test_file(path: str, name: str) -> str:
    with open(path, "rb") as file:
        data = file.read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PlainSyntaxError(f"Plain syntax error: File '{name}' under a tests folder is not a text file.") from error
    blob = loaders.find_large_base64_blob(text)
    if blob is not None:
        raise UnsupportedBase64Content(
            f"Test plain file '{name}' contains a base64-encoded blob ({len(blob)} characters) inlined in the "
            "scenarios. This is not supported. Remove the base64 data from the file."
        )
    return normalize_line_endings(text)


def _frontmatter(text: str, name: str) -> dict:
    try:
        metadata = frontmatter.loads(text).metadata
    except yaml.YAMLError as error:
        raise PlainSyntaxError(
            f"Plain syntax error: File '{name}' under a tests folder has invalid frontmatter: {error}"
        ) from error
    if not is_test_plain_file(metadata):
        raise PlainSyntaxError(
            f"Plain syntax error: File '{name}' is under a tests folder but is not a test plain file: its frontmatter "
            "needs the keys `module:` and `func_id:`."
        )
    return metadata


def _functionality(tree: dict, func_id) -> dict | None:
    for functionality in tree.get(plain_spec.FUNCTIONAL_REQUIREMENTS, []) or []:
        if functionality["id"] == func_id:
            return functionality
    return None


def bind_test_plain_files(chain, tests_folders, template_dirs, entry_dir) -> list[BoundTestPlainFile]:
    """Add the scenarios of every discovered test plain file to the functionality of the chain it binds to."""
    trees = dict(chain)
    bound: list[BoundTestPlainFile] = []
    for path, name in discover_test_plain_files(tests_folders, entry_dir):
        text = _read_test_file(path, name)
        metadata = _frontmatter(text, name)
        if metadata.get("module") not in trees:
            continue
        parsed = parse_test_plain_file_source(text, name, template_dirs, {})
        functionality = _functionality(trees[parsed.module], parsed.func_id)
        if functionality is None:
            raise PlainSyntaxError(
                f"Plain syntax error: Test plain file '{name}' binds to functionality '{parsed.module}:"
                f"{parsed.func_id}', which module '{parsed.module}' does not have."
            )
        functionality.setdefault(plain_spec.CONFORMANCE_TESTS, []).extend(
            scenario.to_dict() for scenario in parsed.conformance_tests
        )
        functionality.setdefault(plain_spec.ACCEPTANCE_TESTS, []).extend(
            scenario.to_dict() for scenario in parsed.acceptance_tests
        )
        bound.append(BoundTestPlainFile(path=path, name=name, parsed=parsed))
    return bound


def check_test_plain_files(chain, bound) -> None:
    """Check the concepts and scenario-ids of the bound test plain files."""
    trees = dict(chain)
    first_use: dict[tuple[str, str, str], tuple[int, str]] = {}
    for bound_file in bound:
        parsed = bound_file.parsed
        concepts, _ = concept_utils.collect_concepts(trees[parsed.module])
        errors = validate_scenario_concepts(parsed, set(concepts))
        if errors:
            raise PlainSyntaxError(
                f"Plain syntax error: Found {len(errors)} errors in test plain file '{parsed.name}':\n"
                + "\n".join(errors)
            )
        for scenario in parsed.scenarios:
            key = (parsed.module, parsed.func_id, scenario.id)
            if key in first_use:
                first_line, first_name = first_use[key]
                raise PlainSyntaxError(
                    f"Plain syntax error: Syntax error at line {scenario.line_number} in test plain file "
                    f"'{parsed.name}': Duplicate scenario-id `{scenario.id}` for functionality '{parsed.module}:"
                    f"{parsed.func_id}'; it is first used at line {first_line} in test plain file '{first_name}'."
                )
            first_use[key] = (scenario.line_number, parsed.name)


def _require_test_plain_files(chain, bound) -> None:
    bound_keys = {(b.parsed.module, b.parsed.func_id) for b in bound}
    for module, tree in chain:
        for func_id in plain_spec.get_frids(tree):
            if (module, func_id) not in bound_keys:
                raise MissingTestPlainFileError(
                    f"Functionality {module}:{func_id} has no test plain file. Add one, by convention "
                    f"tests/{module}/{func_id}.plain, with the add-test-scenarios skill."
                )


def _entry_dir(plain_file_name: str, template_dirs: list[str]) -> str:
    if os.path.isabs(plain_file_name):
        return os.path.dirname(plain_file_name)
    for directory in template_dirs:
        path = os.path.join(directory, plain_file_name)
        if os.path.isfile(path):
            return os.path.dirname(os.path.abspath(path))
    return os.path.abspath(template_dirs[0]) if template_dirs else os.getcwd()


def parse_project(
    plain_file_name: str, template_dirs: list[str], tests_folders: list[str], require_test_plain_files: bool
) -> ProjectParseResult:
    """Parse a module's requires chain and bind the test plain files of the tests folders to its functionalities."""
    chain = parse_module_chain(plain_file_name, template_dirs)
    entry_dir = _entry_dir(plain_file_name, template_dirs)
    bound = bind_test_plain_files(chain, tests_folders or [], template_dirs, entry_dir)
    check_test_plain_files(chain, bound)
    if require_test_plain_files:
        _require_test_plain_files(chain, bound)
    return ProjectParseResult(chain=chain, test_plain_files=bound)
