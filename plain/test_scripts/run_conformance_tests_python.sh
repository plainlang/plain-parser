#!/bin/bash
# Runs the conformance tests of one functionality against a generated plain-parser build folder.
# Install-inline variant: there is no prepare-environment script.
# Usage: run_conformance_tests_python.sh <build_folder> <conformance_tests_folder>
# Exit codes: 69 bad usage, missing toolchain or working folder problem; 1 no tests ran; else pytest's exit code.

echo "===== [1/8] Toolchain check (install-inline variant) ====="
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

echo "===== [2/8] Argument validation ====="
if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Error: build folder and conformance tests folder are required."
  echo "Usage: $0 <build_folder> <conformance_tests_folder>"
  exit 69
fi
BUILD_FOLDER="$1"
echo "Build folder: $BUILD_FOLDER"

echo "===== [3/8] Resolve the conformance tests folder ====="
case "$2" in
  /*) CONFORMANCE_TESTS_FOLDER="$2" ;;
  *)  CONFORMANCE_TESTS_FOLDER="$(pwd)/$2" ;;
esac
echo "Conformance tests folder: $CONFORMANCE_TESTS_FOLDER"

echo "===== [4/8] Working directory setup ====="
WORKING_FOLDER="/tmp/python_$(basename "$BUILD_FOLDER")"
echo "Working folder: $WORKING_FOLDER"
trap 'rm -rf "$WORKING_FOLDER"' EXIT
rm -rf "$WORKING_FOLDER"
mkdir -p "$WORKING_FOLDER"

echo "===== [5/8] Copy the build ====="
echo "+ cp -R $BUILD_FOLDER/. $WORKING_FOLDER"
cp -R "$BUILD_FOLDER"/. "$WORKING_FOLDER"

echo "===== [6/8] Enter the working directory ====="
cd "$WORKING_FOLDER" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "Error: cannot enter working folder '$WORKING_FOLDER'."
  exit 69
fi
echo "Now in: $(pwd)"

echo "===== [7/8] Install dependencies into ./.venv (install-inline) ====="
start_time=$(date +%s)
set -x
$PYTHON_CMD -m venv .venv || exit 69
./.venv/bin/pip install --upgrade pip || exit $?
# The package takes its version from git, which the working folder does not have.
SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 ./.venv/bin/pip install -e ".[dev]" || exit $?
set +x
echo "Requirements setup completed in $(( $(date +%s) - start_time )) seconds"

echo "===== [8/8] Run the conformance tests ====="
# The installed plain-parser command must be on PATH for tests that run it.
export PATH="$WORKING_FOLDER/.venv/bin:$PATH"
echo "PATH=$PATH"
echo "+ ./.venv/bin/python -m pytest -p no:cacheprovider --rootdir=$WORKING_FOLDER --basetemp=$WORKING_FOLDER/.pytest_tmp $CONFORMANCE_TESTS_FOLDER"
./.venv/bin/python -m pytest -p no:cacheprovider --rootdir="$WORKING_FOLDER" --basetemp="$WORKING_FOLDER/.pytest_tmp" "$CONFORMANCE_TESTS_FOLDER"
exit_code=$?
if [ $exit_code -eq 5 ]; then
  echo "Error: no conformance tests were collected in $CONFORMANCE_TESTS_FOLDER."
  exit_code=1
fi
echo "Summary: install-inline variant, pytest exited with $exit_code, tests $CONFORMANCE_TESTS_FOLDER, working folder $WORKING_FOLDER"
exit $exit_code
