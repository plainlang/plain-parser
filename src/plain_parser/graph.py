"""Cycle search over a directed graph given as a mapping from node to its successors.

Nodes that appear only as successors are treated as having no outgoing edges.

The search is Johnson's algorithm, written from the pseudocode in the paper, with the
strongly connected components found by Tarjan's algorithm as given on Wikipedia.

- D. B. Johnson, "Finding all the elementary circuits of a directed graph",
  SIAM J. Comput. 4(1):77-84, 1975, doi:10.1137/0204007
- R. Tarjan, "Depth-first search and linear graph algorithms",
  SIAM J. Comput. 1(2):146-160, 1972, doi:10.1137/0201010
- https://en.wikipedia.org/wiki/Tarjan%27s_strongly_connected_components_algorithm

Both searches keep their own stack of frames instead of recursing, so the depth of a
tangle is not limited by Python's recursion limit.
"""

from collections import defaultdict
from collections.abc import Hashable, Iterable, Iterator, Mapping
from typing import Optional, TypeVar

Node = TypeVar("Node", bound=Hashable)


def _successors(graph: Mapping[Node, Iterable[Node]]) -> dict[Node, list[Node]]:
    successors = {node: list(targets) for node, targets in graph.items()}
    for targets in list(successors.values()):
        for target in targets:
            successors.setdefault(target, [])
    return successors


def strongly_connected_components(graph: Mapping[Node, Iterable[Node]]) -> list[set[Node]]:
    """Tarjan: one depth-first walk, each node stamped with its visit index and the lowest
    index it can reach; a node whose lowest reachable index is its own closes a component."""
    successors = _successors(graph)
    index: dict[Node, int] = {}
    lowlink: dict[Node, int] = {}
    stack: list[Node] = []
    on_stack: set[Node] = set()
    components: list[set[Node]] = []

    def visit(node: Node) -> tuple[Node, Iterator[Node]]:
        index[node] = lowlink[node] = len(index)
        stack.append(node)
        on_stack.add(node)
        return node, iter(successors[node])

    for root in successors:
        if root in index:
            continue
        frames = [visit(root)]
        while frames:
            node, targets = frames[-1]
            for target in targets:
                if target not in index:
                    frames.append(visit(target))
                    break
                if target in on_stack:
                    lowlink[node] = min(lowlink[node], index[target])
            else:
                frames.pop()
                if frames:
                    parent = frames[-1][0]
                    lowlink[parent] = min(lowlink[parent], lowlink[node])
                if lowlink[node] == index[node]:
                    component: set[Node] = set()
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        component.add(member)
                        if member == node:
                            break
                    components.append(component)
    return components


def _cycles_through(adjacency: dict[Node, list[Node]], s: Node) -> Iterator[list[Node]]:
    """Johnson's CIRCUIT: every elementary cycle through `s` in one strongly connected component.

    A node is blocked while it is on the path, and stays blocked after backtracking until a
    cycle is found through some node it was waiting on."""
    blocked: set[Node] = set()
    blocked_map: dict[Node, set[Node]] = defaultdict(set)

    def unblock(node: Node) -> None:
        pending = [node]
        while pending:
            current = pending.pop()
            blocked.discard(current)
            pending.extend(waiting for waiting in blocked_map.pop(current, ()) if waiting in blocked)

    path = [s]
    blocked.add(s)
    frames = [iter(adjacency[s])]
    found_below = [False]
    while frames:
        node = path[-1]
        for target in frames[-1]:
            if target == s:
                yield list(path)
                found_below[-1] = True
            elif target not in blocked:
                path.append(target)
                blocked.add(target)
                frames.append(iter(adjacency[target]))
                found_below.append(False)
                break
        else:
            frames.pop()
            path.pop()
            if found_below.pop():
                unblock(node)
                if found_below:
                    found_below[-1] = True
            else:
                for target in adjacency[node]:
                    blocked_map[target].add(node)


def _all_cycles(graph: Mapping[Node, Iterable[Node]]) -> Iterator[list[Node]]:
    """Johnson's main loop: every cycle lies inside one strongly connected component, and
    every cycle inside a component either passes through its least node or survives that
    node's removal. So search each component from its least node, drop the node, and split
    what is left into components again."""
    successors = _successors(graph)
    for node, targets in successors.items():
        if node in targets:
            yield [node]
    successors = {node: [t for t in targets if t != node] for node, targets in successors.items()}
    position = {node: i for i, node in enumerate(successors)}

    components = [c for c in strongly_connected_components(successors) if len(c) >= 2]
    while components:
        component = components.pop()
        s = min(component, key=position.__getitem__)
        adjacency = {n: [t for t in successors[n] if t in component] for n in component}
        yield from _cycles_through(adjacency, s)
        del adjacency[s]
        for targets in adjacency.values():
            if s in targets:
                targets.remove(s)
        components.extend(c for c in strongly_connected_components(adjacency) if len(c) >= 2)


def simple_cycles(graph: Mapping[Node, Iterable[Node]], limit: Optional[int] = None) -> Iterator[list[Node]]:
    """Yield the elementary cycles of `graph`, each as its nodes in edge order, stopping
    after `limit` cycles when one is given."""
    for found, cycle in enumerate(_all_cycles(graph), start=1):
        if limit is not None and found > limit:
            return
        yield cycle
