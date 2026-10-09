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
