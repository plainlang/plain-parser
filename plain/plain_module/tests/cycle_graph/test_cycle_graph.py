"""Conformance tests of module cycle_graph."""

import itertools
import random
import sys
import time

from plain_parser.graph import simple_cycles, strongly_connected_components


def _canonical(cycle):
    i = cycle.index(min(cycle))
    return tuple(cycle[i:] + cycle[:i])


def _complete(nodes):
    return {n: [m for m in nodes if m != n] for n in nodes}


# find-strongly-connected-components


def test_find_strongly_connected_components__components_of_mixed_graph():
    graph = {"a": ["b"], "b": ["a", "c"], "c": ["d"], "d": ["c"], "e": []}
    components = strongly_connected_components(graph)
    assert sorted(map(frozenset, components), key=sorted) == sorted(
        [frozenset("ab"), frozenset("cd"), frozenset("e")], key=sorted
    )


def test_find_strongly_connected_components__successor_only_node_is_a_component():
    components = strongly_connected_components({"a": ["b"]})
    assert sorted(map(frozenset, components), key=sorted) == [frozenset("a"), frozenset("b")]


def test_find_strongly_connected_components__long_chain():
    n = 2 * sys.getrecursionlimit()
    graph = {i: [i + 1] for i in range(n)}
    assert len(strongly_connected_components(graph)) == n + 1


# list-simple-cycles


def test_list_simple_cycles__graph_without_cycles():
    assert list(simple_cycles({"a": ["b"], "b": ["c"], "c": []})) == []


def test_list_simple_cycles__empty_graph():
    assert list(simple_cycles({})) == []


def test_list_simple_cycles__self_loop():
    assert list(simple_cycles({"a": ["a"]})) == [["a"]]


def test_list_simple_cycles__two_node_cycle():
    cycles = list(simple_cycles({"a": ["b"], "b": ["a"]}))
    assert len(cycles) == 1
    assert sorted(cycles[0]) == ["a", "b"]


def test_list_simple_cycles__successor_only_node_is_tolerated():
    cycles = list(simple_cycles({"a": ["b", "ghost"], "b": ["a"]}))
    assert len(cycles) == 1
    assert sorted(cycles[0]) == ["a", "b"]


def test_list_simple_cycles__complete_graph_on_three_nodes():
    assert len(list(simple_cycles(_complete("abc")))) == 5


def test_list_simple_cycles__complete_graph_on_four_nodes():
    assert len(list(simple_cycles(_complete("abcd")))) == 20


def test_list_simple_cycles__separate_cycles():
    graph = {"a": ["b"], "b": ["a"], "x": ["y"], "y": ["x"], "lone": []}
    cycles = list(simple_cycles(graph))
    assert sorted(sorted(c) for c in cycles) == [["a", "b"], ["x", "y"]]


def test_list_simple_cycles__edge_order():
    graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
    cycles = list(simple_cycles(graph))
    assert len(cycles) == 1
    cycle = cycles[0]
    for i, node in enumerate(cycle):
        assert cycle[(i + 1) % len(cycle)] in graph[node]


def test_list_simple_cycles__repeated_edge():
    assert list(simple_cycles({"a": ["b", "b"], "b": ["a", "a"]})) == [["a", "b"]]


def test_list_simple_cycles__separate_cycles_in_node_order():
    graph = {}
    for p in "pqrst":
        graph[p + "0"] = [p + "1"]
        graph[p + "1"] = [p + "0"]
    cycles = list(simple_cycles(graph))
    assert [c[0][0] for c in cycles] == list("pqrst")


def _brute_force(graph, n):
    found = set()
    for size in range(1, n + 1):
        for perm in itertools.permutations(range(n), size):
            if all(perm[(i + 1) % size] in graph[perm[i]] for i in range(size)):
                found.add(_canonical(list(perm)))
    return found


def test_list_simple_cycles__matches_brute_force():
    rng = random.Random(1234)
    for _ in range(200):
        n = rng.randint(1, 6)
        graph = {i: [j for j in range(n) if rng.random() < 0.4] for i in range(n)}
        cycles = list(simple_cycles(graph))
        canon = [_canonical(c) for c in cycles]
        assert len(canon) == len(set(canon))
        assert set(canon) == _brute_force(graph, n)
        firsts = [min(c) for c in cycles if len(c) >= 2]
        assert firsts == sorted(firsts)


# limit-cycle-search


def test_limit_cycle_search__limit_stops_the_search():
    graph = _complete("abcd")
    assert len(list(simple_cycles(graph, limit=10))) == 10
    assert list(simple_cycles(graph, limit=0)) == []


def test_limit_cycle_search__limit_is_lazy():
    graph = _complete(list(range(14)))
    started = time.monotonic()
    assert len(list(simple_cycles(graph, limit=11))) == 11
    assert time.monotonic() - started < 10


def test_limit_cycle_search__acyclic_appendage_is_not_searched():
    graph = {"a": ["b", "d0"], "b": ["a"]}
    for i in range(40):
        graph[f"d{i}"] = [f"l{i}", f"r{i}"]
        graph[f"l{i}"] = [f"d{i + 1}"]
        graph[f"r{i}"] = [f"d{i + 1}"]
    graph["d40"] = []
    cycles = list(simple_cycles(graph))
    assert len(cycles) == 1
    assert sorted(cycles[0]) == ["a", "b"]


def test_limit_cycle_search__cycle_longer_than_the_recursion_limit():
    n = 2 * sys.getrecursionlimit()
    graph = {i: [(i + 1) % n] for i in range(n)}
    cycles = list(simple_cycles(graph))
    assert len(cycles) == 1
    assert len(cycles[0]) == n
