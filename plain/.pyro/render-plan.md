# Render Plan

| Order | Module | Spec File | Imports | Requires | Functional Reqs | Status* |
|-------|--------|-----------|---------|----------|-----|--------|
| 1 | cycle_graph | cycle_graph.plain | plain_parser_base | - | 3 | done |
| 2 | spec_tree | spec_tree.plain | plain_parser_base | cycle_graph | 8 | done |
| 3 | resource_loading | resource_loading.plain | plain_parser_base | spec_tree | 7 | done |
| 4 | concepts | concepts.plain | plain_parser_base | resource_loading | 5 | done |
| 5 | spec_module | spec_module.plain | plain_parser_base | concepts | 17 | done |
| 6 | requires_chain | requires_chain.plain | plain_parser_base | spec_module | 4 | done |
| 7 | test_plain_file | test_plain_file.plain | plain_parser_base | requires_chain | 7 | done |
| 8 | project | project.plain | plain_parser_base | test_plain_file | 5 | done |
| 9 | plain_parser | plain_parser.plain | plain_parser_base | project | 8 | done |

*Valid statuses: todo, in progress, retrying, done, failed
