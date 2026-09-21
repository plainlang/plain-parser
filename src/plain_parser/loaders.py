import os
import re
from typing import Optional

from liquid2 import Environment, FileSystemLoader, StrictUndefined
from liquid2.exceptions import UndefinedError

from plain_parser import plain_spec
from plain_parser.exceptions import UnsupportedBase64Content, UnsupportedResourceType
from plain_parser.liquid_nodes import Plain2CodeIncludeTag, Plain2CodeLoaderMixin

MAX_BASE64_BLOB_LENGTH = 8192

# Matches a long contiguous base64 / base64url run, optionally preceded by a data: URI header.
_BASE64_BLOB_PATTERN = re.compile(
    r"(?:data:[\w.+-]+/[\w.+-]+;base64,)?[A-Za-z0-9+/_-]{%d,}={0,2}" % MAX_BASE64_BLOB_LENGTH
)


def find_large_base64_blob(text: str) -> Optional[str]:
    """Return the first contiguous base64 blob at or above the threshold, or None."""
    match = _BASE64_BLOB_PATTERN.search(text)
    return match.group(0) if match else None


def open_from(dirs, file_name):
    for dir in dirs:
        full_file_name = os.path.join(dir, file_name)
        if not os.path.isfile(full_file_name):
            continue

        with open(full_file_name, "rb") as f:
            content = f.read()
        return content.decode("utf-8")

    return None


def load_linked_resources(template_dirs: list[str], resources_list, module_name: str):
    linked_resources = {}

    for resource in resources_list:
        file_name = resource["target"]
        if file_name in linked_resources:
            continue

        try:
            content = open_from(template_dirs, file_name)
        except UnicodeDecodeError:
            raise UnsupportedResourceType(
                f"Referenced resource '{file_name}' in module '{module_name}' is a binary file. "
                f"Only text files (e.g. .md, .txt, .json, .yaml) can be referenced from a .plain file."
            )

        if content is None:
            raise FileNotFoundError(f"Resource file '{file_name}' referenced in module '{module_name}' not found.")

        blob = find_large_base64_blob(content)
        if blob is not None:
            raise UnsupportedBase64Content(
                f"Referenced resource '{file_name}' in module '{module_name}' contains a large "
                f"base64-encoded blob ({len(blob)} characters), such as an embedded image. Inline "
                "base64 data is not supported. Remove the data from the resource. "
                "If the data should be used by the end software, "
                "save the data to a separate file and include the file path in the specification without it being a reference file."
            )

        linked_resources[file_name] = content

    return linked_resources


class TrackingFileSystemLoader(Plain2CodeLoaderMixin, FileSystemLoader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loaded_templates = {}

    def get_source(self, env, template_name, **kwargs):
        source = super().get_source(env, template_name, **kwargs)
        self.loaded_templates[template_name] = source.source
        return source


def get_loaded_templates(source_path, plain_source):
    # Render the plain source with Liquid templating engine
    # to identify the templates that are being loaded

    liquid_loader = TrackingFileSystemLoader(source_path)
    liquid_env = Environment(loader=liquid_loader, undefined=StrictUndefined)
    liquid_env.tags["include"] = Plain2CodeIncludeTag(liquid_env)

    liquid_env.filters["code_variable"] = plain_spec.code_variable_liquid_filter
    liquid_env.filters["prohibited_chars"] = plain_spec.prohibited_chars_liquid_filter

    plain_source_template = liquid_env.from_string(plain_source)
    try:
        plain_source = plain_source_template.render()
    except UndefinedError as e:
        raise Exception(f"Undefined liquid variable: {str(e)}")

    return plain_source, liquid_loader.loaded_templates
