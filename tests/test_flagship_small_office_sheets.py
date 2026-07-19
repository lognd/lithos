"""WO-65 (D218.2) fleet proof: the small_office member schedule renders
the section-search WINNER for its two `section: in registry(std.civil.
w_shape)` girders (G2_AB, GR_AB) instead of the `free` placeholder.

Unlike `test_flagship_timber_pavilion_sheets.py`, which drives
`civil_plan_section` over `compiler.check(...)`'s RAW payload (where a
`free` member still reads `unresolved`), this test drives the FULL
`staged_build` -> `derive_producer_inputs` chain: the section search
runs at discharge, pins each winner with an `optimize(mass_per_length,
trace=...)` lock row, and `derive_producer_inputs` literalizes that
winner into the FramePayload the civil producer consumes. The schedule
cell is therefore the real pinned section, not a re-run of the search.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.drawings.producers import civil_plan_section
from regolith.backends.ship import derive_producer_inputs
from regolith.orchestrator.lockfile import Lockfile
from regolith.orchestrator.orchestrate import staged_build
from regolith.orchestrator.tiers import BuildTier

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROJECT = _REPO_ROOT / "examples" / "flagships" / "small_office"
_STDLIB = str(_REPO_ROOT / "stdlib")

# The lightest w_shape clearing every DECLARED bound under each girder's
# resolved (tributary) demand: G2_AB (43.2 m2 tributary, span/360
# deflection claim) needs w16x40; GR_AB (lighter roof tributary) clears
# on w8x10. See `frame_resolve.search_free_section`'s honesty ledger.
_EXPECT_WINNERS = {"G2_AB": "w16x40", "GR_AB": "w8x10"}


def _report():
    result = staged_build(
        (str(_PROJECT),), BuildTier.RELEASE, frame_record_paths=(_STDLIB,)
    )
    assert result.is_ok, result
    return result.danger_ok


# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def test_section_search_pins_both_girders_with_optimize_cause() -> None:
    report = _report()
    rows = {r.slot: r for r in report.final.frame_lock_rows}
    for member, key in _EXPECT_WINNERS.items():
        slot = f"Frame.{member}.section"
        assert slot in rows, sorted(rows)
        assert rows[slot].value == f"{member}={key}"
        assert rows[slot].cause.startswith("optimize(mass_per_length, trace=blake3:")


def test_member_schedule_renders_the_pinned_sections() -> None:
    report = _report()
    inputs = derive_producer_inputs(
        report,
        lockfile=Lockfile(tool_version="0.1.0"),
        native=NativeArtifactStore(tempfile.mkdtemp()),
    )
    frame = next(iter(inputs.frames.values()))
    model = civil_plan_section("small_office", frame)
    schedule = model.sheets[0].tables[0]
    assert schedule.title == "Member Schedule"
    id_col = schedule.columns.index("id")
    section_col = schedule.columns.index("section")
    by_id = {row.cells[id_col]: row.cells[section_col] for row in schedule.rows}
    for member, key in _EXPECT_WINNERS.items():
        assert by_id[member] == key, by_id
        assert by_id[member] != "unresolved"
