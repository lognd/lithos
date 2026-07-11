"""WO-88 (F112): the ConverterGraph execution FFI + its buck consumer.

Covers the whole seam as data:

1. the compiled converter graph crosses the FFI on
   ``BuildPayload.converter_graphs`` (deliverable 2 -- the keystone);
2. every require obligation on an elec behavioral body carries a
   content-addressed ``converter_graph`` ``PayloadRef`` (Rust attach);
3. the orchestrator stores that graph so a discharge-time ``resolve``
   is a hit (deliverable 2);
4. THE acceptance criterion: graph-derived topology reaches a
   ``DischargeRequest`` and the buck model discharges from it, with NO
   hand-supplied topology input duplicating it; and
5. the honest fallbacks -- no graph keeps the hand-supplied path, a
   graph that is not a switching converter is out-of-domain.
"""

from __future__ import annotations

import json
from pathlib import Path

from regolith import compiler
from regolith._schema.models import ConverterGraph, Obligation, PayloadRef
from regolith.harness import DischargeRequest, Interval
from regolith.harness.converter_topology import derive_buck_topology
from regolith.harness.models.buck_ripple import (
    CLAIM_KIND,
    GRAPH_KIND,
    GRAPH_PORT,
    BuckRippleModel,
)
from regolith.orchestrator.orchestrate import _put_converter_graph_payloads
from regolith.orchestrator.payload_store import PayloadStore
from typani.result import Ok

_SAMPLED_BUCK = "examples/tracks/cuprite/sampled_buck.cupr"

# The datasheet operating point (shared with tests/harness/test_buck_ripple.py).
_POINT = {"v_in": 12.0, "v_out": 5.0, "f_sw": 500e3, "l": 22e-6, "c_out": 47e-6}


def _payload() -> dict:
    result = compiler.check([_SAMPLED_BUCK])
    assert result.is_ok, result
    return json.loads(result.danger_ok.payload_json)


def test_graph_crosses_the_ffi_on_the_payload() -> None:
    """Deliverable 1/2: the graph WO-36 builds Rust-side now rides the
    payload -- the premise did NOT dissolve (the payload carried nothing
    before this WO)."""
    graphs = _payload()["converter_graphs"]
    assert "DigitalBuck" in graphs
    graph = ConverterGraph.model_validate(graphs["DigitalBuck"])
    assert graph.nodes, "the behavioral body's graph has nodes"
    topo = derive_buck_topology(graph)
    # The adc-sampled feedback and the pwm-driven switch are both present:
    # the graph structurally confirms a switching converter.
    assert topo.is_switching_converter
    assert topo.switch_nodes and topo.sense_nodes
    assert topo.switch_clock == "ctrl_clk"


def test_require_obligations_carry_the_converter_graph_ref() -> None:
    """The Rust attach: every require obligation on the behavioral body
    carries a content-addressed `converter_graph` PayloadRef; the
    conformance obligations (import/impl) do not."""
    payload = _payload()
    require_names = {"settle", "ripple", "margin", "no_limit_cycle"}
    seen_require = 0
    for raw in payload["obligations"]:
        ob = Obligation.model_validate(raw)
        refs = [r for r in ob.payloads if r.kind == GRAPH_KIND]
        if ob.claim.name in require_names:
            assert refs, f"{ob.claim.name} missing converter_graph ref"
            assert refs[0].origin == "DigitalBuck"
            assert refs[0].digest
            seen_require += 1
        else:
            assert not refs, f"{ob.claim.name} should carry no graph ref"
    assert seen_require >= 1


def test_orchestrator_stores_the_graph_for_resolution(tmp_path: Path) -> None:
    """Deliverable 2: the orchestrator puts the graph under the EXACT
    Rust-computed digest, so a discharge-time resolve is a hit."""
    payload = _payload()
    obligations = tuple(Obligation.model_validate(o) for o in payload["obligations"])
    store = PayloadStore(str(tmp_path))
    _put_converter_graph_payloads(store, payload, obligations)
    ref = next(r for o in obligations for r in o.payloads if r.kind == GRAPH_KIND)
    resolved = store.resolve(ref.digest)
    assert resolved.is_ok, resolved
    graph = ConverterGraph.model_validate_json(resolved.danger_ok)
    assert derive_buck_topology(graph).is_switching_converter


def test_graph_derived_topology_reaches_a_discharge_request() -> None:
    """ACCEPTANCE: graph-derived parameters reach a DischargeRequest and
    the buck model discharges from them, with NO hand-supplied topology
    input duplicating the graph."""
    payload = _payload()
    ref_raw = next(
        r
        for o in payload["obligations"]
        for r in o["payloads"]
        if r["kind"] == GRAPH_KIND
    )
    graph_bytes = json.dumps(payload["converter_graphs"][ref_raw["origin"]]).encode()

    def resolver(digest: str):
        assert digest == ref_raw["digest"]
        return Ok(graph_bytes)

    request = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=0.02,
        inputs={k: Interval.point(v) for k, v in _POINT.items()},
        payloads={
            GRAPH_PORT: PayloadRef(
                kind=GRAPH_KIND, digest=ref_raw["digest"], origin=ref_raw["origin"]
            )
        },
    )
    # No hand-supplied topology input duplicates the graph-derived one.
    assert "domain" not in request.inputs
    assert "topology" not in request.inputs

    prediction = BuckRippleModel().estimate(request, resolver=resolver)
    assert prediction.is_ok, prediction
    assert prediction.danger_ok.in_domain


def test_no_graph_keeps_the_hand_supplied_fallback() -> None:
    """A buck design with no behavioral body (no graph) still discharges
    from hand-supplied inputs -- the fallback the WO preserves."""
    request = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=0.02,
        inputs={k: Interval.point(v) for k, v in _POINT.items()},
    )
    assert BuckRippleModel().estimate(request).is_ok


def test_non_switching_graph_is_out_of_domain() -> None:
    """A resolvable graph that is NOT a switching converter is an honest
    out-of-domain result, never a silent pass on a wrong topology."""
    graph = ConverterGraph.model_validate(
        {"nodes": [{"name": "a", "domain": "Continuous"}], "edges": []}
    )

    def resolver(_digest: str):
        return Ok(graph.model_dump_json().encode())

    request = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=0.02,
        inputs={k: Interval.point(v) for k, v in _POINT.items()},
        payloads={GRAPH_PORT: PayloadRef(kind=GRAPH_KIND, digest="x", origin="a")},
    )
    assert BuckRippleModel().estimate(request, resolver=resolver).is_err
