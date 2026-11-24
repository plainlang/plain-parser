"""The Liquid include tag of plain files: included templates are indented to the position of the tag."""

from collections.abc import Sequence
from typing import TextIO

from liquid2 import RenderContext
from liquid2.builtin.tags.include_tag import IncludeNode, IncludeTag
from liquid2.exceptions import TemplateNotFoundError
from liquid2.loader import TemplateSource

INDENT_KEYWORD = "plain_indent"


def _line_prefix(source: str, start: int) -> str:
    """Return the text of the tag's line before the tag."""
    line_start = source.rfind("\n", 0, start) + 1
    return source[line_start:start]


def _indentation(prefix: str) -> int:
    """Return the number of spaces that indent the tag's line."""
    count = 0
    for char in prefix:
        if char != " ":
            break
        count += 1
    return count


class Plain2CodeLoaderMixin:
    """Loader mixin that strips the trailing whitespace of a template and indents its lines after the first."""

    def get_source(self, env, template_name: str, *, context=None, **kwargs) -> TemplateSource:
        indent = kwargs.pop(INDENT_KEYWORD, 0)
        template_source = super().get_source(env, template_name, context=context, **kwargs)  # type: ignore[misc]
        self.on_template_loaded(template_name, template_source.source)
        source = template_source.source.rstrip()
        if indent:
            lines = source.split("\n")
            source = "\n".join([lines[0]] + [" " * indent + line for line in lines[1:]])
        return TemplateSource(source, template_source.name, template_source.uptodate, template_source.matter)

    def on_template_loaded(self, template_name: str, source: str) -> None:
        """Hook called with the original source of every loaded template."""


class Plain2CodeIncludeNode(IncludeNode):
    """Include node that indents the included template, and keeps tags in comment lines as written."""

    def _prefix(self) -> str:
        token = self.token
        source = getattr(token, "source", "") or ""
        start = getattr(token, "start", -1)
        if start < 0:
            return ""
        return _line_prefix(source, start)

    def render_to_output(self, context: RenderContext, buffer: TextIO) -> int:
        prefix = self._prefix()
        if ">" in prefix:
            text = str(self)
            buffer.write(text)
            return len(text)

        name = self.name.evaluate(context)
        try:
            loader_arguments: dict = {"tag": self.tag, INDENT_KEYWORD: _indentation(prefix)}
            template = context.env.get_template(str(name), context=context, **loader_arguments)
        except TemplateNotFoundError as err:
            err.token = self.name.token
            err.template_name = context.template.full_name()
            raise

        namespace: dict[str, object] = dict(arg.evaluate(context) for arg in self.args)
        with context.extend(namespace, template=template):
            if not self.var:
                return template.render_with_context(context, buffer, partial=True)
            value = self.var.evaluate(context)
            key = str(self.alias or template.name.split(".")[0])
            if isinstance(value, Sequence) and not isinstance(value, str):
                context.raise_for_loop_limit(len(value))
                count = 0
                for item in value:
                    namespace[key] = item
                    count += template.render_with_context(context, buffer, partial=True)
                return count
            namespace[key] = value
            return template.render_with_context(context, buffer, partial=True)


class Plain2CodeIncludeTag(IncludeTag):
    """The include tag of plain files."""

    node_class = Plain2CodeIncludeNode
