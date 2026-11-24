- [x] :ModuleParser: reads the rendered text into a mistletoe `Document` inside a `MarkdownRenderer` subclass context, so blank lines become `BlankLine` tokens, and removes every block quote token, nested ones included, as a :CommentLine:.

- [x] :ModuleParser: renders tokens back to markdown with a `MarkdownRenderer` subclass whose link rendering is :LinkRendering:.

- [x] :ModuleParser: keeps each list section as a mistletoe `Document` whose children are list items, and each :Functionality: as its func-id, heading line number, the block tokens of its body, and its links.

- [x] :ModuleParser: replaces each recorded code-variable token in marshalled text with the placeholder of its variable name, the name between double curly braces with one space inside each brace pair.

- [x] :Implementation: is a Python 3.11 package named `plain_parser` under `src/plain_parser`, distributed as `plain-parser` with the MIT license.

- [x] :Implementation: has a `pyproject.toml` built with `hatchling>=1.32,<2` and `hatch-vcs>=0.5,<0.6`, the version taken from git, `requires-python = ">=3.11"`, and the wheel package `src/plain_parser`.

- [x] :Implementation: depends on `python-liquid2>=0.4.0,<0.5`, `mistletoe>=1.6.0,<2`, `python-frontmatter>=1.3.0,<2` and `pyyaml>=6,<7`, and nothing else at run time.

- [x] :Implementation: has the optional dependency group `dev` with `pytest==9.2.0`, `flake8==7.5.0`, `black==26.10.1`, `isort==9.0.2` and `mypy==2.4.1`.

- [x] :Implementation: exposes exactly the names, signatures, constants and return shapes of :PythonApi:.

- [x] :Implementation: raises the error classes and exact message texts of :ErrorMessages:.

- [x] :Implementation: parses markdown with mistletoe, runs Liquid with python-liquid2, reads :Frontmatter: with python-frontmatter and YAML with pyyaml.

- [x] :Implementation: is formatted with black and isort (profile black) at line length 120, passes flake8 with max line length 120, and passes `mypy src`.

- [x] :UnitTests: use pytest, live in `tests/` with files named `test_*.py`, and keep their fixture files in `tests/data/`.

- [x] :UnitTests: are run with [test_scripts/run_unittests_python.sh](test_scripts/run_unittests_python.sh).
