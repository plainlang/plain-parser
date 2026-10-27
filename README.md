# plain-parser

Python parser for [`***plain`](https://www.plainlang.org/docs/) specification files.

Reads a `.plain` module with its `import` / `requires` chain and its test plain files, resolves Liquid templates,
validates concepts and linked resources, and returns the marshalled specification tree of every module in the
chain, with the test scenarios of each functionality merged in.

## Install

```bash
pip install plain-parser
```

## Command line

```
plain-parser check <file.plain> [--template-dir DIR] [--test-dir DIR]... [--config-name NAME]
plain-parser parse <file.plain> [--template-dir DIR] [--test-dir DIR]... [--config-name NAME]
```

Both commands parse the module and its `requires` chain, bind the test plain files under the test directories to the
functionalities, check that every linked resource is an existing file (not a directory), and walk the module's
functionalities. They stop at the first error.

### `check`

Validates the module. In addition to the steps above it reads every linked file and rejects binary files and
files holding a large base64 blob. When the config file names a `conformance-tests-script`, every functionality
of every module in the chain needs a test plain file bound to it; the sections of the file may be empty.

```
$ plain-parser check my_spec.plain
my_spec.plain: OK
```

Exit `0` when the module is valid. On an error, `Error: …` is written to stderr and the exit code is `1`. The
message names the file and the line where known. The previous syntax (`- ` bullets instead of `# <func-id>`
headings in `***functional specs***`, an `***acceptance tests***` section in a spec plain file) is reported as not
supported. A functionality without a test plain file names the `add-test-scenarios` skill.

### `parse`

Prints the parse result as one UTF-8 JSON document on stdout. Linked files are located but not read.

```
$ plain-parser parse my_spec.plain
{
  "format_version": 2,
  "modules": [{"module": "...", "tree": {...}}, ...],
  "resources": {...},
  "test_plain_files": {...}
}
```

- `format_version`: `2`.
- `modules`: every module in the `requires` chain, in build order: deepest ancestor first, the module itself last.
  Each entry has the module name and its specification tree, in the shape described under *Python* below.
- `resources`: every linked-resource target in the chain and its test plain files, as written in the spec, mapped
  to the path it resolves to, relative to the entry module's directory, with `/` as separator: `notes.md` when
  found next to the module, `../tpl/notes.md` when found in a template directory. The directory part is lexical
  (symlinks not resolved) and the target is appended as written (`..` kept), so joining the value onto the entry
  module's directory names the file the parser matched. When no relative path exists (another drive on Windows)
  the value is the absolute path, still with `/`. Two spellings of one file (`notes.md`, `./notes.md`) are two
  keys.
- `test_plain_files`: every test plain file read, by its path relative to the entry module's directory with `/`
  as separator, mapped to `{"module": ..., "func_id": ...}`, the functionality it binds to.

Exit `0` on success. On a parser error the JSON is `{"format_version": 2, "type": "<error class>",
"message": "…"}` and the exit code is `1`.

### Options and exit codes

Modules and `{% include %}` templates are looked up in the `.plain` file's directory, then in `--template-dir`.
When `--template-dir` is not given, it is read from the `template-dir` key of `config.yaml` (or the file named by
`--config-name`), found next to the `.plain` file or in the working directory. Finding it in both is a usage
error. The config file is read even when `--template-dir` is given, so a malformed one fails the run either way.

Test plain files are the `.plain` files under the test directories: those given with `--test-dir` (repeat the
option for more than one), else the `test-dir` key of the config file (a string or a list). Without both, no test
plain files are read, and a config file that names a `conformance-tests-script` makes that a usage error. A test
directory that does not exist is skipped. Linked resources in a scenario are looked up
as in a module. The `conformance-tests-script` key of the config file turns on the check that every
functionality has a test plain file. Other config keys are ignored.

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | The module, its chain, a test plain file, or a linked resource is invalid |
| `2` | Usage error, including an ambiguous or malformed config file |
| `130` | Interrupted |

## Python

```python
from plain_parser import plain_file_parser, project

module_name, plain_source_tree, required_modules = plain_file_parser("my_spec.plain", ["."])

result = project.parse_project("my_spec.plain", ["."], ["tests"], require_test_plain_files=True)
chain = result.chain  # (module name, plain source tree) pairs, deepest ancestor first, the module itself last
```

`plain_source_tree` is a dict keyed by section. `definitions`, `implementation reqs` and `test reqs` are lists
of `{"markdown": ..., "linked_resources": [...]}` entries. `functional specs` is a list of
`{"id", "markdown", "linked_resources", "conformance_tests", "acceptance_tests"}` entries, one per `# <func-id>`
heading in file order; each test entry is `{"id", "text", "linked_resources"}` with the scenario text as written.
`plain_parser.plain_spec` has helpers for walking functionalities by func-id (`get_frids`,
`get_specifications_for_frid`, `collect_linked_resources`).

## Development

```bash
uv venv --python 3.11 && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
black . --check && isort . --check-only && flake8 . && mypy src
```

## License

MIT, see [LICENSE](LICENSE).
