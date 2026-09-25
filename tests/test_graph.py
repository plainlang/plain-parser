import random
from itertools import permutations

import pytest

from plain_parser import graph


def canonical(cycles) -> set[tuple]:
    """Rotate each cycle to start at its smallest node so equal cycles compare equal."""
    result = set()
    for cycle in cycles:
        start = cycle.index(min(cycle))
        result.add(tuple(cycle[start:] + cycle[:start]))
    return result


def brute_force_cycles(adjacency: dict[int, list[int]]) -> set[tuple]:
    """Try every node subset in every order; keep the ones that close a loop."""
    nodes = sorted(adjacency)
    found = set()
    for length in range(1, len(nodes) + 1):
        for perm in permutations(nodes, length):
            if all(perm[(i + 1) % length] in adjacency[perm[i]] for i in range(length)):
                found.add(perm)
    return canonical(list(c) for c in found)


def test_dag_has_no_cycles():
    assert list(graph.simple_cycles({"a": ["b"], "b": ["c"], "c": []})) == []


def test_empty_graph():
    assert list(graph.simple_cycles({})) == []


def test_self_loop():
    assert list(graph.simple_cycles({"a": ["a"]})) == [["a"]]


def test_two_node_cycle():
    assert canonical(graph.simple_cycles({"a": ["b"], "b": ["a"]})) == {("a", "b")}


def test_targets_only_nodes_are_tolerated():
    assert canonical(graph.simple_cycles({"a": ["b", "ghost"], "b": ["a"]})) == {("a", "b")}


def test_complete_graph_on_three_nodes_has_five_cycles():
    k3 = {n: [m for m in "abc" if m != n] for n in "abc"}
    assert len(list(graph.simple_cycles(k3))) == 5


def test_complete_graph_on_four_nodes_has_twenty_cycles():
    k4 = {n: [m for m in "abcd" if m != n] for n in "abcd"}
    assert len(list(graph.simple_cycles(k4))) == 20


def test_two_separate_cycles_are_both_found():
    g = {"a": ["b"], "b": ["a"], "x": ["y"], "y": ["x"], "lone": []}
    assert canonical(graph.simple_cycles(g)) == {("a", "b"), ("x", "y")}


def test_cycles_are_reported_in_edge_order():
    g = {"a": ["b"], "b": ["c"], "c": ["a"]}
    (cycle,) = list(graph.simple_cycles(g))
    for node, following in zip(cycle, cycle[1:] + cycle[:1]):
        assert following in g[node]


def test_strongly_connected_components():
    g = {"a": ["b"], "b": ["a", "c"], "c": ["d"], "d": ["c"], "e": []}
    components = graph.strongly_connected_components(g)
    assert sorted(sorted(c) for c in components) == [["a", "b"], ["c", "d"], ["e"]]


def test_limit_stops_after_that_many_cycles():
    k4 = {n: [m for m in "abcd" if m != n] for n in "abcd"}
    assert len(list(graph.simple_cycles(k4, limit=10))) == 10
    assert len(list(graph.simple_cycles(k4, limit=0))) == 0


def test_acyclic_appendage_is_never_entered():
    # a 2-cycle with a chain of 40 diamonds hanging off it: exponentially many paths, one cycle
    g = {"a": ["b", "d0"], "b": ["a"]}
    for i in range(40):
        g[f"d{i}"] = [f"l{i}", f"r{i}"]
        g[f"l{i}"] = g[f"r{i}"] = [f"d{i + 1}"]
    g["d40"] = []
    assert canonical(graph.simple_cycles(g)) == {("a", "b")}


@pytest.mark.parametrize("seed", range(200))
def test_matches_brute_force_on_random_graphs(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 6)
    density = rng.choice([0.2, 0.4, 0.7, 1.0])
    adjacency = {u: [v for v in range(n) if rng.random() < density] for u in range(n)}
    assert canonical(graph.simple_cycles(adjacency)) == brute_force_cycles(adjacency)
