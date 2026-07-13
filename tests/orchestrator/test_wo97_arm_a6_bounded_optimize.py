"""WO-97 / D209 coupling END TO END: `arm_a6` UpperArm's bounded
profile-width slot (`UpperArmSection.b = in [24mm, 40mm] minimize`,
`link1.hema`) pinned from a REAL cantilever-deflection margin search --
the deliverable the WO-97 close-out ledger deferred as
`optimizer_evaluator_deferred` (E1: no registered structural model
reached the label-named `mech.deflection(...)` claim; E2: no
result-to-part linkage).

Both are resolved here: the discharge channel is `beam_bending.py`'s
already-registered `mech.beam.cantilever_deflection` model (F126.1: the
coupling recognizes the claim by its call form and drives the model with
the candidate geometry in hand), and E2 is by construction (the coupling
works from the declared part, never an obligation content hash).

All inputs are DECLARED data, cited to source (never fabricated):
- slot bounds + span: the promoted `feature_programs` payload (proving
  the real promotion, not a fixture).
- force 6.87N: `link1.hema`'s `payload_deflection: mech.deflection(...,
  under=6.87N at mill.elbow_bore) < 1.5mm` claim clause (POSE_REACH:
  0.3kg tip payload + ~0.4kg distal self-weight, `arm_a6.cupr` rung 1).
- E = 68.9 GPa: `stdlib/std.materials/records/aluminum.toml` AL6061_T6.
- thickness 20mm: `Blank(UpperArmSection, thickness=20mm)`, same file.

`uav_talon` WingSpar (whose gust reaction is `derived(sf=1.5)` with no
declared scalar load) stays honestly deferred -- exercised by the
infeasible/unresolved arms below via a tightened limit.
"""

from __future__ import annotations

import json

import pytest
from regolith.orchestrator.optimize_sketch import (
    CantileverSlot,
    pin_bounded_slot,
    pinned_slot_program,
    stage_pinned_slot,
)
from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.tiers import BuildTier
from regolith.realizer.mech.interpreter import realize_feature_program

# Declared-data constants, cited to source in the module docstring above.
_FORCE_N = 6.87
_E_PA = 68.9e9
_THICKNESS_M = 0.020
_LIMIT_M = 0.0015  # link1.hema: payload_deflection < 1.5mm


def _upper_arm_slot(limit_m: float = _LIMIT_M) -> CantileverSlot:
    """Resolve the bounded slot from the REAL compiled arm_a6 payload,
    then attach the declared claim/material inputs."""
    report = build(("examples/flagships/arm_a6",), BuildTier.CHECK).danger_ok
    payload = json.loads(report.payload_json)
    for program in payload.get("feature_programs") or []:
        if program.get("part_name") != "UpperArm":
            continue
        for profile, sketch in (program.get("sketches") or {}).items():
            promoted = sketch.get("promoted") if isinstance(sketch, dict) else None
            if not isinstance(promoted, dict):
                continue
            segments = {
                s.get("name"): s.get("length") for s in promoted.get("segments") or []
            }
            bounded = (segments.get("b") or {}).get("bounded")
            span = (segments.get("a") or {}).get("pinned")
            if bounded is None or span is None:
                continue
            return CantileverSlot(
                part_name="UpperArm",
                profile=str(profile),
                segment="b",
                material="AL6061_T6",
                lo_m=float(bounded["lo"]) / 1000.0,
                hi_m=float(bounded["hi"]) / 1000.0,
                length_m=float(span) / 1000.0,
                thickness_m=_THICKNESS_M,
                force_n=_FORCE_N,
                e_pa=_E_PA,
                limit_m=limit_m,
            )
    raise AssertionError("UpperArm bounded slot not found in the arm_a6 payload")


def test_upper_arm_slot_promotes_from_real_source() -> None:
    """The slot inputs come from the genuine compiled payload, not a
    hand fixture: bounds [24mm, 40mm], span 300mm."""
    slot = _upper_arm_slot()
    assert slot.lo_m == pytest.approx(0.024)
    assert slot.hi_m == pytest.approx(0.040)
    assert slot.length_m == pytest.approx(0.300)


def test_upper_arm_slot_pins_from_margin_search(tmp_path) -> None:
    """The D209 coupling pins `UpperArm.UpperArmSection.b` from a real
    deflection-margin search: it converges to the minimal feasible width
    (the 1.5mm limit is slack at every candidate, so the minimizer is the
    lower bound, ~24mm) with a genuine `optimize(...)` LockRow and
    STEP-able realized-geometry evidence."""
    slot = _upper_arm_slot()
    store = PayloadStore(str(tmp_path))
    trace, row = pin_bounded_slot(slot, store)

    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    assert winner.feasible
    assert winner.objective_vector[0] == pytest.approx(0.024, abs=5e-4)
    # The winner carries STEP-able realized geometry back to the store.
    assert winner.evidence_digests and winner.evidence_digests[0].startswith("blake3:")

    assert row.is_ok, row
    assert row.danger_ok.cause.startswith("optimize(")
    assert "trace=blake3:" in row.danger_ok.cause


def test_feasibility_gate_binds_when_limit_tightens(tmp_path) -> None:
    """The search is a REAL constrained optimize, not a rubber stamp: a
    limit between the deflection at the upper and lower bounds makes the
    smallest widths INfeasible, so the winner moves off the lower bound
    to the minimal width that still discharges."""
    slot = _upper_arm_slot(limit_m=2.0e-5)  # 0.02mm: infeasible at 24mm
    store = PayloadStore(str(tmp_path))
    trace, row = pin_bounded_slot(slot, store)

    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    assert winner.feasible
    # Binding constraint: the minimal feasible width sits above the lower
    # bound (deflection ~ 1/b**3 crosses the 0.02mm limit near ~30mm).
    assert winner.objective_vector[0] > 0.026
    assert row.is_ok, row


def test_pinned_slot_ships_a_visible_step_that_differs_from_unpinned() -> None:
    """WO116R-F2: literalizing the winning width (`Bounded -> Pinned`) and
    routing the pinned program through `staged_build`'s override channel
    lands a real native STEP artifact -- exactly where preview/ship read
    part bytes -- and that pinned STEP DIFFERS from an unpinned build
    (a build at any other width), proving the optimizer actually
    determined the shipped geometry, never a fixed stand-in."""
    slot = _upper_arm_slot()
    result = stage_pinned_slot(slot, ("examples/flagships/arm_a6",))

    assert result.is_ok, result
    artifact = result.danger_ok
    assert artifact.subject == "UpperArm.body"
    assert artifact.step_bytes, "pinned slot must ship real STEP bytes"
    assert artifact.step_content_hash
    assert artifact.lock_cause.startswith("optimize(")
    # The winner is the minimal feasible width (~24mm), the pinned value.
    assert artifact.width_m == pytest.approx(0.024, abs=5e-4)

    # Differs from an unpinned build: the SAME part realized at a
    # different width (the upper bound) yields a distinct STEP -- the
    # pin is a real geometric choice, not a constant.
    other = realize_feature_program(pinned_slot_program(slot, slot.hi_m))
    assert other.is_ok, other.danger_err
    assert other.danger_ok.geometry.step_content_hash != artifact.step_content_hash, (
        "pinned STEP must differ from a build at a different width"
    )


def test_unreachable_limit_defers_honestly(tmp_path) -> None:
    """When NO candidate width discharges (a limit below the deflection
    at the stiffest/widest section), the search terminates infeasible and
    yields no pin -- the honest `optimizer_evaluator_deferred` outcome
    (uav_talon WingSpar's fate, surfaced as a real search result rather
    than a fabricated closure)."""
    slot = _upper_arm_slot(limit_m=1.0e-7)  # below deflection at any b
    store = PayloadStore(str(tmp_path))
    trace, row = pin_bounded_slot(slot, store)

    assert trace.termination.value == "infeasible"
    assert row.is_err
