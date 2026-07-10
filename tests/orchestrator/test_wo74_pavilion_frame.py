"""WO-74 flagship-5 (`timber_pavilion`, D183): end-to-end demonstration
that the calcite frame chain discharges REAL verdicts over the
declared-rung-1-load post+girder+purlin design, and that the twin
girders G1/G2 (two independently-resolved `in
registry(std.civil.timber_sawn)` member groups) run a real `regolith
optimize`-shaped section search with a disclosed mass tie-breaker
(WO-56 rule) -- the same `orchestrate.build`-over-real-corpus recipe
WO-65 used for `footbridge.calx` (see
`test_footbridge_deflect_flips_to_a_real_discharged_verdict`), pointed
at this flagship instead.

The `std.civil.timber_sawn` family was widened mid-dispatch (WO-74
ledger note, coordinator ack) from 2 to 11 dressed sawn sizes (NDS
Supplement Table 1B); this test runs over the widened, real 11-
candidate domain.
"""

from __future__ import annotations

from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.tiers import BuildTier

_FLAGSHIP = "examples/flagships/timber_pavilion"
_STDLIB = ("stdlib",)


def test_pavilion_frame_checks_clean_and_discharges_strength_and_deflection() -> None:
    """`orchestrate.build` at T1 over the whole flagship: the frame
    elaborates (one frame, `PavilionFrame`), and both landed frame
    claim forms (`civil.utilization`, `mech.deflection`) discharge
    with a real harness verdict over the declared snow/wind loads --
    not merely check-clean, an actual evidenced discharge (INV-21)."""
    report = build(
        (
            f"{_FLAGSHIP}/site.calx",
            f"{_FLAGSHIP}/program.calx",
            f"{_FLAGSHIP}/frame.calx",
        ),
        BuildTier.BUILD,
        frame_record_paths=_STDLIB,
    ).danger_ok
    assert report.ok, report.results

    discharged = [
        r for r in report.results if r.evidence is not None and r.deferral is None
    ]
    # civil.utilization (beam_utilization_interaction) over the
    # NDS strength combination sweep:
    assert any(
        r.evidence.model_id.startswith("beam_utilization_interaction")
        and r.evidence.status.value == "discharged"
        for r in discharged
    ), report.results
    # mech.deflection (beam_simple_span_deflection_udl) over the
    # G1 girder, NDS service combination:
    assert any(
        r.evidence.model_id.startswith("beam_simple_span_deflection_udl")
        and r.evidence.status.value == "discharged"
        for r in discharged
    ), report.results


def test_pavilion_section_search_pins_two_member_groups_with_optimize_cause() -> None:
    """G1 and G2 (twin girders) each independently run the WO-65
    section search over `std.civil.timber_sawn` and each produce a
    `frame_lock_rows` entry whose `cause` is
    `optimize(mass_per_length, trace=blake3:...)` (WO-65's winner-
    provenance rule, INV-21/INV-22) -- the WO-74 "section search on
    >= 2 member groups" requirement, demonstrated over the real
    flagship source rather than a synthetic frame. Posts (`P_A`/
    `P_B`) stay fixed-section (WO-74 ledger wall note 4: a column has
    no resolvable demand in the landed harness, so a search cannot
    even start for it)."""
    report = build(
        (
            f"{_FLAGSHIP}/site.calx",
            f"{_FLAGSHIP}/program.calx",
            f"{_FLAGSHIP}/frame.calx",
        ),
        BuildTier.BUILD,
        frame_record_paths=_STDLIB,
    ).danger_ok
    assert report.ok, report.results

    rows_by_slot = {row.slot: row for row in report.frame_lock_rows}
    searched_slots = {"PavilionFrame.G1.section", "PavilionFrame.G2.section"}
    assert searched_slots <= set(rows_by_slot), rows_by_slot

    for slot in searched_slots:
        row = rows_by_slot[slot]
        assert row.cause.startswith("optimize(mass_per_length, trace=blake3:"), row

    # The widened 11-candidate `timber_sawn` family (WO-74 ledger: was
    # 2 candidates, widened mid-dispatch) -- the winner is whichever
    # dressed sawn size is the LIGHTEST candidate that clears both the
    # declared strength AND deflection bounds under the 3m-bay demand
    # (the disclosed mass tie-breaker, WO-65/WO-56 rule); assert only
    # that a real winner from the real family landed, not a specific
    # size (a toolchain-side registry change should not need a golden
    # bump in this test to stay honest about which size wins).
    for slot in searched_slots:
        winner_value = rows_by_slot[slot].value
        assert winner_value.startswith(f"{slot.split('.')[1]}=sawn_"), winner_value
