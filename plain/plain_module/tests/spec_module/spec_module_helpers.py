import os

from plain_parser import plain_file


def c(name):
    return f":{name}:"


PREFIX_LINES = [
    "***definitions***",
    "",
    f"- {c('Task')} is a thing to do.",
    "",
    "***implementation reqs***",
    "",
    f"- {c('Implementation')} is written in Python.",
    "",
    "***functional specs***",
    "",
]
PREFIX = "\n".join(PREFIX_LINES) + "\n"  # line 11 is the first line after it


def prefix_of(lines: int) -> str:
    """A module start of ``lines`` lines that ends inside the functional specs section."""
    base = PREFIX_LINES[:]
    while len(base) < lines:
        base.insert(1, "")
    while len(base) > lines:
        base.pop()
    assert base[-1] in ("", "***functional specs***")
    return "\n".join(base) + "\n"


class Project:
    def __init__(self, root):
        self.root = str(root)

    def write(self, name, text, binary=False):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if binary:
            with open(path, "wb") as file:
                file.write(text)
        else:
            with open(path, "w", encoding="utf-8") as file:
                file.write(text)
        return path

    def parse(self, name, text=None, dirs=None):
        if text is not None:
            self.write(name, text)
        return plain_file.plain_file_parser(name, dirs or [self.root])

    def parse_text(self, text, module_name=None, code_variables=None, dirs=None):
        return plain_file.parse_plain_source(
            text, {} if code_variables is None else code_variables, dirs or [self.root], [], [], module_name
        )
