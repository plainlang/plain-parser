import pytest

from plain_parser import concept_utils
from plain_parser.exceptions import PlainSyntaxError


def definitions(*markdown: str) -> list[dict]:
    return [{"markdown": line} for line in markdown]


def defined_concepts(sorted_definitions: list[dict]) -> list[str]:
    return [concept_utils.extract_concepts_from_definition(d["markdown"])[0][0] for d in sorted_definitions]


def test_sort_single_definition_is_unchanged():
    defs = definitions("- :A: is x.")
    concept_utils.sort_definitions(defs)
    assert defined_concepts(defs) == [":A:"]


def test_sort_definitions_without_concept_references_keeps_file_order():
    defs = definitions("- :B: is y.", "- :A: is x.")
    concept_utils.sort_definitions(defs)
    assert defined_concepts(defs) == [":B:", ":A:"]


def test_sort_places_dependency_before_dependant():
    defs = definitions("- :B: uses :A:.", "- :A: is x.")
    concept_utils.sort_definitions(defs)
    assert defined_concepts(defs) == [":A:", ":B:"]


def test_sort_resolves_diamond_dependencies():
    defs = definitions("- :D: uses :B: and :C:.", "- :B: uses :A:.", "- :C: uses :A:.", "- :A: is x.")
    concept_utils.sort_definitions(defs)
    order = defined_concepts(defs)
    assert order.index(":A:") < order.index(":B:") < order.index(":D:")
    assert order.index(":A:") < order.index(":C:") < order.index(":D:")


def test_sort_follows_references_in_sub_bullets():
    defs = definitions("- :B: is y.\n  - it uses :A:.", "- :A: is x.")
    concept_utils.sort_definitions(defs)
    assert defined_concepts(defs) == [":A:", ":B:"]


def test_sort_places_multi_concept_definition_before_its_dependants():
    defs = definitions("- :C: uses :A: and :B:.", "- :A:, :B: are twins.")
    concept_utils.sort_definitions(defs)
    assert defined_concepts(defs) == [":A:", ":C:"]


def test_sort_ignores_self_reference():
    defs = definitions("- :B: uses :A:.", "- :A: is like :A:.")
    concept_utils.sort_definitions(defs)
    assert defined_concepts(defs) == [":A:", ":B:"]


def test_sort_ignores_predefined_concepts():
    defs = definitions("- :B: uses :A: and :Implementation:.", "- :A: is x.")
    concept_utils.sort_definitions(defs)
    assert defined_concepts(defs) == [":A:", ":B:"]


def test_sort_rejects_two_node_cycle_and_lists_both_definitions():
    defs = definitions("- :A: uses :B:.", "- :B: uses :A:.")
    with pytest.raises(PlainSyntaxError, match="Cycles are not allowed") as exc_info:
        concept_utils.sort_definitions(defs)
    assert "- :A: uses :B:." in str(exc_info.value)
    assert "- :B: uses :A:." in str(exc_info.value)


def test_sort_rejects_long_cycle_and_lists_every_definition_on_it():
    defs = definitions("- :A: uses :B:.", "- :B: uses :C:.", "- :C: uses :A:.", "- :D: is on its own.")
    with pytest.raises(PlainSyntaxError) as exc_info:
        concept_utils.sort_definitions(defs)
    message = str(exc_info.value)
    for definition in ("- :A: uses :B:.", "- :B: uses :C:.", "- :C: uses :A:."):
        assert definition in message
    assert "- :D: is on its own." not in message


def test_sort_rejects_cycle_through_multi_concept_definition():
    defs = definitions("- :A:, :B: use :C:.", "- :C: uses :B:.")
    with pytest.raises(PlainSyntaxError, match="Cycles are not allowed"):
        concept_utils.sort_definitions(defs)


def test_sort_rejects_graph_with_two_separate_cycles_and_reports_both():
    defs = definitions("- :A: uses :B:.", "- :B: uses :A:.", "- :X: uses :Y:.", "- :Y: uses :X:.")
    with pytest.raises(PlainSyntaxError, match="Found 2 cycle") as exc_info:
        concept_utils.sort_definitions(defs)
    message = str(exc_info.value)
    assert "Cycle 1: :A: -> :B: -> :A:" in message
    assert "Cycle 2: :X: -> :Y: -> :X:" in message


def test_sort_reports_every_elementary_cycle_of_a_tangle():
    defs = definitions(
        "- :Order: is placed by a :Customer: and billed by an :Invoice:.",
        "- :Customer: has :Order: items and :Invoice: items.",
        "- :Invoice: bills an :Order: to a :Customer:.",
    )
    with pytest.raises(PlainSyntaxError, match="Found 5 cycle") as exc_info:
        concept_utils.sort_definitions(defs)
    assert str(exc_info.value).count("Cycle ") == 5


def test_sort_caps_the_number_of_reported_cycles():
    defs = definitions(
        "- :Order: is placed by a :Customer:, billed by an :Invoice:, settled by a :Payment:.",
        "- :Customer: has :Order:, :Invoice: and :Payment: items.",
        "- :Invoice: bills an :Order: to a :Customer: and is settled by a :Payment:.",
        "- :Payment: settles an :Invoice: for an :Order: by a :Customer:.",
    )
    with pytest.raises(PlainSyntaxError, match="Found more than 10 cycles") as exc_info:
        concept_utils.sort_definitions(defs)
    message = str(exc_info.value)
    assert "Showing the first 10." in message
    assert message.count("Cycle ") == 10


def test_sort_reports_cycle_in_reference_order():
    defs = definitions("- :A: uses :B:.", "- :B: uses :C:.", "- :C: uses :A:.")
    with pytest.raises(PlainSyntaxError) as exc_info:
        concept_utils.sort_definitions(defs)
    assert "Cycle 1: :A: -> :B: -> :C: -> :A:\n- :A: uses :B:.\n- :B: uses :C:.\n- :C: uses :A:." in str(exc_info.value)


def test_sort_rejects_cycle_that_also_references_undefined_concept():
    defs = definitions("- :A: uses :B: and :Ghost:.", "- :B: uses :A:.")
    with pytest.raises(PlainSyntaxError, match="Cycles are not allowed"):
        concept_utils.sort_definitions(defs)
