import io
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence, cast
from urllib.parse import urlparse

import frontmatter
import mistletoe
import mistletoe.block_token
from liquid2 import DictLoader, Environment
from mistletoe.block_token import Heading, List, Paragraph, Quote
from mistletoe.markdown_renderer import BlankLine, Fragment, MarkdownRenderer
from mistletoe.span_token import Emphasis, Link, RawText, SpanToken, Strong
from mistletoe.token import Token
from mistletoe.utils import traverse

from plain_parser import concept_utils, loaders, plain_spec
from plain_parser.exceptions import (
    ImportedModuleWithFunctionalitiesError,
    MissingFunctionalitiesError,
    ModuleDoesNotExistError,
    PlainSyntaxError,
    UnsupportedBase64Content,
)
from plain_parser.liquid_nodes import Plain2CodeIncludeTag, Plain2CodeLoaderMixin
from plain_parser.loaders import find_large_base64_blob

RESOURCE_MARKER = "[resource]"

IMPORT_DIRECTIVE = "import"
REQUIRES_DIRECTIVE = "requires"
PREVIOUS_SYNTAX_HINT = (
    "A functionality is a `# <func-id>` heading followed by its body; the previous syntax is not supported."
)
REQUIRED_CONCEPTS_DIRECTIVE = "required_concepts"
EXPORTED_CONCEPTS_DIRECTIVE = "exported_concepts"

PLAIN_SOURCE_FILE_EXTENSION = ".plain"

PLAIN_SOURCE_TEMPLATE = {
    plain_spec.DEFINITIONS: None,
    plain_spec.NON_FUNCTIONAL_REQUIREMENTS: None,
    plain_spec.TEST_REQUIREMENTS: None,
}


@dataclass
class Functionality:
    """A functionality of ***functional specs***: its func-id and the block tokens of its body."""

    id: str
    line_number: int
    # The statement paragraph and the lists under it, in source order.
    body: list = field(default_factory=list)
    linked_resources: list[dict] = field(default_factory=list)


@dataclass
class PlainFileParseResult:
    plain_source: dict
    plain_source_obj: frontmatter.Post
    required_modules: list[str]
    required_concepts: list[str]


class PlainRenderer(MarkdownRenderer):
    def render_link(self, token: Link) -> Iterable[Fragment]:
        yield from self.embed_span(
            Fragment(f"`{RESOURCE_MARKER}"),
            cast("Iterable[SpanToken]", token.children),
            Fragment("`"),
        )


def get_filename_from_module_name(module_name: str) -> str:
    return f"{module_name}{PLAIN_SOURCE_FILE_EXTENSION}"


def get_module_name_from_filename(filename: str) -> str:
    return filename.replace(PLAIN_SOURCE_FILE_EXTENSION, "")


def remove_quotes(token):
    # If the token has no children, there's nothing to remove.
    if not hasattr(token, "children") or token.children is None:
        return

    # Convert children to a list for easy filtering.
    children_list = list(token.children)

    # Build a filtered list that excludes Quote tokens.
    new_children = []
    for child in children_list:
        if not isinstance(child, Quote):
            # Recursively remove quotes in any nested children.
            remove_quotes(child)
            new_children.append(child)

    # Convert the filtered list back to a tuple (or a list, if you prefer).
    # Mistletoe tokens often expect a tuple, so tuple is safest.
    token.children = tuple(new_children)


def find_linked_resources(tokens, template_dirs, where: str = "") -> list[dict]:
    """The links in the tokens, each checked to be a relative path to an existing file that is not a .plain file.

    ``where`` names the place of the links in error messages, e.g. " in test plain file 'tests/m/f.plain'".
    """
    linked_resources = []
    for link in (link for token in tokens for link in traverse(token, klass=Link)):
        parsed_url = urlparse(link.node.target)
        if parsed_url.scheme != "" or os.path.isabs(link.node.target):
            raise PlainSyntaxError(
                f"Plain syntax error: Only relative links are allowed{where} (text: {link.node.children[0].content}, target: {link.node.target})."
            )

        resolved_target = loaders.resolve_linked_resource(template_dirs, link.node.target)
        if resolved_target is None:
            searched_dirs = "\n".join(f"  {position}. {dir}" for position, dir in enumerate(template_dirs, start=1))
            raise PlainSyntaxError(
                f"Plain syntax error: Link {link.node.target}{where} does not exist. "
                f"Linked resources are looked up relative to the following directories "
                f"(highest to lowest precedence):\n{searched_dirs}"
            )

        if not os.path.isfile(resolved_target):
            raise PlainSyntaxError(
                f"Plain syntax error: Link {link.node.target}{where} must be a file (resolved to {resolved_target})."
            )

        if len(link.node.children) != 1:
            raise PlainSyntaxError(
                f"Plain syntax error: Link{where} must have text specified (link: {link.node.target})."
            )

        linked_resource_file_extension = os.path.splitext(os.path.basename(link.node.target))[1]
        if linked_resource_file_extension == ".plain":
            raise PlainSyntaxError(
                f"Referenced resource '{link.node.target}'{where} is a .plain file. "
                f"Referencing .plain files through Linked Resources is not supported. "
                "Please use the import section to include definitions or implementation/test requirements from another module."
            )

        linked_resources.append({"text": link.node.children[0].content, "target": link.node.target})

    return linked_resources


def check_section_for_linked_resources(section, template_dirs):
    linked_resources = find_linked_resources([section], template_dirs)
    if linked_resources:
        section.linked_resources = linked_resources


def check_for_linked_resources(plain_source, template_dirs):
    for specification_heading in plain_spec.LIST_SECTION_HEADINGS:
        if specification_heading in plain_source and hasattr(plain_source[specification_heading], "children"):
            for requirement in plain_source[specification_heading].children:
                check_section_for_linked_resources(requirement, template_dirs)

    for functionality in plain_source.get(plain_spec.FUNCTIONAL_REQUIREMENTS) or []:
        functionality.linked_resources = find_linked_resources(functionality.body, template_dirs)


def process_section_code_variables(section, code_variables, text_key="markdown"):
    """Put `{{ name }}` placeholders back into the section text and record the code variables it uses."""
    if text_key not in section:
        return

    code_variables_array = []
    for key, value in code_variables.items():
        if key not in section[text_key]:
            continue

        variable_name = next(iter(value))
        section[text_key] = section[text_key].replace(key, f"{{{{ {variable_name} }}}}")

        code_variables_array.append({"name": variable_name, "value": value[variable_name]})

    if code_variables_array:
        section["code_variables"] = code_variables_array


def process_code_variables(plain_source, code_variables):
    for specification_heading in plain_spec.ALLOWED_SPECIFICATION_HEADINGS:
        if specification_heading in plain_source:
            for requirement in plain_source[specification_heading]:
                process_section_code_variables(requirement, code_variables)


def has_functional_specs_section(plain_source) -> bool:
    """Whether the module declares a ***functional specs*** section (even if it is empty)."""
    return plain_spec.FUNCTIONAL_REQUIREMENTS in plain_source


def count_functionalities(plain_source) -> int:
    """Number of functionalities under the ***functional specs*** section (0 if absent or empty)."""
    functionalities = plain_source.get(plain_spec.FUNCTIONAL_REQUIREMENTS)
    return len(functionalities) if functionalities is not None else 0


def validate_functionalities_have_implementation_reqs(plain_source, module_name, has_requires=False) -> None:
    """Raise if the module has functionalities but no implementation reqs are specified.

    ``has_requires`` indicates whether the module depends on another module via ``requires``.
    Unlike ``import``, ``requires`` does not inherit implementation reqs, so a hint is added to
    steer users who expected inheritance.
    """
    implementation_reqs = plain_source[plain_spec.NON_FUNCTIONAL_REQUIREMENTS]
    has_implementation_reqs = (
        implementation_reqs is not None
        and hasattr(implementation_reqs, "children")
        and len(implementation_reqs.children) > 0
    )
    if not has_implementation_reqs:
        message = (
            f"Plain syntax error: Module '{module_name}' defines functionalities but specifies no "
            f"{plain_spec.NON_FUNCTIONAL_REQUIREMENTS}. At least one implementation req is required."
        )
        if has_requires:
            message += (
                " Implementation reqs are not inherited through 'requires' — "
                "add them to this module, or 'import' a module that provides them."
            )
        raise PlainSyntaxError(message)


def get_raw_text(token):
    if isinstance(token, RawText):
        yield token.content
    elif hasattr(token, "children"):
        if token.children is None:
            return
        for child in token.children:
            yield from get_raw_text(child)
    elif hasattr(token, "content"):
        yield token.content
    else:
        raise Exception(f"Unknown token type: {type(token)}")


def render_tokens(renderer: MarkdownRenderer, tokens) -> str:
    """The block tokens rendered as one markdown text, without leading and trailing blank lines."""
    document = mistletoe.Document("")
    document.children = list(tokens)
    return renderer.render(document).strip("\n")


def marshall_functionality(renderer: MarkdownRenderer, functionality: Functionality) -> dict:
    return {
        "id": functionality.id,
        "markdown": render_tokens(renderer, functionality.body),
        "linked_resources": functionality.linked_resources,
        plain_spec.CONFORMANCE_TESTS: [],
        plain_spec.ACCEPTANCE_TESTS: [],
    }


def marshall_plain_source(input_plain_source):
    plain_source = {}
    with PlainRenderer() as renderer:
        for specification_heading in plain_spec.LIST_SECTION_HEADINGS:
            if specification_heading in input_plain_source and hasattr(
                input_plain_source[specification_heading], "children"
            ):
                list_of_requirements = []
                for requirement in input_plain_source[specification_heading].children:
                    requirement_section = {"markdown": renderer.render(requirement).strip()}
                    if hasattr(requirement, "linked_resources"):
                        requirement_section["linked_resources"] = requirement.linked_resources

                    list_of_requirements.append(requirement_section)

                plain_source[specification_heading] = list_of_requirements

        if plain_spec.FUNCTIONAL_REQUIREMENTS in input_plain_source:
            plain_source[plain_spec.FUNCTIONAL_REQUIREMENTS] = [
                marshall_functionality(renderer, functionality)
                for functionality in input_plain_source[plain_spec.FUNCTIONAL_REQUIREMENTS] or []
            ]

    return plain_source


class Plain2CodeDictLoader(Plain2CodeLoaderMixin, DictLoader):
    pass


def render_plain_source(plain_source, loaded_templates, code_variables):
    env = Environment(loader=Plain2CodeDictLoader(loaded_templates))
    env.tags["include"] = Plain2CodeIncludeTag(env)
    env.filters["code_variable"] = plain_spec.code_variable_liquid_filter
    env.filters["prohibited_chars"] = plain_spec.prohibited_chars_liquid_filter

    template = env.from_string(plain_source)

    return template.render(code_variables=code_variables)


def process_imports(
    plain_source: dict,
    imports: list[str],
    code_variables: dict,
    template_dirs: list[str],
    imported_modules: list[str],
    modules_trace: list[str],
) -> list[str]:
    required_concepts = list[str]()
    for module_name in imports:
        if module_name in modules_trace:
            raise PlainSyntaxError(f"Plain syntax error: Circular import detected: {module_name}.")

        if module_name in imported_modules:
            continue

        plain_file_parse_result = parse_plain_file(
            module_name, code_variables, template_dirs, imported_modules, modules_trace
        )

        if has_functional_specs_section(plain_file_parse_result.plain_source):
            raise ImportedModuleWithFunctionalitiesError(
                f"Module '{module_name}' is imported but contains functional specs. "
                f"Imported modules may only provide definitions, implementation reqs, and test reqs — "
                f"use 'requires' instead of 'import' if this module's functionalities should be built on."
            )

        for specification_heading in plain_file_parse_result.plain_source:
            if specification_heading not in plain_spec.ALLOWED_IMPORT_SPECIFICATION_HEADINGS:
                raise PlainSyntaxError(
                    f"Plain syntax error: Invalid specification heading (`{specification_heading}`). Allowed headings: {', '.join(plain_spec.ALLOWED_IMPORT_SPECIFICATION_HEADINGS)}"
                )

            if plain_source[specification_heading] is None:
                plain_source[specification_heading] = plain_file_parse_result.plain_source[specification_heading]
            elif plain_file_parse_result.plain_source[specification_heading] is not None:
                plain_source[specification_heading].children.extend(
                    plain_file_parse_result.plain_source[specification_heading].children
                )

        if REQUIRED_CONCEPTS_DIRECTIVE in plain_file_parse_result.plain_source_obj.metadata:
            for item in plain_file_parse_result.plain_source_obj.metadata[REQUIRED_CONCEPTS_DIRECTIVE]:
                assert isinstance(
                    item, str
                ), f"Syntax error: Invalid {REQUIRED_CONCEPTS_DIRECTIVE} metadata. Expected a string."
                new_concepts, _ = concept_utils.extract_concepts_from_definition(item)
                required_concepts.extend(new_concepts)

            required_concepts.extend(plain_file_parse_result.required_concepts)

        imported_modules.append(module_name)

    return required_concepts


def normalize_line_endings(plain_source_text: str) -> str:
    return plain_source_text.replace("\r\n", "\n").replace("\r", "\n")


def restore_stripped_lines(plain_source_text: str, content: str) -> str:
    stripped_source = plain_source_text.rstrip()
    if not content or not stripped_source.endswith(content):
        return content

    stripped_line_count = stripped_source[: len(stripped_source) - len(content)].count("\n")
    return "\n" * stripped_line_count + content


def syntax_error_at(line_number: int | None, module_name: str | None) -> str:
    """`Syntax error at line N in module 'm'`, without the parts that are not known."""
    where = "Syntax error"
    if line_number is not None:
        where += f" at line {line_number}"
    if module_name:
        where += f" in module '{module_name}'"
    return where


def read_plain_source_metadata(plain_source_text):
    try:
        plain_source_obj = frontmatter.loads(plain_source_text)
    except Exception as e:
        raise PlainSyntaxError(f"Plain syntax error: Invalid frontmatter: {e}")

    for directive in [EXPORTED_CONCEPTS_DIRECTIVE, REQUIRED_CONCEPTS_DIRECTIVE]:
        if directive in plain_source_obj.metadata:
            assert isinstance(
                plain_source_obj.metadata[directive], list
            ), f"Syntax error: Invalid {directive} metadata. Expected a list."
            prepared_metadata = []
            for item in plain_source_obj.metadata[directive]:
                if isinstance(item, dict):
                    for k, v in item.items():
                        prepared_metadata.append(f"- {k}: {v}")
                elif isinstance(item, str):
                    prepared_metadata.append(f"- {item}")
                else:
                    raise PlainSyntaxError(
                        f"Plain syntax error: Invalid {directive} metadata. Expected a dictionary or a string."
                    )

            plain_source_obj.metadata[directive] = prepared_metadata

    return plain_source_obj


TEST_PLAIN_FILE_SECTION_HEADINGS = (plain_spec.CONFORMANCE_TEST_HEADING, plain_spec.ACCEPTANCE_TEST_HEADING)


def check_no_test_sections(plain_source_full_text: str, module_name: str | None) -> None:
    """Raise when a `***conformance tests***` or `***acceptance tests***` marker is anywhere in a spec plain file."""
    for line_number, line in enumerate(plain_source_full_text.split("\n"), start=1):
        for heading in TEST_PLAIN_FILE_SECTION_HEADINGS:
            if line.strip() == f"***{heading}***":
                raise PlainSyntaxError(
                    f"Plain syntax error: {syntax_error_at(line_number, module_name)}: The `{heading}` section is not "
                    f"allowed in a spec plain file; test scenarios live in test plain files."
                )


def section_marker(token: Paragraph) -> str | None:
    """The name in a `***name***` paragraph, or None when the paragraph is not a section marker."""
    paragraph_children = cast("Sequence[Token]", token.children)
    if len(paragraph_children) != 1 or not isinstance(paragraph_children[0], Emphasis):
        return None
    emphasis_children = cast("Sequence[Token]", paragraph_children[0].children)
    if len(emphasis_children) != 1 or not isinstance(emphasis_children[0], Strong):
        return None
    strong_children = cast("Sequence[Token]", emphasis_children[0].children)
    return cast(RawText, strong_children[0]).content


def read_sections(plain_source: dict, document: mistletoe.Document, module_name: str | None) -> None:  # noqa: C901
    """Add the sections of the rendered spec plain file to ``plain_source``.

    A list section holds a mistletoe Document whose children are its list items; ``functional specs`` holds a list
    of Functionality items, one per `# <func-id>` heading, each with every block token up to the next heading or
    section marker. Raise on the first structural error.
    """
    current_specification_heading = None
    current_functionality: Functionality | None = None
    processed_specification_headings = set[str]()
    functionality_lines: dict[str, int] = {}  # func-id to the line of its heading

    def close_functionality():
        if current_functionality is not None and all(isinstance(t, BlankLine) for t in current_functionality.body):
            raise PlainSyntaxError(
                f"Plain syntax error: {syntax_error_at(current_functionality.line_number, module_name)}: "
                f"Functionality `{current_functionality.id}` has no body."
            )

    for token in document.children:
        if isinstance(token, BlankLine):
            # Kept inside a functionality body, so its paragraphs stay apart; meaningless anywhere else.
            if current_functionality is not None:
                current_functionality.body.append(token)
            continue
        token_text = "".join(get_raw_text(token)).strip()
        where = syntax_error_at(token.line_number, module_name)
        in_functional_specs = current_specification_heading == plain_spec.FUNCTIONAL_REQUIREMENTS
        if isinstance(token, Heading):
            if not in_functional_specs:
                raise PlainSyntaxError(
                    f"Plain syntax error: {where}: A `# <func-id>` heading is allowed only in the "
                    f"{plain_spec.FUNCTIONAL_REQUIREMENTS} section (`{token_text}`)."
                )
            if token.level != 1:
                raise PlainSyntaxError(
                    f"Plain syntax error: {where}: Invalid heading level {token.level} (`{token_text}`). "
                    f"A functionality heading is `# <func-id>`."
                )
            if not plain_spec.is_semantic_id(token_text):
                raise PlainSyntaxError(
                    f"Plain syntax error: {where}: Invalid func-id (`{token_text}`). A func-id is lowercase letters "
                    f"and digits, with single hyphens between them."
                )
            if token_text in functionality_lines:
                raise PlainSyntaxError(
                    f"Plain syntax error: {where}: Duplicate func-id `{token_text}`; it is first used at line "
                    f"{functionality_lines[token_text]}."
                )
            close_functionality()
            functionality_lines[token_text] = token.line_number
            current_functionality = Functionality(token_text, token.line_number)
            plain_source[plain_spec.FUNCTIONAL_REQUIREMENTS].append(current_functionality)
        elif isinstance(token, Paragraph):
            specification_heading = section_marker(token)
            if specification_heading is None:
                if not in_functional_specs:
                    raise PlainSyntaxError(f"Plain syntax error: {where}: Invalid specification (`{token_text}`)")
                if current_functionality is None:
                    raise PlainSyntaxError(
                        f"Plain syntax error: {where}: Content before the first `# <func-id>` heading in the "
                        f"{plain_spec.FUNCTIONAL_REQUIREMENTS} section (`{token_text}`). {PREVIOUS_SYNTAX_HINT}"
                    )
                current_functionality.body.append(token)
                continue

            if specification_heading not in plain_spec.ALLOWED_SPECIFICATION_HEADINGS:
                raise PlainSyntaxError(
                    f"Plain syntax error: {where}: Invalid specification heading (`{specification_heading}`). "
                    f"Allowed headings: {', '.join(plain_spec.ALLOWED_SPECIFICATION_HEADINGS)}"
                )

            if specification_heading in processed_specification_headings:
                raise PlainSyntaxError(
                    f"Plain syntax error: {where}: Duplicate specification heading (`{specification_heading}`)"
                )

            if specification_heading == plain_spec.DEFINITIONS and current_specification_heading is not None:
                raise PlainSyntaxError(
                    f"Plain syntax error: {where}: Definitions specification must be the first specification in "
                    f"the section (`{token_text}`)"
                )

            close_functionality()
            current_functionality = None
            current_specification_heading = specification_heading
            if specification_heading == plain_spec.FUNCTIONAL_REQUIREMENTS:
                plain_source[specification_heading] = []
            elif plain_source[specification_heading] is None:
                plain_source[specification_heading] = mistletoe.Document("")

            processed_specification_headings.add(specification_heading)
        elif isinstance(token, List) and not in_functional_specs:
            if current_specification_heading is None:
                raise PlainSyntaxError(f"Plain syntax error: {where}: Missing specification heading (`{token_text}`)")
            plain_source[current_specification_heading].children.extend(token.children)
        elif in_functional_specs:
            # The body of a functionality is free text: a list at any indentation, a code block, or any other block.
            if current_functionality is None:
                raise PlainSyntaxError(
                    f"Plain syntax error: {where}: Content before the first `# <func-id>` heading in the "
                    f"{plain_spec.FUNCTIONAL_REQUIREMENTS} section (`{token_text}`). {PREVIOUS_SYNTAX_HINT}"
                )
            current_functionality.body.append(token)
        else:
            raise PlainSyntaxError(f"Plain syntax error: {where}: Invalid source structure (`{token_text}`)")

    close_functionality()


def parse_plain_source(  # noqa: C901
    plain_source_text: str,
    code_variables: dict,
    template_dirs: list[str],
    imported_modules: list[str],
    modules_trace: list[str],
    module_name: str | None = None,
) -> PlainFileParseResult:
    plain_source_text = normalize_line_endings(plain_source_text)

    plain_source_obj = read_plain_source_metadata(plain_source_text)

    plain_source = PLAIN_SOURCE_TEMPLATE.copy()

    if IMPORT_DIRECTIVE in plain_source_obj.metadata:
        required_concepts = process_imports(
            plain_source,
            plain_source_obj.metadata[IMPORT_DIRECTIVE],
            code_variables,
            template_dirs,
            imported_modules,
            modules_trace,
        )
    else:
        required_concepts = list[str]()

    [_, loaded_templates] = loaders.get_loaded_templates(template_dirs, plain_source_text, module_name)

    plain_source_content = restore_stripped_lines(plain_source_text, plain_source_obj.content)

    plain_source_full_text = render_plain_source(plain_source_content, loaded_templates, code_variables)

    check_no_test_sections(plain_source_full_text, module_name)

    # Parsed inside a renderer context, so blank lines become BlankLine tokens and survive in functionality bodies.
    with PlainRenderer():
        plain_file = mistletoe.Document(io.StringIO(plain_source_full_text))

    remove_quotes(plain_file)

    read_sections(plain_source, plain_file, module_name)

    defined_concepts = set[str]()
    if plain_source[plain_spec.DEFINITIONS] is not None:
        with PlainRenderer() as renderer:
            for token in plain_source[plain_spec.DEFINITIONS].children:
                rendered_token = renderer.render(token)
                new_concepts, _ = concept_utils.extract_concepts_from_definition(rendered_token)
                defined_concepts.update(new_concepts)
                for concept in new_concepts:
                    if concept in required_concepts:
                        required_concepts.remove(concept)

    if EXPORTED_CONCEPTS_DIRECTIVE in plain_source_obj.metadata:
        module_name = modules_trace[-1] if modules_trace else None
        subject = f"Module '{module_name}'" if module_name else "Module"

        for entry in plain_source_obj.metadata[EXPORTED_CONCEPTS_DIRECTIVE]:
            exported_concepts, errors = concept_utils.extract_concepts_from_definition(entry)
            if errors:
                raise PlainSyntaxError(
                    f"Plain syntax error: {subject} exports an invalid concept (`{entry}`). "
                    f"Expected a concept token, e.g. :ConceptName:."
                )

            for exported_concept in exported_concepts:
                if exported_concept in concept_utils.DEFAULT_CONCEPTS:
                    raise PlainSyntaxError(
                        f"Plain syntax error: {subject} cannot export default concept {exported_concept}. "
                        f"Only user-defined concepts can be exported."
                    )

                if exported_concept not in defined_concepts:
                    message = f"Plain syntax error: {subject} exports undefined concept {exported_concept}."
                    if REQUIRES_DIRECTIVE in plain_source_obj.metadata:
                        message += (
                            " An exported concept must be defined in this module's definitions or in an "
                            "imported module; a concept inherited through requires cannot be re-exported."
                        )
                    raise PlainSyntaxError(message)

    required_modules = []
    if REQUIRES_DIRECTIVE in plain_source_obj.metadata:
        required_modules = plain_source_obj.metadata[REQUIRES_DIRECTIVE]

    return PlainFileParseResult(
        plain_source=plain_source,
        plain_source_obj=plain_source_obj,
        required_modules=required_modules,
        required_concepts=required_concepts,
    )


def read_module_plain_source(module_name: str, template_dirs: list[str]) -> str:
    plain_source_text = loaders.open_from(template_dirs, module_name + PLAIN_SOURCE_FILE_EXTENSION)
    if plain_source_text is None:
        raise ModuleDoesNotExistError(f"Module does not exist ({module_name}).")

    blob = find_large_base64_blob(plain_source_text)
    if blob is not None:
        raise UnsupportedBase64Content(
            f"Module '{module_name}' contains a base64-encoded blob ({len(blob)} characters) "
            "inlined in the specification. This is not supported. "
            "Remove the base64 data from the .plain file or if necessary, "
            "include the binary file path in the specification."
        )

    return plain_source_text


def parse_plain_file(
    module_name: str,
    code_variables: dict,
    template_dirs: list[str],
    imported_modules: list[str],
    modules_trace: list[str],
) -> PlainFileParseResult:  # noqa: C901
    plain_source_text = read_module_plain_source(module_name, template_dirs)

    return parse_plain_source(
        plain_source_text,
        code_variables,
        template_dirs,
        imported_modules,
        modules_trace + [module_name],
        module_name=module_name,
    )


@dataclass
class RequiredModule:
    """A required module as parsed by the requires walk; validated once the top module is complete."""

    parse_result: PlainFileParseResult
    # Definitions exported to this module by the modules it requires.
    ancestor_exported_definitions: list[mistletoe.block_token.token]
    code_variables: dict
    # Definitions this module exports to the modules that require it.
    exported_definitions: list[mistletoe.block_token.token]
    # Marshalled plain source tree, set once the module is validated.
    tree: dict | None = None


def process_required_modules(
    required_modules: list[str],
    template_dirs: list[str],
    all_required_modules: list[str],
    modules_trace: list[str],
    required: dict[str, RequiredModule],
) -> list[mistletoe.block_token.token]:
    """Parse every required module, deepest first, without validating it.

    Records each module in ``required`` the first time it is reached (deepest ancestors first) and returns
    the exported definitions of the directly required modules.
    """
    exported_definitions = list[mistletoe.block_token.token]()
    for module_name in required_modules:
        if module_name in modules_trace:
            raise PlainSyntaxError(f"Plain syntax error: Circular required module detected: {module_name}.")

        if len(all_required_modules) > 0 and module_name == all_required_modules[-1]:
            # Already processed as an earlier entry; its exports are still visible to this module.
            exported_definitions.extend(required[module_name].exported_definitions)
            continue

        code_variables: dict = {}
        plain_file_parse_result = parse_plain_file(
            module_name, code_variables, template_dirs, imported_modules=[], modules_trace=[]
        )

        ancestor_exported_definitions: list[mistletoe.block_token.token] = []
        if len(plain_file_parse_result.required_modules) == 0:
            if len(all_required_modules) > 0:
                # For now we require that there is fixed order how required modules are dependent.
                # In the future we will support the cases where required modules can be rendered independently
                # and then merged (somehow).
                raise PlainSyntaxError(
                    f"Plain syntax error: There must be a fixed order how required modules are dependent ({module_name})."
                )
        else:
            ancestor_exported_definitions = process_required_modules(
                plain_file_parse_result.required_modules,
                template_dirs,
                all_required_modules,
                modules_trace + [module_name],
                required,
            )

        own_exported_definitions = list[mistletoe.block_token.token]()
        if EXPORTED_CONCEPTS_DIRECTIVE in plain_file_parse_result.plain_source_obj.metadata:
            exported_concepts = list[str]()
            for concept in plain_file_parse_result.plain_source_obj.metadata[EXPORTED_CONCEPTS_DIRECTIVE]:
                exported_concepts.extend(concept_utils.extract_concepts_from_definition(concept)[0])

            with PlainRenderer() as renderer:
                for exported_concept in exported_concepts:
                    own_exported_definitions.extend(
                        concept_utils.find_concept_definitions_in_plain_source(
                            exported_concept, plain_file_parse_result.plain_source, renderer
                        )
                    )
        required[module_name] = RequiredModule(
            plain_file_parse_result, ancestor_exported_definitions, code_variables, own_exported_definitions
        )
        exported_definitions.extend(own_exported_definitions)

        all_required_modules.append(module_name)

    return exported_definitions


def validate_required_modules(
    required_modules: list[str], required: dict[str, RequiredModule], template_dirs: list[str]
) -> None:
    """Validate recorded required modules top-down, in listed order, each module once."""
    for module_name in required_modules:
        module = required[module_name]
        if module.tree is not None:
            continue

        validate_module_structure(module.parse_result, module_name)
        module.tree = validate_and_build_module_tree(
            module.parse_result, module_name, module.ancestor_exported_definitions, module.code_variables, template_dirs
        )
        validate_required_modules(module.parse_result.required_modules, required, template_dirs)


def process_exported_definitions(plain_source: dict, exported_definitions: list[mistletoe.block_token.token]) -> None:
    if len(exported_definitions) == 0:
        return

    if plain_source[plain_spec.DEFINITIONS] is None:
        plain_source[plain_spec.DEFINITIONS] = mistletoe.Document("")

    with PlainRenderer() as renderer:
        for exported_definition in exported_definitions:
            add_defintion = True

            exported_rendered_definition = renderer.render(exported_definition).strip()
            for definition in plain_source[plain_spec.DEFINITIONS].children:
                rendered_definition = renderer.render(definition).strip()
                if exported_rendered_definition == rendered_definition:
                    add_defintion = False
                    break

            if add_defintion:
                plain_source[plain_spec.DEFINITIONS].children.append(exported_definition)


def validate_module_structure(plain_file_parse_result: PlainFileParseResult, module_name: str) -> None:
    """Required concepts defined, functional specs present and non-empty, implementation reqs present."""
    if len(plain_file_parse_result.required_concepts) > 0:
        missing_required_concepts_msg = "Missing required concepts: "
        missing_required_concepts_msg += ", ".join(plain_file_parse_result.required_concepts)
        raise PlainSyntaxError(
            f"Plain syntax error: Not all required concepts were defined. {missing_required_concepts_msg}."
        )

    if not has_functional_specs_section(plain_file_parse_result.plain_source):
        # No ***functional specs*** section at all: valid as an import, but not renderable. Usage error.
        raise MissingFunctionalitiesError(
            f"Module '{module_name}' does not have any functionality specified. "
            f"At least one functionality is required for rendering."
        )

    if count_functionalities(plain_file_parse_result.plain_source) == 0:
        # ***functional specs*** section present but empty: invalid in every role. Syntax error.
        raise PlainSyntaxError(
            f"Plain syntax error: Module '{module_name}' has a '{plain_spec.FUNCTIONAL_REQUIREMENTS}' section "
            f"without a `# <func-id>` heading. {PREVIOUS_SYNTAX_HINT}"
        )

    validate_functionalities_have_implementation_reqs(
        plain_file_parse_result.plain_source,
        module_name,
        has_requires=bool(plain_file_parse_result.required_modules),
    )


def validate_and_build_module_tree(
    plain_file_parse_result: PlainFileParseResult,
    module_name: str,
    exported_definitions: list[mistletoe.block_token.token],
    code_variables: dict,
    template_dirs: list[str],
) -> dict:
    """Merge exported definitions, validate linked resources and concepts, and return the marshalled plain source
    tree."""
    process_exported_definitions(plain_file_parse_result.plain_source, exported_definitions)

    check_for_linked_resources(plain_file_parse_result.plain_source, template_dirs)

    marshalled_plain_source = marshall_plain_source(plain_file_parse_result.plain_source)

    process_code_variables(marshalled_plain_source, code_variables)

    validation_errors = concept_utils.validate_concepts(marshalled_plain_source)
    if len(validation_errors) > 0:
        errors_msg = "\n".join(validation_errors)
        msg = f"Found {len(validation_errors)} errors in the plain file:\n{errors_msg}"
        raise PlainSyntaxError(f"Plain syntax error: {msg}")

    if plain_spec.DEFINITIONS in marshalled_plain_source:
        concept_utils.sort_definitions(marshalled_plain_source[plain_spec.DEFINITIONS])

    return marshalled_plain_source


def _parse_module(
    plain_source_file_name: str, template_dirs: list[str]
) -> tuple[str, dict, list[str], list[tuple[str, dict]]]:
    plain_source_file_path = Path(plain_source_file_name)
    if plain_source_file_path.suffix != PLAIN_SOURCE_FILE_EXTENSION:
        raise PlainSyntaxError(
            f"Plain syntax error: Invalid plain file extension: {plain_source_file_path.suffix}. Expected: {PLAIN_SOURCE_FILE_EXTENSION}."
        )

    module_name = (
        plain_source_file_path.stem
        if plain_source_file_path.is_absolute()
        else plain_source_file_path.with_suffix("").as_posix()
    )

    # code_variables are populated when liquid templating is applied and consumed by process_code_variables
    # once the plain source is marshalled.
    code_variables: dict = {}

    plain_file_parse_result = parse_plain_file(
        module_name,
        code_variables,
        template_dirs,
        imported_modules=[],
        modules_trace=[],
    )

    # Check the top module's structure, walk its requires, finish the top module's checks, then validate
    # every required module top-down.
    validate_module_structure(plain_file_parse_result, module_name)

    required: dict[str, RequiredModule] = {}
    exported_definitions = process_required_modules(
        plain_file_parse_result.required_modules,
        template_dirs=template_dirs,
        all_required_modules=[],
        modules_trace=[],
        required=required,
    )

    marshalled_plain_source = validate_and_build_module_tree(
        plain_file_parse_result, module_name, exported_definitions, code_variables, template_dirs
    )

    validate_required_modules(plain_file_parse_result.required_modules, required, template_dirs)
    # The walk records modules deepest first, which is the chain order.
    chain = [(chain_module_name, module.tree) for chain_module_name, module in required.items()]

    return module_name, marshalled_plain_source, plain_file_parse_result.required_modules, chain


def plain_file_parser(plain_source_file_name: str, template_dirs: list[str]) -> tuple[str, dict, list[str]]:
    """Parse a module, validating it and every module in its ``requires`` chain."""
    module_name, marshalled_plain_source, required_modules, _ = _parse_module(plain_source_file_name, template_dirs)
    return module_name, marshalled_plain_source, required_modules


def parse_module_chain(plain_file_name: str, template_dirs: list[str]) -> list[tuple[str, dict]]:
    """Parse a module and every module in its ``requires`` chain.

    Returns ``(module name, marshalled plain source tree)`` pairs: every required module
    first, deepest ancestors first, then the module itself. A module reached through more
    than one ``requires`` path appears once, at its first (deepest) position.
    """
    module_name, marshalled_plain_source, _, chain = _parse_module(plain_file_name, template_dirs)
    return chain + [(module_name, marshalled_plain_source)]
