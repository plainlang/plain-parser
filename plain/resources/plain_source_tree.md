# Plain source tree

The marshalled form of one parsed module. A JSON-compatible object (a Python `dict`) keyed by section name.
A key is present only when the module (with its imports and the definitions exported to it) has that section.

```
{
  "definitions":         [ListItem, ...],
  "implementation reqs": [ListItem, ...],
  "test reqs":           [ListItem, ...],
  "functional specs":    [Functionality, ...]
}
```

## ListItem

One `- ` item of a list section, sub-items included.

```
{
  "markdown": "- <the item rendered back to markdown, stripped>",
  "linked_resources": [Link, ...],          present only when the item has at least one link
  "code_variables": [CodeVariable, ...]     present only when the item text holds a code variable
}
```

- The markdown keeps the leading `- ` and the nested items with their indentation.
- Every markdown link `[text](target)` is rendered as `` `[resource]text` ``.
- `>` comment lines are gone.

## Functionality

One `# <func-id>` heading of `***functional specs***`, in file order.

```
{
  "id": "<func-id>",
  "markdown": "<the body rendered back to markdown, without leading and trailing blank lines>",
  "linked_resources": [Link, ...],          always present, may be empty
  "conformance_tests": [Scenario, ...],     always present; filled from bound test plain files
  "acceptance_tests": [Scenario, ...],      always present; filled from bound test plain files
  "code_variables": [CodeVariable, ...]     present only when the body holds a code variable
}
```

- The body keeps blank lines between its blocks, so paragraphs stay apart.
- Links render as `` `[resource]text` `` as in a ListItem.

## Scenario

One `# <scenario-id>` heading of a test plain file.

```
{
  "id": "<scenario-id>",
  "text": "<the body as written, without > comment lines, without leading and trailing blank lines>",
  "linked_resources": [Link, ...],          always present, may be empty
  "code_variables": [CodeVariable, ...]     present only when not empty
}
```

The scenario text is kept verbatim: links are not rewritten.

## Link

```
{"text": "<link text>", "target": "<link target as written>"}
```

## CodeVariable

```
{"name": "<liquid variable name>", "value": "<its value>"}
```

The text holds `{{ name }}` (one space inside each brace pair) where the value was.

## Example

The module `simple.plain`:

```
***implementation reqs***

- Simple implementation requirement

***functional specs***

# simple-functionality
Simple functionality
```

has the tree:

```
{
  "implementation reqs": [{"markdown": "- Simple implementation requirement"}],
  "functional specs": [
    {"id": "simple-functionality", "markdown": "Simple functionality", "linked_resources": [],
     "conformance_tests": [], "acceptance_tests": []}
  ]
}
```
