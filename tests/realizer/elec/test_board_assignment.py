"""WO-163's `board_assignment.realized` put seam: a board-shaped, non-
copper realized kind for substrate-and-assignment capabilities other
than an etched-copper KiCad board (perf-board today, WO-165).

Mirrors `test_kicad_real.py`'s
`test_real_layout_round_trips_through_realized_layout_store` shape but
never depends on real KiCad tooling -- `RealizedBoardAssignment` has no
`.kicad_pcb`/copper concept to fake.
"""

from __future__ import annotations

from pathlib import Path

from regolith.orchestrator.payload_store import PayloadStore
from regolith.realizer.elec.board_assignment import (
    BOARD_ASSIGNMENT_DOMAIN_TAG,
    ComponentAssignment,
    RealizedBoardAssignment,
    WireAssignment,
    put_realized_board_assignment,
)


def test_domain_tag_is_distinct_from_layout_and_geometry() -> None:
    """The A7 fix: a board-shaped kind that is NOT `layout.realized`."""
    assert BOARD_ASSIGNMENT_DOMAIN_TAG == "board_assignment.realized"


# frob:tests python/regolith/realizer/elec/board_assignment.py::put_realized_board_assignment kind="unit"
def test_board_assignment_round_trips_through_the_payload_store(
    tmp_path: Path,
) -> None:
    """Construct -> put -> get by digest -> deserialize (WO-163 acceptance)."""
    assignment = RealizedBoardAssignment(
        netlist_hash="sha256:deadbeef",
        board_outline_ref="mech:test_perfboard_outline",
        substrate_kind="perfboard_2.54mm",
        components=(
            ComponentAssignment(
                reference="U1", footprint="DIP-8", anchor_hole="A1"
            ),
        ),
        wires=(
            WireAssignment(
                net="VCC", from_hole="A1", to_hole="B3", length_mm=12.5
            ),
        ),
    )

    store = PayloadStore(str(tmp_path))
    digest = put_realized_board_assignment(store, assignment)
    resolved = store.resolve(digest)
    assert resolved.is_ok
    assert resolved.danger_ok == assignment.model_dump_json().encode("utf-8")

    # Idempotent: putting the same assignment again yields the same digest.
    assert put_realized_board_assignment(store, assignment) == digest


def test_no_copper_or_kicad_fields_leak_onto_the_non_copper_kind() -> None:
    """A7: unlike `RealizedLayout`, this kind carries no `copper`/
    `kicad_pcb_content_hash` -- both are meaningless for a perf-board
    substrate with no etched copper and no `.kicad_pcb` native file."""
    fields = RealizedBoardAssignment.model_fields
    assert "copper" not in fields
    assert "kicad_pcb_content_hash" not in fields
