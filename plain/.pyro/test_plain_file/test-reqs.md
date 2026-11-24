- [x] :ConformanceTests: of code fences build each file as `---`, `module: todo`, `func_id: add-task`, `---`, an empty line, `***conformance tests***`, an empty line, the scenario, an empty line and `***acceptance tests***`, named `add-task.plain`.

- [x] :ConformanceTests: of invalid test plain files start each file with the frontmatter `module: task-manager` and `func_id: add-task` on lines 1 to 4 and an empty line 5, and name it as the scenario's expected message does.

- [x] :ConformanceTests: use pytest and are run with [test_scripts/run_conformance_tests_python.sh](test_scripts/run_conformance_tests_python.sh).

- [x] :ConformanceTests: use only :PythonApi: and the `plain-parser` command, which is on `PATH`; they never import a name :PythonApi: does not list.

- [x] :ConformanceTests: write every fixture file they need under the pytest `tmp_path` directory and never read files of the build folder.

- [x] :ConformanceTests: match error messages against the texts in :ErrorMessages:.

- [x] :ConformanceTests: do not access the network and are never skipped.

- [x] :ConformanceTests: read `⟨Name⟩` in a scenario as the concept token `Name` written between two colons, so `- ⟨A⟩ uses ⟨B⟩.` is a definition of A that mentions B.
