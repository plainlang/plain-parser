"""Test plain files: the conformance and acceptance scenarios of one functionality.

A test plain file binds to a functionality with the frontmatter keys ``module`` and ``func_id``. It holds a
``***conformance tests***`` section followed by an ``***acceptance tests***`` section; each scenario in them is a
`# <scenario-id>` heading followed by free text, which is kept verbatim.
"""

import io
from dataclasses import dataclass, field

import frontmatter
import mistletoe

from plain_parser import concept_utils, loaders, plain_file, plain_spec
from plain_parser.exceptions import PlainSyntaxError

MODULE_KEY = "module"
FUNC_ID_KEY = "func_id"
FRONTMATTER_KEYS = (MODULE_KEY, FUNC_ID_KEY)
SECTION_HEADINGS = (plain_spec.CONFORMANCE_TEST_HEADING, plain_spec.ACCEPTANCE_TEST_HEADING)


@dataclass
class Scenario:
    id: str
    line_number: int
    # The body as written, without `>` comment lines and without leading and trailing blank lines.
    text: str = ""
    linked_resources: list[dict] = field(default_factory=list)
    code_variables: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        entry = {"id": self.id, "text": self.text, "linked_resources": self.linked_resources}
        if self.code_variables:
            entry["code_variables"] = self.code_variables
        return entry


@dataclass
class TestPlainFile:
    name: str  # The path of the file as shown in messages.
    module: str
    func_id: str
    conformance_tests: list[Scenario]
    acceptance_tests: list[Scenario]

    @property
    def scenarios(self) -> list[Scenario]:
        return [*self.conformance_tests, *self.acceptance_tests]


def is_test_plain_file(metadata: dict) -> bool:
    """Whether a frontmatter binds its file to a functionality, which makes the file a test plain file."""
    return all(key in metadata for key in FRONTMATTER_KEYS)


def _error(message: str) -> PlainSyntaxError:
    return PlainSyntaxError(f"Plain syntax error: {message}")


def _at(line_number: int, name: str) -> str:
    return f"Syntax error at line {line_number} in test plain file '{name}'"


def read_metadata(plain_source_text: str, name: str) -> frontmatter.Post:
    """The frontmatter and content of a test plain file; raise unless the keys are exactly module and func_id."""
    try:
        post = frontmatter.loads(plain_source_text)
    except Exception as e:
        raise _error(f"Test plain file '{name}' has invalid frontmatter: {e}")

    for key in FRONTMATTER_KEYS:
        if key not in post.metadata:
            raise _error(f"Test plain file '{name}' has no `{key}:` key in its frontmatter.")
        value = post.metadata[key]
        if not isinstance(value, str) or not value.strip():
            raise _error(f"Test plain file '{name}': the frontmatter key `{key}:` must be a non-empty string.")

    for key in post.metadata:
        if key not in FRONTMATTER_KEYS:
            raise _error(
                f"Test plain file '{name}' has the frontmatter key `{key}:`; only `module:` and `func_id:` are allowed."
            )

    return post


def _trim_blank_lines(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def read_scenarios(rendered_text: str, name: str) -> dict[str, list[Scenario]]:  # noqa: C901
    """The scenarios of the rendered content, keyed by section heading; raise on the first structural error."""
    sections: dict[str, list[Scenario]] = {}
    current_section: str | None = None
    current: Scenario | None = None
    body: list[str] = []
    fence: str | None = None  # The marker of the open fenced code block (``` or ~~~), None outside one.
    heading_lines: dict[str, int] = {}  # scenario-id to the line of its heading

    def close_scenario() -> None:
        if current is None:
            return
        if fence is not None:
            raise _error(
                f"{_at(current.line_number, name)}: Scenario `{current.id}` has a code fence that is not closed."
            )
        lines = _trim_blank_lines(body)
        if not lines:
            raise _error(f"{_at(current.line_number, name)}: Scenario `{current.id}` has no text.")
        current.text = "\n".join(lines)

    for line_number, line in enumerate(rendered_text.split("\n"), start=1):
        where = _at(line_number, name)
        # Inside a fenced code block every line is body text: a `# ` line is not a heading there, a `***` line is
        # not a section marker, and a `>` line is not a comment.
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            if current is not None:
                body.append(line)
                continue
        elif fence is not None and current is not None:
            body.append(line)
            continue

        if line.startswith("***"):
            heading = line.strip()[3:-3] if line.strip().endswith("***") and len(line.strip()) > 6 else None
            if heading not in SECTION_HEADINGS:
                raise _error(
                    f"{where}: Invalid section (`{line.strip()}`). A test plain file has the sections "
                    f"`***{SECTION_HEADINGS[0]}***` and `***{SECTION_HEADINGS[1]}***`, in this order."
                )
            if heading in sections:
                raise _error(f"{where}: Duplicate section `***{heading}***`.")
            if heading != SECTION_HEADINGS[len(sections)]:
                raise _error(f"{where}: The `***{heading}***` section must come after `***{SECTION_HEADINGS[0]}***`.")
            close_scenario()
            current = None
            current_section = heading
            sections[heading] = []
        elif line.startswith("# ") or line == "#":
            scenario_id = line[1:].strip()
            if current_section is None:
                raise _error(
                    f"{where}: Scenario `{scenario_id}` comes before the first section; a test plain file starts "
                    f"with `***{SECTION_HEADINGS[0]}***`."
                )
            if not plain_spec.is_semantic_id(scenario_id):
                raise _error(
                    f"{where}: Invalid scenario-id (`{scenario_id}`). A scenario-id is lowercase letters and digits, "
                    f"with single hyphens between them."
                )
            if scenario_id in heading_lines:
                raise _error(
                    f"{where}: Duplicate scenario-id `{scenario_id}`; it is first used at line "
                    f"{heading_lines[scenario_id]}."
                )
            close_scenario()
            current = Scenario(scenario_id, line_number)
            body = []
            heading_lines[scenario_id] = line_number
            sections[current_section].append(current)
        elif line.lstrip().startswith(">"):
            continue
        elif current is not None:
            body.append(line)
        elif line.strip():
            if current_section is None:
                raise _error(
                    f"{where}: Content before the first section (`{line.strip()}`); a test plain file starts with "
                    f"`***{SECTION_HEADINGS[0]}***`."
                )
            raise _error(
                f"{where}: Content before the first `# <scenario-id>` heading in the `{current_section}` section "
                f"(`{line.strip()}`)."
            )

    close_scenario()

    for heading in SECTION_HEADINGS:
        if heading not in sections:
            raise _error(f"Test plain file '{name}' has no `***{heading}***` section.")

    return sections


def find_scenario_linked_resources(scenario: Scenario, template_dirs: list[str], name: str) -> list[dict]:
    document = mistletoe.Document(io.StringIO(scenario.text))
    where = f" in test plain file '{name}', scenario `{scenario.id}`"
    return plain_file.find_linked_resources(document.children, template_dirs, where)


def parse_test_plain_file_source(
    plain_source_text: str, name: str, template_dirs: list[str], code_variables: dict
) -> TestPlainFile:
    """Parse the text of a test plain file. Liquid runs as on a spec plain file, with the same template directories;
    every link in a scenario is resolved against them. Concepts are not checked here, see
    validate_scenario_concepts."""
    plain_source_text = plain_file.normalize_line_endings(plain_source_text)

    post = read_metadata(plain_source_text, name)

    _, loaded_templates = loaders.get_loaded_templates(template_dirs, plain_source_text, name)

    content = plain_file.restore_stripped_lines(plain_source_text, post.content)

    rendered_text = plain_file.render_plain_source(content, loaded_templates, code_variables)

    sections = read_scenarios(rendered_text, name)

    for scenario in [*sections[SECTION_HEADINGS[0]], *sections[SECTION_HEADINGS[1]]]:
        scenario.linked_resources = find_scenario_linked_resources(scenario, template_dirs, name)
        entry = {"text": scenario.text}
        plain_file.process_section_code_variables(entry, code_variables, "text")
        scenario.text = entry["text"]
        scenario.code_variables = entry.get("code_variables", [])

    return TestPlainFile(
        name,
        str(post.metadata[MODULE_KEY]),
        str(post.metadata[FUNC_ID_KEY]),
        sections[SECTION_HEADINGS[0]],
        sections[SECTION_HEADINGS[1]],
    )


def validate_scenario_concepts(test_plain_file: TestPlainFile, concepts: set[str]) -> list[str]:
    """One message per concept used in a scenario that is neither in ``concepts`` nor predefined."""
    errors = []
    for scenario in test_plain_file.scenarios:
        for concept in dict.fromkeys(concept_utils.extract_concepts_from_spec_text(scenario.text)):
            if concept not in concepts and concept not in concept_utils.DEFAULT_CONCEPTS:
                errors.append(
                    f"{_at(scenario.line_number, test_plain_file.name)}: Concept {concept} used in scenario "
                    f"`{scenario.id}` is not defined in module '{test_plain_file.module}'."
                )
    return errors
