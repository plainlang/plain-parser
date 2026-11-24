- [x] :ConformanceTests: build the fixture `todo.plain`: it defines `- ⟨Task⟩ is a thing to do.`, has one implementation req and the functionalities `add-task` (`A ⟨Task⟩ can be added.`) and `list-tasks` (`Every ⟨Task⟩ is listed.`); it is parsed with the tests folder `tests` next to it unless a scenario names other folders.

- [x] :ConformanceTests: use pytest and are run with [test_scripts/run_conformance_tests_python.sh](test_scripts/run_conformance_tests_python.sh).

- [x] :ConformanceTests: use only :PythonApi: and the `plain-parser` command, which is on `PATH`; they never import a name :PythonApi: does not list.

- [x] :ConformanceTests: write every fixture file they need under the pytest `tmp_path` directory and never read files of the build folder.

- [x] :ConformanceTests: match error messages against the texts in :ErrorMessages:.

- [x] :ConformanceTests: do not access the network and are never skipped.

- [x] :ConformanceTests: read `⟨Name⟩` in a scenario as the concept token `Name` written between two colons, so `- ⟨A⟩ uses ⟨B⟩.` is a definition of A that mentions B.
