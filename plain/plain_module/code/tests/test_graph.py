from plain_parser.graph import simple_cycles, strongly_connected_components


def test_scc_order_independent_membership():
    comps = strongly_connected_components({1: [2], 2: [3], 3: [1], 4: [4]})
    assert sorted(map(sorted, comps)) == [[1, 2, 3], [4]]


def test_self_loops_first_then_longer_cycles():
    graph = {"a": ["b"], "b": ["a", "b"], "c": ["c"]}
    assert list(simple_cycles(graph)) == [["b"], ["c"], ["a", "b"]]


def test_cycles_start_at_earliest_node():
    graph = {"x": ["y"], "y": ["z"], "z": ["x"]}
    assert list(simple_cycles(graph)) == [["x", "y", "z"]]


def test_limit_none_yields_all():
    graph = {n: [m for m in "abc" if m != n] for n in "abc"}
    assert len(list(simple_cycles(graph, limit=None))) == 5
    assert len(list(simple_cycles(graph, limit=3))) == 3


def test_negative_limit_yields_nothing():
    assert list(simple_cycles({"a": ["a"]}, limit=-1)) == []
