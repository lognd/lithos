"""Buck-family topology derived from a compiled ``ConverterGraph``.

WO-88 deliverable 3 (F112, INV-16): WO-36 builds the continuous/discrete
converter graph for an elec behavioral ``spec:`` body Rust-side and
acyclicity-checks it (INV-16); WO-88 exposes it across the FFI on
``BuildPayload.converter_graphs``. This module is the ONE reader that
turns that graph into the switching-converter topology a buck model
consumes -- the switch (drive) node(s), the sensed feedback node(s), and
the switching clock domain -- so a model derives a design's topology
FROM the compiled graph instead of taking it hand-supplied. Shared by
the buck model family (``harness/models/buck_*.py``); the derivation
lives here, once (NO DUPLICATION).

The graph's own vocabulary carries the topology unambiguously (see
``crates/regolith-sem/src/converter.rs``): a ``Converter`` edge is a ZOH
delta crossing the continuous/discrete boundary, so

- a ``Converter`` edge from a clock domain INTO a continuous node is a
  ``dac``/``pwm`` drive -- its target is a SWITCH node driven by the
  loop; and
- a ``Converter`` edge from a continuous node INTO a clock domain is an
  ``adc``/``comparator`` sample -- its target is a SENSED node.

A design carrying at least one of each is a closed-loop switching
converter (:attr:`BuckTopology.is_switching_converter`): the graph
confirms the buck topology structurally, without the model assuming it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from regolith._schema.models import ConverterGraph

# The ``EdgeKind`` string the Rust ``serde`` enum emits for a converter
# (ZOH-delta) edge; one home for the wire token this module matches on.
_CONVERTER_EDGE = "Converter"


def _clock_name(domain: object) -> str | None:
    """The clock name of a ``Domain`` value, or ``None`` for continuous.

    The Rust ``Domain`` enum crosses as serde's external tagging: the
    bare string ``"Continuous"`` (validated to the ``Domain1`` enum) or
    ``{"Clock": "<name>"}`` (validated to the ``Domain2`` model with a
    ``Clock`` attribute). This reads either shape -- including the raw
    dict, so a caller holding un-validated payload bytes works too --
    without assuming which arrived.
    """
    clock = getattr(domain, "Clock", None)
    if clock is None and isinstance(domain, dict):
        clock = domain.get("Clock")
    return clock if isinstance(clock, str) else None


# frob:doc docs/modules/py-harness.md#converter_topology
class BuckTopology(BaseModel):
    """The switching-converter topology read off a ``ConverterGraph``.

    Every field is derived, never hand-supplied: this is exactly the
    parameter set WO-88 threads from the compiled graph to a buck model
    in place of an assumed ``domain=("buck", ...)`` tag.
    """

    model_config = ConfigDict(frozen=True)

    switch_nodes: tuple[str, ...]
    sense_nodes: tuple[str, ...]
    switch_clock: str | None

    @property
    # frob:doc docs/modules/py-harness.md#converter_topology
    def is_switching_converter(self) -> bool:
        """True iff the graph has both a driven switch and a sensed node.

        A closed-loop switching converter (a buck among them): a
        loop-driven ``pwm``/``dac`` switch node AND an ``adc``/
        ``comparator`` sampled feedback node. The buck model treats this
        as the graph CONFIRMING the topology, never as an assumption.
        """
        return bool(self.switch_nodes) and bool(self.sense_nodes)

    # frob:doc docs/modules/py-harness.md#converter_topology
    def provenance(self) -> str:
        """A one-line, audit-honest description for evidence/logging."""
        return (
            "converter-graph-derived topology "
            f"(switch={list(self.switch_nodes)}, sense={list(self.sense_nodes)}, "
            f"clock={self.switch_clock})"
        )


# frob:doc docs/modules/py-harness.md#converter_topology
def derive_buck_topology(graph: ConverterGraph) -> BuckTopology:
    """Read the buck-family topology off a compiled ``ConverterGraph``.

    Deterministic (nodes/edges are already in the graph's stable order):
    a ``Converter`` edge from a clock domain to a continuous node marks
    the target a switch (drive) node; a ``Converter`` edge from a
    continuous node to a clock domain marks the target a sensed node.
    The switching clock is the (first, source-order) clock domain that
    drives a switch node -- the loop's timebase.
    """
    nodes = graph.nodes
    switch: list[str] = []
    sense: list[str] = []
    switch_clock: str | None = None
    for edge in graph.edges:
        if edge.kind != _CONVERTER_EDGE:
            continue
        src = nodes[edge.from_]
        dst = nodes[edge.to]
        src_clock = _clock_name(src.domain)
        dst_clock = _clock_name(dst.domain)
        if src_clock is not None and dst_clock is None:
            # clock -> continuous: a pwm/dac drive of a switch node.
            if dst.name not in switch:
                switch.append(dst.name)
            if switch_clock is None:
                switch_clock = src_clock
        elif src_clock is None and dst_clock is not None:
            # continuous -> clock: an adc/comparator sample.
            if dst.name not in sense:
                sense.append(dst.name)
    return BuckTopology(
        switch_nodes=tuple(switch),
        sense_nodes=tuple(sense),
        switch_clock=switch_clock,
    )
