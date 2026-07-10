"""WO-73 acceptance (updated by WO-85): hydro_press_h30's `frame.calx`
section search -- the SECOND real `in registry(std.civil.w_shape)`
application (the first being footbridge G1, WO-65's
`test_footbridge_deflect_flips_to_a_real_discharged_verdict`). Runs
the real corpus file (not a synthetic fixture) through
`orchestrator.orchestrate.build`, proving `Head`'s free section
resolves to a real winner with `cause=optimize(...)` and a persisted
trace.

WO-85/D194 closed the WO-73 ledger's wall W4: a direct `kN/m` line
load now lowers (`LoadKind::Line`), and the corpus file declares one
on `Base` (the platen service weight), so `Base` runs its OWN search
and pins its own winner -- the old "Base stays honestly deferred
(frame_load_untargeted)" assertion flipped to a real second lock row.
The columns (`Col_L`/`Col_R`) still defer, now for the NARROWER
honest reason `frame_material_unresolved` (astm_a500_grb has no
std.civil record yet -- a stdlib gap, WO-60/66 territory, not a load
gap: their axial demand resolves since WO-85).
"""

from __future__ import annotations

from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.tiers import BuildTier

_STDLIB = ("stdlib",)


def test_hydro_press_head_and_base_sections_flip_to_real_verdicts() -> None:
    report = build(
        ("examples/flagships/hydro_press_h30/frame.calx",),
        BuildTier.BUILD,
        frame_record_paths=_STDLIB,
    ).danger_ok
    assert report.ok
    rows = {row.slot: row for row in report.frame_lock_rows}
    assert set(rows) == {"Frame.Head.section", "Frame.Base.section"}, rows
    head = rows["Frame.Head.section"]
    assert head.value == "Head=w8x10"
    assert head.cause is not None
    assert head.cause.startswith("optimize(mass_per_length, trace=")
    base = rows["Frame.Base.section"]
    assert base.value.startswith("Base=w")
    assert base.cause is not None
    assert base.cause.startswith("optimize(mass_per_length, trace=")


def test_hydro_press_columns_defer_on_the_missing_material_record() -> None:
    """`Col_L`/`Col_R` resolve a real AXIAL demand since WO-85 (the
    head beam's Moment-transferred end reactions), so the old
    `frame_load_untargeted` deferral is gone -- what remains is the
    NARROWER stdlib gap: `astm_a500_grb` names no std.civil material
    record. The deferral must say so, never silently pin a winner."""
    report = build(
        ("examples/flagships/hydro_press_h30/frame.calx",),
        BuildTier.BUILD,
        frame_record_paths=_STDLIB,
    ).danger_ok
    reasons = {r.deferral.reason for r in report.results if r.deferral is not None}
    assert "frame_material_unresolved" in reasons, reasons
    # The load wall itself is closed: nothing in this frame defers for
    # want of a load path anymore.
    assert "frame_load_untargeted" not in reasons, reasons
