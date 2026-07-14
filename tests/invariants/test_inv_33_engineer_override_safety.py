"""INV-33 Engineer overrides cannot forge a passing release gate
(docs/spec/regolith/13-invariants.md; AD-40; charter 42 secs. 1, 1a, 8;
D243/D246; WO-129A).

Ledger statement: no override can make the release gate pass a design
whose obligations do not discharge under that override's own values.

This is the SAFETY CORE's central proof: an override literalizes a
bounded-slot value and runs it through the SAME real discharge model
`optimize_sketch`'s D209 search uses (`arm_a6`'s real declared
cantilever-deflection claim, the WO-97/WO-70 fixture this repo already
proves with -- see `tests/orchestrator/test_wo97_arm_a6_bounded_optimize.py`),
never a mock verdict. The enforcing case
(`test_inv_33_violating_override_refuses_release`) asserts the release
gate CANNOT be talked into passing a design an override made fail.
"""

from __future__ import annotations

import json

import pytest
from regolith.orchestrator.optimize_sketch import CantileverSlot
from regolith.orchestrator.orchestrate import build, release_gate
from regolith.orchestrator.override_apply import (
    apply_overrides_to_rows,
    engineer_override_cause,
    engineer_override_lock_row,
    literalize_bounded_slot,
)
from regolith.orchestrator.override_resolve import (
    boundary_violation,
    injectable_targets,
    resolve_target,
)
from regolith.orchestrator.overrides import OverrideEntry, OverrideLedger, parse
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.tiers import BuildTier

# The same declared-data constants
# `tests/orchestrator/test_wo97_arm_a6_bounded_optimize.py` cites to
# source (link1.hema / arm_a6.cupr / aluminum.toml) -- never fabricated.
_FORCE_N = 6.87
_E_PA = 68.9e9
_THICKNESS_M = 0.020
_LIMIT_M = 0.0015  # link1.hema: payload_deflection < 1.5mm


def _upper_arm_slot(limit_m: float = _LIMIT_M) -> CantileverSlot:
    """Resolve the bounded slot from the REAL compiled arm_a6 payload
    (identical fixture logic to the WO-97 test, duplicated here rather
    than imported to keep this invariant test self-contained per
    house convention for `tests/invariants/`)."""
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


# --- the enforcing case: proven both ways ---------------------------------


def test_inv_33_satisfying_override_discharges_and_release_passes(tmp_path) -> None:
    """An engineer override that pins the slot to a value the REAL
    deflection model discharges yields `discharged`, and the release
    gate -- the SAME `release_gate` INV-24 uses -- returns `Ok`."""
    slot = _upper_arm_slot()
    entry = OverrideEntry(
        target=f"{slot.slot_id}",
        value="40mm",  # the upper bound: minimal deflection, easily discharges
        author="logan",
        reason="matches the extrusion we already stock",
    )
    store = PayloadStore(str(tmp_path))
    outcome = literalize_bounded_slot(slot, entry, store)
    assert outcome.is_ok, outcome
    width_m, result = outcome.danger_ok
    assert width_m == pytest.approx(0.040)
    assert result.is_resolved
    assert result.evidence is not None and result.evidence.status.value == "discharged"
    assert release_gate((result,)).is_ok


def test_inv_33_violating_override_refuses_release(tmp_path) -> None:
    """THE enforcing case: an override that pins the slot to a value the
    REAL model finds VIOLATED (a limit tightened below what any candidate
    in range achieves) yields `violated`, and the release gate REFUSES --
    it cannot be talked into passing a design this override made fail."""
    slot = _upper_arm_slot(limit_m=1.0e-7)  # tighter than any in-bound width achieves
    entry = OverrideEntry(
        target=f"{slot.slot_id}",
        value="24mm",  # the lower bound: still cannot meet a 0.1um limit
        author="logan",
        reason="testing the tight-tolerance arm variant",
    )
    store = PayloadStore(str(tmp_path))
    outcome = literalize_bounded_slot(slot, entry, store)
    assert outcome.is_ok, outcome
    _width_m, result = outcome.danger_ok
    assert result.is_violated
    assert result.evidence is not None and result.evidence.status.value == "violated"

    gate = release_gate((result,))
    assert gate.is_err, "the release gate must refuse a violated override result"
    assert gate.danger_err.kind == "release_gate_failed"


def test_inv_33_override_out_of_declared_bound_refused(tmp_path) -> None:
    """An override is a declared INPUT, not a license to defeat the
    slot's own `in [lo, hi]` bound -- a value outside it is refused
    before any discharge call."""
    slot = _upper_arm_slot()
    entry = OverrideEntry(
        target=slot.slot_id,
        value="100mm",  # well outside [24mm, 40mm]
        author="logan",
        reason="out of bound on purpose",
    )
    store = PayloadStore(str(tmp_path))
    outcome = literalize_bounded_slot(slot, entry, store)
    assert outcome.is_err
    assert outcome.danger_err.kind == "override_out_of_bound"


# --- waived claim: neither un-waived nor re-waived -------------------------


def test_inv_33_override_does_not_touch_waiver_matching(tmp_path) -> None:
    """A waiver's match is computed from the obligation's content hash
    alone (`compute_acceptance`); an override never participates in that
    match, so it cannot un-waive a waived claim nor forge a waiver for
    one that has none. Unit-level per the INV-24 test file's own
    convention (`test_inv_24_trust_floor_exceeding_claim_cannot_be_memo_waived`):
    a violated override result with NO waiver ledger entry for it stays
    unaccepted regardless of the override's own author/reason -- the
    override's cause never reaches the acceptance ledger's match logic."""
    from regolith.orchestrator.acceptance import compute_acceptance

    slot = _upper_arm_slot(limit_m=1.0e-7)
    entry = OverrideEntry(
        target=slot.slot_id, value="24mm", author="logan", reason="tight variant"
    )
    store = PayloadStore(str(tmp_path))
    _width_m, result = literalize_bounded_slot(slot, entry, store).danger_ok
    result = result.model_copy(update={"content_hash": "h-not-in-any-ledger"})

    # An empty ledger: the override's presence changes NOTHING about
    # whether this result is accepted (it is not -- no waiver names it).
    outcome = compute_acceptance(
        {"entries": []}, (result,), project_root=".", record_search_paths=()
    )
    assert outcome.accepted_hashes == ()
    assert not release_gate((result,), outcome).is_ok


# --- D246 boundary: refused before resolution -------------------------------


@pytest.mark.parametrize(
    "target",
    [
        "widget.require",
        "widget.Strength.trust",
        "widget.model",
        "widget.sf",
        "widget.scatter_factor",
        "widget.forall",
        "widget.waive",
    ],
)
def test_inv_33_d246_boundary_refuses_claim_vocab_targets(target: str) -> None:
    """A target naming claim semantics or the evidence ladder is refused
    (E1002) BEFORE resolution -- unreachability by construction."""
    assert boundary_violation(target) is not None
    result = resolve_target(target, {"choice_points": {}, "resolutions": []})
    assert result.is_err
    assert result.danger_err.kind == "E1002"


def test_inv_33_d246_boundary_does_not_flag_unrelated_names() -> None:
    """A legitimately-named part/segment is not blocked by a substring
    coincidence (whole-segment matching only)."""
    assert boundary_violation("model_shop.Widget.length") is None
    assert boundary_violation("distrust_sensor.gain") is None


def test_inv_33_unresolvable_target_names_near_matches() -> None:
    """An unresolvable target is a constructive diagnostic (E1003) naming
    the nearest valid paths, never a silent no-op."""
    payload = {
        "choice_points": {"decoder_board.AddressDecodeGlue": {}},
        "resolutions": [{"cause": {"cause": "planner", "ref": "VaneFlat.a.length"}}],
    }
    ok = resolve_target("decoder_board.AddressDecodeGlue", payload)
    assert ok.is_ok

    bad = resolve_target("VaneFlat.a.lenght", payload)  # typo
    assert bad.is_err
    assert bad.danger_err.kind == "E1003"
    assert "VaneFlat.a.length" in bad.danger_err.message


def test_inv_33_injectable_targets_reads_real_surfaces() -> None:
    """`injectable_targets` reads the SAME `choice_points`/`resolutions`
    surfaces a real compiled payload carries (proven against the real
    `ebi_decode.cupr` `by select(...)` fixture)."""
    from regolith import compiler

    result = compiler.compile(("examples/tracks/cuprite/ebi_decode.cupr",))
    assert result.is_ok, result
    payload = json.loads(result.danger_ok.payload_json)
    targets = injectable_targets(payload)
    assert "decoder_board.AddressDecodeGlue" in targets


# --- value-source integration: engineer_override outranks optimize(...) ----


def test_inv_33_override_supersedes_optimize_lock_row() -> None:
    """D243.3: an override's cause OUTRANKS `optimize(...)` for the same
    slot -- the prior row is REPLACED, not blended."""
    from regolith.orchestrator.lockfile import LockRow

    prior = (
        LockRow(
            slot="UpperArm.UpperArmSection.b",
            value="0.024m",
            cause="optimize(declared_objective, trace=blake3:abc)",
        ),
    )
    entry = OverrideEntry(
        target="UpperArm.UpperArmSection.b",
        value="40mm",
        author="logan",
        reason="matches stock",
    )
    rows = apply_overrides_to_rows(prior, (entry,))
    assert len(rows) == 1
    assert rows[0].cause == engineer_override_cause(entry)
    assert rows[0].cause.startswith("engineer_override(")
    assert "optimize(" not in rows[0].cause


def test_inv_33_override_lock_row_appends_when_no_prior_row() -> None:
    """A target with no prior resolution still gets its override row."""
    entry = OverrideEntry(
        target="new.slot", value="5mm", author="logan", reason="fresh injection"
    )
    row = engineer_override_lock_row(entry)
    assert row.slot == "new.slot"
    assert row.cause == "engineer_override(logan, fresh injection)"
    rows = apply_overrides_to_rows((), (entry,))
    assert rows == (row,)


# --- E1001: unexplained override refused ------------------------------------


def test_inv_33_unexplained_override_refused_missing_author() -> None:
    text = '[[override]]\ntarget = "x.y"\nvalue = "1mm"\nreason = "why"\n'
    result = parse(text)
    assert result.is_err
    assert result.danger_err.kind == "E1001"


def test_inv_33_unexplained_override_refused_missing_reason() -> None:
    text = '[[override]]\ntarget = "x.y"\nvalue = "1mm"\nauthor = "logan"\n'
    result = parse(text)
    assert result.is_err
    assert result.danger_err.kind == "E1001"


def test_inv_33_unexplained_override_refused_empty_reason() -> None:
    text = (
        '[[override]]\ntarget = "x.y"\nvalue = "1mm"\nauthor = "logan"\n'
        'reason = "   "\n'
    )
    result = parse(text)
    assert result.is_err
    assert result.danger_err.kind == "E1001"


def test_inv_33_fully_specified_override_round_trips() -> None:
    entry = OverrideEntry(
        target="a.b.c", value="3mm", author="logan", reason="declared reason"
    )
    from regolith.orchestrator.overrides import render

    text = render(OverrideLedger(overrides=(entry,)))
    parsed = parse(text)
    assert parsed.is_ok, parsed
    assert parsed.danger_ok.overrides == (entry,)
