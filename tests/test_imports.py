import pytest

from plain_parser import plain_file
from plain_parser.exceptions import ImportedModuleWithFunctionalitiesError, PlainSyntaxError


def test_imported_module_with_functionalities(load_test_data, get_test_data_path):
    plain_source_text = load_test_data("data/imports/imports_module_with_functionalities.plain")
    template_dirs = [get_test_data_path("data/imports")]
    with pytest.raises(
        ImportedModuleWithFunctionalitiesError,
        match="use 'requires' instead of 'import'",
    ):
        plain_file.parse_plain_source(plain_source_text, {}, template_dirs, [], [])


def test_non_existent_import(load_test_data, get_test_data_path):
    plain_source_text = load_test_data("data/imports/non_existent_import.plain")
    with pytest.raises(Exception, match="Module does not exist"):
        plain_file.parse_plain_source(plain_source_text, {}, [], [], [])


def test_circular_imports(load_test_data, get_test_data_path):
    plain_source_text = load_test_data("data/imports/circular_imports_main.plain")
    template_dirs = [get_test_data_path("data/imports")]
    with pytest.raises(Exception, match="Circular import detected"):
        plain_file.parse_plain_source(plain_source_text, {}, template_dirs, [], [])


def test_diamond_imports(load_test_data, get_test_data_path):
    plain_source_text = load_test_data("data/imports/diamond_imports_main.plain")
    template_dirs = [get_test_data_path("data/imports")]
    plain_file_parse_result = plain_file.parse_plain_source(plain_source_text, {}, template_dirs, [], [])

    assert plain_file.marshall_plain_source(plain_file_parse_result.plain_source) == {
        "definitions": [
            {"markdown": "- :CommonImportDef: is a definition in diamond_import_common."},
            {"markdown": "- :Import1Def: is a definition in diamond_import_1."},
            {"markdown": "- :Import2Def: is a definition in diamond_import_2."},
        ],
        "implementation reqs": [
            {"markdown": "- :CommonImportDef: is used in diamond_import_common."},
            {"markdown": "- :Import1Def: is used in diamond_import_1."},
            {"markdown": "- :Import2Def: is used in diamond_import_2."},
            {"markdown": '- :MainExecutableFile: of :App: should be called "hello_world.py".'},
        ],
        "test reqs": [
            {"markdown": "- :CommonImportDef: is tested in diamond_import_common."},
            {"markdown": "- :Import1Def: is tested in diamond_import_1."},
            {"markdown": "- :Import2Def: is tested in diamond_import_2."},
        ],
        "functional specs": [{"markdown": '- Display "hello, world"'}],
    }


@pytest.mark.parametrize("fixture", ["scalar_import", "scalar_import_single_char"])
def test_scalar_import_is_a_list_of_one(load_test_data, get_test_data_path, fixture):
    plain_source_text = load_test_data(f"data/imports/{fixture}/main.plain")
    template_dirs = [get_test_data_path(f"data/imports/{fixture}")]
    plain_file_parse_result = plain_file.parse_plain_source(plain_source_text, {}, template_dirs, [], [])

    assert plain_file.marshall_plain_source(plain_file_parse_result.plain_source)["implementation reqs"] == [
        {"markdown": '- The main executable file should be called "hello_world.py".'},
        {"markdown": '- The main executable file should be called "hello_world.py".'},
    ]


@pytest.mark.parametrize("directive", ["import", "requires"])
def test_non_string_module_entry_is_a_syntax_error(directive):
    plain_source_text = f"---\n{directive}: [1]\n---\n\n***functional specs***\n\n- Display text\n"
    with pytest.raises(PlainSyntaxError, match=f"Invalid {directive} metadata"):
        plain_file.parse_plain_source(plain_source_text, {}, [], [], [])


@pytest.mark.parametrize("directive", ["exported_concepts", "required_concepts"])
def test_scalar_concept_directive_is_a_list_of_one(directive):
    plain_source_obj = plain_file.read_plain_source_metadata(f'---\n{directive}: ":A:"\n---\n')

    assert plain_source_obj.metadata[directive] == ["- :A:"]


@pytest.mark.parametrize("directive", ["exported_concepts", "required_concepts"])
def test_non_string_concept_entry_is_a_syntax_error(directive):
    with pytest.raises(PlainSyntaxError, match=f"Invalid {directive} metadata"):
        plain_file.read_plain_source_metadata(f"---\n{directive}: [1]\n---\n")


@pytest.mark.parametrize("value", ["foo", "[foo]"])
def test_imported_required_concept_without_concept_token_is_a_syntax_error(tmp_path, value):
    (tmp_path / "lib.plain").write_text(f"---\nrequired_concepts: {value}\n---\n\n***implementation reqs***\n\n- x\n")
    plain_source_text = (
        "---\nimport: [lib]\n---\n\n***implementation reqs***\n\n- y\n\n***functional specs***\n\n- Display text\n"
    )
    with pytest.raises(PlainSyntaxError, match="requires an invalid concept"):
        plain_file.parse_plain_source(plain_source_text, {}, [str(tmp_path)], [], [])
