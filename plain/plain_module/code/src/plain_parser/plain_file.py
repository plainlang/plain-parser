"""Parsing of spec plain files into plain source trees, with imports, links, code variables and requires chains."""

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import frontmatter
import yaml
from liquid2 import DictLoader
from mistletoe import Document, block_token, span_token
from mistletoe.markdown_renderer import BlankLine, Fragment, MarkdownRenderer

from plain_parser import concept_utils, loaders, plain_spec
from plain_parser.exceptions import (
    ImportedModuleWithFunctionalitiesError,
    MissingFunctionalitiesError,
    ModuleDoesNotExistError,
    PlainSyntaxError,
    UnsupportedBase64Content,
)
from plain_parser.liquid_nodes import Plain2CodeLoaderMixin

RESOURCE_MARKER = "[resource]"
IMPORT_DIRECTIVE = "import"
REQUIRES_DIRECTIVE = "requires"
REQUIRED_CONCEPTS_DIRECTIVE = "required_concepts"
EXPORTED_CONCEPTS_DIRECTIVE = "exported_concepts"
PLAIN_SOURCE_FILE_EXTENSION = ".plain"

_SECTION_LINE = re.compile(r"\*\*\*(.+?)\*\*\*")
_TEST_SECTION_HEADINGS = [plain_spec.CONFORMANCE_TEST_HEADING, plain_spec.ACCEPTANCE_TEST_HEADING]
_PREVIOUS_SYNTAX_HINT = (
    "A functionality is a `# <func-id>` heading followed by its body; the previous syntax is not supported."
)


@dataclass
class PlainFileParseResult:
    plain_source: dict
    plain_source_obj: frontmatter.Post
    required_modules: list[str] = field(default_factory=list)
    required_concepts: list[str] = field(default_factory=list)


class PlainMarkdownRenderer(MarkdownRenderer):
    """Markdown renderer that writes every link as a code span holding ``[resource]`` and the link text."""

    def render_link(self, token: span_token.Link):
        yield Fragment("`" + RESOURCE_MARKER + _span_text(token) + "`")


def _span_text(token) -> str:
    if hasattr(token, "content") and not getattr(token, "children", None):
        return token.content
    return "".join(_span_text(child) for child in getattr(token, "children", None) or [])


def _render(tokens) -> str:
    with PlainMarkdownRenderer() as renderer:
        return "".join(renderer.render(token) for token in tokens)


def _parse_markdown(text: str) -> Document:
    with PlainMarkdownRenderer():
        document = Document(text)
    _remove_comments(document)
    return document


def _remove_comments(token) -> None:
    """Remove every block quote token, nested ones included: they are comment lines."""
    children = getattr(token, "_children", None)
    if children is None or isinstance(token, span_token.SpanToken):
        return
    kept = [child for child in children if not isinstance(child, block_token.Quote)]
    if len(kept) != len(children):
        token.children = kept
    for child in kept:
        if isinstance(child, block_token.BlockToken):
            _remove_comments(child)


# Module names


def get_filename_from_module_name(module_name: str) -> str:
    return module_name + PLAIN_SOURCE_FILE_EXTENSION


def get_module_name_from_filename(filename: str) -> str:
    return filename.replace(PLAIN_SOURCE_FILE_EXTENSION, "")


def normalize_line_endings(plain_source_text: str) -> str:
    return plain_source_text.replace("\r\n", "\n").replace("\r", "\n")


def restore_stripped_lines(plain_source_text: str, content: str) -> str:
    """Prefix ``content`` with the lines that precede it in ``plain_source_text``, so line numbers match the file."""
    stripped = content.strip("\n")
    if not stripped:
        return content
    index = plain_source_text.rfind(stripped)
    if index < 0:
        return content
    line_start = plain_source_text.rfind("\n", 0, index) + 1
    return "\n" * plain_source_text.count("\n", 0, line_start) + plain_source_text[line_start:]


def _where(line: int | None, module_name: str | None) -> str:
    where = "Syntax error"
    if line is not None:
        where += f" at line {line}"
    if module_name:
        where += f" in module '{module_name}'"
    return where


def _syntax_error(line, module_name, message) -> PlainSyntaxError:
    return PlainSyntaxError(f"Plain syntax error: {_where(line, module_name)}: {message}")


# Liquid


class _TemplateDictLoader(Plain2CodeLoaderMixin, DictLoader):
    """Loader over already loaded templates that indents included templates."""


def render_plain_source(plain_source, loaded_templates, code_variables) -> str:
    """Render ``plain_source`` with Liquid over ``loaded_templates``, recording code variables in ``code_variables``."""
    environment = loaders.create_environment(_TemplateDictLoader(dict(loaded_templates)))
    global_data = {"code_variables": code_variables} if code_variables is not None else None
    return loaders.render_liquid(environment, plain_source, None, global_data)


# Sections


def _block_text(token) -> str:
    if isinstance(token, (block_token.CodeFence, block_token.BlockCode)):
        return token.children[0].content.strip() if token.children else ""
    if isinstance(token, (block_token.List, block_token.ListItem)):
        children = [child for child in token.children or [] if not isinstance(child, BlankLine)]
        return _block_text(children[0]) if children else ""
    if isinstance(token, block_token.Heading):
        return _span_text(token).strip()
    return _render([token]).strip()


def _section_name(token, lines: list[str]) -> str | None:
    if not isinstance(token, block_token.Paragraph):
        return None
    line = token.line_number
    if line is None or line > len(lines):
        return None
    text = _render([token]).strip()
    if "\n" in text:
        return None
    match = _SECTION_LINE.fullmatch(lines[line - 1].strip())
    return match.group(1) if match else None


def _check_test_sections(text: str, module_name: str | None) -> None:
    for number, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        for heading in _TEST_SECTION_HEADINGS:
            if stripped == f"***{heading}***":
                raise _syntax_error(
                    number,
                    module_name,
                    f"The `{heading}` section is not allowed in a spec plain file; test scenarios live in test plain "
                    "files.",
                )


def _new_section_document() -> Document:
    with PlainMarkdownRenderer():
        document = Document("")
    document.children = []
    return document


def _parse_sections(text: str, module_name: str | None) -> dict:
    lines = text.split("\n")
    document = _parse_markdown(text)
    sections: dict = {}
    current: str | None = None
    functionality: dict | None = None
    first_lines: dict[str, int] = {}

    def close_functionality() -> None:
        if functionality is None:
            return
        if not any(not isinstance(token, BlankLine) for token in functionality["tokens"]):
            raise _syntax_error(
                functionality["line_number"], module_name, f"Functionality `{functionality['id']}` has no body."
            )

    for token in document.children:
        line = token.line_number
        name = _section_name(token, lines)
        if name is not None:
            close_functionality()
            functionality = None
            if name not in plain_spec.ALLOWED_SPECIFICATION_HEADINGS:
                raise _syntax_error(
                    line,
                    module_name,
                    f"Invalid specification heading (`{name}`). Allowed headings: "
                    + ", ".join(plain_spec.ALLOWED_SPECIFICATION_HEADINGS),
                )
            if name in sections:
                raise _syntax_error(line, module_name, f"Duplicate specification heading (`{name}`)")
            if name == plain_spec.DEFINITIONS and sections:
                raise _syntax_error(
                    line,
                    module_name,
                    f"Definitions specification must be the first specification in the section (`{name}`)",
                )
            current = name
            sections[name] = [] if name == plain_spec.FUNCTIONAL_REQUIREMENTS else _new_section_document()
            continue

        if isinstance(token, BlankLine):
            if functionality is not None:
                functionality["tokens"].append(token)
            continue

        if current == plain_spec.FUNCTIONAL_REQUIREMENTS:
            if isinstance(token, block_token.Heading):
                if token.level != 1:
                    raise _syntax_error(
                        line,
                        module_name,
                        f"Invalid heading level {token.level} (`{_block_text(token)}`). "
                        "A functionality heading is `# <func-id>`.",
                    )
                func_id = _block_text(token)
                if not plain_spec.is_semantic_id(func_id):
                    raise _syntax_error(
                        line,
                        module_name,
                        f"Invalid func-id (`{func_id}`). A func-id is lowercase letters and digits, with single "
                        "hyphens between them.",
                    )
                if func_id in first_lines:
                    raise _syntax_error(
                        line,
                        module_name,
                        f"Duplicate func-id `{func_id}`; it is first used at line {first_lines[func_id]}.",
                    )
                close_functionality()
                first_lines[func_id] = line
                functionality = {"id": func_id, "line_number": line, "tokens": [], "linked_resources": []}
                sections[current].append(functionality)
                continue
            if functionality is None:
                raise _syntax_error(
                    line,
                    module_name,
                    f"Content before the first `# <func-id>` heading in the functional specs section "
                    f"(`{_block_text(token)}`). {_PREVIOUS_SYNTAX_HINT}",
                )
            functionality["tokens"].append(token)
            continue

        if isinstance(token, block_token.Heading):
            raise _syntax_error(
                line,
                module_name,
                f"A `# <func-id>` heading is allowed only in the functional specs section (`{_block_text(token)}`).",
            )
        if current is None:
            if isinstance(token, block_token.List):
                raise _syntax_error(line, module_name, f"Missing specification heading (`{_block_text(token)}`)")
            if isinstance(token, block_token.Paragraph):
                raise _syntax_error(line, module_name, f"Invalid specification (`{_block_text(token)}`)")
            raise _syntax_error(line, module_name, f"Invalid source structure (`{_block_text(token)}`)")
        if isinstance(token, block_token.List):
            sections[current].children = list(sections[current].children) + list(token.children)
            continue
        if isinstance(token, block_token.Paragraph):
            raise _syntax_error(line, module_name, f"Invalid specification (`{_block_text(token)}`)")
        raise _syntax_error(line, module_name, f"Invalid source structure (`{_block_text(token)}`)")

    close_functionality()
    return sections


# Concept lists


def _normalize_concept_list(metadata: dict, directive: str) -> None:
    if directive not in metadata:
        return
    value = metadata[directive]
    assert isinstance(value, list), f"Syntax error: Invalid {directive} metadata. Expected a list."
    normalized: list[str] = []
    for entry in value:
        if isinstance(entry, str):
            normalized.append(f"- {entry}")
        elif isinstance(entry, dict):
            normalized.extend(f"- {key}: {item}" for key, item in entry.items())
        else:
            raise PlainSyntaxError(
                f"Plain syntax error: Invalid {directive} metadata. Expected a dictionary or a string."
            )
    metadata[directive] = normalized


def _metadata_list(metadata: dict, directive: str) -> list[str]:
    value = metadata.get(directive)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _defined_concepts(definitions) -> list[str]:
    result: list[str] = []
    if definitions is None:
        return result
    for token in definitions.children:
        concepts, _ = concept_utils.extract_concepts_from_definition(_render([token]).strip())
        result.extend(concepts)
    return result


def _check_exported_concepts(result: PlainFileParseResult, module_name: str | None) -> None:
    metadata = result.plain_source_obj.metadata
    subject = f"Module '{module_name}'" if module_name else "Module"
    defined = set(_defined_concepts(result.plain_source.get(plain_spec.DEFINITIONS)))
    for entry in metadata.get(EXPORTED_CONCEPTS_DIRECTIVE, []) or []:
        concepts, errors = concept_utils.extract_concepts_from_definition(entry)
        if errors or not concepts:
            raise PlainSyntaxError(
                f"Plain syntax error: {subject} exports an invalid concept (`{entry}`). "
                "Expected a concept token, e.g. :ConceptName:."
            )
        for concept in concepts:
            if concept in concept_utils.DEFAULT_CONCEPTS:
                raise PlainSyntaxError(
                    f"Plain syntax error: {subject} cannot export default concept {concept}. "
                    "Only user-defined concepts can be exported."
                )
            if concept not in defined:
                message = f"Plain syntax error: {subject} exports undefined concept {concept}."
                if result.required_modules:
                    message += (
                        " An exported concept must be defined in this module's definitions or in an imported module;"
                        " a concept inherited through requires cannot be re-exported."
                    )
                raise PlainSyntaxError(message)


# Parsing one module


def _merge_list_sections(target: dict, source: dict) -> None:
    for heading in plain_spec.LIST_SECTION_HEADINGS:
        if heading not in source:
            continue
        if heading not in target:
            target[heading] = _new_section_document()
        target[heading].children = list(target[heading].children) + list(source[heading].children)


def _process_imports(
    metadata, code_variables, template_dirs, imported_modules, modules_trace
) -> tuple[dict, list[str]]:
    merged: dict = {}
    required_concepts: list[str] = []
    for import_name in _metadata_list(metadata, IMPORT_DIRECTIVE):
        if import_name in modules_trace:
            raise PlainSyntaxError(f"Plain syntax error: Circular import detected: {import_name}.")
        if import_name in imported_modules:
            continue
        imported = parse_plain_file(
            import_name, code_variables, template_dirs, imported_modules, modules_trace + [import_name]
        )
        if plain_spec.FUNCTIONAL_REQUIREMENTS in imported.plain_source:
            raise ImportedModuleWithFunctionalitiesError(
                f"Module '{import_name}' is imported but contains functional specs. Imported modules may only "
                "provide definitions, implementation reqs, and test reqs — use 'requires' instead of 'import' if "
                "this module's functionalities should be built on."
            )
        for heading in imported.plain_source:
            if heading not in plain_spec.ALLOWED_IMPORT_SPECIFICATION_HEADINGS:
                raise PlainSyntaxError(
                    f"Plain syntax error: Invalid specification heading (`{heading}`). Allowed headings: "
                    + ", ".join(plain_spec.ALLOWED_IMPORT_SPECIFICATION_HEADINGS)
                )
        _merge_list_sections(merged, imported.plain_source)
        imported_modules.append(import_name)
        imported_required = imported.plain_source_obj.metadata.get(REQUIRED_CONCEPTS_DIRECTIVE)
        if imported_required:
            for entry in imported_required:
                concepts, _ = concept_utils.extract_concepts_from_definition(entry)
                required_concepts.extend(concepts)
            required_concepts.extend(imported.required_concepts)
    return merged, required_concepts


def parse_plain_source(
    plain_source_text: str,
    code_variables: dict,
    template_dirs: list[str],
    imported_modules: list[str],
    modules_trace: list[str],
    module_name: str | None = None,
) -> PlainFileParseResult:
    """Parse the text of a module into its sections, before validation."""
    text = normalize_line_endings(plain_source_text)
    try:
        post = frontmatter.loads(text)
    except yaml.YAMLError as error:
        raise PlainSyntaxError(f"Plain syntax error: Invalid frontmatter: {error}") from error
    if not isinstance(post.metadata, dict):
        post.metadata = {}
    content = restore_stripped_lines(text, post.content)

    _, loaded_templates = loaders.get_loaded_templates(template_dirs, content, module_name)
    rendered = render_plain_source(content, loaded_templates, code_variables)
    _check_test_sections(rendered, module_name)

    own_sections = _parse_sections(rendered, module_name)

    for directive in (EXPORTED_CONCEPTS_DIRECTIVE, REQUIRED_CONCEPTS_DIRECTIVE):
        _normalize_concept_list(post.metadata, directive)

    imported_sections, required_concepts = _process_imports(
        post.metadata, code_variables, template_dirs, imported_modules, modules_trace
    )

    plain_source: dict = {}
    _merge_list_sections(plain_source, imported_sections)
    _merge_list_sections(plain_source, own_sections)
    if plain_spec.FUNCTIONAL_REQUIREMENTS in own_sections:
        plain_source[plain_spec.FUNCTIONAL_REQUIREMENTS] = own_sections[plain_spec.FUNCTIONAL_REQUIREMENTS]
    ordered = {
        heading: plain_source[heading]
        for heading in plain_spec.ALLOWED_SPECIFICATION_HEADINGS
        if heading in plain_source
    }

    defined = set(_defined_concepts(ordered.get(plain_spec.DEFINITIONS)))
    still_required: list[str] = []
    for concept in required_concepts:
        if concept not in defined and concept not in still_required:
            still_required.append(concept)

    result = PlainFileParseResult(
        plain_source=ordered,
        plain_source_obj=post,
        required_modules=_metadata_list(post.metadata, REQUIRES_DIRECTIVE),
        required_concepts=still_required,
    )
    _check_exported_concepts(result, module_name)
    return result


def _read_module_text(file_name: str, template_dirs: list[str], module_name: str) -> str:
    text = loaders.open_from(template_dirs, file_name)
    if text is None:
        raise ModuleDoesNotExistError(f"Module does not exist ({module_name}).")
    blob = loaders.find_large_base64_blob(text)
    if blob is not None:
        raise UnsupportedBase64Content(
            f"Module '{module_name}' contains a base64-encoded blob ({len(blob)} characters) inlined in the "
            "specification. This is not supported. Remove the base64 data from the .plain file or if necessary, "
            "include the binary file path in the specification."
        )
    return text


def parse_plain_file(
    module_name: str,
    code_variables: dict,
    template_dirs: list[str],
    imported_modules: list[str],
    modules_trace: list[str],
) -> PlainFileParseResult:
    """Read the module ``module_name`` from the template directories and parse it."""
    text = _read_module_text(get_filename_from_module_name(module_name), template_dirs, module_name)
    return parse_plain_source(text, code_variables, template_dirs, imported_modules, modules_trace, module_name)


# Links


def find_linked_resources(tokens, template_dirs, where: str = "") -> list[dict]:
    """Return every link of ``tokens`` as ``{"text", "target"}``, in text order, after checking it."""
    found: list[dict] = []

    def visit(token) -> None:
        if isinstance(token, span_token.Link):
            found.append(_check_link(token, template_dirs, where))
        for child in getattr(token, "children", None) or []:
            visit(child)

    for token in tokens:
        visit(token)
    return found


def _check_link(token: span_token.Link, template_dirs, where: str) -> dict:
    target = token.target
    children = list(token.children or [])
    text = _span_text(token)
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or os.path.isabs(target) or target.startswith("/"):
        raise PlainSyntaxError(
            f"Plain syntax error: Only relative links are allowed{where} (text: {text}, target: {target})."
        )
    if len(children) != 1 or not text:
        raise PlainSyntaxError(f"Plain syntax error: Link{where} must have text specified (link: {target}).")
    if target.endswith(PLAIN_SOURCE_FILE_EXTENSION):
        raise PlainSyntaxError(
            f"Referenced resource '{target}'{where} is a .plain file. Referencing .plain files through Linked "
            "Resources is not supported. Please use the import section to include definitions or "
            "implementation/test requirements from another module."
        )
    resolved = loaders.resolve_linked_resource(template_dirs, target)
    if resolved is None:
        directories = "\n".join(f"  {number}. {directory}" for number, directory in enumerate(template_dirs, start=1))
        raise PlainSyntaxError(
            f"Plain syntax error: Link {target}{where} does not exist. Linked resources are looked up relative to "
            f"the following directories (highest to lowest precedence):\n{directories}"
        )
    if os.path.isdir(resolved):
        raise PlainSyntaxError(f"Plain syntax error: Link {target}{where} must be a file (resolved to {resolved}).")
    return {"text": text, "target": target}


# Marshalling


def _strip_blank_lines(tokens: list) -> list:
    start, end = 0, len(tokens)
    while start < end and isinstance(tokens[start], BlankLine):
        start += 1
    while end > start and isinstance(tokens[end - 1], BlankLine):
        end -= 1
    return tokens[start:end]


def _links_of(tokens) -> list[dict]:
    found: list[dict] = []

    def visit(token) -> None:
        if isinstance(token, span_token.Link):
            found.append({"text": _span_text(token), "target": token.target})
        for child in getattr(token, "children", None) or []:
            visit(child)

    for token in tokens:
        visit(token)
    return found


def marshall_plain_source(input_plain_source) -> dict:
    """Turn the sections of a parse result into a plain source tree."""
    tree: dict = {}
    for heading in plain_spec.ALLOWED_SPECIFICATION_HEADINGS:
        if heading not in input_plain_source:
            continue
        section = input_plain_source[heading]
        if heading != plain_spec.FUNCTIONAL_REQUIREMENTS:
            items = []
            for token in section.children:
                item: dict = {"markdown": _render([token]).strip()}
                links = _links_of([token])
                if links:
                    item["linked_resources"] = links
                items.append(item)
            tree[heading] = items
            continue
        functionalities = []
        for functionality in section:
            body = _strip_blank_lines(functionality["tokens"])
            functionalities.append(
                {
                    "id": functionality["id"],
                    "markdown": _render(body).strip("\n"),
                    "linked_resources": _links_of(body),
                    plain_spec.CONFORMANCE_TESTS: [],
                    plain_spec.ACCEPTANCE_TESTS: [],
                }
            )
        tree[heading] = functionalities
    return tree


def process_section_code_variables(section, code_variables, text_key="markdown") -> None:
    """Replace code-variable tokens in the items of ``section`` with placeholders and record them."""
    for item in section:
        for token, mapping in code_variables.items():
            if token not in item[text_key]:
                continue
            for name, value in mapping.items():
                item[text_key] = item[text_key].replace(token, "{{ " + name + " }}")
                item.setdefault("code_variables", []).append({"name": name, "value": value})


# Module checks and trees


def _check_module_shape(result: PlainFileParseResult, module_name: str) -> None:
    if result.required_concepts:
        raise PlainSyntaxError(
            "Plain syntax error: Not all required concepts were defined. Missing required concepts: "
            + ", ".join(result.required_concepts)
            + "."
        )
    if plain_spec.FUNCTIONAL_REQUIREMENTS not in result.plain_source:
        raise MissingFunctionalitiesError(
            f"Module '{module_name}' does not have any functionality specified. At least one functionality is "
            "required for rendering."
        )
    if not result.plain_source[plain_spec.FUNCTIONAL_REQUIREMENTS]:
        raise PlainSyntaxError(
            f"Plain syntax error: Module '{module_name}' has a 'functional specs' section without a `# <func-id>` "
            f"heading. {_PREVIOUS_SYNTAX_HINT}"
        )
    implementation_reqs = result.plain_source.get(plain_spec.NON_FUNCTIONAL_REQUIREMENTS)
    if implementation_reqs is None or not implementation_reqs.children:
        message = (
            f"Plain syntax error: Module '{module_name}' defines functionalities but specifies no implementation "
            "reqs. At least one implementation req is required."
        )
        if result.required_modules:
            message += (
                " Implementation reqs are not inherited through 'requires' — add them to this module, or 'import' a "
                "module that provides them."
            )
        raise PlainSyntaxError(message)


def _exported_definitions(result: PlainFileParseResult) -> list:
    """Return the definition tokens of the concepts a module exports, each followed by those it mentions."""
    definitions = result.plain_source.get(plain_spec.DEFINITIONS)
    if definitions is None:
        return []
    collected: list = []
    visited: set[str] = set()

    with PlainMarkdownRenderer() as renderer:

        def add(concept: str) -> None:
            if concept in visited or concept in concept_utils.DEFAULT_CONCEPTS:
                return
            visited.add(concept)
            for token in concept_utils.find_concept_definitions_in_plain_source(concept, result.plain_source, renderer):
                if any(token is existing for existing in collected):
                    continue
                collected.append(token)
                for mentioned in concept_utils.extract_concepts_from_spec_text(renderer.render(token)):
                    add(mentioned)

        for entry in result.plain_source_obj.metadata.get(EXPORTED_CONCEPTS_DIRECTIVE, []) or []:
            concepts, _ = concept_utils.extract_concepts_from_definition(entry)
            for concept in concepts:
                add(concept)
    return collected


def _merge_exported_definitions(result: PlainFileParseResult, required: list[PlainFileParseResult]) -> None:
    exported: list = []
    for required_result in required:
        exported.extend(_exported_definitions(required_result))
    if not exported:
        return
    if plain_spec.DEFINITIONS not in result.plain_source:
        sections = {plain_spec.DEFINITIONS: _new_section_document()}
        sections.update(result.plain_source)
        result.plain_source = sections
    definitions = result.plain_source[plain_spec.DEFINITIONS]
    present = {_render([token]).strip() for token in definitions.children}
    merged = list(definitions.children)
    for token in exported:
        text = _render([token]).strip()
        if text in present:
            continue
        present.add(text)
        merged.append(token)
    definitions.children = merged


def _build_tree(
    result: PlainFileParseResult,
    module_name: str,
    template_dirs: list[str],
    code_variables: dict,
    required: list[PlainFileParseResult],
) -> dict:
    _merge_exported_definitions(result, required)

    for heading in plain_spec.LIST_SECTION_HEADINGS:
        if heading in result.plain_source:
            for token in result.plain_source[heading].children:
                find_linked_resources([token], template_dirs)
    for functionality in result.plain_source.get(plain_spec.FUNCTIONAL_REQUIREMENTS, []):
        functionality["linked_resources"] = find_linked_resources(functionality["tokens"], template_dirs)

    tree = marshall_plain_source(result.plain_source)
    for section in tree.values():
        process_section_code_variables(section, code_variables)

    errors = concept_utils.validate_concepts(tree)
    if errors:
        raise PlainSyntaxError(
            f"Plain syntax error: Found {len(errors)} errors in the plain file:\n" + "\n".join(errors)
        )
    if plain_spec.DEFINITIONS in tree:
        concept_utils.sort_definitions(tree[plain_spec.DEFINITIONS])
    return tree


# Requires chains


def _entry_module_name(plain_source_file_name: str) -> str:
    suffix = os.path.splitext(plain_source_file_name)[1]
    if suffix != PLAIN_SOURCE_FILE_EXTENSION:
        raise PlainSyntaxError(f"Plain syntax error: Invalid plain file extension: {suffix}. Expected: .plain.")
    if os.path.isabs(plain_source_file_name):
        name = os.path.basename(plain_source_file_name)
    else:
        name = plain_source_file_name.replace(os.sep, "/")
    return name[: -len(PLAIN_SOURCE_FILE_EXTENSION)]


@dataclass
class _ChainModule:
    name: str
    result: PlainFileParseResult
    code_variables: dict


def _walk_requires(
    module: _ChainModule,
    template_dirs: list[str],
    recorded: list[_ChainModule],
    trace: list[str],
) -> None:
    for required_name in module.result.required_modules:
        if recorded and recorded[-1].name == required_name:
            continue
        if required_name in trace:
            raise PlainSyntaxError(f"Plain syntax error: Circular required module detected: {required_name}.")
        code_variables: dict = {}
        result = parse_plain_file(required_name, code_variables, template_dirs, [], [required_name])
        required = _ChainModule(required_name, result, code_variables)
        if not result.required_modules and recorded:
            raise PlainSyntaxError(
                f"Plain syntax error: There must be a fixed order how required modules are dependent ({required_name})."
            )
        _walk_requires(required, template_dirs, recorded, trace + [required_name])
        recorded.append(required)


def _parse_chain(plain_file_name: str, template_dirs: list[str]) -> tuple[str, dict, list[str], list[tuple[str, dict]]]:
    module_name = _entry_module_name(plain_file_name)
    template_dirs = [os.path.abspath(directory) for directory in template_dirs]
    code_variables: dict = {}
    if os.path.isabs(plain_file_name):
        text = _read_module_text(plain_file_name, [os.path.dirname(plain_file_name)], module_name)
    else:
        text = _read_module_text(get_filename_from_module_name(module_name), template_dirs, module_name)
    result = parse_plain_source(text, code_variables, template_dirs, [], [module_name], module_name)
    entry = _ChainModule(module_name, result, code_variables)
    _check_module_shape(result, module_name)

    recorded: list[_ChainModule] = []
    _walk_requires(entry, template_dirs, recorded, [module_name])
    by_name = {module.name: module for module in recorded}

    def required_of(module: _ChainModule) -> list[PlainFileParseResult]:
        return [by_name[name].result for name in module.result.required_modules if name in by_name]

    requires = list(result.required_modules)
    trees: dict[str, dict] = {
        module_name: _build_tree(result, module_name, template_dirs, code_variables, required_of(entry))
    }

    def validate(names: list[str]) -> None:
        for name in names:
            if name in trees or name not in by_name:
                continue
            module = by_name[name]
            _check_module_shape(module.result, name)
            trees[name] = _build_tree(module.result, name, template_dirs, module.code_variables, required_of(module))
            validate(module.result.required_modules)

    validate(requires)
    chain = [(module.name, trees[module.name]) for module in recorded] + [(module_name, trees[module_name])]
    return module_name, trees[module_name], requires, chain


def plain_file_parser(plain_source_file_name: str, template_dirs: list[str]) -> tuple[str, dict, list[str]]:
    """Parse an entry module file into its module name, plain source tree and own requires list."""
    module_name, tree, requires, _ = _parse_chain(plain_source_file_name, template_dirs)
    return module_name, tree, requires


def parse_module_chain(plain_file_name: str, template_dirs: list[str]) -> list[tuple[str, dict]]:
    """Parse an entry module file into its requires chain, deepest ancestor first and the module itself last."""
    return _parse_chain(plain_file_name, template_dirs)[3]
