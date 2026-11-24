# plain-parser error messages

Every error the parser raises, by error class, with its exact message text. Callers match on these texts, so they
are part of the contract. `{name}` marks a value filled in at run time. A message that spans lines here spans the
same lines in the error (`\n` separated). Where a message starts with `{where}`, `{where}` is built as follows:

- In a spec plain file: `Syntax error`, then ` at line {line}` when the line is known, then ` in module '{module}'`
  when the module name is known. Example: `Syntax error at line 7 in module 'todo'`.
- In a test plain file: `Syntax error at line {line} in test plain file '{name}'`.

Line numbers count from 1 at the first line of the file, frontmatter included, after line endings are normalized.

## Spec plain file structure (PlainSyntaxError)

- `Plain syntax error: Invalid frontmatter: {error}`
- `Plain syntax error: {where}: The `{heading}` section is not allowed in a spec plain file; test scenarios live in test plain files.`
  (`{heading}` is `conformance tests` or `acceptance tests`)
- `Plain syntax error: {where}: A `# <func-id>` heading is allowed only in the functional specs section (`{text}`).`
- `Plain syntax error: {where}: Invalid heading level {level} (`{text}`). A functionality heading is `# <func-id>`.`
- `Plain syntax error: {where}: Invalid func-id (`{text}`). A func-id is lowercase letters and digits, with single hyphens between them.`
- `Plain syntax error: {where}: Duplicate func-id `{func_id}`; it is first used at line {line}.`
- `Plain syntax error: {where}: Invalid specification (`{text}`)`
- `Plain syntax error: {where}: Content before the first `# <func-id>` heading in the functional specs section (`{text}`). A functionality is a `# <func-id>` heading followed by its body; the previous syntax is not supported.`
- `Plain syntax error: {where}: Invalid specification heading (`{heading}`). Allowed headings: definitions, implementation reqs, test reqs, functional specs`
- `Plain syntax error: {where}: Duplicate specification heading (`{heading}`)`
- `Plain syntax error: {where}: Definitions specification must be the first specification in the section (`{text}`)`
- `Plain syntax error: {where}: Missing specification heading (`{text}`)`
- `Plain syntax error: {where}: Invalid source structure (`{text}`)`
- `Plain syntax error: {where}: Functionality `{func_id}` has no body.`
- `Plain syntax error: Invalid plain file extension: {suffix}. Expected: .plain.`

`{text}` is the raw text of the offending block, stripped.

## Module shape (various classes)

- MissingFunctionalitiesError: `Module '{module}' does not have any functionality specified. At least one functionality is required for rendering.`
- PlainSyntaxError: `Plain syntax error: Module '{module}' has a 'functional specs' section without a `# <func-id>` heading. A functionality is a `# <func-id>` heading followed by its body; the previous syntax is not supported.`
- PlainSyntaxError: `Plain syntax error: Module '{module}' defines functionalities but specifies no implementation reqs. At least one implementation req is required.`
  When the module has a `requires` list, this sentence follows: ` Implementation reqs are not inherited through 'requires' — add them to this module, or 'import' a module that provides them.`
- ModuleDoesNotExistError: `Module does not exist ({module}).`
- UnsupportedBase64Content: `Module '{module}' contains a base64-encoded blob ({length} characters) inlined in the specification. This is not supported. Remove the base64 data from the .plain file or if necessary, include the binary file path in the specification.`

## Imports, requires, required and exported concepts

- PlainSyntaxError: `Plain syntax error: Circular import detected: {module}.`
- ImportedModuleWithFunctionalitiesError: `Module '{module}' is imported but contains functional specs. Imported modules may only provide definitions, implementation reqs, and test reqs — use 'requires' instead of 'import' if this module's functionalities should be built on.`
- PlainSyntaxError: `Plain syntax error: Invalid specification heading (`{heading}`). Allowed headings: definitions, implementation reqs, test reqs`
- PlainSyntaxError: `Plain syntax error: Circular required module detected: {module}.`
- PlainSyntaxError: `Plain syntax error: There must be a fixed order how required modules are dependent ({module}).`
- PlainSyntaxError: `Plain syntax error: Not all required concepts were defined. Missing required concepts: {concepts joined by ", "}.`
- PlainSyntaxError: `Plain syntax error: Invalid {directive} metadata. Expected a dictionary or a string.`
- AssertionError: `Syntax error: Invalid {directive} metadata. Expected a list.`
- AssertionError: `Syntax error: Invalid required_concepts metadata. Expected a string.`
- PlainSyntaxError: `Plain syntax error: {subject} exports an invalid concept (`{entry}`). Expected a concept token, e.g. :ConceptName:.`
- PlainSyntaxError: `Plain syntax error: {subject} cannot export default concept {concept}. Only user-defined concepts can be exported.`
- PlainSyntaxError: `Plain syntax error: {subject} exports undefined concept {concept}.`
  When the module has a `requires` list, this sentence follows: ` An exported concept must be defined in this module's definitions or in an imported module; a concept inherited through requires cannot be re-exported.`

`{subject}` is `Module '{module}'`, or `Module` when the module name is not known. `{entry}` is the export entry as
normalized: `- ` followed by the entry.

## Concepts

- `Plain syntax error: Found {count} errors in the plain file:\n{errors joined by \n}` (PlainSyntaxError), where each error is one of:
  - `Syntax error: Invalid definition specification text: {text}. Should start with `- :<concept>:` (where <concept> is any string that does not contain `:`).`
  - `Syntax error: Invalid concept: {candidate}. Should contain only letters, numbers, hyphens and dots.`
  - `Syntax error: Concepts were defined multiple times: {concepts joined by ", "} .`
  - `Syntax error: Concept {concept} is not defined in the definitions. {section}: {markdown}`
- Concept cycles (PlainSyntaxError), at most 10 cycles listed:
  ```
  Plain syntax error: Found {count} cycle(s) in concept definitions. Cycles are not allowed.

  Cycle 1: {c1} -> {c2} -> {c1}
  {definition markdown of each distinct definition on the cycle}

  Cycle 2: ...
  ```
  When more than 10 cycles exist, the first line is replaced by the two lines
  `Plain syntax error: Found more than 10 cycles in concept definitions. Cycles are not allowed.` and
  `Showing the first 10.`

## Linked resources

- PlainSyntaxError: `Plain syntax error: Only relative links are allowed{where} (text: {text}, target: {target}).`
- PlainSyntaxError: `Plain syntax error: Link {target}{where} does not exist. Linked resources are looked up relative to the following directories (highest to lowest precedence):\n  1. {dir1}\n  2. {dir2}`
- PlainSyntaxError: `Plain syntax error: Link {target}{where} must be a file (resolved to {resolved_path}).`
- PlainSyntaxError: `Plain syntax error: Link{where} must have text specified (link: {target}).`
- PlainSyntaxError: `Referenced resource '{target}'{where} is a .plain file. Referencing .plain files through Linked Resources is not supported. Please use the import section to include definitions or implementation/test requirements from another module.`
- UnsupportedResourceType: `Referenced resource '{target}' in module '{module}' is a binary file. Only text files (e.g. .md, .txt, .json, .yaml) can be referenced from a .plain file.`
- FileNotFoundError: `Resource file '{target}' referenced in module '{module}' not found.`
- UnsupportedBase64Content: `Referenced resource '{target}' in module '{module}' contains a large base64-encoded blob ({length} characters), such as an embedded image. Inline base64 data is not supported. Remove the data from the resource. If the data should be used by the end software, save the data to a separate file and include the file path in the specification without it being a reference file.`
- Exception: `The file {target} is linked to multiple linked resources with the same text: {text}`
- Exception: `The linked resource {text} is linked to multiple files: {other_target}`
- Exception: `Duplicate linked resource found: {text} ({target})`

`{where}` is empty in a spec plain file and ` in test plain file '{name}', scenario `{scenario_id}`` in a scenario.

## Liquid

- PlainSyntaxError: `Plain syntax error: Invalid Liquid{position}: {liquid message}`, where `{position}` is
  ` at {template}:{line}:{column}` when both are known, ` at {line}:{column}` when only the position is known,
  ` in {template}` when only the template name is known, and empty otherwise. `{column}` counts from 0.
- Exception: `Undefined liquid variable: {liquid message}`
- TemplateNotFoundError (liquid2): `Template not found: {liquid message naming the template}`
- Exception: `Invalid use of code_variable filter!`
- Exception: `Invalid use of prohibited_chars filter!`
- InvalidLiquidVariableName: `'{char}' is not a valid character for variable '{variable}' (value: '{value}').`
- Exception: `Code variable {name} has multiple values: {first value} and {second value}`

## Func-id navigation

- Exception: `Functionality {frid} does not exist.`
- ValueError: `plain_source_tree must be a dictionary.`
- ValueError: `frid {frid} does not exist.`
- InvalidFridArgument: `Invalid start functionality ID: {start}. Valid IDs are: {python list of func-ids}.`
- InvalidFridArgument: `Invalid end functionality ID: {end}. Valid IDs are: {python list of func-ids}.`
- InvalidFridArgument: `Start functionality ID: {start} must be before end functionality ID: {end}.`

## Test plain files (PlainSyntaxError)

- `Plain syntax error: Test plain file '{name}' has invalid frontmatter: {error}`
- `Plain syntax error: Test plain file '{name}' has no `{key}:` key in its frontmatter.`
- `Plain syntax error: Test plain file '{name}': the frontmatter key `{key}:` must be a non-empty string.`
- `Plain syntax error: Test plain file '{name}' has the frontmatter key `{key}:`; only `module:` and `func_id:` are allowed.`
- `Plain syntax error: {where}: Invalid section (`{line}`). A test plain file has the sections `***conformance tests***` and `***acceptance tests***`, in this order.`
- `Plain syntax error: {where}: Duplicate section `***{heading}***`.`
- `Plain syntax error: {where}: The `***{heading}***` section must come after `***conformance tests***`.`
- `Plain syntax error: {where}: Scenario `{scenario_id}` comes before the first section; a test plain file starts with `***conformance tests***`.`
- `Plain syntax error: {where}: Invalid scenario-id (`{scenario_id}`). A scenario-id is lowercase letters and digits, with single hyphens between them.`
- `Plain syntax error: {where}: Duplicate scenario-id `{scenario_id}`; it is first used at line {line}.`
- `Plain syntax error: {where}: Content before the first section (`{line}`); a test plain file starts with `***conformance tests***`.`
- `Plain syntax error: {where}: Content before the first `# <scenario-id>` heading in the `{section}` section (`{line}`).`
- `Plain syntax error: {where}: Scenario `{scenario_id}` has a code fence that is not closed.` (`{where}` names the scenario's heading line)
- `Plain syntax error: {where}: Scenario `{scenario_id}` has no text.` (`{where}` names the scenario's heading line)
- `Plain syntax error: Test plain file '{name}' has no `***{heading}***` section.`
- Concept error line (one per concept, in a list): `{where}: Concept {concept} used in scenario `{scenario_id}` is not defined in module '{module}'.` (`{where}` names the scenario's heading line)

## Binding test plain files to functionalities

- PlainSyntaxError: `Plain syntax error: File '{name}' under a tests folder is not a text file.`
- UnsupportedBase64Content: `Test plain file '{name}' contains a base64-encoded blob ({length} characters) inlined in the scenarios. This is not supported. Remove the base64 data from the file.`
- PlainSyntaxError: `Plain syntax error: File '{name}' under a tests folder has invalid frontmatter: {error}`
- PlainSyntaxError: `Plain syntax error: File '{name}' is under a tests folder but is not a test plain file: its frontmatter needs the keys `module:` and `func_id:`.`
- PlainSyntaxError: `Plain syntax error: Test plain file '{name}' binds to functionality '{module}:{func_id}', which module '{module}' does not have.`
- PlainSyntaxError: `Plain syntax error: Found {count} errors in test plain file '{name}':\n{concept error lines joined by \n}`
- PlainSyntaxError: `Plain syntax error: Syntax error at line {line} in test plain file '{name}': Duplicate scenario-id `{scenario_id}` for functionality '{module}:{func_id}'; it is first used at line {first_line} in test plain file '{first_name}'.`
- MissingTestPlainFileError: `Functionality {module}:{func_id} has no test plain file. Add one, by convention tests/{module}/{func_id}.plain, with the add-test-scenarios skill.`

## Command line

- Usage error (argparse, exit 2): `Config file '{config_name}' was found in two locations:\n  - Plain file directory: {dir}\n  - Current working directory: {cwd}\nRemove the config file from one of these locations to resolve the ambiguity.`
- Usage error (argparse, exit 2): `Error reading config file: {error}`
- Usage error (argparse, exit 2): `conformance-tests-script is set in the config file, but no tests folder is given. Pass --tests-folder or set tests-folder in the config file.`
- `parse` encoding failure: `The parse result holds text that is not valid UTF-8: {offending output line, stripped, trailing comma removed, non-ASCII as backslash escapes}`
