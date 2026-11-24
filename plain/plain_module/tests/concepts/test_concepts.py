"""Conformance tests of module concepts."""

import re

import pytest
from plain_parser import concept_utils
from plain_parser.exceptions import PlainSyntaxError


def c(name):
    return f":{name}:"


def items(*texts):
    return [{"markdown": text} for text in texts]


def defined_names(definitions):
    return [concept_utils.extract_concepts_from_definition(d["markdown"])[0] for d in definitions]


def sort_error(definitions):
    with pytest.raises(PlainSyntaxError) as error:
        concept_utils.sort_definitions(definitions)
    return str(error.value)


def cycle_lines(message):
    return [line for line in message.split("\n") if line.startswith("Cycle ")]


# extract-defined-concepts


def test_extract_defined_concepts__one_concept():
    assert concept_utils.extract_concepts_from_definition(f"- {c('Task')} is a thing to do.") == ([c("Task")], [])


def test_extract_defined_concepts__several_concepts():
    assert concept_utils.extract_concepts_from_definition(f"- {c('A')}, {c('B')} are twins.") == (
        [c("A"), c("B")],
        [],
    )


def test_extract_defined_concepts__invalid_name():
    concepts, errors = concept_utils.extract_concepts_from_definition(f"- {c('Bad name')} is x.")
    assert concepts == []
    assert errors == [
        f"Syntax error: Invalid concept: {c('Bad name')}. Should contain only letters, numbers, hyphens and dots."
    ]


def test_extract_defined_concepts__no_concept():
    concepts, errors = concept_utils.extract_concepts_from_definition("- A plain sentence.")
    assert concepts == []
    assert len(errors) == 1
    assert errors[0].startswith("Syntax error: Invalid definition specification text: - A plain sentence.")


# extract-used-concepts


def test_extract_used_concepts__mentions_in_order():
    text = f"{c('B')} uses {c('A')} and {c('B')}."
    assert concept_utils.extract_concepts_from_spec_text(text) == [c("B"), c("A"), c("B")]


# validate-concepts


def test_validate_concepts__valid_tree():
    tree = {
        "definitions": items(f"- {c('Task')} is a thing to do."),
        "functional specs": [{"id": "f", "markdown": f"A {c('Task')} is added by {c('Implementation')}."}],
    }
    assert concept_utils.validate_concepts(tree) == []


def test_validate_concepts__undefined_concept():
    markdown = f"A {c('User')} adds a {c('Task')}."
    tree = {
        "definitions": items(f"- {c('Task')} is a thing to do."),
        "functional specs": [{"id": "f", "markdown": markdown}],
    }
    assert concept_utils.validate_concepts(tree) == [
        f"Syntax error: Concept {c('User')} is not defined in the definitions. functional specs: {markdown}"
    ]


def test_validate_concepts__defined_twice():
    tree = {"definitions": items(f"- {c('Task')} is x.", f"- {c('Task')} is y.")}
    errors = concept_utils.validate_concepts(tree)
    assert any(e.startswith(f"Syntax error: Concepts were defined multiple times: {c('Task')}") for e in errors)


def test_validate_concepts__predefined_redefined():
    tree = {"definitions": items(f"- {c('Implementation')} is mine.")}
    errors = concept_utils.validate_concepts(tree)
    assert any(
        e.startswith(f"Syntax error: Concepts were defined multiple times: {c('Implementation')}") for e in errors
    )


def test_validate_concepts__words_between_colons_are_not_concepts():
    tree = {"implementation reqs": items("- Time is 12:30 and ratio 1 : 2.")}
    assert concept_utils.validate_concepts(tree) == []


# sort-definitions


def test_sort_definitions__single_item():
    definitions = items(f"- {c('A')} is x.")
    concept_utils.sort_definitions(definitions)
    assert definitions == items(f"- {c('A')} is x.")


def test_sort_definitions__no_mentions_keep_file_order():
    definitions = items(f"- {c('B')} is y.", f"- {c('A')} is x.")
    concept_utils.sort_definitions(definitions)
    assert defined_names(definitions) == [[c("B")], [c("A")]]


def test_sort_definitions__dependency_first():
    definitions = items(f"- {c('B')} uses {c('A')}.", f"- {c('A')} is x.")
    concept_utils.sort_definitions(definitions)
    assert defined_names(definitions) == [[c("A")], [c("B")]]


def test_sort_definitions__diamond():
    definitions = items(
        f"- {c('D')} uses {c('B')} and {c('C')}.",
        f"- {c('B')} uses {c('A')}.",
        f"- {c('C')} uses {c('A')}.",
        f"- {c('A')} is x.",
    )
    concept_utils.sort_definitions(definitions)
    order = [names[0] for names in defined_names(definitions)]
    assert order.index(c("A")) < order.index(c("B"))
    assert order.index(c("A")) < order.index(c("C"))
    assert order.index(c("B")) < order.index(c("D"))
    assert order.index(c("C")) < order.index(c("D"))


def test_sort_definitions__sub_item_mention():
    definitions = items(f"- {c('B')} is y.\n  - it uses {c('A')}.", f"- {c('A')} is x.")
    concept_utils.sort_definitions(definitions)
    assert defined_names(definitions) == [[c("A")], [c("B")]]


def test_sort_definitions__multi_concept_definition():
    definitions = items(f"- {c('C')} uses {c('A')} and {c('B')}.", f"- {c('A')}, {c('B')} are twins.")
    concept_utils.sort_definitions(definitions)
    assert defined_names(definitions) == [[c("A"), c("B")], [c("C")]]


def test_sort_definitions__self_mention_is_ignored():
    definitions = items(f"- {c('B')} uses {c('A')}.", f"- {c('A')} is like {c('A')}.")
    concept_utils.sort_definitions(definitions)
    assert defined_names(definitions) == [[c("A")], [c("B")]]


def test_sort_definitions__predefined_mention_is_ignored():
    definitions = items(f"- {c('B')} uses {c('A')} and {c('Implementation')}.", f"- {c('A')} is x.")
    concept_utils.sort_definitions(definitions)
    assert defined_names(definitions) == [[c("A")], [c("B")]]


def test_sort_definitions__graph_order():
    spec = [
        ("Concept3", ["Concept1", "Concept2"]),
        ("Concept2", ["Concept1"]),
        ("Concept1", []),
        ("NonReferencedConcept", []),
        ("Concept4", ["Concept3"]),
        ("Concept8", ["Concept1"]),
        ("Concept5", ["Concept1"]),
        ("Concept6", ["Concept1", "Concept4"]),
        ("Concept7", []),
        ("Concept9", ["Concept8"]),
    ]
    definitions = []
    for name, mentions in spec:
        text = f"- {c(name)} is a concept."
        if mentions:
            text = f"- {c(name)} uses " + " and ".join(c(m) for m in mentions) + "."
        definitions.append({"markdown": text})
    concept_utils.sort_definitions(definitions)
    assert [names[0] for names in defined_names(definitions)] == [
        c(n)
        for n in [
            "Concept1",
            "NonReferencedConcept",
            "Concept7",
            "Concept2",
            "Concept8",
            "Concept5",
            "Concept3",
            "Concept9",
            "Concept4",
            "Concept6",
        ]
    ]


# report-concept-cycles


def test_report_concept_cycles__two_node_cycle():
    message = sort_error(items(f"- {c('A')} uses {c('B')}.", f"- {c('B')} uses {c('A')}."))
    assert "Cycles are not allowed" in message
    assert f"- {c('A')} uses {c('B')}." in message
    assert f"- {c('B')} uses {c('A')}." in message


def test_report_concept_cycles__long_cycle_in_reference_order():
    message = sort_error(
        items(
            f"- {c('A')} uses {c('B')}.",
            f"- {c('B')} uses {c('C')}.",
            f"- {c('C')} uses {c('A')}.",
            f"- {c('D')} is on its own.",
        )
    )
    expected = "\n".join(
        [
            f"Cycle 1: {c('A')} -> {c('B')} -> {c('C')} -> {c('A')}",
            f"- {c('A')} uses {c('B')}.",
            f"- {c('B')} uses {c('C')}.",
            f"- {c('C')} uses {c('A')}.",
        ]
    )
    assert expected in message
    assert f"- {c('D')} is on its own." not in message


def test_report_concept_cycles__cycle_through_multi_concept_definition():
    message = sort_error(items(f"- {c('A')}, {c('B')} use {c('C')}.", f"- {c('C')} uses {c('B')}."))
    assert "Cycles are not allowed" in message


def test_report_concept_cycles__two_separate_cycles():
    message = sort_error(
        items(
            f"- {c('A')} uses {c('B')}.",
            f"- {c('B')} uses {c('A')}.",
            f"- {c('X')} uses {c('Y')}.",
            f"- {c('Y')} uses {c('X')}.",
        )
    )
    assert "Found 2 cycle" in message
    assert f"Cycle 1: {c('A')} -> {c('B')} -> {c('A')}" in message
    assert f"Cycle 2: {c('X')} -> {c('Y')} -> {c('X')}" in message


def test_report_concept_cycles__tangle():
    message = sort_error(
        items(
            f"- {c('Order')} is placed by a {c('Customer')} and billed by an {c('Invoice')}.",
            f"- {c('Customer')} has {c('Order')} items and {c('Invoice')} items.",
            f"- {c('Invoice')} bills an {c('Order')} to a {c('Customer')}.",
        )
    )
    assert "Found 5 cycle" in message
    assert len(cycle_lines(message)) == 5


def test_report_concept_cycles__capped_at_ten():
    names = ["Order", "Customer", "Invoice", "Payment"]
    definitions = items(
        *[f"- {c(name)} relates to " + ", ".join(c(other) for other in names if other != name) + "." for name in names]
    )
    message = sort_error(definitions)
    assert "Found more than 10 cycles" in message
    assert "Showing the first 10." in message
    assert len(cycle_lines(message)) == 10


def _pairs(count):
    texts = []
    for i in range(count):
        texts.append(f"- {c(f'A{i}')} uses {c(f'B{i}')}.")
        texts.append(f"- {c(f'B{i}')} uses {c(f'A{i}')}.")
    return texts


def test_report_concept_cycles__exactly_ten():
    message = sort_error(items(*_pairs(10)))
    assert "Found 10 cycle(s)" in message
    assert "Showing" not in message
    assert len(cycle_lines(message)) == 10


def test_report_concept_cycles__earliest_defined_cycles_shown():
    lines = cycle_lines(sort_error(items(*_pairs(12))))
    assert lines[0] == f"Cycle 1: {c('A0')} -> {c('B0')} -> {c('A0')}"
    assert lines[-1] == f"Cycle 10: {c('A9')} -> {c('B9')} -> {c('A9')}"


def test_report_concept_cycles__definition_order_not_first_mention():
    texts = _pairs(12)
    texts[0] = f"- {c('A0')} uses {c('B0')}, {c('A10')} and {c('A11')}."
    lines = cycle_lines(sort_error(items(*texts)))
    assert lines[-1] == f"Cycle 10: {c('A9')} -> {c('B9')} -> {c('A9')}"
    assert not any(c("A10") in line or c("A11") in line for line in lines)


def test_report_concept_cycles__shared_definition_once():
    shared = f"- {c('A')}, {c('B')} use {c('X')} and {c('Y')}."
    message = sort_error(items(shared, f"- {c('X')} uses {c('B')}.", f"- {c('Y')} uses {c('A')}."))
    blocks = [block for block in re.split(r"\n\n", message) if block.startswith("Cycle ")]
    assert blocks
    for block in blocks:
        assert block.count(shared) == 1


def test_report_concept_cycles__cycle_with_undefined_mention():
    message = sort_error(items(f"- {c('A')} uses {c('B')} and {c('Ghost')}.", f"- {c('B')} uses {c('A')}."))
    assert "Cycles are not allowed" in message
