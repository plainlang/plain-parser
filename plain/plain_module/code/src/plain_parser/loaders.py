"""File lookup over template directories, linked-file loading, and Liquid rendering of plain files."""

import os
import re

from liquid2 import Environment, StrictUndefined
from liquid2.builtin import FileSystemLoader
from liquid2.exceptions import LiquidSyntaxError, TemplateNotFoundError, UndefinedError

from plain_parser.exceptions import PlainSyntaxError, UnsupportedBase64Content, UnsupportedResourceType
from plain_parser.liquid_nodes import Plain2CodeIncludeTag, Plain2CodeLoaderMixin

MAX_BASE64_BLOB_LENGTH = 8192

_BASE64_RUN = re.compile(r"[A-Za-z0-9+/_-]+")
_DATA_URI_HEADER = re.compile(r"data:[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+;base64,$")
_DATA_URI_HEADER_MAX = 256


def find_large_base64_blob(text: str) -> str | None:
    """Return the first base64 blob of at least MAX_BASE64_BLOB_LENGTH characters in ``text``, or None."""
    for match in _BASE64_RUN.finditer(text):
        if match.end() - match.start() < MAX_BASE64_BLOB_LENGTH:
            continue
        start, end = match.start(), match.end()
        header = _DATA_URI_HEADER.search(text[max(0, start - _DATA_URI_HEADER_MAX) : start])
        if header:
            start -= header.end() - header.start()
        padding = 0
        while padding < 2 and end < len(text) and text[end] == "=":
            end += 1
            padding += 1
        return text[start:end]
    return None


def open_from(dirs, file_name) -> str | None:
    """Return the UTF-8 text of the first regular file ``file_name`` in ``dirs``, or None."""
    for directory in dirs:
        path = os.path.join(directory, file_name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as file:
                return file.read()
    return None


def find_resource_dir(dirs, file_name) -> str | None:
    """Return the first directory of ``dirs`` in which ``file_name`` exists, as a file or a directory."""
    for directory in dirs:
        if os.path.exists(os.path.join(directory, file_name)):
            return directory
    return None


def resolve_linked_resource(dirs, file_name) -> str | None:
    """Return the first existing path of ``file_name`` over ``dirs``, joined as written, or None."""
    directory = find_resource_dir(dirs, file_name)
    if directory is None:
        return None
    return os.path.join(directory, file_name)


def _posix(path: str) -> str:
    return path.replace(os.sep, "/") if os.sep != "/" else path


def relative_resource_path(base_dir: str, resource_dir: str, target: str) -> str:
    """Name ``target`` found in ``resource_dir`` relative to ``base_dir``, with ``/`` as separator."""
    try:
        relative_dir = os.path.relpath(resource_dir, base_dir)
    except ValueError:
        return _posix(os.path.join(resource_dir, target))
    if relative_dir == os.curdir:
        return target
    return _posix(relative_dir) + "/" + target


def load_linked_resources(template_dirs: list[str], resources_list, module_name: str) -> dict[str, str]:
    """Read every linked file of a module and return a mapping from target to text."""
    result: dict[str, str] = {}
    for resource in resources_list:
        target = resource["target"]
        if target in result:
            continue
        try:
            content = open_from(template_dirs, target)
        except UnicodeDecodeError as error:
            raise UnsupportedResourceType(
                f"Referenced resource '{target}' in module '{module_name}' is a binary file. "
                "Only text files (e.g. .md, .txt, .json, .yaml) can be referenced from a .plain file."
            ) from error
        if content is None:
            raise FileNotFoundError(f"Resource file '{target}' referenced in module '{module_name}' not found.")
        blob = find_large_base64_blob(content)
        if blob is not None:
            raise UnsupportedBase64Content(
                f"Referenced resource '{target}' in module '{module_name}' contains a large base64-encoded blob "
                f"({len(blob)} characters), such as an embedded image. Inline base64 data is not supported. "
                "Remove the data from the resource. If the data should be used by the end software, save the data "
                "to a separate file and include the file path in the specification without it being a reference "
                "file."
            )
        result[target] = content
    return result


def _error_position(error) -> tuple[int, int] | None:
    token = getattr(error, "token", None)
    if token is None:
        return None
    source = getattr(token, "source", None)
    start = getattr(token, "start", -1)
    if not isinstance(source, str) or not isinstance(start, int) or start < 0 or start > len(source):
        return None
    line = source.count("\n", 0, start) + 1
    column = start - (source.rfind("\n", 0, start) + 1)
    return line, column


def liquid_error_message(error: LiquidSyntaxError) -> str:
    """Return the PlainSyntaxError message for a Liquid syntax error."""
    position = _error_position(error)
    template = error.template_name or None
    if position and template:
        where = f" at {template}:{position[0]}:{position[1]}"
    elif position:
        where = f" at {position[0]}:{position[1]}"
    elif template:
        where = f" in {template}"
    else:
        where = ""
    return f"Plain syntax error: Invalid Liquid{where}: {error.message}"


class TrackingFileSystemLoader(Plain2CodeLoaderMixin, FileSystemLoader):
    """A liquid2 file system loader that records every loaded template source by name."""

    def __init__(self, search_path, **kwargs):
        super().__init__(search_path, **kwargs)
        self.loaded_templates: dict[str, str] = {}

    def on_template_loaded(self, template_name: str, source: str) -> None:
        self.loaded_templates[template_name] = source


class _TemplateNotFoundError(TemplateNotFoundError):
    """The liquid2 template-not-found error with a plain message."""

    def __str__(self) -> str:
        return str(self.message)


def create_environment(loader) -> Environment:
    """Create the liquid2 environment used to render plain files."""
    from plain_parser.plain_spec import code_variable_liquid_filter, prohibited_chars_liquid_filter

    environment = Environment(loader=loader, undefined=StrictUndefined)
    environment.tags["include"] = Plain2CodeIncludeTag(environment)
    environment.filters["code_variable"] = code_variable_liquid_filter
    environment.filters["prohibited_chars"] = prohibited_chars_liquid_filter
    return environment


def render_liquid(environment: Environment, plain_source: str, template_name=None, globals=None) -> str:
    """Render ``plain_source`` with ``environment``, mapping Liquid errors to plain-parser errors."""
    try:
        template = environment.from_string(plain_source, name=template_name or "")
        return template.render(**(globals or {}))
    except UndefinedError as error:
        raise Exception(f"Undefined liquid variable: {error.message}") from error
    except TemplateNotFoundError as error:
        raise _TemplateNotFoundError(f"Template not found: {error.message}") from error
    except LiquidSyntaxError as error:
        raise PlainSyntaxError(liquid_error_message(error)) from error


def get_loaded_templates(source_path, plain_source, template_name=None) -> tuple[str, dict[str, str]]:
    """Render ``plain_source`` with Liquid over the template directories ``source_path``.

    Returns the rendered text and a mapping from each loaded template name to its source.
    """
    dirs = [source_path] if isinstance(source_path, (str, os.PathLike)) else list(source_path)
    loader = TrackingFileSystemLoader(dirs)
    rendered = render_liquid(create_environment(loader), plain_source, template_name)
    return rendered, dict(loader.loaded_templates)
