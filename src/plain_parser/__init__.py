"""Parser for ***plain specification files."""

from plain_parser import concept_utils, exceptions, loaders, plain_file, plain_spec
from plain_parser.plain_file import (
    PlainFileParseResult,
    get_filename_from_module_name,
    get_module_name_from_filename,
    marshall_plain_source,
    parse_module_chain,
    parse_plain_file,
    parse_plain_source,
    plain_file_parser,
)

__all__ = [
    "PlainFileParseResult",
    "concept_utils",
    "exceptions",
    "get_filename_from_module_name",
    "get_module_name_from_filename",
    "loaders",
    "marshall_plain_source",
    "parse_module_chain",
    "parse_plain_file",
    "parse_plain_source",
    "plain_file",
    "plain_file_parser",
    "plain_spec",
]
