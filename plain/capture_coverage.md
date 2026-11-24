# Capture coverage map

Every original test (`tests/*.py`) and the spec / scenario that covers it, as `module:func-id/scenario-id`.
Parametrized tests are covered by one scenario that lists every parameter. Error-path tests are acceptance scenarios.

## test_graph.py → cycle_graph
- dag_has_no_cycles → list-simple-cycles/graph-without-cycles
- empty_graph → list-simple-cycles/empty-graph
- self_loop → list-simple-cycles/self-loop
- two_node_cycle → list-simple-cycles/two-node-cycle
- targets_only_nodes_are_tolerated → list-simple-cycles/successor-only-node-is-tolerated
- complete_graph_on_three/four_nodes → list-simple-cycles/complete-graph-on-three-nodes, complete-graph-on-four-nodes
- two_separate_cycles_are_both_found → list-simple-cycles/separate-cycles
- cycles_are_reported_in_edge_order → list-simple-cycles/edge-order
- strongly_connected_components → find-strongly-connected-components/components-of-mixed-graph
- limit_stops_after_that_many_cycles → limit-cycle-search/limit-stops-the-search
- acyclic_appendage_is_never_entered → limit-cycle-search/acyclic-appendage-is-not-searched
- repeated_edge_yields_each_cycle_once → list-simple-cycles/repeated-edge
- limit_does_not_enumerate_the_rest → limit-cycle-search/limit-is-lazy
- separate_cycles_come_in_graph_order → list-simple-cycles/separate-cycles-in-node-order
- cycle_longer_than_the_recursion_limit → limit-cycle-search/cycle-longer-than-the-recursion-limit
- components_of_a_chain_longer_than_the_recursion_limit → find-strongly-connected-components/long-chain
- matches_brute_force_on_random_graphs[200] → list-simple-cycles/matches-brute-force

## test_exceptions.py → spec_tree
- parser_exceptions_exist_and_are_exceptions[8] → define-error-classes/error-classes-are-exceptions

## test_plainspec.py → spec_tree
- get_linked_resources_invalid_input → collect-linked-resources/tree-is-not-a-mapping
- has_acceptance_tests_true/false/false_when_no_functional_requirements → walk-func-ids/has-acceptance-tests
- get_frids_simple, get_frids_yields_ids_in_file_order → walk-func-ids/func-ids-in-file-order
- get_first_functional_requirement_simple → walk-func-ids/first-func-id
- get_next_frid_simple, get_previous_frid_no_previous_frid → walk-func-ids/next-and-previous
- get_next_frid_not_exists, get_previous_frid_not_exists → walk-func-ids/unknown-func-id
- get_frids_before → walk-func-ids/func-ids-before
- get_specifications_simple → collect-specifications-for-func-id/single-functionality, unknown-func-id
- get_specifications_for_frid_takes_functional_specs_up_to_the_frid_and_its_scenarios → collect-specifications-for-func-id/specifications-up-to-the-func-id
- get_specifications_for_frid_replaces_code_variables_in_scenarios → replace-code-variables/replace-in-scenario
- collect_linked_resources_stops_at_the_frid_and_takes_only_its_scenarios → collect-linked-resources/stops-at-the-func-id
- collect_linked_resources_without_frid_takes_every_functionality_and_scenario → collect-linked-resources/every-functionality-and-scenario
- collect_linked_resources_can_leave_out_the_scenarios → collect-linked-resources/without-scenarios
- collect_linked_resources_unknown_frid_raises → collect-linked-resources/unknown-func-id
- get_frids_range_* (5) → select-func-id-range/start-and-end-inclusive, without-end, unknown-start, unknown-end, start-after-end
- is_semantic_id_accepts_*[6] / rejects_*[11] → check-semantic-id/accepts-hyphen-joined-segments, rejects-other-shapes

## test_loaders.py → resource_loading
- load_linked_resources_text_file → load-linked-files/text-file
- load_linked_resources_binary_file_raises_unsupported_resource_type → load-linked-files/binary-file
- load_linked_resources_missing_file_raises_file_not_found → load-linked-files/missing-file
- load_linked_resources_base64_blob_raises, real_base64_image_raises → load-linked-files/base64-blob (a long run of `A` stands in for the real JPEG sample)
- load_linked_resources_small_base64_allowed → load-linked-files/small-base64-is-allowed
- get_loaded_templates_missing_include_names_template → render-liquid/missing-include
- resolve_linked_resource_returns_none_when_missing → look-up-files/missing-file
- resolve_linked_resource_first_dir_wins → look-up-files/first-dir-wins
- resolve_linked_resource_falls_back_to_later_dir, find_resource_dir_returns_the_dir_not_the_joined_path → look-up-files/later-dir-is-searched, missing-file
- resolve_linked_resource_parent_relative_path → look-up-files/parent-relative-path
- resolve_linked_resource_directory_in_first_dir_shadows_file_in_second → look-up-files/directory-hides-later-file
- get_loaded_templates_malformed_tag / unterminated_output → render-liquid/malformed-tag, unterminated-output
- liquid_error_message_without_position → render-liquid/error-message-without-position
- relative_resource_path_* (3) → relative-resource-path/same-directory, other-directory, subdirectory, no-relative-path

## test_concept_utils.py → concepts
- sort_single_definition_is_unchanged → sort-definitions/single-item
- sort_definitions_without_concept_references_keeps_file_order → sort-definitions/no-mentions-keep-file-order
- sort_places_dependency_before_dependant → sort-definitions/dependency-first
- sort_resolves_diamond_dependencies → sort-definitions/diamond
- sort_follows_references_in_sub_bullets → sort-definitions/sub-item-mention
- sort_places_multi_concept_definition_before_its_dependants → sort-definitions/multi-concept-definition
- sort_ignores_self_reference / predefined_concepts → sort-definitions/self-mention-is-ignored, predefined-mention-is-ignored
- sort_rejects_two_node_cycle_and_lists_both_definitions → report-concept-cycles/two-node-cycle
- sort_rejects_long_cycle_and_lists_every_definition_on_it, sort_reports_cycle_in_reference_order → report-concept-cycles/long-cycle-in-reference-order
- sort_rejects_cycle_through_multi_concept_definition → report-concept-cycles/cycle-through-multi-concept-definition
- sort_rejects_graph_with_two_separate_cycles_and_reports_both → report-concept-cycles/two-separate-cycles
- sort_reports_every_elementary_cycle_of_a_tangle → report-concept-cycles/tangle
- sort_caps_the_number_of_reported_cycles → report-concept-cycles/capped-at-ten
- sort_rejects_cycle_that_also_references_undefined_concept → report-concept-cycles/cycle-with-undefined-mention
- sort_reports_exactly_the_maximum_without_truncating → report-concept-cycles/exactly-ten
- sort_truncated_report_shows_the_earliest_defined_cycles → report-concept-cycles/earliest-defined-cycles-shown
- sort_truncation_follows_definition_order_not_first_mention → report-concept-cycles/definition-order-not-first-mention
- sort_prints_a_shared_definition_once_per_cycle → report-concept-cycles/shared-definition-once

## test_plainfileparser.py → spec_module (and concepts, resource_loading)
- regular_plain_source → read-list-sections/regular-module
- unknown_section, syntax_error_line_number_accounts_for_frontmatter, ..._with_windows_line_endings → reject-invalid-sections/unknown-section, line-number-counts-frontmatter, line-number-with-windows-line-endings
- duplicate_section, duplicate_specification_heading → reject-invalid-sections/duplicate-section, duplicate-section-names-the-module
- invalid_top_level_element → reject-invalid-sections/code-block-in-list-section
- normalize_line_endings_does_not_duplicate_newlines → normalize-line-endings/mixed-line-endings
- plain_file_parser_with_comments / _indented → read-list-sections/comment-lines-are-dropped, indented-comment-lines-are-dropped
- invalid_url_link, invalid_absolute_link → find-linked-resources/url-link, absolute-link
- missing_link_error_lists_searched_directories → find-linked-resources/missing-link-lists-directories
- reference_link_parsing → marshall-plain-source/links-are-rendered-as-resources
- reference_link_parsing_independent_of_working_directory → find-linked-resources/independent-of-working-directory
- invalid_specification_order → reject-invalid-sections/definitions-not-first
- missing_non_functional_requirements, without_non_functional_requirement, missing_impl_reqs_without_requires_has_no_hint → check-module-shape/no-implementation-reqs
- missing_impl_reqs_with_requires_adds_hint → check-module-shape/no-implementation-reqs-with-requires
- no_functional_specs_section / empty_functional_specs_section → check-module-shape/no-functional-specs-section, empty-functional-specs-section
- indented_include_tags → resource_loading:indent-included-templates/indented-includes, include-in-comment-is-kept
- code_variables → record-code-variables/functionality-code-variable, list-items-and-first-argument-name; mark-code-variables/token-is-recorded
- block_include_with_trailing_newline_keeps_structure_and_ignores_quote → parse-single-module/include-ending-in-newline
- functionality_is_its_heading_id_and_its_body → read-functionalities/heading-and-body
- functionality_body_may_start_with_a_list → read-functionalities/body-starts-with-a-list
- bullets_without_a_heading_are_the_previous_syntax → reject-invalid-functionalities/previous-syntax
- flush_left_list_after_a_heading_is_body → read-functionalities/flush-left-list-is-body
- test_section_in_spec_plain_file_is_rejected[2] → reject-invalid-sections/test-section-in-spec-file
- nested_acceptance_tests_section_is_rejected → reject-invalid-sections/nested-test-section
- heading_outside_functional_specs_is_rejected → reject-invalid-functionalities/heading-outside-functional-specs
- heading_of_another_level_is_rejected → reject-invalid-functionalities/heading-of-level-two
- func_id_with_other_characters_is_rejected → reject-invalid-functionalities/invalid-func-id-message
- func_id_syntax_is_checked[10] → reject-invalid-functionalities/invalid-func-id
- duplicate_func_id_is_rejected → reject-invalid-functionalities/duplicate-func-id
- content_before_the_first_heading_is_rejected[2] → reject-invalid-functionalities/content-before-first-heading
- functionality_without_body_is_rejected[4] → reject-invalid-functionalities/functionality-without-body
- any_block_after_a_heading_is_body → read-functionalities/any-block-is-body
- block_in_a_list_section_is_still_rejected → reject-invalid-sections/block-after-list-items
- invalid_plain_file_extension → parse-single-module/wrong-extension
- concept_validation_definitions → parse-single-module/definition-without-concept, valid-concepts
- concept_validation_usage → parse-single-module/valid-concepts, undefined-concept
- concept_validation_redefinition → parse-single-module/concept-defined-twice
- concept_validation_non_concept_usage → concepts:validate-concepts/words-between-colons-are-not-concepts
- concept_validation_several_concepts → parse-single-module/valid-concepts
- concept_validation_cyclic_definitions, ..._reports_every_definition_on_the_cycle → parse-single-module/cyclic-definitions; concepts:report-concept-cycles/long-cycle-in-reference-order
- concept_validation_cyclic_definitions_across_import → parse-single-module/cyclic-definitions-across-import
- concept_validation_cyclic_definitions_through_sub_bullet → parse-single-module/cyclic-definitions-through-sub-item
- topological_sort_across_import → require-imported-concepts/required-concept-defined-by-another-import
- required_concepts → require-imported-concepts/* (all five scenarios)
- exported_concepts_valid[4] → check-exported-concepts/export-own-concept, export-imported-concept, several-per-entry; requires_chain:share-exported-concepts/exported-concept-is-visible, export-of-imported-concept
- exported_concepts_invalid[9] → check-exported-concepts/export-predefined-concept, export-inherited-concept, export-malformed, export-undefined-names-module, export-undefined-in-multi-entry, export-without-definitions; requires_chain:share-exported-concepts/concept-not-exported, exports-are-not-transitive
- requires_without_definitions → requires_chain:share-exported-concepts/export-arrives-in-definitions
- topological_sort → parse-single-module/sorted-definitions; concepts:sort-definitions/graph-order
- liquid_syntax_error_names_module → parse-single-module/liquid-error-names-module

## test_imports.py → spec_module
- imported_module_with_functionalities → import-modules/imported-module-with-functionalities
- non_existent_import → import-modules/non-existent-import
- circular_imports → import-modules/circular-imports
- diamond_imports → marshall-plain-source/imports-merge-in-order, import-modules/diamond-import-merged-once

## test_requires.py → requires_chain
- non_existent_require, parse_module_chain_propagates_required_module_errors → walk-requires/non-existent-require
- independent_requires, requires_independent_branches_are_rejected[2] → walk-requires/independent-branches
- diamond_requires, requires_diamond_is_rejected[5] → walk-requires/two-branches-share-base
- circular_requires → walk-requires/circular-requires
- normal_requires → walk-requires/normal-requires
- parse_module_chain_orders_required_modules_first → list-requires-chain/chain-deepest-first
- parse_module_chain_single_module → list-requires-chain/single-module
- parse_module_chain_deduplicates_shared_ancestor → list-requires-chain/shared-ancestor-once
- plain_file_parser_validates_required_modules → list-requires-chain/invalid-ancestor
- middle_module_sees_exports_of_base_module → share-exported-concepts/middle-module-sees-base-exports
- middle_module_sees_exports_of_base_module_when_parsing_above_module → list-requires-chain/nested-walk-keeps-exports
- middle_module_redefining_an_export_of_base_module_is_rejected → share-exported-concepts/redefined-export
- base_module_may_export_nothing → share-exported-concepts/base-module-may-export-nothing
- requires_chain_is_accepted[4] (2 pass, 2 strict xfail) → walk-requires/ancestor-listed-first, module-listed-twice-in-a-row; the xfail cases as rejections: ancestor-listed-after-dependent, ancestor-listed-in-every-module
- top_module_shape_is_checked_before_its_requires_are_read → order-chain-errors/top-shape-before-requires
- top_module_shape_is_checked_before_required_modules_are_validated → order-chain-errors/top-shape-before-required-validation
- parse_errors_of_required_modules_come_before_top_module_concept_errors → order-chain-errors/required-parse-error-before-top-concept-error
- top_module_concept_errors_come_before_required_module_concept_errors → order-chain-errors/top-concept-error-before-required-concept-error
- required_modules_are_validated_top_down → order-chain-errors/required-modules-top-down
- module_listed_twice_around_its_dependent_is_rejected → walk-requires/listed-again-after-dependent
- chain_has_a_tree_for_every_module_reached_by_the_walk → walk-requires/ancestor-listed-first, list-requires-chain/chain-deepest-first
- required_module_without_functional_specs_is_rejected → order-chain-errors/required-module-without-functional-specs
- top_module_concept_errors_come_before_required_module_structure_errors → order-chain-errors/top-concept-error-before-required-shape-error
- each_required_module_is_validated_once_top_down → order-chain-errors/listed-order-decides (black box: the call count needs a monkeypatch of an internal function; the order is observed through which error wins)

## test_test_plain_file.py → test_plain_file
- valid_file_binds_to_its_functionality_and_keeps_the_scenarios_verbatim → read-scenarios/valid-file
- both_sections_may_be_empty[3] → read-scenarios/empty-sections
- invalid_file_is_rejected_with_its_place[13] → reject-invalid-scenarios/* (10 scenarios), read-test-frontmatter/extra-key, missing-func-id, module-not-a-string
- missing_link_names_the_file_and_the_scenario → resolve-scenario-links/missing-link
- link_to_a_plain_file_is_rejected → resolve-scenario-links/link-to-plain-file
- scenario_id_syntax_is_checked[7] → reject-invalid-scenarios/scenario-id-shapes
- lines_inside_a_code_fence_are_scenario_text[4] → keep-code-fences/fenced-lines-are-text
- heading_after_a_closed_code_fence_starts_a_scenario → keep-code-fences/heading-after-closed-fence
- code_fence_that_is_not_closed_is_rejected → keep-code-fences/fence-not-closed
- code_fence_before_the_first_scenario_is_content_before_a_heading → keep-code-fences/fence-before-first-scenario
- invalid_frontmatter_is_rejected → read-test-frontmatter/invalid-yaml
- liquid_runs_with_the_template_directories → read-scenarios/liquid-and-code-variables
- liquid_error_names_the_file → read-scenarios/liquid-error-names-the-file
- scenario_concepts_are_checked_against_the_visible_concepts → check-scenario-concepts/all-concepts-visible, missing-concept
- predefined_concepts_need_no_definition → check-scenario-concepts/predefined-concepts
- is_test_plain_file[4] → recognize-test-plain-file/binding-keys

## test_project.py → project
- scenarios_are_merged_into_the_bound_functionality → bind-test-plain-files/scenarios-are-merged
- location_and_name_of_a_test_plain_file_are_convention_only → bind-test-plain-files/name-is-convention-only
- files_bound_to_one_functionality_merge_in_path_order → bind-test-plain-files/merge-in-discovery-order, discover-test-plain-files/path-order
- tests_folders_are_read_in_the_given_order → bind-test-plain-files/folders-in-given-order, discover-test-plain-files/folder-order
- missing_tests_folder_is_not_an_error → discover-test-plain-files/missing-folder
- duplicate_scenario_id_across_files_is_rejected → check-bound-scenarios/duplicate-id-across-files
- same_scenario_id_for_two_functionalities_is_allowed → check-bound-scenarios/same-id-in-two-functionalities
- a_file_of_a_module_outside_the_chain_is_passed_over → bind-test-plain-files/file-of-another-module-is-passed-over
- a_file_outside_the_chain_is_not_read_at_all → bind-test-plain-files/file-of-another-module-is-not-read
- a_module_name_that_is_a_typo_leaves_the_functionality_without_a_test_plain_file → require-test-plain-files/misspelled-module
- unknown_func_id_is_rejected → reject-invalid-test-plain-files/unknown-func-id
- plain_file_under_tests_folder_without_binding_keys_is_rejected → reject-invalid-test-plain-files/no-binding-keys
- file_under_tests_folder_with_invalid_frontmatter_is_rejected → reject-invalid-test-plain-files/invalid-frontmatter
- test_plain_file_errors_name_their_file → reject-invalid-test-plain-files/file-errors-name-the-file
- scenario_concepts_are_checked_against_the_bound_module → check-bound-scenarios/undefined-concept
- scenarios_see_imported_and_exported_concepts → bind-test-plain-files/required-module-files
- required_module_scenarios_do_not_see_the_top_modules_concepts → check-bound-scenarios/required-module-does-not-see-entry-concepts
- every_functionality_needs_a_test_plain_file_when_required → require-test-plain-files/missing-file, check-off-by-default
- a_test_plain_file_with_empty_sections_satisfies_the_check[2] → require-test-plain-files/empty-sections-satisfy-the-check
- completeness_covers_the_required_modules_first → require-test-plain-files/required-modules-first

## test_cli.py → plain_parser (top-level)
- check_valid_module_exits_zero, check_valid_module_prints_ok_line_with_file_as_given → check-command/valid-module
- check_without_file_argument_is_usage_error, parse_without_file_argument_is_usage_error, without_subcommand_is_usage_error → accept-command-line/*
- console_script_is_installed_and_exits_zero → export-package-api/console-script
- check_valid_module_in_subdirectory_from_parent → parse-spec/relative-entry-path
- check_probe_module_without_config_prints_ok → check-command/probe-module
- check_nonexistent_template_dir_is_ignored → parse-spec/missing-template-dir-is-ignored
- check_undefined_concept → check-command/undefined-concepts
- check_missing_linked_resource → check-command/missing-linked-resource
- check_missing_linked_resource_lists_relative_template_dir_as_absolute → check-command/relative-template-dir-listed-absolute
- check_binary_linked_resource, check_invalid_linked_resource_in_required_module → check-command/binary-resource
- check_base64_blob_linked_resource → check-command/base64-resource
- check_code_variable_with_two_values, parse_reports_an_error_only_the_frid_walk_finds → parse-spec/code-variable-with-two-values
- check_missing_plain_file → check-command/missing-module
- check_wrong_extension → check-command/wrong-extension
- check_empty_template_dir_is_ignored → parse-spec/empty-template-dir-is-ignored
- check_interrupted_exits_130_without_traceback[2] → check-command/interrupted
- check_reads_template_dir_from_config_next_to_spec → find-config-file/config-next-to-spec
- check_accepts_template_dir_key_with_underscore → read-config-values/underscore-key
- check_ignores_other_config_keys → read-config-values/other-keys-ignored
- check_without_config_does_not_search_template_dir → find-config-file/no-config
- check_config_name_selects_config_file → find-config-file/config-name-option
- check_explicit_template_dir_overrides_config → read-config-values/template-dir-option-wins
- check_reads_config_from_working_directory → find-config-file/config-in-working-directory
- check_config_in_both_locations_is_usage_error (+ _even_with_explicit_template_dir), parse_config_in_both_locations_is_usage_error → find-config-file/config-in-both-places
- check_unreadable_config_is_usage_error → find-config-file/unreadable-config
- check_project_with_test_plain_files_prints_ok → read-config-values/project-with-test-plain-files
- check_missing_test_plain_file_names_the_functionality_and_the_skill → check-command/missing-test-plain-file
- check_minimal_test_plain_file_satisfies_the_completeness_check → check-command/minimal-test-plain-file
- check_without_conformance_tests_script_needs_no_test_plain_files → read-config-values/without-conformance-script
- without_tests_folder_no_test_plain_files_are_read → read-config-values/without-tests-folder
- conformance_tests_script_without_tests_folder_is_usage_error[2] → read-config-values/conformance-without-tests-folder
- check_test_plain_file_error_is_reported_with_its_file → check-command/test-plain-file-error
- check_reads_tests_folder_from_config[3] → read-config-values/tests-folder-from-config
- check_config_tests_folder_is_the_only_directory_scanned → read-config-values/config-tests-folder-only
- check_link_in_scenario_is_read → check-command/binary-scenario-resource
- check_tests_folder_option_overrides_the_config → read-config-values/tests-folder-option-wins
- check_tests_folder_option_can_be_repeated → read-config-values/tests-folder-option-repeated
- check_reports_ancestor_resource_before_frid_walk_error → parse-spec/ancestor-resource-before-func-id-walk
- parse_valid_module_prints_success_json → parse-command/valid-module
- parse_invalid_module_prints_error_json → parse-command/invalid-module
- parse_prints_every_module_of_the_chain_deepest_ancestor_first[2] → parse-command/chain-deepest-first
- parse_diverging_requires_is_parser_error → parse-command/diverging-requires
- parse_resolves_link_from_template_dir, parse_spec_resource_path_joined_onto_the_entry_dir_names_the_resolved_file → parse-spec/resource-from-template-dir
- parse_accepts_binary_resource_that_check_rejects[2] → parse-command/binary-resource-is-not-read
- parse_lists_a_target_linked_from_two_modules_once → parse-spec/target-from-two-modules
- parse_lists_the_test_plain_files_and_merges_their_scenarios → parse-command/test-plain-files-and-scenarios
- parse_resources_include_the_links_of_the_scenarios → parse-spec/scenario-links
- parse_missing_test_plain_file_is_a_parser_error → parse-command/missing-test-plain-file
- parse_writes_utf8_json_whatever_the_stdout_encoding → write-parse-output/utf8-whatever-the-encoding
- parse_to_a_closed_pipe_keeps_the_exit_code_and_prints_no_error → write-parse-output/closed-pipe
- parse_resource_path_is_the_template_dir_relative_to_the_entry_dir_joined_with_the_target → parse-spec/parent-relative-target
- parse_resource_path_keeps_a_symlink_unresolved → parse-spec/symlink-not-resolved
- parse_resource_path_falls_back_to_absolute_when_no_relative_path_exists → parse-spec/no-relative-path
- parse_with_template_dir_from_config_prints_only_json → parse-command/template-dir-from-config
- parse_interrupted_exits_130_with_empty_stdout[2] → parse-command/interrupted
- parse_missing_or_non_plain_entry_is_parser_error[2] → parse-command/missing-or-non-plain-entry
- parse_dir_name_that_is_not_utf8_stays_out_of_a_valid_result → write-parse-output/non-utf8-directory-stays-out
- parse_module_name_that_is_not_utf8_is_quoted_without_trailing_comma → write-parse-output/non-utf8-module-name
- parse_error_naming_a_path_that_is_not_utf8_keeps_its_type → write-parse-output/non-utf8-path-in-error
- parse_result_that_is_not_json_is_reported_as_json_error → write-parse-output/result-not-json
- parse_writes_to_a_stdout_without_byte_buffer → parse-command/stdout-without-byte-buffer

## Left out
- None of the original tests are left out. Behaviour captured beyond the tests (each checked against the original):
  filter edge cases, `prohibited_chars`, hashing, `get_frids_range` with start = end, file reading order.
