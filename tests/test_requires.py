import pytest

from plain_parser import plain_file
from plain_parser.exceptions import ModuleDoesNotExistError


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


def test_required_module_sees_exports_of_an_ancestor_listed_before_it(get_test_data_path):
    # shared_export_top requires [base, middle]; middle uses :KeyStore: exported by base.
    plain_file.plain_file_parser("shared_export_top.plain", [get_test_data_path("data/requires")])


def test_module_above_a_repeated_ancestor_parses(get_test_data_path):
    chain = plain_file.parse_module_chain("shared_export_above.plain", [get_test_data_path("data/requires")])

    assert [module_name for module_name, _ in chain] == [
        "shared_export_base",
        "shared_export_middle",
        "shared_export_top",
        "shared_export_above",
    ]


def write_modules_using_required_exports(directory, requires_by_module):
    # Writes one <name>.plain per entry, with the listed modules as its requires. Each module exports
    # :<name>Concept: and uses the exported concept of every module it requires, so an export that does
    # not reach a dependent module fails the parse with "Concept ... is not defined".
    for module_name, required_modules in requires_by_module.items():
        requires = "".join(f"  - {required_module}\n" for required_module in required_modules)
        used_concepts = "".join(f" :{required_module}Concept:" for required_module in required_modules)
        (directory / f"{module_name}.plain").write_text(
            "---\n"
            f"exported_concepts:\n  - :{module_name}Concept:\n"
            + (f"requires:\n{requires}" if required_modules else "")
            + "---\n\n"
            f"***definitions***\n\n- :{module_name}Concept: is defined by {module_name}.\n\n"
            "***implementation reqs***\n\n- An implementation requirement.\n\n"
            f"***functional specs***\n\n- :{module_name}Concept: uses{used_concepts or ' nothing'}.\n"
        )


# In each diagram, a line down from one module to another means the upper module requires the lower one.
@pytest.mark.parametrize(
    "requires_by_module, expected_chain",
    [
        #   Top
        #   |  \
        #   |  Middle
        #   |  /
        #   Base
        pytest.param(
            {"Top": ["Base", "Middle"], "Middle": ["Base"], "Base": []},
            ["Base", "Middle", "Top"],
            id="top-relists-base-before-middle",
        ),
        # Same shape, but Top lists Base after Middle.
        pytest.param(
            {"Top": ["Middle", "Base"], "Middle": ["Base"], "Base": []},
            ["Base", "Middle", "Top"],
            id="top-relists-base-after-middle",
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
            id="upper-relists-base-and-middle",
            marks=pytest.mark.xfail(strict=True, reason="only the last processed module is recognised as repeated"),
        ),
    ],
)
def test_requires_chain_is_accepted(tmp_path, requires_by_module, expected_chain):
    write_modules_using_required_exports(tmp_path, requires_by_module)

    chain = plain_file.parse_module_chain("Top.plain", [str(tmp_path)])

    assert [module_name for module_name, _ in chain] == expected_chain


# In each diagram, a line down from one module to another means the upper module requires the lower one.
@pytest.mark.parametrize(
    "requires_by_module",
    [
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
            id="two-branches-share-base-top-relists-base",
        ),
    ],
)
def test_requires_diamond_is_rejected(tmp_path, requires_by_module):
    write_modules_using_required_exports(tmp_path, requires_by_module)

    with pytest.raises(Exception, match="There must be a fixed order how required modules are dependent"):
        plain_file.parse_module_chain("Top.plain", [str(tmp_path)])


# In each diagram, a line down from one module to another means the upper module requires the lower one.
@pytest.mark.parametrize(
    "requires_by_module",
    [
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
    ],
)
def test_requires_independent_branches_are_rejected(tmp_path, requires_by_module):
    write_modules_using_required_exports(tmp_path, requires_by_module)

    with pytest.raises(Exception, match="There must be a fixed order how required modules are dependent"):
        plain_file.parse_module_chain("Top.plain", [str(tmp_path)])
