from plain_parser import concept_utils


def test_default_concepts_count():
    assert len(concept_utils.DEFAULT_CONCEPTS) == 10


def test_build_adjacency_list():
    adjacency, definitions = concept_utils.build_adjacency_list(
        [{"markdown": "- :B: uses :A:."}, {"markdown": "- :A: is x."}]
    )
    assert adjacency == {":B:": [], ":A:": [":B:"]}
    assert definitions == {":B:": "- :B: uses :A:.", ":A:": "- :A: is x."}


def test_undefined_mention_in_definition_is_reported():
    errors = concept_utils.validate_concepts({"definitions": [{"markdown": "- :A: uses :Ghost:."}]})
    assert errors == [
        "Syntax error: Concept :Ghost: is not defined in the definitions. definitions: - :A: uses :Ghost:."
    ]


def test_section_order_of_errors():
    tree = {
        "definitions": [{"markdown": "- :A: uses :D1:."}],
        "functional specs": [{"id": "f", "markdown": ":F1:"}],
        "implementation reqs": [{"markdown": "- :I1:"}],
        "test reqs": [{"markdown": "- :T1:"}],
    }
    errors = concept_utils.validate_concepts(tree)
    assert [e.split()[3] for e in errors] == [":I1:", ":T1:", ":F1:", ":D1:"]


def test_empty_list_sort():
    definitions: list = []
    concept_utils.sort_definitions(definitions)
    assert definitions == []
