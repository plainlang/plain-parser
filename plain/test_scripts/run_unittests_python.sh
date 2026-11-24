#!/bin/bash
# Runs the unit tests of a generated plain-parser build folder.
# Usage: run_unittests_python.sh <build_folder>
# Exit codes: 1 bad usage, 2 working folder problem, 69 missing toolchain, else pytest's exit code.

echo "===== [1/7] Toolchain check ====="
if command -v python3 &> /dev/null; then
  PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
  PYTHON_CMD="python"
else
  echo "Error: Python interpreter not found. Install Python 3.11 or newer."
  exit 69
fi
echo "Python: $(command -v $PYTHON_CMD)"
$PYTHON_CMD --version
if ! $PYTHON_CMD -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Error: Python 3.11 or newer is required."
  exit 69
fi

echo "===== [2/7] Argument validation ====="
if [ -z "$1" ]; then
  echo "Error: No build folder provided."
  echo "Usage: $0 <build_folder>"
  exit 1
fi
BUILD_FOLDER="$1"
echo "Build folder: $BUILD_FOLDER"
echo "Invoked from: $(pwd)"

echo "===== [3/7] Working directory setup ====="
WORKING_FOLDER="/tmp/python_$(basename "$BUILD_FOLDER")"
echo "Working folder: $WORKING_FOLDER"
trap 'rm -rf "$WORKING_FOLDER"' EXIT
rm -rf "$WORKING_FOLDER"
mkdir -p "$WORKING_FOLDER"

echo "===== [4/7] Copy the build ====="
echo "+ cp -R $BUILD_FOLDER/. $WORKING_FOLDER"
cp -R "$BUILD_FOLDER"/. "$WORKING_FOLDER"

echo "===== [5/7] Enter the working directory ====="
cd "$WORKING_FOLDER" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "Error: cannot enter working folder '$WORKING_FOLDER'."
  exit 2
fi
echo "Now in: $(pwd)"

echo "===== [6/7] Install dependencies into ./.venv ====="
set -x
$PYTHON_CMD -m venv .venv || exit $?
./.venv/bin/pip install --upgrade pip || exit $?
# The package takes its version from git, which the working folder does not have.
SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 ./.venv/bin/pip install -e ".[dev]" || exit $?
set +x

echo "===== [7/7] Run the unit tests ====="
echo "+ ./.venv/bin/python -m pytest -p no:cacheprovider (in $WORKING_FOLDER)"
./.venv/bin/python -m pytest -p no:cacheprovider
exit_code=$?
echo "Summary: pytest exited with $exit_code in working folder $WORKING_FOLDER"
exit $exit_code
