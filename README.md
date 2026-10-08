# plain-parser

Python parser for [`***plain`](https://www.plainlang.org/docs/) specification files.

Reads a `.plain` module and its `import` / `requires` chain, resolves Liquid templates,
validates concepts and linked resources, and returns the marshalled specification tree
plus the ordered list of functionalities (FRIDs).

## Install

```bash
pip install plain-parser
```

## Command line

```
plain-parser check <file.plain> [--template-dir DIR] [--config-name NAME]
plain-parser parse <file.plain> [--template-dir DIR] [--config-name NAME]
```

Both commands parse the module and its `requires` chain, check that every linked resource is an existing
file (not a directory), and walk the module's functionalities. They stop at the first error.

### `check`

Validates the module. In addition to the steps above it reads every linked file and rejects binary files and
files holding a large base64 blob.

```
$ plain-parser check my_spec.plain
my_spec.plain: OK
```

Exit `0` when the module is valid. On an error, `Error: …` is written to stderr and the exit code is `1`.

### `parse`

Prints the parse result as one UTF-8 JSON document on stdout. Linked files are located but not read.

```
$ plain-parser parse my_spec.plain
{
  "format_version": 1,
  "modules": [{"module": "...", "tree": {...}}, ...],
  "resources": {...}
}
```

- `format_version`: `1`.
- `modules`: every module in the `requires` chain, in build order: deepest ancestor first, the module itself last.
  Each entry has the module name and its specification tree, in the shape described under *Python* below.
- `resources`: every linked-resource target in the chain, as written in the spec, mapped to the absolute path it
  resolves to. Two spellings of one file (`notes.md`, `./notes.md`) are two keys.

Exit `0` on success. On a parser error the JSON is `{"format_version": 1, "type": "<error class>",
"message": "…"}` and the exit code is `1`.

### Options and exit codes

Modules and `{% include %}` templates are looked up in the `.plain` file's directory, then in `--template-dir`.
When `--template-dir` is not given, it is read from the `template-dir` key of `config.yaml` (or the file named by
`--config-name`), found next to the `.plain` file or in the working directory. Finding it in both is a usage
error. The config file is read even when `--template-dir` is given, so a malformed one fails the run either way.
Other config keys are ignored.

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | The module, its chain, or a linked resource is invalid |
| `2` | Usage error, including an ambiguous or malformed config file |
| `130` | Interrupted |

## Python

```python
from plain_parser import plain_file_parser

module_name, plain_source_tree, required_modules = plain_file_parser("my_spec.plain", ["."])
```

`plain_source_tree` is a dict keyed by section (`definitions`, `implementation reqs`,
`test reqs`, `functional specs`), each a list of `{"markdown": ..., "linked_resources": [...]}`
entries. `plain_parser.plain_spec` has helpers for walking functionalities
(`get_frids`, `get_specifications_for_frid`, `collect_linked_resources`).

## Development

```bash
uv venv --python 3.11 && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
black . --check && isort . --check-only && flake8 . && mypy src
```

## License

MIT, see [LICENSE](LICENSE).
