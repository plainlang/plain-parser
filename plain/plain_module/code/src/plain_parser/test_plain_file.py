"""Parsing of test plain files into their conformance and acceptance scenarios."""

from dataclasses import dataclass, field

import frontmatter
import yaml

from plain_parser import concept_utils, loaders, plain_file, plain_spec
from plain_parser.exceptions import PlainSyntaxError

MODULE_KEY = "module"
FUNC_ID_KEY = "func_id"

_SECTION_KEYS = {
    plain_spec.CONFORMANCE_TEST_HEADING: plain_spec.CONFORMANCE_TESTS,
    plain_spec.ACCEPTANCE_TEST_HEADING: plain_spec.ACCEPTANCE_TESTS,
}
_FENCE_MARKERS = ("```", "~~~")


@dataclass
class Scenario:
    id: str
    line_number: int
    text: str = ""
    linked_resources: list[dict] = field(default_factory=list)
    code_variables: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        result: dict = {"id": self.id, "text": self.text, "linked_resources": list(self.linked_resources)}
        if self.code_variables:
            result["code_variables"] = list(self.code_variables)
        return result


@dataclass
class TestPlainFile:
    __test__ = False  # not a pytest test class

    name: str
    module: str
    func_id: str
    conformance_tests: list[Scenario]
    acceptance_tests: list[Scenario]

    @property
    def scenarios(self) -> list[Scenario]:
        return self.conformance_tests + self.acceptance_tests


def is_test_plain_file(metadata: dict) -> bool:
    return isinstance(metadata, dict) and MODULE_KEY in metadata and FUNC_ID_KEY in metadata


def _where(line: int, name: str) -> str:
    return f"Syntax error at line {line} in test plain file '{name}'"


def _error(line: int, name: str, message: str) -> PlainSyntaxError:
    return PlainSyntaxError(f"Plain syntax error: {_where(line, name)}: {message}")


def _read_frontmatter(text: str, name: str) -> frontmatter.Post:
    try:
        post = frontmatter.loads(text)
    except yaml.YAMLError as error:
        raise PlainSyntaxError(
            f"Plain syntax error: Test plain file '{name}' has invalid frontmatter: {error}"
        ) from error
    metadata = post.metadata if isinstance(post.metadata, dict) else {}
    for key in (MODULE_KEY, FUNC_ID_KEY):
        if key not in metadata:
            raise PlainSyntaxError(
                f"Plain syntax error: Test plain file '{name}' has no `{key}:` key in its frontmatter."
            )
    for key in (MODULE_KEY, FUNC_ID_KEY):
        value = metadata[key]
        if not isinstance(value, str) or not value:
            raise PlainSyntaxError(
                f"Plain syntax error: Test plain file '{name}': the frontmatter key `{key}:` must be a non-empty "
                "string."
            )
    for key in metadata:
        if key not in (MODULE_KEY, FUNC_ID_KEY):
            raise PlainSyntaxError(
                f"Plain syntax error: Test plain file '{name}' has the frontmatter key `{key}:`; only `module:` and "
                "`func_id:` are allowed."
            )
    return post


def _fence_marker(line: str) -> str | None:
    stripped = line.lstrip(" ")
    for marker in _FENCE_MARKERS:
        if stripped.startswith(marker):
            return marker
    return None


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith(">")


def _is_heading(line: str) -> bool:
    return line.startswith("# ") or line.rstrip() == "#"


class _ScenarioReader:
    def __init__(self, name: str):
        self.name = name
        self.sections: dict[str, list[Scenario]] = {}
        self.section: str | None = None
        self.scenario: Scenario | None = None
        self.lines: list[str] = []
        self.fence: str | None = None
        self.first_lines: dict[str, int] = {}

    def close_scenario(self) -> None:
        scenario = self.scenario
        if scenario is None:
            return
        if self.fence is not None:
            raise _error(
                scenario.line_number, self.name, f"Scenario `{scenario.id}` has a code fence that is not closed."
            )
        lines = self.lines
        while lines and not lines[0].strip():
            lines = lines[1:]
        while lines and not lines[-1].strip():
            lines = lines[:-1]
        if not lines:
            raise _error(scenario.line_number, self.name, f"Scenario `{scenario.id}` has no text.")
        scenario.text = "\n".join(lines)
        self.scenario = None
        self.lines = []

    def read(self, text: str) -> None:
        for number, line in enumerate(text.split("\n"), start=1):
            self.read_line(number, line)
        self.close_scenario()

    def read_line(self, number: int, line: str) -> None:
        if self.fence is not None:
            self.lines.append(line)
            if _fence_marker(line) == self.fence:
                self.fence = None
            return
        if line.startswith("***"):
            self.read_section_line(number, line)
            return
        if _is_comment(line):
            return
        if _is_heading(line):
            self.read_heading(number, line[1:].strip())
            return
        if not line.strip():
            if self.scenario is not None:
                self.lines.append(line)
            return
        if self.section is None:
            raise _error(
                number,
                self.name,
                f"Content before the first section (`{line.strip()}`); a test plain file starts with "
                "`***conformance tests***`.",
            )
        if self.scenario is None:
            heading = next(h for h, key in _SECTION_KEYS.items() if key == self.section)
            raise _error(
                number,
                self.name,
                f"Content before the first `# <scenario-id>` heading in the `{heading}` section (`{line.strip()}`).",
            )
        marker = _fence_marker(line)
        if marker is not None:
            self.fence = marker
        self.lines.append(line)

    def read_section_line(self, number: int, line: str) -> None:
        stripped = line.strip()
        heading = stripped[3:-3] if stripped.endswith("***") and len(stripped) > 6 else None
        if heading not in _SECTION_KEYS:
            raise _error(
                number,
                self.name,
                f"Invalid section (`{stripped}`). A test plain file has the sections `***conformance tests***` and "
                "`***acceptance tests***`, in this order.",
            )
        self.close_scenario()
        key = _SECTION_KEYS[heading]
        if key in self.sections:
            raise _error(number, self.name, f"Duplicate section `***{heading}***`.")
        if key == plain_spec.ACCEPTANCE_TESTS and plain_spec.CONFORMANCE_TESTS not in self.sections:
            raise _error(
                number,
                self.name,
                f"The `***{heading}***` section must come after `***{plain_spec.CONFORMANCE_TEST_HEADING}***`.",
            )
        self.sections[key] = []
        self.section = key

    def read_heading(self, number: int, scenario_id: str) -> None:
        if self.section is None:
            raise _error(
                number,
                self.name,
                f"Scenario `{scenario_id}` comes before the first section; a test plain file starts with "
                "`***conformance tests***`.",
            )
        if not plain_spec.is_semantic_id(scenario_id):
            raise _error(
                number,
                self.name,
                f"Invalid scenario-id (`{scenario_id}`). A scenario-id is lowercase letters and digits, with single "
                "hyphens between them.",
            )
        if scenario_id in self.first_lines:
            raise _error(
                number,
                self.name,
                f"Duplicate scenario-id `{scenario_id}`; it is first used at line {self.first_lines[scenario_id]}.",
            )
        self.close_scenario()
        self.first_lines[scenario_id] = number
        self.scenario = Scenario(id=scenario_id, line_number=number)
        self.sections[self.section].append(self.scenario)


def _resolve_links(scenario: Scenario, name: str, template_dirs: list[str]) -> None:
    document = plain_file._parse_markdown(scenario.text)
    where = f" in test plain file '{name}', scenario `{scenario.id}`"
    scenario.linked_resources = plain_file.find_linked_resources(document.children, template_dirs, where)


def _record_code_variables(scenario: Scenario, code_variables: dict) -> None:
    item: dict = {"text": scenario.text}
    plain_file.process_section_code_variables([item], code_variables, text_key="text")
    scenario.text = item["text"]
    scenario.code_variables = list(item.get("code_variables", []))


def parse_test_plain_file_source(
    plain_source_text: str, name: str, template_dirs: list[str], code_variables: dict
) -> TestPlainFile:
    """Parse the text of a test plain file, shown by ``name`` in messages, into its scenarios."""
    text = plain_file.normalize_line_endings(plain_source_text)
    post = _read_frontmatter(text, name)
    content = plain_file.restore_stripped_lines(text, post.content)

    if code_variables is None:
        code_variables = {}
    _, loaded_templates = loaders.get_loaded_templates(template_dirs, content, name)
    rendered = plain_file.render_plain_source(content, loaded_templates, code_variables)

    reader = _ScenarioReader(name)
    reader.read(rendered)
    for heading, key in _SECTION_KEYS.items():
        if key not in reader.sections:
            raise PlainSyntaxError(f"Plain syntax error: Test plain file '{name}' has no `***{heading}***` section.")

    for scenarios in reader.sections.values():
        for scenario in scenarios:
            _resolve_links(scenario, name, template_dirs)
            _record_code_variables(scenario, code_variables)

    return TestPlainFile(
        name=name,
        module=post.metadata[MODULE_KEY],
        func_id=post.metadata[FUNC_ID_KEY],
        conformance_tests=reader.sections[plain_spec.CONFORMANCE_TESTS],
        acceptance_tests=reader.sections[plain_spec.ACCEPTANCE_TESTS],
    )


def validate_scenario_concepts(test_plain_file: TestPlainFile, concepts: set[str]) -> list[str]:
    """Return one error per scenario and distinct concept that is neither visible nor predefined."""
    errors = []
    for scenario in test_plain_file.scenarios:
        reported: set[str] = set()
        for concept in concept_utils.extract_concepts_from_spec_text(scenario.text):
            if concept in concepts or concept in concept_utils.DEFAULT_CONCEPTS or concept in reported:
                continue
            reported.add(concept)
            errors.append(
                f"{_where(scenario.line_number, test_plain_file.name)}: Concept {concept} used in scenario "
                f"`{scenario.id}` is not defined in module '{test_plain_file.module}'."
            )
    return errors
