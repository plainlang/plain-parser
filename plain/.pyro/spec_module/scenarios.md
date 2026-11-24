# Test scenarios of spec_module
## name-module-files
***conformance tests***
# file-name-of-module
The file name of the module `sub/todo` is `sub/todo.plain`, and the module name of `sub/todo.plain` is `sub/todo`.
## normalize-line-endings
***conformance tests***
# mixed-line-endings
The text `a`, CR LF, `b`, CR, `c`, LF, `d` becomes `a`, LF, `b`, LF, `c`, LF, `d`.
## read-list-sections
***conformance tests***
# regular-module
Parsing the module `regular_plain_source.plain`:
```
***acceptance tests***
# invalid-frontmatter
Parsing a text whose frontmatter is `module: [` raises `PlainSyntaxError` whose message starts with `Plain syntax error: Invalid frontmatter: `.
## reject-invalid-sections
***acceptance tests***
# unknown-section
Parsing the text of an empty line, `***definitions***`, an empty line and `***Unknown Section:***` raises an error whose message holds `Syntax error at line 4: Invalid specification heading (`Unknown Section:`). Allowed headings: definitions, implementation reqs, test reqs, functional specs`.
# line-number-counts-frontmatter
The same text after a frontmatter of three lines (`---`, `description: 'x'`, `---`) and an empty line reports line 7.
# line-number-with-windows-line-endings
The same text with frontmatter, written with CR LF line endings, reports line 7.
# duplicate-section
Parsing an empty line, `***definitions***`, an empty line and `***definitions***` raises an error holding `Syntax error at line 4: Duplicate specification heading (`definitions`)`.
# duplicate-section-names-the-module
Parsing the module `duplicate_specification_heading` whose second `***definitions***` is on line 6 raises an error holding `Syntax error at line 6 in module 'duplicate_specification_heading': Duplicate specification heading (`definitions`)`.
# definitions-not-first
Parsing the module `invalid_specification_order` with `***implementation reqs***`, an item, and `***definitions***` on line 6 raises an error holding `Syntax error at line 6 in module 'invalid_specification_order': Definitions specification must be the first specification in the section (`definitions`)`.
# code-block-in-list-section
Parsing an empty line, `***definitions***`, and a fenced code block holding `code block` raises an error holding `Syntax error at line 3: Invalid source structure (`code block`)`.
# block-after-list-items
Parsing `***implementation reqs***`, an empty line, `- A req.`, an empty line and a fenced code block holding `code` raises `PlainSyntaxError` holding `Syntax error at line 5: Invalid source structure`.
# test-section-in-spec-file
Parsing `***definitions***`, an empty line, `- ⟨Task⟩ is a thing to do.`, an empty line, `***acceptance tests***`, an empty line, `# add`, `Adding works.` raises `PlainSyntaxError` with exactly `Plain syntax error: Syntax error at line 5: The `acceptance tests` section is not allowed in a spec plain file; test scenarios live in test plain files.`; the same holds for `conformance tests`.
# nested-test-section
A module whose functionality body ends with the indented line `    ***acceptance tests***` on line 14 raises `PlainSyntaxError` holding `Syntax error at line 14: The `acceptance tests` section`.
## read-functionalities
***conformance tests***
# heading-and-body
A module with a definition of Task and an implementation req, whose `functional specs` are:
```
# add-task
A ⟨Task⟩ can be added.
It gets an id.
  - Only a ⟨Task⟩ with a name is added.
    - The name is trimmed.
# list-tasks
Every ⟨Task⟩ is listed.
```
gives two functionalities: `add-task` with the markdown of its four body lines joined by newlines, as written, and `list-tasks` with the markdown `Every ⟨Task⟩ is listed.`, each with empty linked_resources, conformance_tests and acceptance_tests.
# body-starts-with-a-list
The functionality `add-task` whose body is the single line `  - A ⟨Task⟩ can be added.` has exactly that markdown.
# flush-left-list-is-body
The functionality `add-task` whose body is `A ⟨Task⟩ can be added.`, an empty line, `- A ⟨Task⟩ has a name.` and `    - Deeper, four spaces in.` has exactly those lines, the empty line kept, as markdown.
# any-block-is-body
The functionality `add-task` whose body is a paragraph, a fenced code block holding `todo add`, and the table `| id | name |`, `|---|---|`, `| 1 | Buy milk |`, followed by `# list-tasks`, has the markdown of the paragraph, an empty line, the code block, an empty line, and the table `| id  | name     |`, `| --- | -------- |`, `| 1   | Buy milk |`; `list-tasks` has its own body.
## reject-invalid-functionalities
***acceptance tests***
# heading-outside-functional-specs
Parsing `***implementation reqs***`, an empty line, `# add-task`, `- A req.` raises `PlainSyntaxError` holding `Syntax error at line 3: A `# <func-id>` heading is allowed only in the functional specs section (`add-task`).`.
# heading-of-level-two
A module whose `functional specs` start with `## add-task` on line 11 raises `PlainSyntaxError` holding `Syntax error at line 11: Invalid heading level 2 (`add-task`). A functionality heading is `# <func-id>`.`.
# invalid-func-id
Each of the heading lines `#`, `# `, `# add_task`, `# add-task!`, `# Ädd`, `# -add-task`, `# add-task-`, `# add--task`, `# -`, `# ---` on line 11 raises `PlainSyntaxError` holding `Syntax error at line 11: Invalid func-id`.
# invalid-func-id-message
The module `func_id_invalid` whose heading `# Add Task 2` is on line 10 raises exactly `Plain syntax error: Syntax error at line 10 in module 'func_id_invalid': Invalid func-id (`Add Task 2`). A func-id is lowercase letters and digits, with single hyphens between them.`.
# duplicate-func-id
The module `func_id_duplicate` with `# add-task` on lines 7 and 13 raises exactly `Plain syntax error: Syntax error at line 13 in module 'func_id_duplicate': Duplicate func-id `add-task`; it is first used at line 7.`.
# content-before-first-heading
A module whose `functional specs` start on line 11 with `A ⟨Task⟩ can be added.`, or with `  - A ⟨Task⟩ can be added.`, before `# add-task` raises `PlainSyntaxError` holding `Syntax error at line 11: Content before the first `# <func-id>` heading in the functional specs section (`A ⟨Task⟩ can be added.`). A functionality is a `# <func-id>` heading followed by its body; the previous syntax is not supported.`.
# previous-syntax
The module `old_syntax_functional_specs`, whose `functional specs` hold the item `- Display "hello, world"` on line 11, raises exactly `Plain syntax error: Syntax error at line 11 in module 'old_syntax_functional_specs': Content before the first `# <func-id>` heading in the functional specs section (`Display "hello, world"`). A functionality is a `# <func-id>` heading followed by its body; the previous syntax is not supported.`.
# functionality-without-body
A module whose heading `# add-task` on line 11 is followed by another heading, by `***test reqs***`, by the end of the file, or by only a comment line raises `PlainSyntaxError` holding `Syntax error at line 11: Functionality `add-task` has no body.`.
## marshall-plain-source
***conformance tests***
# links-are-rendered-as-resources
A module with the files `task_list_ui_specification.yaml` and `add_new_task_modal_specification.yaml` next to it, whose second and third functionalities each link one of them with the file name as link text, gives the second functionality linked_resources [{text `task_list_ui_specification.yaml`, target `task_list_ui_specification.yaml`}] and the third [{text `add_new_task_modal_specification.yaml`, target `add_new_task_modal_specification.yaml`}].
- The functionality markdown holds `` `[resource]task_list_ui_specification.yaml` `` and `` `[resource]add_new_task_modal_specification.yaml` `` in place of the links.
# imports-merge-in-order
The module `diamond_imports_main` imports `diamond_import_1` and `diamond_import_2`, which both import `diamond_import_common`; each import module defines one concept and has one implementation req and one test req naming it, and the main module has the implementation req `- ⟨MainExecutableFile⟩ of ⟨App⟩ should be called "hello_world.py".` and the functionality `display-hello-world`.
- Its marshalled tree lists the definitions, implementation reqs and test reqs of `diamond_import_common`, `diamond_import_1` and `diamond_import_2`, in that order, each once, and then the own implementation req.
## find-linked-resources
***conformance tests***
# independent-of-working-directory
Parsing the module with the two linked yaml files from another working directory gives the same linked_resources.
***acceptance tests***
# url-link
A module linking `https://example.com/spec.yaml` raises an error holding `Only relative links are allowed`.
# absolute-link
A module linking an absolute path raises an error holding `Only relative links are allowed`.
# missing-link-lists-directories
A module linking `resources/missing_resource.yaml`, which does not exist, raises `PlainSyntaxError` whose message holds `resources/missing_resource.yaml does not exist`, `highest to lowest precedence` and the module's directory.
## import-modules
***conformance tests***
# diamond-import-merged-once
In the module `diamond_imports_main`, the definition of `diamond_import_common` appears once in the tree.
***acceptance tests***
# imported-module-with-functionalities
Parsing a module that imports `import_with_functionalities`, which has a `functional specs` section, raises `ImportedModuleWithFunctionalitiesError` whose message holds `use 'requires' instead of 'import'`.
# non-existent-import
Parsing a module that imports `non_existent_module` raises an error whose message holds `Module does not exist`.
# circular-imports
Parsing `circular_imports_main`, which imports `circular_imports_1`, which imports `circular_imports_2`, which imports `circular_imports_1`, raises an error whose message holds `Circular import detected`.
## read-module-file
***conformance tests***
# first-directory-wins
With `m.plain` in two template directories, parsing `m.plain` reads the one in the first directory.
***acceptance tests***
# missing-module
Parsing `does_not_exist.plain` raises `ModuleDoesNotExistError` with `Module does not exist (does_not_exist).`.
# base64-in-module
Parsing a module whose functionality body holds 8292 `A` characters in a row raises `UnsupportedBase64Content` whose message holds `contains a base64-encoded blob (8292 characters)`.
## require-imported-concepts
***conformance tests***
# required-concept-defined
The import module `required_concepts` has `required_concepts` [`⟨Concept⟩ is a required concept and needs to be defined in the module that imports this one.`] and the definition `- ⟨DependantConcept⟩ is a concept that depends on the ⟨Concept⟩ concept.`; a module importing it and defining `- ⟨Concept⟩ is a concept.` parses.
# required-concept-defined-by-another-import
A module importing `required_concepts` and `required_concepts_defs`, which defines Concept, parses, and its definitions are sorted to [`- ⟨Concept⟩ is a concept.`, `- ⟨DependantConcept⟩ is a concept that depends on the ⟨Concept⟩ concept.`].
# nested-required-concepts
`required_concepts_l2` requires Concept1 and Concept2; `required_concepts_l1` imports it, defines Concept1 and lists no `required_concepts`; a module importing `required_concepts_l1` and defining only Concept2 parses.
***acceptance tests***
# required-concept-missing
A module importing `required_concepts` and defining nothing raises `PlainSyntaxError` whose message holds `Not all required concepts were defined. Missing required concepts: ⟨Concept⟩.`.
# required-concept-defined-twice
A module importing `required_concepts_l1` and defining Concept1 and Concept2 raises `PlainSyntaxError` holding `Concepts were defined multiple times`.
## normalize-concept-lists
***conformance tests***
# string-entries
Parsing a module with `exported_concepts` [`⟨Concept⟩ is a concept.`] leaves the frontmatter value [`- ⟨Concept⟩ is a concept.`].
***acceptance tests***
# entry-of-another-type
A module with `exported_concepts` [5] raises `PlainSyntaxError` with `Plain syntax error: Invalid exported_concepts metadata. Expected a dictionary or a string.`.
## check-exported-concepts
***conformance tests***
# export-own-concept
The module `exported_concepts`, which defines and exports Concept, parses.
# export-imported-concept
A module that imports `exported_concepts_base`, which defines Concept, and exports Concept parses.
# several-per-entry
A module exporting `⟨NewConcept⟩, ⟨OtherConcept⟩` in one entry and defining both parses.
***acceptance tests***
# export-predefined-concept
A module exporting `⟨Implementation⟩` raises `PlainSyntaxError` holding `cannot export default concept`.
# export-inherited-concept
A module that requires `exported_concepts`, uses its Concept, and exports Concept raises `PlainSyntaxError` holding `cannot be re-exported`.
# export-malformed
A module exporting `Concept` without colons raises `PlainSyntaxError` holding `exports an invalid concept`.
# export-undefined-names-module
The module `exported_concepts_missing_definition`, which exports a concept it does not define, raises `PlainSyntaxError` holding `'exported_concepts_missing_definition' exports` and `exports undefined concept`, also when parsed as the requires of another module.
# export-undefined-in-multi-entry
A module exporting `⟨NewConcept⟩, ⟨OtherConcept⟩` and defining only NewConcept raises `PlainSyntaxError` holding `exports undefined concept`.
# export-without-definitions
A module exporting Concept with no `definitions` section raises `PlainSyntaxError` holding `exports undefined concept`.
## mark-code-variables
***conformance tests***
# token-is-recorded
Rendering `{% raw %}{% include 't', a: 'A', b: 'B' %}{% endraw %}` with `t` holding `{% raw %}{{ b | code_variable }}{% endraw %}` and an empty code-variables mapping outputs a 32-character hex token, and the mapping becomes {token: {`a`: `B`}}.
# outside-include
Rendering `a {% raw %}{{ 'x' | code_variable }}{% endraw %}` with an empty code-variables mapping outputs `a ` and a token mapped to {`code_variables`: `x`}.
## record-code-variables
***conformance tests***
# functionality-code-variable
The module `code_variables` with the functionality `implement` whose body is `Implement` followed by an include of `implement.plain` with `variable_name: "nice"`, where `implement.plain` holds `something nice and useful`, `  - the nice thing should be really {% raw %}{{ variable_name | code_variable }}{% endraw %}`, `  - the useful thing should be really useful`, gives the functionality markdown with the placeholder of `variable_name` in place of the value and code_variables [{name `variable_name`, value `nice`}].
- The definitions are [{markdown `- ⟨concept⟩ is a concept.`}].
# list-items-and-first-argument-name
The module `template_include` includes `header.plain` with `variable_name_1: "nice_1", variable_name_2: "nice_2"`; its two implementation reqs use `variable_name_1` and `variable_name_2` with the `code_variable` filter.
- Both items get the placeholder of `variable_name_1`, with code_variables [{name `variable_name_1`, value `nice_1`}] and [{name `variable_name_1`, value `nice_2`}].
# same-include-two-values
A module including one template with `variable_name: "first"` in one functionality and `variable_name: "second"` in another parses, each functionality recording its own value.
## check-module-shape
***acceptance tests***
# no-implementation-reqs
A module with a functionality and an empty `implementation reqs` section, and one without that section, each raise an error holding `defines functionalities but specifies no implementation reqs` and not holding `requires`.
# no-implementation-reqs-with-requires
A module with a `requires` list, a functionality and no implementation req raises `PlainSyntaxError` holding `not inherited through 'requires'`.
# no-functional-specs-section
A module without a `functional specs` section raises `MissingFunctionalitiesError` holding `does not have any functionality specified`.
# empty-functional-specs-section
A module with an empty `functional specs` section raises `PlainSyntaxError` holding `has a 'functional specs' section without a `# <func-id>` heading. A functionality is a `# <func-id>` heading followed by its body; the previous syntax is not supported.`.
## parse-single-module
***conformance tests***
# simple-module
Parsing `simple.plain` gives the module name `simple`, the tree of :PlainSourceTree: Example, and an empty `requires` list.
# nested-module-name
Parsing `sub/m.plain` over the parent directory gives the module name `sub/m`.
# valid-concepts
A module defining `- ⟨Task⟩ is a thing to do.` and `- ⟨User⟩, ⟨Admin⟩ are people.`, and using them in its implementation reqs and functional specs together with ⟨Implementation⟩, parses.
# sorted-definitions
A module defining, in this order, `- ⟨Concept3⟩ ... ⟨Concept1⟩ and ⟨Concept2⟩ ...`, `- ⟨Concept2⟩ ... ⟨Concept1⟩ ...`, `- ⟨Concept1⟩ is a concept.` gives the definitions Concept1, Concept2, Concept3 in that order.
***acceptance tests***
# wrong-extension
Parsing `test.txt` raises `PlainSyntaxError`.
# undefined-concept
A module using ⟨User⟩ in a functionality without defining it raises `PlainSyntaxError`; so does one that defines Task but uses Task and the undefined Visitor in one sentence.
# definition-without-concept
A module whose definition is `- A plain sentence.` raises `PlainSyntaxError` holding `Invalid definition specification text`.
# concept-defined-twice
A module defining Task twice raises `PlainSyntaxError` holding `Concepts were defined multiple times`.
# cyclic-definitions
A module whose definitions mention each other in a cycle raises `PlainSyntaxError` holding `cycle(s) in concept definitions`.
# cyclic-definitions-across-import
A module defining `- ⟨Concept⟩ is the concept that ⟨DependantConcept⟩ builds on.` and importing `required_concepts`, whose definition of DependantConcept mentions Concept, raises `PlainSyntaxError` holding `Found 1 cycle` and both definitions.
# cyclic-definitions-through-sub-item
A module with `- ⟨Order⟩ is a purchase.` and the nested item `  - It is placed by a ⟨Customer⟩.`, `- ⟨Customer⟩ has ⟨Order⟩ items.`, and `- ⟨Receipt⟩ is for an ⟨Order⟩.` raises a message holding `Cycle 1: ⟨Order⟩ -> ⟨Customer⟩ -> ⟨Order⟩` and the Order item with its nested line, and not naming Receipt.
# liquid-error-names-module
The module `unterminated_output` raises `PlainSyntaxError` whose message starts with `Plain syntax error: Invalid Liquid at unterminated_output`, then the line `5` and the column `0`, each after a colon.
# include-ending-in-newline
A functionality whose body includes, in a nested item, a template that ends with a newline, followed by a comment line, parses.
