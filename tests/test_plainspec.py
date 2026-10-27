import pytest

from plain_parser import plain_file, plain_spec


def _functionality(id_, markdown, conformance_tests=(), acceptance_tests=(), linked_resources=()):
    return {
        "id": id_,
        "markdown": markdown,
        "linked_resources": list(linked_resources),
        plain_spec.CONFORMANCE_TESTS: list(conformance_tests),
        plain_spec.ACCEPTANCE_TESTS: list(acceptance_tests),
    }


def _scenario(id_, text, linked_resources=()):
    return {"id": id_, "text": text, "linked_resources": list(linked_resources)}


def _link(target):
    return {"text": target, "target": target}


def test_get_linked_resources_invalid_input():
    with pytest.raises(ValueError, match="plain_source_tree must be a dictionary."):
        plain_spec.collect_linked_resources([], [], None, True)


def test_has_acceptance_tests_true():
    plain_source = {
        plain_spec.FUNCTIONAL_REQUIREMENTS: [
            _functionality("first", "First functionality."),
            _functionality("second", "Second functionality.", acceptance_tests=[_scenario("works", "It works.")]),
        ]
    }
    assert plain_spec.has_acceptance_tests(plain_source) is True


def test_has_acceptance_tests_false_when_no_acceptance_tests():
    plain_source = {
        plain_spec.FUNCTIONAL_REQUIREMENTS: [
            _functionality("first", "First functionality."),
            _functionality("second", "Second functionality."),
        ]
    }
    assert plain_spec.has_acceptance_tests(plain_source) is False


def test_has_acceptance_tests_false_when_no_functional_requirements():
    assert plain_spec.has_acceptance_tests({}) is False


def test_get_frids_simple(get_test_data_path):
    _, plain_source, _ = plain_file.plain_file_parser("simple.plain", [get_test_data_path("data/")])

    frids = list(plain_spec.get_frids(plain_source))

    assert frids == ["simple-functionality"]


def test_get_first_functional_requirement_simple(get_test_data_path):
    _, plain_source, _ = plain_file.plain_file_parser("simple.plain", [get_test_data_path("data/")])

    assert plain_spec.get_first_frid(plain_source) == "simple-functionality"


def test_get_next_frid_not_exists(get_test_data_path):
    _, plain_source, _ = plain_file.plain_file_parser("simple.plain", [get_test_data_path("data/")])

    with pytest.raises(Exception, match="Functionality missing does not exist."):
        plain_spec.get_next_frid(plain_source, "missing")


def test_get_next_frid_simple(get_test_data_path):
    _, plain_source, _ = plain_file.plain_file_parser("simple.plain", [get_test_data_path("data/")])

    assert plain_spec.get_next_frid(plain_source, "simple-functionality") is None


def test_get_previous_frid_not_exists(get_test_data_path):
    _, plain_source, _ = plain_file.plain_file_parser("simple.plain", [get_test_data_path("data/")])

    with pytest.raises(Exception, match="Functionality missing does not exist."):
        plain_spec.get_previous_frid(plain_source, "missing")


def test_get_previous_frid_no_previous_frid(get_test_data_path):
    _, plain_source, _ = plain_file.plain_file_parser("simple.plain", [get_test_data_path("data/")])

    assert plain_spec.get_previous_frid(plain_source, "simple-functionality") is None


def test_get_specifications_simple(get_test_data_path):
    _, plain_source, _ = plain_file.plain_file_parser("simple.plain", [get_test_data_path("data/")])

    with pytest.raises(Exception, match="Functionality a does not exist."):
        plain_spec.get_specifications_for_frid(plain_source, "a")

    frid = plain_spec.get_first_frid(plain_source)

    specifications, code_variables = plain_spec.get_specifications_for_frid(plain_source, frid)

    assert specifications == {
        "definitions": [],
        "implementation reqs": ["- Simple implementation requirement"],
        "test reqs": [],
        "functional specs": ["Simple functionality"],
        "conformance_tests": [],
        "acceptance_tests": [],
    }
    assert code_variables is None


def _four_functionalities():
    return {
        plain_spec.DEFINITIONS: [{"markdown": "- :Thing: is a thing."}],
        plain_spec.FUNCTIONAL_REQUIREMENTS: [
            _functionality(
                f"f{i}",
                f"Functionality {i}.",
                conformance_tests=[_scenario(f"f{i}-works", f"Functionality {i} works.", [_link(f"c{i}.md")])],
                acceptance_tests=[_scenario(f"f{i}-flow", f"Functionality {i} flows.", [_link(f"a{i}.md")])],
                linked_resources=[_link(f"r{i}.md")],
            )
            for i in range(1, 5)
        ],
    }


def test_get_frids_yields_ids_in_file_order():
    assert list(plain_spec.get_frids(_four_functionalities())) == ["f1", "f2", "f3", "f4"]


def test_get_frids_before():
    assert plain_spec.get_frids_before(_four_functionalities(), "f3") == ["f1", "f2"]


def test_get_specifications_for_frid_takes_functional_specs_up_to_the_frid_and_its_scenarios():
    specifications, _ = plain_spec.get_specifications_for_frid(_four_functionalities(), "f2")

    assert specifications == {
        "definitions": ["- :Thing: is a thing."],
        "implementation reqs": [],
        "test reqs": [],
        "functional specs": ["Functionality 1.", "Functionality 2."],
        "conformance_tests": [{"id": "f2-works", "text": "Functionality 2 works."}],
        "acceptance_tests": [{"id": "f2-flow", "text": "Functionality 2 flows."}],
    }


def test_get_specifications_for_frid_replaces_code_variables_in_scenarios():
    tree = _four_functionalities()
    tree[plain_spec.FUNCTIONAL_REQUIREMENTS][0][plain_spec.CONFORMANCE_TESTS] = [
        {
            "id": "greets",
            "text": "It prints {{ greeting }}.",
            "linked_resources": [],
            "code_variables": [{"name": "greeting", "value": "hello"}],
        }
    ]

    specifications, code_variables = plain_spec.get_specifications_for_frid(tree, "f1")

    assert specifications["conformance_tests"] == [{"id": "greets", "text": "It prints hello."}]
    assert code_variables == {"greeting": "hello"}


def _collected_targets(tree, include_test_scenarios, frid=None):
    linked_resources = []
    reached = plain_spec.collect_linked_resources(tree, linked_resources, None, include_test_scenarios, frid)
    return reached, [resource["target"] for resource in linked_resources]


def test_collect_linked_resources_stops_at_the_frid_and_takes_only_its_scenarios():
    reached, targets = _collected_targets(_four_functionalities(), True, "f2")

    assert reached is True
    assert targets == ["a2.md", "c2.md", "r1.md", "r2.md"]


def test_collect_linked_resources_without_frid_takes_every_functionality_and_scenario():
    reached, targets = _collected_targets(_four_functionalities(), True)

    assert reached is False
    assert targets == sorted(f"{kind}{i}.md" for kind in "acr" for i in range(1, 5))


def test_collect_linked_resources_can_leave_out_the_scenarios():
    _, targets = _collected_targets(_four_functionalities(), False)

    assert targets == ["r1.md", "r2.md", "r3.md", "r4.md"]


def test_collect_linked_resources_unknown_frid_raises():
    with pytest.raises(ValueError, match="frid f9 does not exist."):
        plain_spec.collect_linked_resources(_four_functionalities(), [], None, True, "f9")


def test_get_frids_range_start_and_end_inclusive():
    assert plain_spec.get_frids_range(_four_functionalities(), "f2", "f3") == ["f2", "f3"]


def test_get_frids_range_without_end_runs_to_last_frid():
    assert plain_spec.get_frids_range(_four_functionalities(), "f3") == ["f3", "f4"]


def test_get_frids_range_unknown_start_raises():
    with pytest.raises(plain_spec.InvalidFridArgument, match="Invalid start functionality ID: f9"):
        plain_spec.get_frids_range(_four_functionalities(), "f9")


def test_get_frids_range_unknown_end_raises():
    with pytest.raises(plain_spec.InvalidFridArgument, match="Invalid end functionality ID: f9"):
        plain_spec.get_frids_range(_four_functionalities(), "f1", "f9")


def test_get_frids_range_start_after_end_raises():
    with pytest.raises(plain_spec.InvalidFridArgument, match="must be before"):
        plain_spec.get_frids_range(_four_functionalities(), "f3", "f2")


@pytest.mark.parametrize("text", ["a", "add-task", "add-task-2", "2", "a-b-c", "x1-y2"])
def test_is_semantic_id_accepts_segments_joined_by_single_hyphens(text):
    assert plain_spec.is_semantic_id(text) is True


@pytest.mark.parametrize(
    "text",
    ["", "-", "---", "-add-task", "add-task-", "add--task", "add_task", "Add-task", "add task", "add.task", "ädd"],
)
def test_is_semantic_id_rejects_other_shapes(text):
    assert plain_spec.is_semantic_id(text) is False
