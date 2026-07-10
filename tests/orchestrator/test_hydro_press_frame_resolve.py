"""WO-73 acceptance (updated by WO-85, then by the cycle-33
astm_a500_grb record): hydro_press_h30's `frame.calx` section search --
the SECOND real `in registry(std.civil.w_shape)` application (the
first being footbridge G1, WO-65's
`test_footbridge_deflect_flips_to_a_real_discharged_verdict`). Runs
the real corpus file (not a synthetic fixture) through
`orchestrator.orchestrate.build`, proving every free section resolves
to a real winner with `cause=optimize(...)` and a persisted trace.

WO-85/D194 closed the WO-73 ledger's wall W4: a direct `kN/m` line
load lowers (`LoadKind::Line`), so `Base` runs its own search. The
cycle-33 `astm_a500_grb` material record (WO-85 close-out's recorded
stdlib gap) then closed the columns' `frame_material_unresolved`
deferral too: `Col_L`/`Col_R` resolve a real WO-85 axial demand (the
head beam's Moment-transferred end reactions) and pin their own
hss_square winners. What still defers is honest and NARROWER: the
RamPad plate section names no std.civil record
(`frame_section_unresolved`); its bearing-pressure claim reaches the
cycle-33 closed-form model but the site-datum bound stays symbolic
(`unresolved_limit`) until the comparator-literalization follow-up.
"""

from __future__ import annotations

from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.tiers import BuildTier

_STDLIB = ("stdlib",)


def test_hydro_press_every_free_section_flips_to_a_real_verdict() -> None:
    report = build(
        ("examples/flagships/hydro_press_h30/frame.calx",),
        BuildTier.BUILD,
        frame_record_paths=_STDLIB,
    ).danger_ok
    assert report.ok
    rows = {row.slot: row for row in report.frame_lock_rows}
    assert set(rows) == {
        "Frame.Head.section",
        "Frame.Base.section",
        "Frame.Col_L.section",
        "Frame.Col_R.section",
    }, rows
    assert rows["Frame.Head.section"].value == "Head=w8x10"
    assert rows["Frame.Base.section"].value.startswith("Base=w")
    assert rows["Frame.Col_L.section"].value == "Col_L=hss4x4x3_16"
    assert rows["Frame.Col_R.section"].value == "Col_R=hss4x4x3_16"
    for row in rows.values():
        assert row.cause is not None
        assert row.cause.startswith("optimize(mass_per_length, trace=")


def test_hydro_press_remaining_deferrals_are_the_narrow_honest_ones() -> None:
    """Both load walls (W4) and the Grade B material gap are closed;
    what remains must be exactly the named narrow gaps -- never a
    load-path or material deferral, and never a silent pass. Both
    columns pinned a real HSS winner via section-search optimize."""
    report = build(
        ("examples/flagships/hydro_press_h30/frame.calx",),
        BuildTier.BUILD,
        frame_record_paths=_STDLIB,
    ).danger_ok
    reasons = {r.deferral.reason for r in report.results if r.deferral is not None}
    assert "frame_load_untargeted" not in reasons, reasons
    assert "frame_material_unresolved" not in reasons, reasons
    assert "frame_section_unresolved" in reasons, reasons  # RamPad plate
    cols = {
        row.slot: row
        for row in report.frame_lock_rows
        if row.slot in ("Frame.Col_L.section", "Frame.Col_R.section")
    }
    assert set(cols) == {"Frame.Col_L.section", "Frame.Col_R.section"}, cols
    for row in cols.values():
        assert "=hss" in row.value, row
        assert row.cause is not None and row.cause.startswith("optimize(")
