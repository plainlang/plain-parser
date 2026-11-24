"""Conformance tests of module requires_chain."""

import os

import pytest
from plain_parser import plain_file
from plain_parser.exceptions import MissingFunctionalitiesError, ModuleDoesNotExistError, PlainSyntaxError

FIXED_ORDER = "There must be a fixed order how required modules are dependent"


def c(name):
    return f":{name}:"


class Modules:
    def __init__(self, root):
        self.root = str(root)
        self.requires: dict[str, list[str]] = {}

    def add(
        self,
        name,
        requires=(),
        *,
        export=True,
        define=True,
        functional=True,
        mentions=(),
        definitions=(),
        impl=None,
        frontmatter_extra="",
    ):
        """Module X exports and defines XConcept, has one implementation req and the functionality `main` that
        mentions the exported concept of every module X requires (unless told otherwise)."""
        self.requires[name] = list(requires)
        concept = c(f"{name}Concept")
        frontmatter = []
        if requires:
            frontmatter.append("requires:\n" + "".join(f"  - {r}\n" for r in requires))
        if export:
            frontmatter.append(f"exported_concepts:\n  - '{concept}'\n")
        if frontmatter_extra:
            frontmatter.append(frontmatter_extra)
        text = ("---\n" + "".join(frontmatter) + "---\n") if frontmatter else ""
        defs = ([f"- {concept} is the concept of {name}."] if define else []) + list(definitions)
        if defs:
            text += "***definitions***\n\n" + "".join(f"{d}\n" for d in defs) + "\n"
        text += "***implementation reqs***\n\n" + (impl or f"- {name} is written in Python.") + "\n\n"
        if functional:
            used = [c(f"{r}Concept") for r in dict.fromkeys(requires)] + [c(m) for m in mentions]
            sentence = f"{name} works" + (" with " + ", ".join(used) if used else "") + "."
            text += f"***functional specs***\n\n# main\n{sentence}\n"
        with open(os.path.join(self.root, f"{name}.plain"), "w", encoding="utf-8") as file:
            file.write(text)
        return self

    def parse(self, name):
        return plain_file.plain_file_parser(f"{name}.plain", [self.root])

    def chain(self, name):
        return plain_file.parse_module_chain(f"{name}.plain", [self.root])

    def chain_names(self, name):
        return [module for module, _ in self.chain(name)]


@pytest.fixture
def modules(tmp_path):
    return Modules(tmp_path)


def raises(exception, call, *args):
    with pytest.raises(exception) as error:
        call(*args)
    return str(error.value)


# walk-requires


def test_walk_requires__normal_requires(modules):
    modules.add("normal_requires_common")
    modules.add("normal_requires_1", ["normal_requires_common"])
    modules.add("normal_requires_2", ["normal_requires_1"])
    modules.add("normal_requires_main", ["normal_requires_2"])
    name, tree, requires = modules.parse("normal_requires_main")
    assert name == "normal_requires_main"
    assert requires == ["normal_requires_2"]


def test_walk_requires__ancestor_listed_first(modules):
    modules.add("Base").add("Middle", ["Base"]).add("Top", ["Base", "Middle"])
    assert modules.chain_names("Top") == ["Base", "Middle", "Top"]


def test_walk_requires__module_listed_twice_in_a_row(modules):
    modules.add("Base").add("Top", ["Base", "Base"])
    assert modules.chain_names("Top") == ["Base", "Top"]


def test_walk_requires__two_branches_share_base(modules):
    modules.add("Base").add("Left", ["Base"]).add("Right", ["Base"])
    modules.add("Top", ["Left", "Right"])
    assert FIXED_ORDER in raises(PlainSyntaxError, modules.parse, "Top")
    modules.add("Top", ["Right", "Left"])
    assert FIXED_ORDER in raises(PlainSyntaxError, modules.parse, "Top")
    modules.add("LeftDeep", ["Base"]).add("RightDeep", ["Base"])
    modules.add("Left", ["LeftDeep"]).add("Right", ["RightDeep"]).add("Top", ["Left", "Right"])
    assert FIXED_ORDER in raises(PlainSyntaxError, modules.parse, "Top")
    modules.add("Left", ["Base"]).add("Right", ["Base"]).add("Top", ["Base", "Left", "Right"])
    assert FIXED_ORDER in raises(PlainSyntaxError, modules.parse, "Top")
    modules.add("Left", ["Base"]).add("Other", ["Base"]).add("Right", ["Left", "Other"]).add("Top", ["Left", "Right"])
    assert FIXED_ORDER in raises(PlainSyntaxError, modules.parse, "Top")


def test_walk_requires__independent_branches(modules):
    modules.add("Left").add("Right").add("Top", ["Left", "Right"])
    assert FIXED_ORDER in raises(PlainSyntaxError, modules.parse, "Top")
    modules.add("Other").add("Right", ["Other"])
    assert FIXED_ORDER in raises(PlainSyntaxError, modules.parse, "Top")


def test_walk_requires__listed_again_after_dependent(modules):
    modules.add("Base").add("Middle", ["Base"]).add("Top", ["Base", "Middle", "Base"])
    assert FIXED_ORDER in raises(PlainSyntaxError, modules.parse, "Top")


def test_walk_requires__ancestor_listed_after_dependent(modules):
    modules.add("Base").add("Middle", ["Base"]).add("Top", ["Middle", "Base"])
    assert FIXED_ORDER in raises(PlainSyntaxError, modules.parse, "Top")


def test_walk_requires__ancestor_listed_in_every_module(modules):
    modules.add("Base").add("Middle", ["Base"]).add("Upper", ["Base", "Middle"])
    modules.add("Top", ["Base", "Middle", "Upper"])
    assert FIXED_ORDER in raises(PlainSyntaxError, modules.parse, "Top")


def test_walk_requires__circular_requires(modules):
    modules.add("circular_requires_sub", ["circular_requires_main"])
    modules.add("circular_requires_main", ["circular_requires_sub"])
    assert "Circular required module detected" in raises(Exception, modules.parse, "circular_requires_main")


def test_walk_requires__non_existent_require(modules):
    modules.add("Top", ["non_existent_module"], mentions=["non_existent_moduleConcept"])
    assert "Module does not exist" in raises(ModuleDoesNotExistError, modules.parse, "Top")
    assert "Module does not exist" in raises(ModuleDoesNotExistError, modules.chain, "Top")


# share-exported-concepts


def test_share_exported_concepts__exported_concept_is_visible(modules):
    modules.add(
        "exported_concepts",
        define=False,
        definitions=[f"- {c('Concept')} is a concept."],
        export=False,
        frontmatter_extra=f"exported_concepts:\n  - '{c('Concept')}'\n",
    )
    modules.add(
        "Dependant",
        export=False,
        define=False,
        frontmatter_extra="requires:\n  - exported_concepts\n",
        definitions=[f"- {c('DependantConcept')} depends on the {c('Concept')} concept."],
        mentions=["DependantConcept"],
    )
    modules.parse("Dependant")


def test_share_exported_concepts__export_of_imported_concept(modules, tmp_path):
    (tmp_path / "exported_concepts_base.plain").write_text(f"***definitions***\n\n- {c('Concept')} is a concept.\n")
    modules.add(
        "exported_concepts_nested",
        export=False,
        define=False,
        definitions=[f"- {c('NestedConcept')} depends on the {c('Concept')} concept."],
        frontmatter_extra=f"import:\n  - exported_concepts_base\nexported_concepts:\n  - '{c('NestedConcept')}'\n",
    )
    modules.add(
        "User",
        export=False,
        define=False,
        frontmatter_extra="requires:\n  - exported_concepts_nested\n",
        mentions=["NestedConcept"],
    )
    modules.parse("User")


def test_share_exported_concepts__export_arrives_in_definitions(modules):
    modules.add(
        "exported_concepts",
        define=False,
        definitions=[f"- {c('Concept')} is a concept."],
        export=False,
        frontmatter_extra=f"exported_concepts:\n  - '{c('Concept')}'\n",
    )
    modules.add(
        "User", export=False, define=False, frontmatter_extra="requires:\n  - exported_concepts\n", mentions=["Concept"]
    )
    _, tree, _ = modules.parse("User")
    assert tree["definitions"] == [{"markdown": f"- {c('Concept')} is a concept."}]


def test_share_exported_concepts__middle_module_sees_base_exports(modules):
    modules.add(
        "shared_export_base",
        export=False,
        define=False,
        definitions=[f"- {c('KeyStore')} keeps keys."],
        frontmatter_extra=f"exported_concepts:\n  - '{c('KeyStore')}'\n",
    )
    modules.add(
        "shared_export_middle",
        export=False,
        define=False,
        frontmatter_extra="requires:\n  - shared_export_base\n",
        mentions=["KeyStore"],
    )
    modules.add(
        "shared_export_top",
        export=False,
        define=False,
        frontmatter_extra="requires:\n  - shared_export_base\n  - shared_export_middle\n",
        mentions=["KeyStore"],
    )
    modules.parse("shared_export_top")


def test_share_exported_concepts__base_module_may_export_nothing(modules):
    modules.add("Base", export=False).add("Middle", ["Base"])
    modules.add("Top", ["Base", "Middle"], mentions=[])
    # Base exports nothing, so Top mentions only MiddleConcept.
    modules.add("Top", ["Base", "Middle"], functional=False)
    with open(os.path.join(modules.root, "Top.plain"), "a", encoding="utf-8") as file:
        file.write(f"***functional specs***\n\n# main\nTop works with {c('MiddleConcept')}.\n")
    with open(os.path.join(modules.root, "Middle.plain"), encoding="utf-8") as file:
        middle = file.read().replace(f"with {c('BaseConcept')}", "alone")
    with open(os.path.join(modules.root, "Middle.plain"), "w", encoding="utf-8") as file:
        file.write(middle)
    assert modules.chain_names("Top") == ["Base", "Middle", "Top"]


def test_share_exported_concepts__exports_are_not_transitive(modules):
    modules.add(
        "exported_concepts_transitive_l2",
        define=False,
        export=False,
        definitions=[f"- {c('Concept')} is a concept."],
        frontmatter_extra=f"exported_concepts:\n  - '{c('Concept')}'\n",
    )
    modules.add("exported_concepts_transitive_l1", ["exported_concepts_transitive_l2"], export=False, functional=False)
    with open(os.path.join(modules.root, "exported_concepts_transitive_l1.plain"), "a", encoding="utf-8") as file:
        file.write(f"***functional specs***\n\n# main\nUses {c('Concept')}.\n")
    modules.add(
        "User",
        export=False,
        define=False,
        frontmatter_extra="requires:\n  - exported_concepts_transitive_l1\n",
        mentions=["Concept"],
    )
    assert "not defined" in raises(PlainSyntaxError, modules.parse, "User")


def test_share_exported_concepts__concept_not_exported(modules):
    modules.add(
        "exported_concepts_not_declared", export=False, define=False, definitions=[f"- {c('Concept')} is a concept."]
    )
    modules.add(
        "User",
        export=False,
        define=False,
        frontmatter_extra="requires:\n  - exported_concepts_not_declared\n",
        mentions=["Concept"],
    )
    assert "not defined" in raises(PlainSyntaxError, modules.parse, "User")


def test_share_exported_concepts__redefined_export(modules):
    modules.add("Base")
    modules.add("Middle", ["Base"], definitions=[f"- {c('BaseConcept')} is redefined in Middle."])
    modules.add("Top", ["Base", "Middle"])
    message = raises(PlainSyntaxError, modules.chain, "Top")
    assert f"Concepts were defined multiple times: {c('BaseConcept')}" in message


# list-requires-chain


def test_list_requires_chain__chain_deepest_first(modules):
    modules.add("chain_base").add("chain_middle", ["chain_base"]).add("chain_top", ["chain_middle"])
    chain = modules.chain("chain_top")
    assert [name for name, _ in chain] == ["chain_base", "chain_middle", "chain_top"]
    assert all("functional specs" in tree for _, tree in chain)


def test_list_requires_chain__single_module(modules):
    modules.add("chain_base")
    assert modules.chain_names("chain_base") == ["chain_base"]


def test_list_requires_chain__shared_ancestor_once(modules):
    modules.add("chain_base").add("chain_middle", ["chain_base"]).add("chain_fork_top", ["chain_base", "chain_middle"])
    assert modules.chain_names("chain_fork_top") == ["chain_base", "chain_middle", "chain_fork_top"]


def test_list_requires_chain__nested_walk_keeps_exports(modules):
    modules.add("shared_export_base")
    modules.add("shared_export_middle", ["shared_export_base"])
    modules.add("shared_export_top", ["shared_export_base", "shared_export_middle"])
    modules.add("shared_export_above", ["shared_export_top"])
    assert modules.chain_names("shared_export_above") == [
        "shared_export_base",
        "shared_export_middle",
        "shared_export_top",
        "shared_export_above",
    ]


def test_list_requires_chain__invalid_ancestor(modules):
    modules.add("invalid_ancestor_base", mentions=["UndefinedThing"])
    modules.add("invalid_ancestor_top", ["invalid_ancestor_base"])
    assert f"Concept {c('UndefinedThing')} is not defined" in raises(Exception, modules.parse, "invalid_ancestor_top")


# order-chain-errors


def test_order_chain_errors__listed_order_decides(modules):
    modules.add("Base", mentions=["BaseMissing"]).add("Middle", ["Base"], mentions=["MiddleMissing"])
    modules.add("Top", ["Base", "Middle"])
    assert f"Concept {c('BaseMissing')} is not defined" in raises(PlainSyntaxError, modules.chain, "Top")


def test_order_chain_errors__top_shape_before_requires(modules):
    modules.add("Top", ["Missing"], functional=False)
    raises(MissingFunctionalitiesError, modules.parse, "Top")


def test_order_chain_errors__top_shape_before_required_validation(modules):
    modules.add("Base", mentions=["BaseMissing"]).add("Top", ["Base"], functional=False)
    raises(MissingFunctionalitiesError, modules.parse, "Top")


def test_order_chain_errors__required_parse_error_before_top_concept_error(modules):
    modules.add("Base", impl="- {% if %}").add("Top", ["Base"], mentions=["TopMissing"])
    assert "Invalid Liquid" in raises(PlainSyntaxError, modules.parse, "Top")


def test_order_chain_errors__top_concept_error_before_required_concept_error(modules):
    modules.add("Base", mentions=["BaseMissing"]).add("Top", ["Base"], mentions=["TopMissing"])
    assert f"Concept {c('TopMissing')} is not defined" in raises(PlainSyntaxError, modules.parse, "Top")


def test_order_chain_errors__top_concept_error_before_required_shape_error(modules):
    modules.add("Base", functional=False).add("Top", ["Base"], mentions=["TopMissing"])
    assert f"Concept {c('TopMissing')} is not defined" in raises(PlainSyntaxError, modules.parse, "Top")


def test_order_chain_errors__required_modules_top_down(modules):
    modules.add("Base", mentions=["BaseMissing"]).add("Middle", ["Base"], mentions=["MiddleMissing"])
    modules.add("Top", ["Middle"])
    assert f"Concept {c('MiddleMissing')} is not defined" in raises(PlainSyntaxError, modules.parse, "Top")


def test_order_chain_errors__required_module_without_functional_specs(modules):
    modules.add("Base", functional=False).add("Top", ["Base"])
    assert "Module 'Base'" in raises(MissingFunctionalitiesError, modules.parse, "Top")
