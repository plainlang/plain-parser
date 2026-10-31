import hashlib
import json
import re
import uuid

from liquid2.filter import with_context

from plain_parser.exceptions import InvalidFridArgument, InvalidLiquidVariableName

DEFINITIONS = "definitions"
NON_FUNCTIONAL_REQUIREMENTS = "implementation reqs"
TEST_REQUIREMENTS = "test reqs"
FUNCTIONAL_REQUIREMENTS = "functional specs"
CONFORMANCE_TESTS = "conformance_tests"
ACCEPTANCE_TESTS = "acceptance_tests"
CONFORMANCE_TEST_HEADING = "conformance tests"
ACCEPTANCE_TEST_HEADING = "acceptance tests"

# The sections whose content is a list of `- ` items.
LIST_SECTION_HEADINGS = [DEFINITIONS, NON_FUNCTIONAL_REQUIREMENTS, TEST_REQUIREMENTS]

ALLOWED_SPECIFICATION_HEADINGS = [*LIST_SECTION_HEADINGS, FUNCTIONAL_REQUIREMENTS]

ALLOWED_IMPORT_SPECIFICATION_HEADINGS = LIST_SECTION_HEADINGS

# A func-id or scenario-id: segments of lowercase letters and digits, with one hyphen between segments. So a
# hyphen never starts or ends an id, two hyphens never touch, and an id is never only hyphens.
SEMANTIC_ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def is_semantic_id(text: str) -> bool:
    return SEMANTIC_ID_PATTERN.fullmatch(text) is not None


def has_acceptance_tests(plain_source_tree) -> bool:
    """Return True if any functional requirement in the plain source defines acceptance tests."""
    functional_requirements = plain_source_tree.get(FUNCTIONAL_REQUIREMENTS) or []
    for functional_requirement in functional_requirements:
        if functional_requirement.get(ACCEPTANCE_TESTS):
            return True
    return False


def collect_specification_linked_resources(specification, specification_heading, linked_resources_list):
    linked_resources = []
    if "linked_resources" in specification:
        linked_resources.extend(specification["linked_resources"])

    for resource in linked_resources:
        resource_found = False
        for resource_map in linked_resources_list:
            if resource["text"] == resource_map["text"]:
                if resource["target"] != resource_map["target"]:
                    raise Exception(
                        f"The file {resource['target']} is linked to multiple linked resources with the same text: {resource['text']}"
                    )
            elif resource["target"] == resource_map["target"]:
                if resource["text"] != resource_map["text"]:
                    raise Exception(
                        f"The linked resource {resource['text']} is linked to multiple files: {resource_map['target']}"
                    )
            else:
                continue

            if resource_found:
                raise Exception(
                    "Duplicate linked resource found: " + resource["text"] + " (" + resource["target"] + ")"
                )

            resource_found = True
            resource_map["sections"].append(specification_heading)

        if not resource_found:
            linked_resources_list.append(
                {"text": resource["text"], "target": resource["target"], "sections": [specification_heading]}
            )


def collect_linked_resources(
    plain_source_tree, linked_resources_list, specifications_list, include_test_scenarios, frid=None
):
    """Add the linked resources of the tree to ``linked_resources_list`` and sort the list by link text.

    ``specifications_list`` limits the sections read; None reads every section. The functional specs are read up to
    and including ``frid``, or all of them when ``frid`` is None. With ``include_test_scenarios`` the links of the
    conformance and acceptance scenarios are added too, for ``frid`` alone when one is given. Returns True when
    ``frid`` was reached.
    """
    if not isinstance(plain_source_tree, dict):
        raise ValueError("plain_source_tree must be a dictionary.")

    if frid is not None and frid not in get_frids(plain_source_tree):
        raise ValueError(f"frid {frid} does not exist.")

    sections_to_collect = [
        heading
        for heading in ALLOWED_SPECIFICATION_HEADINGS
        if heading in plain_source_tree and (not specifications_list or heading in specifications_list)
    ]
    frid_reached = False
    for specification_heading in sections_to_collect:
        for specification in plain_source_tree[specification_heading]:
            collect_specification_linked_resources(specification, specification_heading, linked_resources_list)

            if specification_heading != FUNCTIONAL_REQUIREMENTS:
                continue

            if include_test_scenarios and (frid is None or frid == specification["id"]):
                scenarios = [*specification.get(CONFORMANCE_TESTS, []), *specification.get(ACCEPTANCE_TESTS, [])]
                for scenario in scenarios:
                    collect_specification_linked_resources(scenario, FUNCTIONAL_REQUIREMENTS, linked_resources_list)

            if specification["id"] == frid:
                frid_reached = True
                break

    linked_resources_list.sort(key=lambda x: x["text"])

    return frid_reached


def get_frids(plain_source_tree):
    """The func-ids of the tree's functionalities, in file order."""
    for functionality in plain_source_tree.get(FUNCTIONAL_REQUIREMENTS) or []:
        yield functionality["id"]


def get_first_frid(plain_source_tree):
    return next(get_frids(plain_source_tree), None)


def get_next_frid(plain_source_tree, frid):
    functional_requirements = get_frids(plain_source_tree)
    for temp_frid in functional_requirements:
        if temp_frid == frid:
            return next(functional_requirements, None)

    raise Exception(f"Functionality {frid} does not exist.")


def get_previous_frid(plain_source_tree, frid):
    previous_frid = None
    for temp_frid in get_frids(plain_source_tree):
        if temp_frid == frid:
            return previous_frid

        previous_frid = temp_frid

    raise Exception(f"Functionality {frid} does not exist.")


def get_frids_before(plain_source_tree, target_frid: str) -> list[str]:
    """The func-ids that come before ``target_frid`` in the specification, in order."""
    previous_frids = []
    for frid in get_frids(plain_source_tree):
        if frid == target_frid:
            break
        previous_frids.append(frid)

    return previous_frids


def get_specification_item_markdown(specification_item, code_variables, replace_code_variables, key="markdown"):
    """The text under ``key`` of the item, with its code variables recorded in ``code_variables`` and, when
    ``replace_code_variables`` is set, their values put in place of the `{{ name }}` placeholders."""
    markdown = specification_item[key]
    if "code_variables" in specification_item:
        for code_variable in specification_item["code_variables"]:
            if code_variable["name"] in code_variables:
                if code_variables[code_variable["name"]] != code_variable["value"]:
                    raise Exception(
                        f"Code variable {code_variable['name']} has multiple values: {code_variables[code_variable['name']]} and {code_variable['value']}"
                    )
            else:
                code_variables[code_variable["name"]] = code_variable["value"]

            if replace_code_variables:
                markdown = markdown.replace(f"{{{{ {code_variable['name']} }}}}", code_variable["value"])

    return markdown


def get_specifications_for_frid(plain_source_tree, frid, replace_code_variables=True):
    """The specifications that build ``frid``: every list section, the functional specs up to and including
    ``frid``, and the conformance and acceptance scenarios of ``frid`` as `{"id", "text"}` entries.

    Returns the specifications and the code variables they use (None when there are none). Raise when ``frid``
    is not in the tree.
    """
    functionalities = plain_source_tree.get(FUNCTIONAL_REQUIREMENTS) or []
    position = next((index for index, item in enumerate(functionalities) if item["id"] == frid), None)
    if position is None:
        raise Exception(f"Functionality {frid} does not exist.")

    code_variables = {}

    def texts(items, key="markdown"):
        return [get_specification_item_markdown(item, code_variables, replace_code_variables, key) for item in items]

    def scenarios(items):
        return [{"id": item["id"], "text": text} for item, text in zip(items, texts(items, "text"))]

    functionality = functionalities[position]
    specifications = {
        DEFINITIONS: texts(plain_source_tree.get(DEFINITIONS) or []),
        NON_FUNCTIONAL_REQUIREMENTS: texts(plain_source_tree.get(NON_FUNCTIONAL_REQUIREMENTS) or []),
        TEST_REQUIREMENTS: texts(plain_source_tree.get(TEST_REQUIREMENTS) or []),
        FUNCTIONAL_REQUIREMENTS: texts(functionalities[: position + 1]),
        CONFORMANCE_TESTS: scenarios(functionality.get(CONFORMANCE_TESTS, [])),
        ACCEPTANCE_TESTS: scenarios(functionality.get(ACCEPTANCE_TESTS, [])),
    }

    return specifications, (code_variables or None)


@with_context
def code_variable_liquid_filter(value, *, context):
    if len(context.scope) == 0:
        raise Exception("Invalid use of code_variable filter!")

    if "code_variables" in context.globals:
        code_variables = context.globals["code_variables"]

        variable = next(iter(context.scope.items()))

        unique_str = uuid.uuid4().hex

        code_variables[unique_str] = {variable[0]: value}

        return unique_str
    else:

        return value


@with_context
def prohibited_chars_liquid_filter(value, prohibited_chars, *, context):
    if not isinstance(value, str):
        value = str(value)

    if len(context.scope) == 0:
        raise Exception("Invalid use of prohibited_chars filter!")

    variable = next(iter(context.scope.items()))
    variable_name = variable[0]

    for char in prohibited_chars:
        if char in value:
            raise InvalidLiquidVariableName(
                f"'{char}' is not a valid character for variable '{variable_name}' (value: '{value}')."
            )

    return value


def hash_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def get_hash_value(specifications):
    return hash_text(json.dumps(specifications, indent=4))


def get_frids_range(plain_source, start, end=None):
    """The func-ids from ``start`` through ``end`` inclusive, or through the last one when ``end`` is None."""
    frids = list(get_frids(plain_source))

    if start not in frids:
        raise InvalidFridArgument(f"Invalid start functionality ID: {start}. Valid IDs are: {frids}.")

    if end is not None:
        if end not in frids:
            raise InvalidFridArgument(f"Invalid end functionality ID: {end}. Valid IDs are: {frids}.")

        end_idx = frids.index(end) + 1
    else:
        end_idx = len(frids)

    start_idx = frids.index(start)
    if start_idx >= end_idx:
        raise InvalidFridArgument(f"Start functionality ID: {start} must be before end functionality ID: {end}.")

    return frids[start_idx:end_idx]
