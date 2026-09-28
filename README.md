# plain-parser

Python parser for [`***plain`](https://www.plainlang.org/docs/) specification files.

Reads a `.plain`  module and its `import` / `requires` chain, resolves Liquid templates,
validates concepts and linked resources, and returns the marshalled specification tree
plus the ordered list of functionalities (FRIDs).

## Install

```bash
pip install plain-parser
```

## Usage

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
