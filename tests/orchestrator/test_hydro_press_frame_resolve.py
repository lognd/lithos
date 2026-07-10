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
The columns (`Col_L`/`Col_R`) resolve too as of cycle 33: the
`astm_a500_grb` std.civil material record landed (the WO-85 close-out's
recorded stdlib gap), so their HSS section search now pins a real
winner rather than deferring `frame_material_unresolved`.
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
    # Cycle-33: the `astm_a500_grb` std.civil material record landed
    # (stdlib gap closed), so the columns' HSS section search now resolves
    # too -- all four members pin a real winner, not just Head/Base.
    assert set(rows) == {
        "Frame.Head.section",
        "Frame.Base.section",
        "Frame.Col_L.section",
        "Frame.Col_R.section",
    }, rows
    head = rows["Frame.Head.section"]
    assert head.value == "Head=w8x10"
    assert head.cause is not None
    assert head.cause.startswith("optimize(mass_per_length, trace=")
    base = rows["Frame.Base.section"]
    assert base.value.startswith("Base=w")
    assert base.cause is not None
    assert base.cause.startswith("optimize(mass_per_length, trace=")
    for col in ("Frame.Col_L.section", "Frame.Col_R.section"):
        row = rows[col]
        assert row.value.startswith(col.split(".")[1] + "=hss"), row
        assert row.cause is not None
        assert row.cause.startswith("optimize(mass_per_length, trace=")


def test_hydro_press_columns_resolve_now_that_the_material_record_landed() -> None:
    """`Col_L`/`Col_R` resolve a real AXIAL demand since WO-85 (the head
    beam's Moment-transferred end reactions), and cycle-33 landed the
    `astm_a500_grb` std.civil material record that was the last gap -- so
    the columns now pin a real HSS winner instead of deferring. Neither
    the old `frame_load_untargeted` nor the `frame_material_unresolved`
    stdlib-gap deferral remains for this frame's members."""
    report = build(
        ("examples/flagships/hydro_press_h30/frame.calx",),
        BuildTier.BUILD,
        frame_record_paths=_STDLIB,
    ).danger_ok
    reasons = {r.deferral.reason for r in report.results if r.deferral is not None}
    # The load wall and the material-record gap are both closed: no member
    # defers for want of a load path or the A500 grade-B record.
    assert "frame_load_untargeted" not in reasons, reasons
    assert "frame_material_unresolved" not in reasons, reasons
    # Both columns pinned a real HSS winner via section-search optimize.
    cols = {
        row.slot: row
        for row in report.frame_lock_rows
        if row.slot in ("Frame.Col_L.section", "Frame.Col_R.section")
    }
    assert set(cols) == {"Frame.Col_L.section", "Frame.Col_R.section"}, cols
    for row in cols.values():
        assert "=hss" in row.value, row
        assert row.cause is not None and row.cause.startswith("optimize(")
