import os
import subprocess


def c(name):
    return f":{name}:"


VALID = (
    f"***definitions***\n\n- {c('App')} is a console application.\n\n"
    f"***implementation reqs***\n\n- {c('App')} is written in Python.\n\n"
    f'***functional specs***\n\n# app-prints-hello-world\n{c("App")} prints "hello, world".\n'
)

TOP = (
    "---\nrequires:\n  - helper\n---\n\n***implementation reqs***\n\n- Top is written in Python.\n\n"
    "***functional specs***\n\n# main\nTop runs.\n"
)
HELPER = (
    "***implementation reqs***\n\n- Helper is written in Python.\n\n***functional specs***\n\n# main\nHelper helps.\n"
)

TODO = (
    f"***definitions***\n\n- {c('Task')} is a thing to do.\n\n"
    "***implementation reqs***\n\n- The todo app is written in Python.\n\n"
    f"***functional specs***\n\n# add-task\nA {c('Task')} can be added.\n\n# list-tasks\nEvery {c('Task')} is listed.\n"
)
ADD_TASK = (
    "---\nmodule: todo\nfunc_id: add-task\n---\n\n***conformance tests***\n\n"
    f"# add-first-task\nAdding a {c('Task')} shows it.\n\n"
    "# add-without-name\nAdding without a name fails.\n\n"
    "***acceptance tests***\n\n"
    "# add-then-list\nAdding, then listing shows the task.\n"
)
LIST_TWO_TEXT = (
    f"With two {c('Task')} items added, `todo list` prints two lines, lowest id first, and exits with status 0."
)
LIST_TASKS = (
    "---\nmodule: todo\nfunc_id: list-tasks\n---\n\n***conformance tests***\n\n"
    f"# list-two-tasks\n{LIST_TWO_TEXT}\n\n***acceptance tests***\n"
)
TODO_CONFIG = "conformance-tests-script: test_scripts/run_conformance_tests.sh\ntests-folder: tests\n"


class Workspace:
    def __init__(self, root):
        self.root = str(root)

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def write(self, name, text):
        path = self.path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if isinstance(text, bytes):
            with open(path, "wb") as file:
                file.write(text)
        else:
            with open(path, "w", encoding="utf-8") as file:
                file.write(text)
        return path

    def remove(self, name):
        os.remove(self.path(name))

    def valid(self, name="valid.plain"):
        return self.write(name, VALID)

    def top_project(self, config=None):
        self.write("project/top.plain", TOP)
        self.write("project/template/helper.plain", HELPER)
        if config is not None:
            self.write("project/config.yaml", config)

    def todo_project(self, config=TODO_CONFIG):
        self.write("project/todo.plain", TODO)
        if config is not None:
            self.write("project/config.yaml", config)
        self.write("project/tests/todo/add-task.plain", ADD_TASK)
        self.write("project/tests/todo/list-tasks.plain", LIST_TASKS)

    def run(self, *args, cwd=None, env=None, **kwargs):
        full_env = dict(os.environ)
        full_env.update(env or {})
        return subprocess.run(
            ["plain-parser", *args],
            cwd=cwd or self.root,
            env=full_env,
            capture_output=True,
            text=True,
            **kwargs,
        )
