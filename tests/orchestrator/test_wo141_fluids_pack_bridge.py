"""WO-141 (D258.4/F159): lithos-side routing for `fluids.mdot`,
`fluids.flow_imbalance`, and multi-path `fluids.dp` onto the feldspar
fluids pack's Hardy-Cross network solver (`feldspar.fluids.network`,
wrapped as `FluidsMdotModel`/`FluidsFlowImbalanceModel`/`FluidsDpModel`
in `feldspar.pack.models` -- a SEPARATE, already-dispatched WO in the
feldspar repo; this test only exercises the lithos-side adapter).

Two test classes:

- Parser/deferral unit tests (`_dp_role`/`_flow_imbalance_role`, and
  the honest-deferral paths with no fluid context/payload store) --
  always run, no pack required.
- Pack-present integration tests (`@pytest.mark.skipif` gated the
  `test_wo110_crit_speed_adapter.py` way) that build a SYNTHETIC
  minimal flownet payload (a `pipe` + `imposer` two/three-edge network
  Hardy-Cross actually solves -- the espresso/hydronics/garden-
  irrigation corpus fixtures all carry edge kinds -- `orifice`,
  `hx_segment`, `edge_params:geom_extract` -- outside this solver
  DIRECTION's declared coverage, so a real end-to-end DISCHARGE, not
  just an honest abstain, needs a fixture built from `pipe`/`imposer`
  edges only) and drive `translate()` + `ModelRegistry.discharge`
  straight through to a genuine `discharged`/`violated` status,
  proving the wire shape (`ClaimTarget.role` conventions, the
  `schema_version` envelope key `RegolithResolverAdapter.resolve`
  checks) is exactly right.

WO-141 residual (named per the WO's own escape clause rather than
silently worked around): none of `thermosiphon.fluo`'s `flow`/`stall`
(`fluids.mdot`) or `hydronics.fluo`'s `balance` (`fluids.flow_
imbalance`) F126.1 waivers convert to a discharge with today's
feldspar pack, because their OWN flownets carry edge kinds
(`orifice`/`hx_segment`) `feldspar.fluids.network`'s Hardy-Cross
direction does not yet cover (`hardy_cross: unsupported feature
edge_kind:...`) -- an honest ABSTAIN (`fluids_mdot_lo@1#abstained`,
never a silent pass), not a routing failure: the routing itself (this
test module) discharges for real once the pack's own solver direction
covers those edge kinds. Handed to WO-144. A SECOND, more serious
residual: `examples/flagships/espresso_machine/steam_service.fluo`
(also `fluids.mdot`-waived) makes feldspar's own
`_hardy_cross_solve` raise an uncaught `KeyError('flow_rate')`
(`feldspar/fluids/network.py:472`, an `imposer` edge whose `values`
apparently lacks the key its OWN `_Edge.__init__` requires) --
a feldspar-side model bug (harness models must return `Result`, never
raise, `regolith.harness.model.Model.discharge`'s whole-repo
contract), out of scope for this lithos-only WO to patch; escalated,
not touched here.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from regolith import compiler
from regolith._schema.models import Obligation
from regolith.harness import default_registry
from regolith.orchestrator.fluid_resolve import load_fluid_context
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.translate import (
    _FLUID_FLOW_IMBALANCE_KIND,
    _FLUID_MDOT_HI_KIND,
    _FLUID_MDOT_LO_KIND,
    _FLUID_NETWORK_PORT,
    _dp_role,
    _flow_imbalance_role,
    translate,
)

_THERMOSIPHON = Path(__file__).parents[2] / (
    "examples/flagships/espresso_machine/thermosiphon.fluo"
)

_PACK_LOADED = _FLUID_MDOT_LO_KIND in default_registry()._by_kind


# ---------------------------------------------------------------------
# Role-string parsing (pure functions, no pack/network needed)
# ---------------------------------------------------------------------


def test_dp_role_strips_arrow_spacing() -> None:
    """`"riser_top -> group_in"` (the claim's own spelling) becomes
    `"riser_top->group_in"` (feldspar `FluidsDpModel`'s `_DP_ROLE_SEP`,
    no surrounding spaces)."""
    assert _dp_role("riser_top -> group_in") == "riser_top->group_in"


def test_dp_role_none_for_single_edge_subject() -> None:
    """A single-edge `fluids.dp(<edge>)` subject (no arrow) has no
    pack multi-path role to attach -- honest `None`, never a guess."""
    assert _dp_role("riser") is None


def test_flow_imbalance_role_sorts_and_joins() -> None:
    """`"[e2, e1, e3]"` becomes `"e1,e2,e3"` (feldspar
    `FluidsFlowImbalanceModel`'s `_FLOW_IMBALANCE_ROLE_SEP`, SORTED)."""
    assert _flow_imbalance_role("[e2, e1, e3]") == "e1,e2,e3"


def test_flow_imbalance_role_none_for_non_list() -> None:
    """A bare (non-bracketed) argument is not the list shape --
    honest `None`."""
    assert _flow_imbalance_role("e1") is None


def test_flow_imbalance_role_none_for_empty_list() -> None:
    assert _flow_imbalance_role("[]") is None


# ---------------------------------------------------------------------
# Honest deferral when no flownet payload/fluid context is available
# (the F126.1-gap posture BEFORE this WO -- still the honest floor
# when the pack or the payload is simply absent).
# ---------------------------------------------------------------------


def _thermosiphon_obligations() -> list[Obligation]:
    result = compiler.check((str(_THERMOSIPHON),))
    assert result.is_ok, f"check({_THERMOSIPHON!r}) returned Err: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    return [Obligation.model_validate(raw) for raw in payload["obligations"]]


def _by_name(name: str) -> Obligation:
    for ob in _thermosiphon_obligations():
        if ob.claim.name == name:
            return ob
    raise AssertionError(f"no obligation named {name!r} in {_THERMOSIPHON}")


def test_mdot_defers_honestly_with_no_fluid_context() -> None:
    """`fluids.mdot(riser) >= ...` with `fluid_context=None` (no
    payload store threaded, e.g. a T0/static-only build) defers named
    -- never a silent pass, never a crash."""
    ob = _by_name("flow")
    result = translate(ob, fluid_context=None)
    assert result.is_err, result
    assert result.danger_err.reason == "fluids_mdot_no_flownet_payload"


def test_mdot_defers_honestly_with_unknown_flownet() -> None:
    """A fluid context that never loaded the named flownet (an empty
    build payload) defers the same way -- honest, never fabricated."""
    ob = _by_name("flow")
    with tempfile.TemporaryDirectory() as tmp:
        store = PayloadStore(tmp)
        fc = load_fluid_context(tmp, build_payload={}, payload_store=store).danger_ok
        result = translate(ob, fluid_context=fc)
    assert result.is_err, result
    assert result.danger_err.reason == "fluids_mdot_no_flownet_payload"


def test_flow_imbalance_defers_on_malformed_edge_list() -> None:
    """A non-list argument to `fluids.flow_imbalance(...)` defers named
    (`fluids_flow_imbalance_edges_unresolved`), independent of pack
    presence."""
    ob = _by_name("flow")
    balance_form = ob.claim.form.model_copy(
        update={"lhs": "fluids.flow_imbalance(e1)", "op": "<", "rhs": "10%"}
    )
    balance_claim = ob.claim.model_copy(
        update={"name": "balance", "form": balance_form}
    )
    balance_ob = ob.model_copy(update={"claim": balance_claim})
    result = translate(balance_ob, fluid_context=None)
    assert result.is_err, result
    assert result.danger_err.reason == "fluids_flow_imbalance_edges_unresolved"


# ---------------------------------------------------------------------
# Pack-present: real end-to-end discharge through a synthetic,
# Hardy-Cross-solvable flownet (pipe + imposer edges only).
# ---------------------------------------------------------------------


def _pipe_edge(
    edge_id: str, a: str, b: str, diameter: float = 0.05
) -> dict[str, object]:
    """One `pipe`-kind `FlowEdge` dict, Hardy-Cross's own supported
    edge kind (`feldspar.fluids.network._Edge.__init__`)."""
    return {
        "id": edge_id,
        "a": a,
        "b": b,
        "kind": "pipe",
        "curves": [],
        "params": {
            "source": "scalars",
            "values": {
                "length": {"lo": 10.0, "hi": 10.0, "unit": "m"},
                "diameter": {"lo": diameter, "hi": diameter, "unit": "m"},
                "density": {"lo": 1000.0, "hi": 1000.0, "unit": "kg/m3"},
                "viscosity": {"lo": 0.001, "hi": 0.001, "unit": "Pa*s"},
                "roughness": {"lo": 0.0, "hi": 0.0, "unit": "m"},
            },
        },
    }


def _imposer_edge(edge_id: str, a: str, b: str, flow_kg_s: float) -> dict[str, object]:
    """One `imposer`-kind `FlowEdge` dict (a fixed, known flow -- the
    OTHER edge kind Hardy-Cross's own solver direction supports)."""
    return {
        "id": edge_id,
        "a": a,
        "b": b,
        "kind": "imposer",
        "curves": [],
        "params": {
            "source": "scalars",
            "values": {"flow_rate": {"lo": flow_kg_s, "hi": flow_kg_s, "unit": "kg/s"}},
        },
    }


def _synthetic_flownet(edges: list[dict[str, object]]) -> dict[str, object]:
    """A minimal, solvable flownet payload dict (`FlownetPayload`'s
    wire shape) -- two nodes, an imposed reference state, no medium
    property records (the pack's Hardy-Cross reads its scalar edge
    params directly, `_scalar_value`, never the medium registry)."""
    return {
        "medium": {"records": []},
        "nodes": ["A", "B"],
        "reference": {
            "node": "A",
            "p": {"lo": 300000.0, "hi": 300000.0, "unit": "Pa"},
            "t": {"lo": 293.0, "hi": 293.0, "unit": "K"},
        },
        "edges": edges,
        "states": [],
    }


def _obligation_like(
    template: Obligation, *, name: str, lhs: str, op: str, rhs: str, flownet_name: str
) -> Obligation:
    """A synthetic obligation with a real (compiled) `Obligation`'s
    exact nested-type shape, `template`'s claim form/name and payload
    origin overridden -- avoids hand-building every required-but-
    irrelevant field of `ClaimForm1`/`Given`/`Obligation` from scratch."""
    form = template.claim.form.model_copy(update={"lhs": lhs, "op": op, "rhs": rhs})
    claim = template.claim.model_copy(update={"name": name, "form": form})
    payloads = [
        p.model_copy(update={"origin": flownet_name}) for p in template.payloads
    ]
    return template.model_copy(update={"claim": claim, "payloads": payloads})


def _fluid_context_for(flownet_name: str, flownet: dict[str, object]):
    """A `(PayloadStore, FluidContext)` pair rooted at a fresh temp
    dir, carrying exactly one named synthetic flownet."""
    project_root = tempfile.mkdtemp()
    store = PayloadStore(project_root)
    fc = load_fluid_context(
        project_root,
        build_payload={"flownets": {flownet_name: flownet}},
        payload_store=store,
    ).danger_ok
    return store, fc


@pytest.mark.skipif(not _PACK_LOADED, reason="feldspar pack not installed")
def test_mdot_discharges_through_the_pack_end_to_end() -> None:
    """A single `pipe` edge fed by a fixed-flow `imposer` (a closed
    two-edge loop) solves for real: `fluids.mdot(e1) <= 0.01` (0.01
    kg/s, comfortably above the ~0 net loop flow) discharges
    `discharged` through `fluids_mdot_hi@1` -- pack attribution
    resolves to `("feldspar", <version>)` (INV-28/AD-19)."""
    template = _by_name("flow")
    flownet = _synthetic_flownet(
        [_pipe_edge("e1", "A", "B"), _imposer_edge("feed", "B", "A", 0.001)]
    )
    store, fc = _fluid_context_for("TestNet", flownet)
    ob = _obligation_like(
        template,
        name="flow",
        lhs="fluids.mdot(e1)",
        op="<=",
        rhs="0.01",
        flownet_name="TestNet",
    )
    result = translate(ob, fluid_context=fc)
    assert result.is_ok, result
    request = result.danger_ok
    assert request.claim_kind == _FLUID_MDOT_HI_KIND
    assert _FLUID_NETWORK_PORT in request.payloads
    registry = default_registry()
    evidence = registry.discharge(request, resolver=store.resolver())
    assert evidence.status.value == "discharged", evidence
    pack_name, pack_version = registry.pack_of(evidence.model_id)
    assert pack_name == "feldspar"
    assert pack_version != ""


@pytest.mark.skipif(not _PACK_LOADED, reason="feldspar pack not installed")
def test_mdot_lo_bound_reports_violated_honestly() -> None:
    """The SAME network's `>= 0.0005` lower-bound half genuinely
    fails at the solved (~0) loop flow -- `violated`, not masked."""
    template = _by_name("flow")
    flownet = _synthetic_flownet(
        [_pipe_edge("e1", "A", "B"), _imposer_edge("feed", "B", "A", 0.001)]
    )
    store, fc = _fluid_context_for("TestNet", flownet)
    ob = _obligation_like(
        template,
        name="flow",
        lhs="fluids.mdot(e1)",
        op=">=",
        rhs="0.0005",
        flownet_name="TestNet",
    )
    result = translate(ob, fluid_context=fc)
    assert result.is_ok, result
    assert result.danger_ok.claim_kind == _FLUID_MDOT_LO_KIND
    evidence = default_registry().discharge(result.danger_ok, resolver=store.resolver())
    assert evidence.status.value == "violated", evidence


@pytest.mark.skipif(not _PACK_LOADED, reason="feldspar pack not installed")
def test_flow_imbalance_discharges_through_the_pack_end_to_end() -> None:
    """Two parallel `pipe` edges (different diameters, so their flows
    genuinely differ) fed by one `imposer` -- `fluids.flow_imbalance(
    [e1, e2]) < 50%` discharges for real through `fluids_flow_
    imbalance@1` (the computed imbalance is ~0.67, so this specific
    claim is honestly `violated` -- still a REAL discharge, never
    `indeterminate`/`no_model`)."""
    template = _by_name("flow")
    flownet = _synthetic_flownet(
        [
            _pipe_edge("e1", "A", "B", diameter=0.05),
            _pipe_edge("e2", "A", "B", diameter=0.03),
            _imposer_edge("feed", "B", "A", 0.01),
        ]
    )
    store, fc = _fluid_context_for("TestNet", flownet)
    ob = _obligation_like(
        template,
        name="balance",
        lhs="fluids.flow_imbalance([e1, e2])",
        op="<",
        rhs="50%",
        flownet_name="TestNet",
    )
    result = translate(ob, fluid_context=fc)
    assert result.is_ok, result
    request = result.danger_ok
    assert request.claim_kind == _FLUID_FLOW_IMBALANCE_KIND
    evidence = default_registry().discharge(request, resolver=store.resolver())
    assert evidence.status.value in ("discharged", "violated")


@pytest.mark.skipif(not _PACK_LOADED, reason="feldspar pack not installed")
def test_multipath_dp_discharges_through_the_pack_end_to_end() -> None:
    """`fluids.dp(A -> B) <= 500000Pa` (a node-pair subject, no
    literal single-segment kwargs -- the closed-form
    `FluidPressureDropModel` never matches this claim shape) routes
    onto the pack's `FluidsDpModel` and discharges for real."""
    template = _by_name("flow")
    flownet = _synthetic_flownet(
        [
            _pipe_edge("e1", "A", "B", diameter=0.05),
            _pipe_edge("e2", "A", "B", diameter=0.03),
            _imposer_edge("feed", "B", "A", 0.01),
        ]
    )
    store, fc = _fluid_context_for("TestNet", flownet)
    ob = _obligation_like(
        template,
        name="margin",
        lhs="fluids.dp(A -> B)",
        op="<=",
        rhs="500000Pa",
        flownet_name="TestNet",
    )
    result = translate(ob, fluid_context=fc)
    assert result.is_ok, result
    request = result.danger_ok
    assert request.claim_kind == "fluids.dp"
    assert _FLUID_NETWORK_PORT in request.payloads
    evidence = default_registry().discharge(request, resolver=store.resolver())
    assert evidence.status.value == "discharged", evidence
    pack_name, _ = default_registry().pack_of(evidence.model_id)
    assert pack_name == "feldspar"


@pytest.mark.skipif(not _PACK_LOADED, reason="feldspar pack not installed")
def test_single_edge_dp_still_prefers_the_closed_form_when_inputs_present() -> None:
    """A single-segment `fluids.dp(<edge>, ...)` claim with LITERAL
    kwargs still discharges through the cheaper closed-form
    `FluidPressureDropModel` (cost order, `ModelRegistry.select`) --
    the pack payload is attached too (this WO's deliverable), but never
    displaces the existing, cheaper single-segment route. Regression
    guard for `_translate_fluid_dp`'s WO-141 extension."""
    ob = _by_name("dp")
    result = translate(ob, fluid_context=None)
    assert result.is_ok, result
    assert result.danger_ok.claim_kind == "fluids.dp"
    evidence = default_registry().discharge(result.danger_ok)
    assert evidence.model_id.startswith("fluid_darcy_weisbach_dp")
