"""WO-165's perf-board jumper/wire assignment realizer: the completeness
guarantee (every net assigned exactly once, none left out or duplicated)
and the one real DFM check the capability registration requires.
"""

from __future__ import annotations

from regolith.realizer.elec.board_assignment import ComponentAssignment
from regolith.realizer.elec.perfboard import (
    PERFBOARD_HOLE_PITCH_MM,
    PerfboardAssignmentError,
    PerfboardNet,
    PerfboardNetlist,
    PerfboardSubstrate,
    assign_jumpers,
    check_no_shared_holes,
    manhattan_length_mm,
    realize_perfboard,
)


def _small_netlist() -> PerfboardNetlist:
    """A tiny honest-demo-shaped netlist: an LED + resistor + switch on
    an 8x12-hole substrate, three nets."""
    return PerfboardNetlist(
        netlist_hash="sha256:test",
        board_outline_ref="demo:perfboard_led_blink",
        substrate=PerfboardSubstrate(rows=8, cols=12),
        components=(
            ComponentAssignment(
                reference="LED1", footprint="LED_3mm", anchor_hole="2,2"
            ),
            ComponentAssignment(reference="R1", footprint="R0805", anchor_hole="2,4"),
            ComponentAssignment(reference="SW1", footprint="SW_PTH", anchor_hole="5,2"),
        ),
        nets=(
            PerfboardNet(name="vcc", pin_holes=("0,0", "2,2")),
            PerfboardNet(name="sig", pin_holes=("2,2", "2,4")),
            PerfboardNet(name="gnd", pin_holes=("2,4", "5,2", "7,0")),
        ),
    )


# frob:tests python/regolith/realizer/elec/perfboard.py::assign_jumpers kind="unit"
# frob:waive PERF002 reason="tiny fixture list .count() in a test assertion loop; N<=6"
def test_every_net_is_assigned_exactly_once() -> None:
    """The closest-to-INV completeness guarantee WO-165 acceptance
    names: no net left unassigned, no net assigned twice."""
    netlist = _small_netlist()
    result = assign_jumpers(netlist)
    assert result.is_ok
    wires = result.danger_ok

    covered = [w.net for w in wires]
    expected_nets = {net.name for net in netlist.nets}
    # Every declared net appears at least once...
    assert set(covered) == expected_nets
    # ...and each net's own wire count matches its own pin-chain length
    # exactly (no duplicate re-assignment of the same net's segments).
    for net in netlist.nets:
        assert covered.count(net.name) == len(net.pin_holes) - 1


def test_hole_out_of_bounds_refuses() -> None:
    netlist = PerfboardNetlist(
        netlist_hash="h",
        board_outline_ref="ref",
        substrate=PerfboardSubstrate(rows=2, cols=2),
        nets=(PerfboardNet(name="n", pin_holes=("0,0", "5,5")),),
    )
    result = assign_jumpers(netlist)
    assert result.is_err
    assert isinstance(result.danger_err, PerfboardAssignmentError)
    assert result.danger_err.kind == "hole_out_of_bounds"


# frob:tests python/regolith/realizer/elec/perfboard.py::manhattan_length_mm kind="unit"
def test_manhattan_length_uses_the_cited_standard_pitch() -> None:
    """0.1in (2.54mm) standard perf-board pitch, cited not invented."""
    assert PERFBOARD_HOLE_PITCH_MM == 25.4 * 0.1
    length = manhattan_length_mm("0,0", "1,2", PERFBOARD_HOLE_PITCH_MM)
    assert length == 3 * PERFBOARD_HOLE_PITCH_MM


# frob:tests python/regolith/realizer/elec/perfboard.py::PerfboardSubstrate.in_bounds
def test_substrate_in_bounds() -> None:
    substrate = PerfboardSubstrate(rows=3, cols=4)
    assert substrate.in_bounds(0, 0)
    assert substrate.in_bounds(2, 3)
    assert not substrate.in_bounds(3, 0)
    assert not substrate.in_bounds(0, 4)
    assert not substrate.in_bounds(-1, 0)


def test_board_width_mm() -> None:
    substrate = PerfboardSubstrate(rows=3, cols=5, hole_pitch_mm=2.54)
    assert substrate.board_width_mm() == 4 * 2.54


def test_board_height_mm() -> None:
    substrate = PerfboardSubstrate(rows=3, cols=5, hole_pitch_mm=2.54)
    assert substrate.board_height_mm() == 2 * 2.54


# frob:tests python/regolith/realizer/elec/perfboard.py::realize_perfboard kind="unit"
def test_realize_perfboard_round_trip_is_dfm_clean() -> None:
    netlist = _small_netlist()
    result = realize_perfboard(netlist)
    assert result.is_ok
    assignment = result.danger_ok
    assert assignment.substrate_kind == "perfboard"
    assert check_no_shared_holes(assignment).is_ok


# frob:tests python/regolith/realizer/elec/perfboard.py::check_no_shared_holes
def test_check_no_shared_holes_catches_duplicate_component_anchor() -> None:
    from regolith.realizer.elec.board_assignment import RealizedBoardAssignment

    assignment = RealizedBoardAssignment(
        netlist_hash="h",
        board_outline_ref="ref",
        substrate_kind="perfboard",
        components=(
            ComponentAssignment(reference="U1", footprint="DIP-8", anchor_hole="1,1"),
            ComponentAssignment(reference="U2", footprint="DIP-8", anchor_hole="1,1"),
        ),
    )
    result = check_no_shared_holes(assignment)
    assert result.is_err
    assert result.danger_err.kind == "duplicate_hole"


# frob:tests python/regolith/realizer/elec/perfboard.py::check_no_shared_holes
def test_check_no_shared_holes_catches_bare_hole_collision_across_nets() -> None:
    from regolith.realizer.elec.board_assignment import (
        RealizedBoardAssignment,
        WireAssignment,
    )

    assignment = RealizedBoardAssignment(
        netlist_hash="h",
        board_outline_ref="ref",
        substrate_kind="perfboard",
        wires=(
            WireAssignment(net="a", from_hole="0,0", to_hole="0,1", length_mm=2.54),
            WireAssignment(net="b", from_hole="0,1", to_hole="0,2", length_mm=2.54),
        ),
    )
    # "0,1" is a bare hole (no component there) claimed by both net "a"
    # and net "b" -- a real physical short.
    result = check_no_shared_holes(assignment)
    assert result.is_err
    assert result.danger_err.kind == "duplicate_hole"


def test_check_no_shared_holes_allows_shared_component_anchor() -> None:
    """A wire terminating at a component's own pin is normal; it is not
    the "bare hole" collision this check guards against."""
    from regolith.realizer.elec.board_assignment import (
        RealizedBoardAssignment,
        WireAssignment,
    )

    assignment = RealizedBoardAssignment(
        netlist_hash="h",
        board_outline_ref="ref",
        substrate_kind="perfboard",
        components=(
            ComponentAssignment(reference="U1", footprint="DIP-8", anchor_hole="1,1"),
        ),
        wires=(
            WireAssignment(net="a", from_hole="0,0", to_hole="1,1", length_mm=2.54),
            WireAssignment(net="b", from_hole="1,1", to_hole="2,2", length_mm=2.54),
        ),
    )
    assert check_no_shared_holes(assignment).is_ok
