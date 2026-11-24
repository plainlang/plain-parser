"""Graph search: strongly connected components (Tarjan) and elementary cycles (Johnson).

Both algorithms keep an explicit stack instead of recursing, so the depth of a graph is not bounded by the
Python recursion limit.
"""

import heapq
from collections.abc import Hashable, Iterable, Iterator, Mapping
from typing import TypeVar

Node = TypeVar("Node", bound=Hashable)


def _node_order(graph: Mapping[Node, Iterable[Node]]) -> tuple[list[Node], dict[Node, list[Node]]]:
    """Return the nodes in node order and the deduplicated successor lists of every node."""
    order: list[Node] = []
    successors: dict[Node, list[Node]] = {}
    for node in graph:
        if node not in successors:
            successors[node] = []
            order.append(node)
    for node in list(graph):
        seen: set = set()
        unique: list[Node] = []
        for succ in graph[node]:
            if succ not in seen:
                seen.add(succ)
                unique.append(succ)
            if succ not in successors:
                successors[succ] = []
                order.append(succ)
        successors[node] = unique
    return order, successors


def _tarjan(order: list[Node], successors: Mapping[Node, list[Node]]) -> list[set[Node]]:
    """Tarjan's strongly connected components algorithm, iterative."""
    index_of: dict[Node, int] = {}
    lowlink: dict[Node, int] = {}
    on_stack: set = set()
    stack: list[Node] = []
    components: list[set[Node]] = []
    counter = 0

    for root in order:
        if root in index_of:
            continue
        index_of[root] = lowlink[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        work: list[tuple[Node, Iterator[Node]]] = [(root, iter(successors[root]))]
        while work:
            node, succ_iter = work[-1]
            advanced = False
            for succ in succ_iter:
                if succ not in index_of:
                    index_of[succ] = lowlink[succ] = counter
                    counter += 1
                    stack.append(succ)
                    on_stack.add(succ)
                    work.append((succ, iter(successors[succ])))
                    advanced = True
                    break
                if succ in on_stack:
                    lowlink[node] = min(lowlink[node], index_of[succ])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
            if lowlink[node] == index_of[node]:
                component: set[Node] = set()
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.add(member)
                    if member == node:
                        break
                components.append(component)
    return components


def strongly_connected_components(graph: Mapping[Node, Iterable[Node]]) -> list[set[Node]]:
    """Return the strongly connected components of ``graph`` as a list of node sets."""
    order, successors = _node_order(graph)
    return _tarjan(order, successors)


def _cycles_through(start: Node, successors: Mapping[Node, list[Node]]) -> Iterator[list[Node]]:
    """Johnson's circuit search for the cycles through ``start`` in a strongly connected subgraph."""
    path: list[Node] = [start]
    blocked: set = {start}
    blocked_map: dict[Node, set[Node]] = {}
    closed: list[bool] = [False]
    stack: list[tuple[Node, Iterator[Node]]] = [(start, iter(successors[start]))]

    def unblock(node: Node) -> None:
        pending = [node]
        while pending:
            current = pending.pop()
            if current in blocked:
                blocked.discard(current)
                pending.extend(blocked_map.pop(current, ()))

    while stack:
        node, succ_iter = stack[-1]
        advanced = False
        for succ in succ_iter:
            if succ == start:
                yield path[:]
                closed[-1] = True
            elif succ not in blocked:
                path.append(succ)
                closed.append(False)
                stack.append((succ, iter(successors[succ])))
                blocked.add(succ)
                advanced = True
                break
        if advanced:
            continue
        stack.pop()
        done = path.pop()
        was_closed = closed.pop()
        if was_closed:
            if closed:
                closed[-1] = True
            unblock(done)
        else:
            for succ in successors[done]:
                blocked_map.setdefault(succ, set()).add(done)


def _all_cycles(graph: Mapping[Node, Iterable[Node]]) -> Iterator[list[Node]]:
    order, successors = _node_order(graph)
    position = {node: i for i, node in enumerate(order)}

    for node in order:
        if node in successors[node]:
            yield [node]

    # Successor lists without self-loops, in node order.
    plain = {node: [s for s in successors[node] if s != node] for node in order}

    def components_of(nodes: set) -> list[set]:
        sub_order = [n for n in order if n in nodes]
        sub = {n: [s for s in plain[n] if s in nodes] for n in sub_order}
        return [c for c in _tarjan(sub_order, sub) if len(c) > 1]

    heap: list[tuple[int, int, set]] = []
    tie = 0
    for component in components_of(set(order)):
        heapq.heappush(heap, (min(position[n] for n in component), tie, component))
        tie += 1

    while heap:
        first, _, component = heapq.heappop(heap)
        start = order[first]
        sub = {n: [s for s in plain[n] if s in component] for n in order if n in component}
        yield from _cycles_through(start, sub)
        rest = component - {start}
        for sub_component in components_of(rest):
            heapq.heappush(heap, (min(position[n] for n in sub_component), tie, sub_component))
            tie += 1


def simple_cycles(graph: Mapping[Node, Iterable[Node]], limit: int | None = None) -> Iterator[list[Node]]:
    """Yield every elementary cycle of ``graph`` once, as the list of its nodes in edge order.

    One-node cycles come first in node order; every longer cycle starts at its earliest node in node order, and
    longer cycles come in non-decreasing order of that first node. The search stops after ``limit`` cycles.
    """
    if limit is not None and limit <= 0:
        return
    count = 0
    for cycle in _all_cycles(graph):
        yield cycle
        count += 1
        if limit is not None and count >= limit:
            return
