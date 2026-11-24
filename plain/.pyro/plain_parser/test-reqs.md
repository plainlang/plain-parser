- [x] :ConformanceTests: build the fixture `valid.plain`: it defines `- ⟨App⟩ is a console application.`, has the implementation req `- ⟨App⟩ is written in Python.` and the functionality `app-prints-hello-world` with the body `⟨App⟩ prints "hello, world".`.

- [x] :ConformanceTests: build the fixture `project/top.plain`: it requires `helper`, and `helper.plain` lives only in `project/template/`; both have one implementation req and the functionality `main` with one line of body.

- [x] :ConformanceTests: build the fixture project `project/`: `todo.plain` defines `- ⟨Task⟩ is a thing to do.`, has one implementation req and the functionalities `add-task` and `list-tasks`; `config.yaml` holds `conformance-tests-script: test_scripts/run_conformance_tests.sh` and `tests-folder: tests`; `tests/todo/add-task.plain` holds the conformance scenarios `add-first-task` and `add-without-name` and the acceptance scenario `add-then-list`, and `tests/todo/list-tasks.plain` holds the conformance scenario `list-two-tasks` with the text `With two ⟨Task⟩ items added, `todo list` prints two lines, lowest id first, and exits with status 0.`.

- [x] :ConformanceTests: use pytest and are run with [test_scripts/run_conformance_tests_python.sh](test_scripts/run_conformance_tests_python.sh).

- [x] :ConformanceTests: use only :PythonApi: and the `plain-parser` command, which is on `PATH`; they never import a name :PythonApi: does not list.

- [x] :ConformanceTests: write every fixture file they need under the pytest `tmp_path` directory and never read files of the build folder.

- [x] :ConformanceTests: match error messages against the texts in :ErrorMessages:.

- [x] :ConformanceTests: do not access the network and are never skipped.

- [x] :ConformanceTests: read `⟨Name⟩` in a scenario as the concept token `Name` written between two colons, so `- ⟨A⟩ uses ⟨B⟩.` is a definition of A that mentions B.
