#!/bin/bash
cd /Users/nero/DevelCodeplain/cap-examples/plain-parser/plain/plain_module/code
V=/Users/nero/DevelCodeplain/cap-examples/plain-parser/.venv/bin
{ $V/black -q . ; $V/isort -q . ; $V/flake8 src tests; $V/mypy src; } 2>&1 | grep -v _editable_impl
