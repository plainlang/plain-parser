"""Concept extraction, concept validation, and dependency ordering of definitions with cycle reports."""

import re
from graphlib import CycleError, TopologicalSorter

from plain_parser import plain_spec
from plain_parser.exceptions import PlainSyntaxError
from plain_parser.graph import simple_cycles

DEFAULT_CONCEPTS: set[str] = {
    ":ConformanceTests:",
    ":UnitTests:",
    ":AcceptanceTest:",
    ":AcceptanceTests:",
    ":Implementation:",
    ":plainDefinitions:",
    ":plainImplementationReqs:",
    ":plainFunctionality:",
    ":plainTestReqs:",
    ":plainImplementationCode:",
}

MAX_REPORTED_CYCLES = 10

CONCEPT_CHARS = r"A-Za-z0-9+\-._"
CONCEPT_PATTERN = re.compile(rf":[{CONCEPT_CHARS}]+:")
_DEFINITION_START = re.compile(r"- (:[^:\n]+:(?:\s*,\s*:[^:\n]+:)*)")
_DEFINITION_NAME = re.compile(r":[^:\n]+:")


def extract_concepts_from_definition(text: str) -> tuple[list[str], list[str]]:
    """Return the concepts a definition text defines, and the errors found."""
    match = _DEFINITION_START.match(text)
    if match is None:
        return [], [
            f"Syntax error: Invalid definition specification text: {text}. Should start with `- :<concept>:` "
            "(where <concept> is any string that does not contain `:`)."
        ]
    concepts: list[str] = []
    errors: list[str] = []
    for candidate in _DEFINITION_NAME.findall(match.group(1)):
        if CONCEPT_PATTERN.fullmatch(candidate):
            concepts.append(candidate)
        else:
            errors.append(
                f"Syntax error: Invalid concept: {candidate}. Should contain only letters, numbers, hyphens and dots."
            )
    return concepts, errors


def extract_concepts_from_spec_text(text: str) -> list[str]:
    """Return every concept token ``text`` mentions, in order, repeats kept."""
    return CONCEPT_PATTERN.findall(text)


def collect_concepts(plain_source) -> tuple[list[str] | set[str], list[str]]:
    """Return the concepts defined by the definitions of a tree, and the errors of those definitions."""
    concepts: list[str] = []
    errors: list[str] = []
    for definition in plain_source.get(plain_spec.DEFINITIONS, []) or []:
        defined, definition_errors = extract_concepts_from_definition(definition["markdown"])
        concepts.extend(defined)
        errors.extend(definition_errors)
    return concepts, errors


def validate_concepts_in_spec(spec: dict, concepts: set[str], spec_group: str) -> list[str]:
    errors = []
    for concept in extract_concepts_from_spec_text(spec["markdown"]):
        if concept not in concepts and concept not in DEFAULT_CONCEPTS:
            errors.append(
                f"Syntax error: Concept {concept} is not defined in the definitions. {spec_group}: {spec['markdown']}"
            )
    return errors


def validate_concepts_in_spec_group(spec_group, plain_source, concepts: set[str]) -> list[str]:
    errors = []
    for spec in plain_source.get(spec_group, []) or []:
        errors.extend(validate_concepts_in_spec(spec, concepts, spec_group))
    return errors


def validate_concepts(marshalled_plain_source) -> list[str]:
    """Validate the concepts of a plain source tree; return the error texts, empty when the tree is valid."""
    defined, errors = collect_concepts(marshalled_plain_source)

    seen: set[str] = set()
    duplicates: list[str] = []
    for concept in defined:
        if (concept in seen or concept in DEFAULT_CONCEPTS) and concept not in duplicates:
            duplicates.append(concept)
        seen.add(concept)
    if duplicates:
        errors.append(f"Syntax error: Concepts were defined multiple times: {', '.join(duplicates)} .")

    concepts = set(defined) | DEFAULT_CONCEPTS
    for spec_group in [
        plain_spec.NON_FUNCTIONAL_REQUIREMENTS,
        plain_spec.TEST_REQUIREMENTS,
        plain_spec.FUNCTIONAL_REQUIREMENTS,
        plain_spec.DEFINITIONS,
    ]:
        errors.extend(validate_concepts_in_spec_group(spec_group, marshalled_plain_source, concepts))
    return errors


def find_concept_definitions_in_plain_source(concept: str, plain_source: dict, renderer) -> list:
    """Return the definition tokens of ``plain_source`` that define ``concept``."""
    definitions = plain_source.get(plain_spec.DEFINITIONS)
    if definitions is None:
        return []
    tokens = definitions.children if hasattr(definitions, "children") else definitions
    result = []
    for token in tokens or []:
        text = renderer.render(token).strip()
        defined, _ = extract_concepts_from_definition(text)
        if concept in defined:
            result.append(token)
    return result


def _mentions(markdown: str, defined: list[str]) -> list[str]:
    """Return the concepts a definition mentions, each once, without its own and the predefined concepts."""
    result: list[str] = []
    for concept in extract_concepts_from_spec_text(markdown):
        if concept in DEFAULT_CONCEPTS or concept in defined or concept in result:
            continue
        result.append(concept)
    return result


def build_adjacency_list(definitions) -> tuple[dict, dict]:
    """Build the concept graph of definition items.

    Returns the adjacency list, mapping each concept to the concepts defined in terms of it, and the mapping from
    each defined concept to the markdown of its definition.
    """
    adjacency_list: dict[str, list[str]] = {}
    concept_definitions: dict[str, str] = {}
    for definition in definitions:
        markdown = definition["markdown"]
        defined, _ = extract_concepts_from_definition(markdown)
        for concept in defined:
            adjacency_list.setdefault(concept, [])
            concept_definitions.setdefault(concept, markdown)
        for mentioned in _mentions(markdown, defined):
            dependents = adjacency_list.setdefault(mentioned, [])
            for concept in defined:
                if concept not in dependents:
                    dependents.append(concept)
    return adjacency_list, concept_definitions


def format_cycles_error(adjacency_list, concept_definitions) -> str:
    """Return the message listing the elementary cycles of the concept graph."""
    graph = {concept: adjacency_list.get(concept, []) for concept in concept_definitions}
    for concept, dependents in adjacency_list.items():
        graph.setdefault(concept, dependents)
    position = {concept: index for index, concept in enumerate(graph)}

    found = list(simple_cycles(graph, limit=MAX_REPORTED_CYCLES + 1))
    # A cycle of the concept graph runs from a concept to the concepts defined in terms of it. It is written in
    # the other direction: each concept is followed by a concept its definition mentions.
    cycles = [[cycle[0]] + list(reversed(cycle[1:])) for cycle in found]
    cycles.sort(key=lambda cycle: (position[cycle[0]], len(cycle)))

    if len(cycles) > MAX_REPORTED_CYCLES:
        head = (
            f"Plain syntax error: Found more than {MAX_REPORTED_CYCLES} cycles in concept definitions. "
            f"Cycles are not allowed.\nShowing the first {MAX_REPORTED_CYCLES}."
        )
        cycles = cycles[:MAX_REPORTED_CYCLES]
    else:
        head = f"Plain syntax error: Found {len(cycles)} cycle(s) in concept definitions. Cycles are not allowed."

    blocks = []
    for number, cycle in enumerate(cycles, start=1):
        lines = [f"Cycle {number}: " + " -> ".join(cycle + [cycle[0]])]
        for concept in cycle:
            markdown = concept_definitions.get(concept)
            if markdown is not None and markdown not in lines[1:]:
                lines.append(markdown)
        blocks.append("\n".join(lines))
    return head + "\n\n" + "\n\n".join(blocks)


def sort_definitions(definitions: list[dict]) -> None:
    """Sort definition items in place so that every concept comes after the concepts its definition mentions."""
    if len(definitions) <= 1:
        return

    adjacency_list, concept_definitions = build_adjacency_list(definitions)
    sorter: TopologicalSorter = TopologicalSorter()
    for concept, dependents in adjacency_list.items():
        sorter.add(concept)
        for dependent in dependents:
            sorter.add(dependent, concept)
    try:
        order = list(sorter.static_order())
    except CycleError:
        raise PlainSyntaxError(format_cycles_error(adjacency_list, concept_definitions)) from None

    position = {concept: index for index, concept in enumerate(order)}

    def item_position(definition: dict) -> int:
        defined, _ = extract_concepts_from_definition(definition["markdown"])
        positions = [position[concept] for concept in defined if concept in position]
        return positions[-1] if positions else -1

    definitions.sort(key=item_position)
