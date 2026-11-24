# Dependencies

## Implementation
- [x] Python >= 3.11 — python3 3.15.2 (/opt/homebrew/bin/python3)
- [x] venv + pip — available
- [x] python-liquid2>=0.4.0,<0.5 — 0.4.0 on PyPI / in ../.venv
- [x] mistletoe>=1.6.0,<2 — 1.6.0
- [x] python-frontmatter>=1.3.0,<2 — 1.3.0
- [x] pyyaml>=6,<7 — 6.0.4
- [x] hatchling>=1.32,<2 — 1.33.0 on PyPI
- [x] hatch-vcs>=0.5,<0.6 — 0.5.0 on PyPI
- [x] git — /opt/homebrew/bin/git (version via SETUPTOOLS_SCM_PRETEND_VERSION in scripts)
- [x] dev: pytest==9.2.0, flake8==7.5.0, black==26.10.1, isort==9.0.2, mypy==2.4.1 — present in ../.venv

## Tests
- [x] bash — test_scripts/run_unittests_python.sh, run_conformance_tests_python.sh
- [x] pytest==9.2.0
- [x] PyPI network access (scripts install inline into a /tmp venv) — reachable
- [x] `plain-parser` console script on PATH — provided by package install in the test scripts
