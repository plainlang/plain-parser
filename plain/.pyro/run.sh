#!/bin/bash
# fast dev test run: .pyro/run.sh <pytest args>
cd /Users/nero/DevelCodeplain/cap-examples/plain-parser/plain
export PYTHONPATH=$PWD/plain_module/code/src
export PATH=$PWD/.pyro/bin:$PATH
/Users/nero/DevelCodeplain/cap-examples/plain-parser/.venv/bin/python -m pytest -p no:cacheprovider -q "$@" 2>&1 | grep -v _editable_impl
