"""WO-110 headline end-to-end (D232.1c): `makeable: manufacturable(
<token>)` claims route through the REAL staged pipeline (lower ->
realize -> re-lower -> translate -> harness discharge) to
`ManufacturableModel` -- a feasible part DISCHARGES at release tier
from build-produced realized geometry, an infeasible one is honestly
VIOLATED, and every gap is a named, golden-visible deferral (D232.1b)."""

from __future__ import annotations

from pathlib import Path

from regolith.harness.models.dfm.models import CLAIM_KIND as _MFG_KIND
from regolith.orchestrator.orchestrate import staged_build
from regolith.orchestrator.tiers import BuildTier

_DATA = Path(__file__).parent / "data"
_FIXTURE = _DATA / "wo110_manufacturable_fixture.hema"
_DEFERRALS = _DATA / "wo110_manufacturable_deferrals.hema"
_RECORDS = str(_DATA)


def _makeable_results(path: Path, tier: BuildTier):  # type: ignore[no-untyped-def]
    import json

    result = staged_build((str(path),), tier, plan_record_paths=(_RECORDS,))
    assert result.is_ok, f"staged_build returned Err: {result}"
    report = result.danger_ok.final
    payload = json.loads(report.payload_json)
    scope = {s["hash"]: s["scope"] for s in payload.get("snapshots", [])}
    makeable_subjects = {
        o["subject_ref"]: scope.get(o["subject_ref"], "?")
        for o in payload.get("obligations", [])
        if (o.get("claim") or {}).get("name") == "makeable"
    }
    out = {}
    for res in report.results:
        part = makeable_subjects.get(res.subject_ref)
        if part is None:
            continue
        is_dfm = (
            res.evidence is not None
            and res.evidence.model_id.startswith("mfg_manufacturable")
        ) or (
            res.deferral is not None
            and (
                res.deferral.reason.startswith("mfg.manufacturable")
                or res.deferral.reason == "dfm_context_unconfigured"
            )
        )
        if is_dfm:
            out[part] = res
    return out, report


def test_feasible_part_discharges_at_release_tier() -> None:
    """The idler-plate shape discharges `mfg.manufacturable` at RELEASE
    (INV-24 totality) -- the D232.1c fixture proof."""
    results, report = _makeable_results(_FIXTURE, BuildTier.RELEASE)
    fit = results["FitPlate"]
    assert fit.deferral is None, fit.deferral
    assert fit.evidence is not None
    assert fit.evidence.status.value == "discharged"
    assert fit.evidence.model_id == "mfg_manufacturable_mill@1"
    assert report.release_ok, "the discharging fixture must gate green"


def test_infeasible_hole_is_honestly_violated() -> None:
    """A 4 mm hole against a 6 mm-only tool table VIOLATES (excess
    2 mm), never a silent pass or an anonymous deferral."""
    results, _ = _makeable_results(_DEFERRALS, BuildTier.BUILD)
    gap = results["ToolGapPlate"]
    assert gap.deferral is None, gap.deferral
    assert gap.evidence is not None
    assert gap.evidence.status.value == "violated"


def test_unspelled_depth_defers_naming_the_parameter() -> None:
    results, _ = _makeable_results(_DEFERRALS, BuildTier.BUILD)
    blind = results["BlindPlate"]
    assert blind.deferral is not None
    assert blind.deferral.reason == f"{_MFG_KIND}_inputs_missing"
    assert "blind.depth" in blind.deferral.detail


def test_ungrounded_family_defers_naming_it() -> None:
    results, _ = _makeable_results(_DEFERRALS, BuildTier.BUILD)
    mold = results["MoldPart"]
    assert mold.deferral is not None
    assert mold.deferral.reason == f"{_MFG_KIND}_ungrounded_process"
    assert "mold" in mold.deferral.detail
