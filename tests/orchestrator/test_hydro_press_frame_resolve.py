"""WO-73 acceptance: hydro_press_h30's `frame.calx` section search --
the SECOND real `in registry(std.civil.w_shape)` application (the
first being footbridge G1, WO-65's
`test_footbridge_deflect_flips_to_a_real_discharged_verdict`). Runs
the real corpus file (not a synthetic fixture) through
`orchestrator.orchestrate.build`, proving `Head`'s free section
resolves to a real winner with `cause=optimize(...)` and a persisted
trace.

`Base` stays honestly deferred (`frame_load_untargeted`): the ram
load reaches `Head` via `RamPad`'s `Bearing(tributary=...)` transfer
(footbridge Deck's own idiom -- WO-73 ledger wall W4 explains why a
direct point/line load on a beam has no landed resolution path), but
`Base`'s own reaction is only Moment-transferred through the columns,
which `resolve_tributary_demand` does not walk -- a real, named gap,
not fabricated through.
"""

from __future__ import annotations

from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.tiers import BuildTier

_STDLIB = ("stdlib",)


def test_hydro_press_head_section_flips_to_a_real_discharged_verdict() -> None:
    report = build(
        ("examples/flagships/hydro_press_h30/frame.calx",),
        BuildTier.BUILD,
        frame_record_paths=_STDLIB,
    ).danger_ok
    assert report.ok
    assert len(report.frame_lock_rows) == 1
    row = report.frame_lock_rows[0]
    assert row.slot == "Frame.Head.section"
    assert row.value == "Head=w8x10"
    assert row.cause is not None
    assert row.cause.startswith("optimize(mass_per_length, trace=")


def test_hydro_press_base_section_defers_honestly() -> None:
    """`Base` has no resolvable direct load or tributary transfer
    (its reaction arrives only via the `Moment()` column transfers,
    which `resolve_tributary_demand` does not walk) -- it must defer
    `frame_load_untargeted`, never silently pin a winner."""
    report = build(
        ("examples/flagships/hydro_press_h30/frame.calx",),
        BuildTier.BUILD,
        frame_record_paths=_STDLIB,
    ).danger_ok
    reasons = {r.deferral.reason for r in report.results if r.deferral is not None}
    assert "frame_load_untargeted" in reasons
