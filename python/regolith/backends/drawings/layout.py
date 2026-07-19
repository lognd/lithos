"""Deterministic mechanical layout helper (WO-58 deliverable 3, charter
25 sec. 1 decision 5 / D165 "mechanical, not aesthetic"): layered DAG
placement + orthogonal edge routing + standoff label ladders, ONE home
shared by every payload-derived diagram producer that needs a node/edge
graph laid out on a grid.

No aesthetic search anywhere: node layer/position is a pure function of
the caller-supplied node/edge ORDER (AD-6 -- callers pass sorted names,
so re-running with the same source always gives the same grid), and
overlapping labels are broken by a fixed step ladder, never a solver.
"""

from __future__ import annotations

from dataclasses import dataclass

_GRID_X_MM = 60.0
_GRID_Y_MM = 40.0
_STANDOFF_MM = 6.0


# frob:doc docs/modules/py-backends.md#drawings-layout
@dataclass(frozen=True)
class LayeredLayout:
    """Deterministic node positions (mm, board-local) and axis-aligned
    (orthogonal) edge routes, both keyed by the caller's own identifiers."""

    positions: dict[str, list[float]]
    routes: dict[tuple[str, str], list[list[float]]]


def _layers(
    nodes: tuple[str, ...], edges: tuple[tuple[str, str], ...]
) -> dict[str, int]:
    """Assign each node a layer index by longest-path DAG layering
    (roots -- no incoming edge that isn't a back-edge -- at layer 0).

    Cycle-breaking is deterministic, not incidental: a DFS (visiting
    each node's out-edges in the CALLER's given order) that finds an
    edge back to a node already on its own current recursion stack
    drops that edge FOR LAYERING PURPOSES ONLY (routing below still
    draws every edge the caller passed in) -- an elec net graph derived
    from harness runs carries no acyclicity guarantee the way a real
    dependency DAG would, so this is the "mechanical, not aesthetic"
    reading of layered placement applied to a general graph.
    """
    # Predecessor adjacency: a node's layer is 1 + the deepest predecessor's
    # layer, so a root (no incoming edge) lands at layer 0 -- the natural
    # "sources on the left" reading of a block diagram.
    predecessors: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        if a in predecessors and b in predecessors:
            predecessors[b].append(a)

    layer: dict[str, int] = {}
    on_stack: set[str] = set()

    def visit(node: str) -> int:
        if node in layer:
            return layer[node]
        on_stack.add(node)
        best = 0
        for neighbor in predecessors[node]:
            if neighbor in on_stack:
                continue  # back-edge: dropped for layering only
            best = max(best, visit(neighbor) + 1)
        on_stack.discard(node)
        layer[node] = best
        return best

    for node in nodes:
        visit(node)
    return layer


# frob:doc docs/modules/py-backends.md#drawings-layout
def layered_positions(
    nodes: tuple[str, ...], edges: tuple[tuple[str, str], ...]
) -> LayeredLayout:
    """Deterministic node grid positions plus one orthogonal (3-segment,
    horizontal/vertical/horizontal) route per edge.

    Layer = longest-path depth; in-layer order is the caller's OWN node
    order (source order, AD-6 -- this function never re-sorts). A node
    absent from ``edges`` (no connections) still lands on the grid at
    layer 0, in its given position among that layer's other members.
    """
    layer = _layers(nodes, edges)
    by_layer: dict[int, list[str]] = {}
    for node in nodes:
        by_layer.setdefault(layer[node], []).append(node)

    positions: dict[str, list[float]] = {}
    for depth in sorted(by_layer):
        row = by_layer[depth]
        for i, node in enumerate(row):
            positions[node] = [depth * _GRID_X_MM, i * _GRID_Y_MM]

    routes: dict[tuple[str, str], list[list[float]]] = {}
    for a, b in edges:
        if a not in positions or b not in positions:
            continue
        pa, pb = positions[a], positions[b]
        mid_x = (pa[0] + pb[0]) / 2.0
        routes[(a, b)] = [list(pa), [mid_x, pa[1]], [mid_x, pb[1]], list(pb)]

    return LayeredLayout(positions=positions, routes=routes)


# frob:doc docs/modules/py-backends.md#drawings-layout
def standoff_ladder(
    base_anchor: list[float], index: int, *, step: float = _STANDOFF_MM
) -> list[float]:
    """Offset a label anchor deterministically by ``index`` standoff
    steps below ``base_anchor`` (a "ladder") so repeated labels sharing a
    base point never overlap -- the v1 mechanical de-overlap rule
    (charter 25's drafting-audit "no overlapping annotations" demand),
    never a layout search.
    """
    return [base_anchor[0], base_anchor[1] + index * step]
