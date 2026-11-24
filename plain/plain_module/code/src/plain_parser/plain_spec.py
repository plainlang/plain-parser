"""Section names, semantic ids and helpers that walk a plain source tree by func-id."""

import hashlib
import json
import re
import uuid
from collections.abc import Iterator

from liquid2.filter import with_context

from plain_parser.exceptions import InvalidFridArgument, InvalidLiquidVariableName  # noqa: F401

DEFINITIONS = "definitions"
NON_FUNCTIONAL_REQUIREMENTS = "implementation reqs"
TEST_REQUIREMENTS = "test reqs"
FUNCTIONAL_REQUIREMENTS = "functional specs"
CONFORMANCE_TESTS = "conformance_tests"
ACCEPTANCE_TESTS = "acceptance_tests"
CONFORMANCE_TEST_HEADING = "conformance tests"
ACCEPTANCE_TEST_HEADING = "acceptance tests"

LIST_SECTION_HEADINGS = [DEFINITIONS, NON_FUNCTIONAL_REQUIREMENTS, TEST_REQUIREMENTS]
ALLOWED_SPECIFICATION_HEADINGS = [*LIST_SECTION_HEADINGS, FUNCTIONAL_REQUIREMENTS]
ALLOWED_IMPORT_SPECIFICATION_HEADINGS = LIST_SECTION_HEADINGS

SEMANTIC_ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

CODE_VARIABLES = "code_variables"
LINKED_RESOURCES = "linked_resources"


def is_semantic_id(text: str) -> bool:
    """Tell whether the whole ``text`` is a semantic id."""
    return isinstance(text, str) and SEMANTIC_ID_PATTERN.fullmatch(text) is not None


def _functionalities(plain_source_tree) -> list:
    return plain_source_tree.get(FUNCTIONAL_REQUIREMENTS, []) or []


def has_acceptance_tests(plain_source_tree) -> bool:
    """Tell whether any functionality of the tree has an acceptance scenario."""
    return any(functionality.get(ACCEPTANCE_TESTS) for functionality in _functionalities(plain_source_tree))


def get_frids(plain_source_tree) -> Iterator[str]:
    """Yield the func-ids of the tree in file order."""
    for functionality in _functionalities(plain_source_tree):
        yield functionality["id"]


def get_first_frid(plain_source_tree) -> str | None:
    return next(get_frids(plain_source_tree), None)


def _frid_position(frids: list[str], frid: str) -> int:
    if frid not in frids:
        raise Exception(f"Functionality {frid} does not exist.")
    return frids.index(frid)


def get_next_frid(plain_source_tree, frid) -> str | None:
    frids = list(get_frids(plain_source_tree))
    position = _frid_position(frids, frid)
    return frids[position + 1] if position + 1 < len(frids) else None


def get_previous_frid(plain_source_tree, frid) -> str | None:
    frids = list(get_frids(plain_source_tree))
    position = _frid_position(frids, frid)
    return frids[position - 1] if position > 0 else None


def get_frids_before(plain_source_tree, target_frid: str) -> list[str]:
    """Return the func-ids before ``target_frid``; every func-id when it is unknown."""
    result = []
    for frid in get_frids(plain_source_tree):
        if frid == target_frid:
            break
        result.append(frid)
    return result


def get_frids_range(plain_source, start, end=None) -> list[str]:
    """Return the func-ids from ``start`` through ``end`` (both inclusive), in file order."""
    frids = list(get_frids(plain_source))
    if start not in frids:
        raise InvalidFridArgument(f"Invalid start functionality ID: {start}. Valid IDs are: {frids}.")
    if end is None:
        return frids[frids.index(start) :]
    if end not in frids:
        raise InvalidFridArgument(f"Invalid end functionality ID: {end}. Valid IDs are: {frids}.")
    start_index = frids.index(start)
    end_index = frids.index(end)
    if start_index > end_index:
        raise InvalidFridArgument(f"Start functionality ID: {start} must be before end functionality ID: {end}.")
    return frids[start_index : end_index + 1]


def _placeholder(name: str) -> str:
    return "{{ " + name + " }}"


def get_specification_item_markdown(specification_item, code_variables, replace_code_variables, key="markdown") -> str:
    """Return the text of an item, recording its code variables and replacing their placeholders when asked."""
    text = specification_item[key]
    for variable in specification_item.get(CODE_VARIABLES, []) or []:
        name = variable["name"]
        value = variable["value"]
        if name in code_variables and code_variables[name] != value:
            raise Exception(f"Code variable {name} has multiple values: {code_variables[name]} and {value}")
        code_variables[name] = value
        if replace_code_variables:
            text = text.replace(_placeholder(name), value)
    return text


def get_specifications_for_frid(plain_source_tree, frid, replace_code_variables=True) -> tuple[dict, dict | None]:
    """Return the specification texts that build functionality ``frid`` and the code variables they use."""
    functionalities = _functionalities(plain_source_tree)
    if frid not in [functionality["id"] for functionality in functionalities]:
        raise Exception(f"Functionality {frid} does not exist.")

    code_variables: dict = {}
    specifications: dict = {}
    for heading in LIST_SECTION_HEADINGS:
        specifications[heading] = [
            get_specification_item_markdown(item, code_variables, replace_code_variables)
            for item in plain_source_tree.get(heading, []) or []
        ]

    specifications[FUNCTIONAL_REQUIREMENTS] = []
    specifications[CONFORMANCE_TESTS] = []
    specifications[ACCEPTANCE_TESTS] = []
    for functionality in functionalities:
        specifications[FUNCTIONAL_REQUIREMENTS].append(
            get_specification_item_markdown(functionality, code_variables, replace_code_variables)
        )
        if functionality["id"] == frid:
            for scenarios_key in (CONFORMANCE_TESTS, ACCEPTANCE_TESTS):
                for scenario in functionality.get(scenarios_key, []) or []:
                    specifications[scenarios_key].append(
                        {
                            "id": scenario["id"],
                            "text": get_specification_item_markdown(
                                scenario, code_variables, replace_code_variables, key="text"
                            ),
                        }
                    )
            break

    return specifications, (code_variables or None)


def collect_specification_linked_resources(specification, specification_heading, linked_resources_list) -> None:
    """Add the links of one item to the link registry."""
    for resource in specification.get(LINKED_RESOURCES, []) or []:
        resource_found = False
        for resource_map in linked_resources_list:
            if resource["text"] == resource_map["text"]:
                if resource["target"] != resource_map["target"]:
                    raise Exception(
                        f"The file {resource['target']} is linked to multiple linked resources with the same text: "
                        f"{resource['text']}"
                    )
            elif resource["target"] == resource_map["target"]:
                raise Exception(
                    f"The linked resource {resource['text']} is linked to multiple files: {resource_map['target']}"
                )
            else:
                continue

            if resource_found:
                raise Exception(f"Duplicate linked resource found: {resource['text']} ({resource['target']})")
            resource_found = True
            resource_map["sections"].append(specification_heading)

        if not resource_found:
            linked_resources_list.append(
                {"text": resource["text"], "target": resource["target"], "sections": [specification_heading]}
            )


def collect_linked_resources(
    plain_source_tree, linked_resources_list, specifications_list, include_test_scenarios, frid=None
) -> bool:
    """Add every link of the tree to the registry, sort it by text, and tell whether ``frid`` was reached."""
    if not isinstance(plain_source_tree, dict):
        raise ValueError("plain_source_tree must be a dictionary.")
    if frid is not None and frid not in list(get_frids(plain_source_tree)):
        raise ValueError(f"frid {frid} does not exist.")

    reached = False
    for heading in ALLOWED_SPECIFICATION_HEADINGS:
        if specifications_list is not None and heading not in specifications_list:
            continue
        if heading not in plain_source_tree:
            continue
        if heading != FUNCTIONAL_REQUIREMENTS:
            for item in plain_source_tree[heading] or []:
                collect_specification_linked_resources(item, heading, linked_resources_list)
            continue
        for functionality in plain_source_tree[heading] or []:
            collect_specification_linked_resources(functionality, heading, linked_resources_list)
            if include_test_scenarios and (frid is None or functionality["id"] == frid):
                for scenarios_key in (CONFORMANCE_TESTS, ACCEPTANCE_TESTS):
                    for scenario in functionality.get(scenarios_key, []) or []:
                        collect_specification_linked_resources(scenario, heading, linked_resources_list)
            if frid is not None and functionality["id"] == frid:
                reached = True
                break

    linked_resources_list.sort(key=lambda resource: resource["text"])
    return reached


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_hash_value(specifications) -> str:
    return hash_text(json.dumps(specifications, indent=4))


def _scope_variable_name(context) -> str | None:
    """Return the first name of the Liquid scope: the first named argument of the enclosing include tag.

    The scope is made of the include namespaces, the template locals and the render globals; the built-in names
    of liquid2 are not part of it.
    """
    for namespace in context.scope._maps:
        for name in namespace:
            return name
        if namespace is context.globals:
            break
    return None


@with_context
def code_variable_liquid_filter(value, *, context):
    """Mark ``value`` as a code variable: store a token in the ``code_variables`` mapping and output it."""
    variable_name = _scope_variable_name(context)
    if variable_name is None:
        raise Exception("Invalid use of code_variable filter!")
    code_variables = context.globals.get(CODE_VARIABLES)
    if not isinstance(code_variables, dict):
        return value
    token = uuid.uuid4().hex
    code_variables[token] = {variable_name: value}
    return token


@with_context
def prohibited_chars_liquid_filter(value, prohibited_chars, *, context):
    """Output ``value`` as text when it holds none of ``prohibited_chars``."""
    variable_name = _scope_variable_name(context)
    if variable_name is None:
        raise Exception("Invalid use of prohibited_chars filter!")
    text = str(value)
    for char in str(prohibited_chars):
        if char in text:
            raise InvalidLiquidVariableName(
                f"'{char}' is not a valid character for variable '{variable_name}' (value: '{text}')."
            )
    return text
