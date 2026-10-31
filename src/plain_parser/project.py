"""A module with its requires chain and the test plain files bound to its functionalities."""

import os
from dataclasses import dataclass

import frontmatter

from plain_parser import concept_utils, loaders, plain_file, plain_spec, test_plain_file
from plain_parser.exceptions import MissingTestPlainFileError, PlainSyntaxError, UnsupportedBase64Content


@dataclass
class BoundTestPlainFile:
    path: str  # The file on disk.
    name: str  # The path relative to the entry module's directory, with `/` as separator.
    parsed: test_plain_file.TestPlainFile


@dataclass
class ProjectParseResult:
    # As parse_module_chain returns it, with the scenarios of the test plain files merged into the functionalities.
    chain: list[tuple[str, dict]]
    test_plain_files: list[BoundTestPlainFile]


def discover_test_plain_files(tests_folders: list[str], entry_dir: str) -> list[tuple[str, str]]:
    """(path, name) of every .plain file under the tests folders: tests folder by tests folder, and within one by path. A
    tests folder that does not exist is skipped."""
    found = []
    for tests_folder in tests_folders:
        if not os.path.isdir(tests_folder):
            continue
        for root, dirs, files in os.walk(tests_folder):
            dirs.sort()
            for file_name in sorted(files):
                if file_name.endswith(plain_file.PLAIN_SOURCE_FILE_EXTENSION):
                    found.append(
                        (os.path.join(root, file_name), loaders.relative_resource_path(entry_dir, root, file_name))
                    )
    return found


def read_test_plain_file_text(path: str, name: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise PlainSyntaxError(f"Plain syntax error: File '{name}' under a tests folder is not a text file.")

    blob = loaders.find_large_base64_blob(text)
    if blob is not None:
        raise UnsupportedBase64Content(
            f"Test plain file '{name}' contains a base64-encoded blob ({len(blob)} characters) inlined in the "
            "scenarios. This is not supported. Remove the base64 data from the file."
        )
    return text


def bind_test_plain_files(
    chain: list[tuple[str, dict]], tests_folders: list[str], template_dirs: list[str], entry_dir: str
) -> list[BoundTestPlainFile]:
    """Read every test plain file under the tests folders and add its scenarios to the functionality it binds to.

    A `.plain` file under a tests folder without the `module:` and `func_id:` keys is an error, as is a file that binds to
    a module outside the chain or to a func-id the module does not have. The concepts of the scenarios must be
    visible to the bound module. Files bound to one functionality are merged in discovery order; a scenario-id is
    unique across that merged set.
    """
    trees = dict(chain)
    bound = []
    scenario_places: dict[tuple[str, str], dict[str, str]] = {}  # (module, func-id) -> scenario-id -> place
    for path, name in discover_test_plain_files(tests_folders, entry_dir):
        text = read_test_plain_file_text(path, name)
        try:
            metadata = frontmatter.loads(text).metadata
        except Exception as e:
            raise PlainSyntaxError(
                f"Plain syntax error: File '{name}' under a tests folder has invalid frontmatter: {e}"
            )
        if not test_plain_file.is_test_plain_file(metadata):
            raise PlainSyntaxError(
                f"Plain syntax error: File '{name}' is under a tests folder but is not a test plain file: its "
                f"frontmatter needs the keys `module:` and `func_id:`."
            )

        parsed = test_plain_file.parse_test_plain_file_source(text, name, template_dirs, {})
        if parsed.module not in trees:
            raise PlainSyntaxError(
                f"Plain syntax error: Test plain file '{name}' binds to module '{parsed.module}', which is not the "
                f"entry module or one of its required modules ({', '.join(trees)})."
            )
        tree = trees[parsed.module]
        functionalities = tree.get(plain_spec.FUNCTIONAL_REQUIREMENTS) or []
        functionality = next((item for item in functionalities if item["id"] == parsed.func_id), None)
        if functionality is None:
            raise PlainSyntaxError(
                f"Plain syntax error: Test plain file '{name}' binds to functionality "
                f"'{parsed.module}:{parsed.func_id}', which module '{parsed.module}' does not have."
            )

        concepts, _ = concept_utils.collect_concepts(tree)
        errors = test_plain_file.validate_scenario_concepts(parsed, set(concepts))
        if errors:
            raise PlainSyntaxError(
                f"Plain syntax error: Found {len(errors)} errors in test plain file '{name}':\n" + "\n".join(errors)
            )

        places = scenario_places.setdefault((parsed.module, parsed.func_id), {})
        for key, scenarios in (
            (plain_spec.CONFORMANCE_TESTS, parsed.conformance_tests),
            (plain_spec.ACCEPTANCE_TESTS, parsed.acceptance_tests),
        ):
            for scenario in scenarios:
                if scenario.id in places:
                    raise PlainSyntaxError(
                        f"Plain syntax error: Syntax error at line {scenario.line_number} in test plain file "
                        f"'{name}': Duplicate scenario-id `{scenario.id}` for functionality "
                        f"'{parsed.module}:{parsed.func_id}'; it is first used {places[scenario.id]}."
                    )
                places[scenario.id] = f"at line {scenario.line_number} in test plain file '{name}'"
                functionality[key].append(scenario.to_dict())

        bound.append(BoundTestPlainFile(path, name, parsed))

    return bound


def check_test_plain_files(chain: list[tuple[str, dict]], bound: list[BoundTestPlainFile]) -> None:
    """Raise for the first functionality of the chain, in render order, that has no test plain file bound to it.

    The sections of the file may be empty; the file itself is what the check asks for.
    """
    bound_functionalities = {(item.parsed.module, item.parsed.func_id) for item in bound}
    for module_name, tree in chain:
        for functionality in tree.get(plain_spec.FUNCTIONAL_REQUIREMENTS) or []:
            func_id = functionality["id"]
            if (module_name, func_id) not in bound_functionalities:
                raise MissingTestPlainFileError(
                    f"Functionality {module_name}:{func_id} has no test plain file. Add one, by convention "
                    f"tests/{module_name}/{func_id}.plain, with the add-test-scenarios skill."
                )


def parse_project(
    plain_file_name: str, template_dirs: list[str], tests_folders: list[str], require_test_plain_files: bool
) -> ProjectParseResult:
    """Parse a module with its requires chain and bind the test plain files under ``tests_folders`` to its functionalities.

    ``template_dirs[0]`` is the entry module's directory; test plain files are named relative to it. With
    ``require_test_plain_files``, every functionality of every module in the chain needs a test plain file.
    """
    chain = plain_file.parse_module_chain(plain_file_name, template_dirs)
    bound = bind_test_plain_files(chain, tests_folders, template_dirs, template_dirs[0])
    if require_test_plain_files:
        check_test_plain_files(chain, bound)
    return ProjectParseResult(chain, bound)
