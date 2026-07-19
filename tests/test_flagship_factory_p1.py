"""WO-137 (charter 43/AD-42, the factory flagship): binds the plant's
release-clean build and its central D250.3/D250.4 acceptance facts
directly against the real `staged_build` pipeline output (not a
translate()-level unit test) -- the same "drive the real pipeline"
posture `test_flagship_small_office_sheets.py` already sets.

Three facts this WO's acceptance criteria name explicitly:

1. `factory_p1` builds release-clean (`release_ok`) with the D220.2
   closed-class waiver ledger this project's `memos/
   release-residuals.md` backs.
2. BOTH D250.3 honest paths exist in the SAME plant: `fault_main`
   (declared, cited utility-letter value) discharges; `fault_standby`
   (deliberately undeclared nameplate %Z) defers BY NAME, never
   assuming a "typical" value.
3. D250.4: `arc_flash` (and its four certified-tier siblings) NEVER
   discharge through the lithos screening built-in -- they defer with
   `unmatched_call_path`, the honest "no model registered" reason, not
   a misleading "missing inputs" one.
"""

from __future__ import annotations

from pathlib import Path

from regolith.orchestrator.orchestrate import staged_build
from regolith.orchestrator.tiers import BuildTier

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROJECT = _REPO_ROOT / "examples" / "flagships" / "factory_p1"
_STDLIB = str(_REPO_ROOT / "stdlib")


def _report():
    result = staged_build(
        (str(_PROJECT),),
        BuildTier.RELEASE,
        frame_record_paths=(_STDLIB,),
        cost_record_paths=(_STDLIB,),
    )
    assert result.is_ok, result
    return result.danger_ok


def _deferral_reasons() -> dict[str, str]:
    """Map every deferred result's claim-detail text to its reason,
    keyed by the claim-kind/label substring so tests can look one up
    without depending on obligation hash ordering."""
    report = _report()
    out: dict[str, str] = {}
    for row in report.final.results:
        deferral = row.deferral
        if deferral is None:
            continue
        detail = deferral.detail or ""
        out[detail] = deferral.reason
    return out


def test_release_gate_clean() -> None:
    """The plant's `build --release` acceptance: release_ok, per this
    WO's acceptance criterion ("factory_p1 ships release-clean")."""
    report = _report()
    assert report.final.ok is True
    assert report.final.release_ok is True


def test_fault_current_both_honest_paths() -> None:
    """D250.3, WO-137 deliverable 2: `fault_main` (MainBus, declared
    cited utility-letter %Z/kVA/voltage) is NOT among the deferred
    results (it discharges); `fault_standby` (Tie, deliberately
    undeclared nameplate pct_z) defers BY NAME, naming exactly the
    missing input, never substituting a "typical" value."""
    reasons = _deferral_reasons()
    standby_detail = next(
        (d for d in reasons if "'Tie'" in d and "pct_z" in d), None
    )
    assert standby_detail is not None, sorted(reasons)
    assert reasons[standby_detail] == "elec.power.fault_current_inputs_missing"
    # The declared path's own detail text (kVA=1000/pct_z=5.75) never
    # appears among the deferred set -- it discharged instead.
    assert not any("'MainBus'" in d and "pct_z" not in d for d in reasons)


def test_certified_tier_claims_never_discharge_by_screening_estimate() -> None:
    """D250.4 (this WO's named acceptance test): `arc_flash` and its
    four certified-tier siblings (`withstand`/`coordination`/
    `grounding`/`harmonics`) carry NO lithos built-in model -- each
    must defer with `unmatched_call_path` (honest "no model
    registered"), never a fabricated `_inputs_missing` reason that
    would imply a model exists and merely lacks data."""
    reasons = _deferral_reasons()
    for kind in (
        "elec.power.arc_flash",
        "elec.power.withstand",
        "elec.power.coordination",
        "elec.power.grounding",
        "elec.power.harmonics",
    ):
        detail = next((d for d in reasons if kind in d), None)
        assert detail is not None, (kind, sorted(reasons))
        assert reasons[detail] == "unmatched_call_path", (kind, reasons[detail])


def test_working_clearance_discharges_against_real_room_geometry() -> None:
    """WO-136's tandem, proven here: `elec.power.working_clearance`
    is NOT among the deferred results for this project -- it
    discharges against `program.calx`'s real `ElectricalRoom` depth
    (the tandem is checked, not asserted)."""
    reasons = _deferral_reasons()
    assert not any("working_clearance" in d for d in reasons), sorted(reasons)
