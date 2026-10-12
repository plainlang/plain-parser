import pytest

from plain_parser import plain_file
from plain_parser.exceptions import ModuleDoesNotExistError, PlainSyntaxError


def test_non_existent_require(get_test_data_path):
    with pytest.raises(ModuleDoesNotExistError, match="Module does not exist"):
        plain_file.plain_file_parser("non_existent_require.plain", [get_test_data_path("data/requires")])


def test_independent_requires(get_test_data_path):
    with pytest.raises(Exception, match="There must be a fixed order how required modules are dependent"):
        plain_file.plain_file_parser("independent_requires_main.plain", [get_test_data_path("data/requires")])


def test_diamond_requires(get_test_data_path):
    with pytest.raises(Exception, match="There must be a fixed order how required modules are dependent"):
        plain_file.plain_file_parser("diamond_requires_main.plain", [get_test_data_path("data/requires")])


def test_circular_requires(get_test_data_path):
    with pytest.raises(Exception, match="Circular required module detected"):
        plain_file.plain_file_parser("circular_requires_main.plain", [get_test_data_path("data/requires")])


def test_normal_requires(get_test_data_path):
    plain_file.plain_file_parser("normal_requires_main.plain", [get_test_data_path("data/requires")])


def test_parse_module_chain_orders_required_modules_first(get_test_data_path):
    chain = plain_file.parse_module_chain("chain_top.plain", [get_test_data_path("data/requires")])

    assert [module_name for module_name, _ in chain] == ["chain_base", "chain_middle", "chain_top"]
    for _, plain_source_tree in chain:
        assert isinstance(plain_source_tree, dict)
        assert "functional specs" in plain_source_tree


def test_parse_module_chain_single_module(get_test_data_path):
    chain = plain_file.parse_module_chain("chain_base.plain", [get_test_data_path("data/requires")])

    assert [module_name for module_name, _ in chain] == ["chain_base"]


def test_parse_module_chain_deduplicates_shared_ancestor(get_test_data_path):
    chain = plain_file.parse_module_chain("chain_fork_top.plain", [get_test_data_path("data/requires")])

    assert [module_name for module_name, _ in chain] == ["chain_base", "chain_middle", "chain_fork_top"]


def test_parse_module_chain_propagates_required_module_errors(get_test_data_path):
    with pytest.raises(ModuleDoesNotExistError, match="Module does not exist"):
        plain_file.parse_module_chain("non_existent_require.plain", [get_test_data_path("data/requires")])


def test_plain_file_parser_validates_required_modules(get_test_data_path):
    # The ancestor is fully validated during the parse of the top module, not only when the chain is walked.
    with pytest.raises(Exception, match="Concept :UndefinedThing: is not defined"):
        plain_file.plain_file_parser("invalid_ancestor_top.plain", [get_test_data_path("data/requires")])


def write_module(directory, module_name, exported_concepts, required_modules, definitions, functional_spec):
    exports = "".join(f"  - {concept}\n" for concept in exported_concepts)
    requires = "".join(f"  - {required_module}\n" for required_module in required_modules)
    (directory / f"{module_name}.plain").write_text(
        "---\n"
        + (f"exported_concepts:\n{exports}" if exported_concepts else "")
        + (f"requires:\n{requires}" if required_modules else "")
        + "---\n\n"
        "***definitions***\n\n"
        + "".join(f"- {definition}\n\n" for definition in definitions)
        + "***implementation reqs***\n\n- An implementation requirement.\n\n"
        f"***functional specs***\n\n- {functional_spec}\n"
    )


# Top requires [Base, Middle] and Middle requires Base. Above requires Top.
def test_middle_module_sees_exports_of_base_module(get_test_data_path):
    # shared_export_top requires [base, middle]; middle uses :KeyStore: exported by base.
    plain_file.plain_file_parser("shared_export_top.plain", [get_test_data_path("data/requires")])


def test_middle_module_sees_exports_of_base_module_when_parsing_above_module(get_test_data_path):
    # The skip of Base happens in a nested call of process_required_modules.
    chain = plain_file.parse_module_chain("shared_export_above.plain", [get_test_data_path("data/requires")])

    assert [module_name for module_name, _ in chain] == [
        "shared_export_base",
        "shared_export_middle",
        "shared_export_top",
        "shared_export_above",
    ]


def test_middle_module_redefining_an_export_of_base_module_is_rejected(tmp_path):
    write_module(tmp_path, "Base", [":BaseConcept:"], [], [":BaseConcept: is defined by Base."], "Base works.")
    write_module(
        tmp_path, "Middle", [], ["Base"], [":BaseConcept: is defined again by Middle."], "Middle uses :BaseConcept:."
    )
    write_module(tmp_path, "Top", [], ["Base", "Middle"], [], "Top uses :BaseConcept:.")

    with pytest.raises(PlainSyntaxError, match="Concepts were defined multiple times: :BaseConcept:"):
        plain_file.parse_module_chain("Top.plain", [str(tmp_path)])


def test_base_module_may_export_nothing(tmp_path):
    write_module(tmp_path, "Base", [], [], [":BaseConcept: is defined by Base."], "Base works.")
    write_module(
        tmp_path, "Middle", [":MiddleConcept:"], ["Base"], [":MiddleConcept: is defined by Middle."], "Middle works."
    )
    write_module(tmp_path, "Top", [], ["Base", "Middle"], [], "Top uses :MiddleConcept:.")

    chain = plain_file.parse_module_chain("Top.plain", [str(tmp_path)])

    assert [module_name for module_name, _ in chain] == ["Base", "Middle", "Top"]


def write_modules_using_required_exports(directory, requires_by_module):
    # Writes one <name>.plain per entry, with the listed modules as its requires. Each module exports
    # :<name>Concept: and uses the exported concept of every module it requires, so an export that does
    # not reach a dependent module fails the parse with "Concept ... is not defined".
    for module_name, required_modules in requires_by_module.items():
        used_concepts = "".join(f" :{required_module}Concept:" for required_module in required_modules)
        write_module(
            directory,
            module_name,
            exported_concepts=[f":{module_name}Concept:"],
            required_modules=required_modules,
            definitions=[f":{module_name}Concept: is defined by {module_name}."],
            functional_spec=f":{module_name}Concept: uses{used_concepts or ' nothing'}.",
        )


# In each diagram, a line down from one module to another means the upper module requires the lower one.

# Each module requires the modules below it. The parser must return the chain deepest first.
ACCEPTED_CHAINS = [
    #   Top
    #   |  \
    #   |  Middle
    #   |  /
    #   Base
    pytest.param(
        {"Top": ["Base", "Middle"], "Middle": ["Base"], "Base": []},
        ["Base", "Middle", "Top"],
        id="top-also-requires-base-before-middle",
    ),
    # Same shape, but Top lists Base after Middle.
    pytest.param(
        {"Top": ["Middle", "Base"], "Middle": ["Base"], "Base": []},
        ["Base", "Middle", "Top"],
        id="top-also-requires-base-after-middle",
        marks=pytest.mark.xfail(strict=True, reason="an ancestor must be listed before its dependent"),
    ),
    #   Top
    #    |
    #   Upper    every module also requires every module below it
    #    |
    #   Middle
    #    |
    #   Base
    pytest.param(
        {"Top": ["Base", "Middle", "Upper"], "Upper": ["Base", "Middle"], "Middle": ["Base"], "Base": []},
        ["Base", "Middle", "Upper", "Top"],
        id="upper-also-requires-base-and-middle",
        marks=pytest.mark.xfail(strict=True, reason="only the last processed module is recognised as repeated"),
    ),
]


# Two branches that meet at a shared base. Rejected with the fixed-order error.
DIAMONDS = [
    #      Top
    #     /   \
    #  Left   Right
    #     \   /
    #      Base
    pytest.param(
        {"Top": ["Left", "Right"], "Left": ["Base"], "Right": ["Base"], "Base": []},
        id="two-branches-share-base",
    ),
    # Same shape, but Top lists Right before Left.
    pytest.param(
        {"Top": ["Right", "Left"], "Left": ["Base"], "Right": ["Base"], "Base": []},
        id="two-branches-share-base-right-listed-first",
    ),
    #        Top
    #       /   \
    #    Left   Right
    #     |       |
    # LeftBase  RightBase
    #       \   /
    #       Base
    pytest.param(
        {
            "Top": ["Left", "Right"],
            "Left": ["LeftBase"],
            "Right": ["RightBase"],
            "LeftBase": ["Base"],
            "RightBase": ["Base"],
            "Base": [],
        },
        id="two-branches-share-base-two-levels-down",
    ),
    #   Top
    #   |  \
    #   |  Right
    #   |  /   \
    #   Left  Other
    #     \   /
    #     Base
    pytest.param(
        {"Top": ["Left", "Right"], "Left": ["Base"], "Other": ["Base"], "Right": ["Left", "Other"], "Base": []},
        id="branches-below-right-share-base",
    ),
    #      Top
    #    /  |  \
    # Left  |  Right
    #    \  |  /
    #     Base
    pytest.param(
        {"Top": ["Base", "Left", "Right"], "Left": ["Base"], "Right": ["Base"], "Base": []},
        id="two-branches-share-base-top-also-requires-base",
    ),
]


# Branches that share no base. Rejected with the fixed-order error.
INDEPENDENT_BRANCHES = [
    #      Top
    #     /   \
    #  Left   Right
    pytest.param({"Top": ["Left", "Right"], "Left": [], "Right": []}, id="two-modules-without-requires"),
    #      Top
    #     /   \
    #  Left   Right
    #           |
    #         Other
    pytest.param(
        {"Top": ["Left", "Right"], "Left": [], "Right": ["Other"], "Other": []},
        id="branches-without-shared-base",
    ),
]


@pytest.mark.parametrize("requires_by_module, expected_chain", ACCEPTED_CHAINS)
def test_requires_chain_is_accepted(tmp_path, requires_by_module, expected_chain):
    write_modules_using_required_exports(tmp_path, requires_by_module)

    chain = plain_file.parse_module_chain("Top.plain", [str(tmp_path)])

    assert [module_name for module_name, _ in chain] == expected_chain


@pytest.mark.parametrize("requires_by_module", DIAMONDS)
def test_requires_diamond_is_rejected(tmp_path, requires_by_module):
    write_modules_using_required_exports(tmp_path, requires_by_module)

    with pytest.raises(PlainSyntaxError, match="There must be a fixed order how required modules are dependent"):
        plain_file.parse_module_chain("Top.plain", [str(tmp_path)])


@pytest.mark.parametrize("requires_by_module", INDEPENDENT_BRANCHES)
def test_requires_independent_branches_are_rejected(tmp_path, requires_by_module):
    write_modules_using_required_exports(tmp_path, requires_by_module)

    with pytest.raises(PlainSyntaxError, match="There must be a fixed order how required modules are dependent"):
        plain_file.parse_module_chain("Top.plain", [str(tmp_path)])
