# plain-parser public Python API

Package `plain_parser` (import name), distribution `plain-parser`, console script `plain-parser = plain_parser.cli:main`.
Every name below is public: callers import it, so names, parameters, defaults and return shapes are fixed.

## `plain_parser` (package `__init__`)

Re-exports, listed in `__all__` in this order:

```
PlainFileParseResult, concept_utils, exceptions, get_filename_from_module_name, get_module_name_from_filename,
loaders, marshall_plain_source, parse_module_chain, parse_plain_file, parse_plain_source, plain_file,
plain_file_parser, plain_spec, project, test_plain_file
```

The submodules `concept_utils`, `exceptions`, `loaders`, `plain_file`, `plain_spec`, `project`, `test_plain_file`
are importable as attributes of the package. The submodules `graph`, `liquid_nodes` and `cli` exist too.

## `plain_parser.exceptions`

Each class derives directly from `Exception` and adds nothing:

```
PlainSyntaxError, UnsupportedBase64Content, UnsupportedResourceType, InvalidFridArgument,
InvalidLiquidVariableName, ModuleDoesNotExistError, MissingFunctionalitiesError,
ImportedModuleWithFunctionalitiesError, MissingTestPlainFileError
```

## `plain_parser.graph`

```
strongly_connected_components(graph: Mapping[Node, Iterable[Node]]) -> list[set[Node]]
simple_cycles(graph: Mapping[Node, Iterable[Node]], limit: int | None = None) -> Iterator[list[Node]]
```

## `plain_parser.plain_spec`

Constants:

```
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
SEMANTIC_ID_PATTERN  (compiled regular expression [a-z0-9]+(?:-[a-z0-9]+)*)
```

`InvalidFridArgument` and `InvalidLiquidVariableName` are importable from `plain_spec` as well.

Functions:

```
is_semantic_id(text: str) -> bool
has_acceptance_tests(plain_source_tree) -> bool
collect_specification_linked_resources(specification, specification_heading, linked_resources_list) -> None
collect_linked_resources(plain_source_tree, linked_resources_list, specifications_list, include_test_scenarios, frid=None) -> bool
get_frids(plain_source_tree) -> Iterator[str]            (a generator)
get_first_frid(plain_source_tree) -> str | None
get_next_frid(plain_source_tree, frid) -> str | None
get_previous_frid(plain_source_tree, frid) -> str | None
get_frids_before(plain_source_tree, target_frid: str) -> list[str]
get_specification_item_markdown(specification_item, code_variables, replace_code_variables, key="markdown") -> str
get_specifications_for_frid(plain_source_tree, frid, replace_code_variables=True) -> tuple[dict, dict | None]
code_variable_liquid_filter(value, *, context)            (a liquid2 filter taking the render context)
prohibited_chars_liquid_filter(value, prohibited_chars, *, context)   (a liquid2 filter taking the render context)
hash_text(text: str) -> str
get_hash_value(specifications) -> str
get_frids_range(plain_source, start, end=None) -> list[str]
```

## `plain_parser.loaders`

```
MAX_BASE64_BLOB_LENGTH = 8192
find_large_base64_blob(text: str) -> str | None
open_from(dirs, file_name) -> str | None
find_resource_dir(dirs, file_name) -> str | None
resolve_linked_resource(dirs, file_name) -> str | None
relative_resource_path(base_dir: str, resource_dir: str, target: str) -> str
load_linked_resources(template_dirs: list[str], resources_list, module_name: str) -> dict[str, str]
liquid_error_message(error: LiquidSyntaxError) -> str
get_loaded_templates(source_path, plain_source, template_name=None) -> tuple[str, dict[str, str]]
TrackingFileSystemLoader   (liquid2 file system loader that records every loaded template source by name)
```

## `plain_parser.liquid_nodes`

```
Plain2CodeIncludeNode, Plain2CodeIncludeTag, Plain2CodeLoaderMixin
```

## `plain_parser.concept_utils`

```
DEFAULT_CONCEPTS: set[str]
MAX_REPORTED_CYCLES = 10
extract_concepts_from_definition(text: str) -> tuple[list[str], list[str]]      (concepts, errors)
extract_concepts_from_spec_text(text: str) -> list[str]
collect_concepts(plain_source) -> tuple[list[str] | set[str], list[str]]        (concepts, errors)
validate_concepts_in_spec(spec: dict, concepts: set[str], spec_group: str) -> list[str]
validate_concepts_in_spec_group(spec_group, plain_source, concepts: set[str]) -> list[str]
validate_concepts(marshalled_plain_source) -> list[str]
find_concept_definitions_in_plain_source(concept: str, plain_source: dict, renderer) -> list[token]
build_adjacency_list(definitions) -> tuple[dict, dict]
format_cycles_error(adjacency_list, concept_definitions) -> str
sort_definitions(definitions: list[dict]) -> None        (sorts the list in place)
```

## `plain_parser.plain_file`

```
RESOURCE_MARKER = "[resource]"
IMPORT_DIRECTIVE = "import"
REQUIRES_DIRECTIVE = "requires"
REQUIRED_CONCEPTS_DIRECTIVE = "required_concepts"
EXPORTED_CONCEPTS_DIRECTIVE = "exported_concepts"
PLAIN_SOURCE_FILE_EXTENSION = ".plain"

@dataclass PlainFileParseResult(plain_source: dict, plain_source_obj: frontmatter.Post,
                                required_modules: list[str], required_concepts: list[str])

get_filename_from_module_name(module_name: str) -> str
get_module_name_from_filename(filename: str) -> str
normalize_line_endings(plain_source_text: str) -> str
restore_stripped_lines(plain_source_text: str, content: str) -> str
find_linked_resources(tokens, template_dirs, where: str = "") -> list[dict]
process_section_code_variables(section, code_variables, text_key="markdown") -> None
render_plain_source(plain_source, loaded_templates, code_variables) -> str
marshall_plain_source(input_plain_source) -> dict
parse_plain_source(plain_source_text: str, code_variables: dict, template_dirs: list[str],
                   imported_modules: list[str], modules_trace: list[str], module_name: str | None = None)
    -> PlainFileParseResult
parse_plain_file(module_name: str, code_variables: dict, template_dirs: list[str],
                 imported_modules: list[str], modules_trace: list[str]) -> PlainFileParseResult
plain_file_parser(plain_source_file_name: str, template_dirs: list[str]) -> tuple[str, dict, list[str]]
    (module name, plain source tree, the module's own requires list)
parse_module_chain(plain_file_name: str, template_dirs: list[str]) -> list[tuple[str, dict]]
```

## `plain_parser.test_plain_file`

```
MODULE_KEY = "module"
FUNC_ID_KEY = "func_id"

@dataclass Scenario(id: str, line_number: int, text: str = "", linked_resources: list[dict] = [],
                    code_variables: list[dict] = [])
    to_dict() -> dict      {"id", "text", "linked_resources"} plus "code_variables" when not empty
@dataclass TestPlainFile(name: str, module: str, func_id: str,
                         conformance_tests: list[Scenario], acceptance_tests: list[Scenario])
    scenarios -> list[Scenario]   (property: conformance then acceptance)

is_test_plain_file(metadata: dict) -> bool
parse_test_plain_file_source(plain_source_text: str, name: str, template_dirs: list[str], code_variables: dict)
    -> TestPlainFile
validate_scenario_concepts(test_plain_file: TestPlainFile, concepts: set[str]) -> list[str]
```

## `plain_parser.project`

```
@dataclass BoundTestPlainFile(path: str, name: str, parsed: TestPlainFile)
@dataclass ProjectParseResult(chain: list[tuple[str, dict]], test_plain_files: list[BoundTestPlainFile])

discover_test_plain_files(tests_folders: list[str], entry_dir: str) -> list[tuple[str, str]]
bind_test_plain_files(chain, tests_folders, template_dirs, entry_dir) -> list[BoundTestPlainFile]
check_test_plain_files(chain, bound) -> None
parse_project(plain_file_name: str, template_dirs: list[str], tests_folders: list[str],
              require_test_plain_files: bool) -> ProjectParseResult
```

## `plain_parser.cli`

```
DEFAULT_CONFIG_NAME = "config.yaml"
PARSE_FORMAT_VERSION = 2
AmbiguousConfigFileError(Exception)
@dataclass Config(template_dir: str | None = None, tests_folders: list[str] | None = None,
                  conformance_tests_enabled: bool = False)
@dataclass ParseResult(modules: list[tuple[str, dict]], resources: dict[str, str], test_plain_files: dict[str, dict] = {})

build_parser() -> argparse.ArgumentParser
resolve_config_file(config_name: str, plain_file_path: str) -> str | None
read_config(config_file: str) -> Config
parse_spec(plain_file_path: str, template_dir: str | None, load_resources: bool,
           tests_folders: list[str] | None = None, require_test_plain_files: bool = False) -> ParseResult
check(plain_file_path: str, template_dir: str | None, tests_folders: list[str] | None = None,
      require_test_plain_files: bool = False) -> None
parse(plain_file_path: str, template_dir: str | None, tests_folders: list[str] | None = None,
      require_test_plain_files: bool = False) -> int
main(argv: list[str] | None = None) -> int
```
