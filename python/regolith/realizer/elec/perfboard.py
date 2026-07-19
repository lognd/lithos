"""Perf-board substrate + jumper/wire assignment realizer (WO-165, AD-47
sec. 5, D268 item 3): the first NEW capability program through the
capability registry (WO-164), and the first real consumer of the
`board_assignment.realized` seam T-0043/WO-163 landed
(`regolith.realizer.elec.board_assignment`).

Scope (WO-165 goal, non-goals): given a netlist already resolved to
per-pin grid-hole placement on a FIXED-GRID perf-board substrate (no
copper etching, no autorouter), assign each net's connections a
straight point-to-point jumper/wire path, hole to hole. Net-crossing/
obstacle-avoidance is explicitly OUT of scope for v1 (the WO's own
non-goals list) -- a straight point-to-point run per net is the honest
v1 posture; this module never claims collision-free routing, only
duplicate-hole detection (see :func:`check_no_shared_holes`).

Input shape note (read before extending): the existing elec chain's
in-process netlist IR is file-path-based (`LayoutRequest.netlist_path`
names a KiCad netlist file for the real-KiCad wrapper to parse) -- there
is no existing in-memory structured netlist/placement type this module
could import and reuse without also reimplementing a KiCad netlist
parser (out of this WO's v1 scope). `PerfboardNetlist` below is
therefore this WO's OWN minimal input IR: a netlist already resolved to
per-pin grid-hole placement (the caller/demo driver does that binding),
mirroring the shape `RealizedBoardAssignment` (WO-163) already expects
on its output side (`ComponentAssignment`/`WireAssignment`).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger
from regolith.realizer.elec.board_assignment import (
    ComponentAssignment,
    RealizedBoardAssignment,
    WireAssignment,
)

_log = get_logger(__name__)

#: The standard perf-board hole pitch: 0.1 in, the near-universal
#: through-hole/perf-board/breadboard grid spacing. Cited as a physical
#: constant (WO-165 deliverable 1: "cite the physical constant, do not
#: invent a number"), never re-derived elsewhere.
# frob:doc docs/modules/py-realizer.md#elec-perfboard
PERFBOARD_HOLE_PITCH_IN = 0.1
# frob:doc docs/modules/py-realizer.md#elec-perfboard
PERFBOARD_HOLE_PITCH_MM = PERFBOARD_HOLE_PITCH_IN * 25.4

#: The `substrate_kind` this module stamps onto every
#: `RealizedBoardAssignment` it produces (`board_assignment.py`'s own
#: `substrate_kind: str` field, free-form per-substrate tag).
# frob:doc docs/modules/py-realizer.md#elec-perfboard
SUBSTRATE_KIND_PERFBOARD = "perfboard"


# frob:doc docs/modules/py-realizer.md#elec-perfboard
class PerfboardSubstrate(BaseModel):
    """A fixed-hole-grid perf-board substrate: `rows` x `cols` holes at
    `hole_pitch_mm` pitch (WO-165 deliverable 1). Board footprint in mm
    is `(cols - 1) * hole_pitch_mm` by `(rows - 1) * hole_pitch_mm`
    (the holes ARE the grid; there is no additional edge margin
    modeled in v1 -- an honest simplification, not a claimed
    manufacturing edge clearance)."""

    model_config = ConfigDict(frozen=True)

    rows: int = Field(gt=0)
    cols: int = Field(gt=0)
    hole_pitch_mm: float = Field(default=PERFBOARD_HOLE_PITCH_MM, gt=0.0)

    # frob:doc docs/modules/py-realizer.md#elec-perfboard
    def in_bounds(self, row: int, col: int) -> bool:
        """Whether `(row, col)` is a real hole on this substrate."""
        return 0 <= row < self.rows and 0 <= col < self.cols

    # frob:doc docs/modules/py-realizer.md#elec-perfboard
    def board_width_mm(self) -> float:
        """The board's outer width (column span), mm."""
        return (self.cols - 1) * self.hole_pitch_mm

    # frob:doc docs/modules/py-realizer.md#elec-perfboard
    def board_height_mm(self) -> float:
        """The board's outer height (row span), mm."""
        return (self.rows - 1) * self.hole_pitch_mm


# frob:doc docs/modules/py-realizer.md#elec-perfboard
class PerfboardNet(BaseModel):
    """One net's ordered pin-hole placements (already resolved by the
    caller to grid holes, `"<row>,<col>"` strings, matching
    `ComponentAssignment.anchor_hole`'s own format). At least two holes
    are required -- a one-pin "net" needs no jumper."""

    model_config = ConfigDict(frozen=True)

    name: str
    pin_holes: tuple[str, ...] = Field(min_length=2)


# frob:doc docs/modules/py-realizer.md#elec-perfboard
class PerfboardNetlist(BaseModel):
    """This program's input IR (see module docstring's input-shape
    note): a substrate, its already-placed components, and the
    already-placed nets to jumper-assign."""

    model_config = ConfigDict(frozen=True)

    netlist_hash: str
    board_outline_ref: str
    substrate: PerfboardSubstrate
    components: tuple[ComponentAssignment, ...] = ()
    nets: tuple[PerfboardNet, ...] = ()


# frob:doc docs/modules/py-realizer.md#elec-perfboard
class PerfboardAssignmentError(BaseModel):
    """A perf-board assignment failure VALUE (house Result doctrine --
    never a bare exception for this recoverable, caller-facing
    condition)."""

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str


def _parse_hole(hole: str) -> tuple[int, int]:
    """`"<row>,<col>"` -> `(row, col)`; raises `ValueError` on a
    malformed string -- caught at the one call site
    (:func:`assign_jumpers`) and turned into a `PerfboardAssignmentError`
    value, never left as an uncaught exception at the module boundary."""
    row_s, _, col_s = hole.partition(",")
    return int(row_s), int(col_s)


# frob:doc docs/modules/py-realizer.md#elec-perfboard
def manhattan_length_mm(from_hole: str, to_hole: str, pitch_mm: float) -> float:
    """The Manhattan (grid-step) wire length between two holes, mm: a
    real point-to-point jumper on a perf-board follows the grid, never
    a diagonal air-line -- this is the honest v1 length model (WO-165
    deliverable 2: "straight point-to-point per net is an honest v1
    scope")."""
    r1, c1 = _parse_hole(from_hole)
    r2, c2 = _parse_hole(to_hole)
    return (abs(r1 - r2) + abs(c1 - c2)) * pitch_mm


# frob:doc docs/modules/py-realizer.md#elec-perfboard
def assign_jumpers(
    netlist: PerfboardNetlist,
) -> Result[tuple[WireAssignment, ...], PerfboardAssignmentError]:
    """Deterministic v1 jumper assignment: for each net (in netlist
    order), connect its pin holes as an ORDERED chain -- a straight
    point-to-point wire between each consecutive pair, in the net's own
    declared pin order (never re-sorted -- the caller's placement order
    is the net's electrical topology, e.g. a daisy-chained bus).

    No routing-around-obstacles solve (WO-165 non-goal): a chain wire
    may cross another chain wire's straight path on the physical board;
    this is NOT detected or resolved here (an honest, named deferral --
    see the module docstring and :func:`check_no_shared_holes`, which
    covers the one collision class v1 DOES check: two different
    assignments claiming the identical hole as an endpoint).

    Refuses (an `Err`) if any pin hole falls outside the substrate
    grid, or if a hole string is malformed -- both are input-data bugs,
    not partial-success conditions, so the whole assignment refuses
    rather than silently dropping the bad net.
    """
    wires: list[WireAssignment] = []
    for net in netlist.nets:
        try:
            holes = [_parse_hole(h) for h in net.pin_holes]
        except ValueError:
            _log.error(
                "perfboard: net %r has a malformed hole string in %r",
                net.name,
                net.pin_holes,
            )
            return Err(
                PerfboardAssignmentError(
                    kind="malformed_hole",
                    message=f"net {net.name!r} has a malformed hole string",
                )
            )
        for row, col in holes:
            if not netlist.substrate.in_bounds(row, col):
                _log.error(
                    "perfboard: net %r hole (%d,%d) is off the %dx%d substrate grid",
                    net.name,
                    row,
                    col,
                    netlist.substrate.rows,
                    netlist.substrate.cols,
                )
                return Err(
                    PerfboardAssignmentError(
                        kind="hole_out_of_bounds",
                        message=(
                            f"net {net.name!r} hole ({row},{col}) is outside "
                            f"the {netlist.substrate.rows}x{netlist.substrate.cols} "
                            "substrate grid"
                        ),
                    )
                )
        for from_hole, to_hole in zip(net.pin_holes, net.pin_holes[1:], strict=False):
            length_mm = manhattan_length_mm(
                from_hole, to_hole, netlist.substrate.hole_pitch_mm
            )
            wires.append(
                WireAssignment(
                    net=net.name,
                    from_hole=from_hole,
                    to_hole=to_hole,
                    length_mm=length_mm,
                )
            )
    covered = {w.net for w in wires}
    expected = {net.name for net in netlist.nets}
    if covered != expected:
        missing = expected - covered
        _log.error("perfboard: net(s) left unassigned: %s", sorted(missing))
        return Err(
            PerfboardAssignmentError(
                kind="incomplete_assignment",
                message=f"net(s) left unassigned: {sorted(missing)}",
            )
        )
    _log.info(
        "perfboard: assigned %d wire(s) across %d net(s)", len(wires), len(covered)
    )
    return Ok(tuple(wires))


# frob:doc docs/modules/py-realizer.md#elec-perfboard
def check_no_shared_holes(
    assignment: RealizedBoardAssignment,
) -> Result[None, PerfboardAssignmentError]:
    """The one REAL DFM check WO-165 deliverable 5 requires land with
    this capability (WO-170 owns the rest of the perf-board-assembly
    process-record population; this check does not wait on it): no two
    components claim the same anchor hole, and no two DIFFERENT nets'
    wires meet at a hole that is NOT a component anchor.

    A wire terminating at a component's own anchor hole is normal (that
    IS how a jumper connects to a part's pin, regardless of which net
    "owns" the component); the physical short this check guards
    against is two BARE jumper ends (no component there to solder to)
    from different nets forced into the same empty hole.
    """
    anchor_owner: dict[str, str] = {}
    for comp in assignment.components:
        prior = anchor_owner.get(comp.anchor_hole)
        if prior is not None:
            _log.error(
                "perfboard DFM: hole %s claimed by both %r and %r",
                comp.anchor_hole,
                prior,
                comp.reference,
            )
            return Err(
                PerfboardAssignmentError(
                    kind="duplicate_hole",
                    message=(
                        f"hole {comp.anchor_hole} claimed by both component "
                        f"{prior!r} and {comp.reference!r}"
                    ),
                )
            )
        anchor_owner[comp.anchor_hole] = comp.reference

    bare_hole_net: dict[str, str] = {}
    for wire in assignment.wires:
        for hole in (wire.from_hole, wire.to_hole):
            if hole in anchor_owner:
                continue  # a component pin -- shared jumper termination is normal
            prior = bare_hole_net.get(hole)
            if prior is not None and prior != wire.net:
                _log.error(
                    "perfboard DFM: bare hole %s claimed by both net %r and net %r",
                    hole,
                    prior,
                    wire.net,
                )
                return Err(
                    PerfboardAssignmentError(
                        kind="duplicate_hole",
                        message=(
                            f"bare hole {hole} claimed by both net {prior!r} "
                            f"and net {wire.net!r}"
                        ),
                    )
                )
            bare_hole_net[hole] = wire.net
    _log.info(
        "perfboard DFM: no shared holes across %d component(s), %d bare jumper hole(s)",
        len(anchor_owner),
        len(bare_hole_net),
    )
    return Ok(None)


# frob:doc docs/modules/py-realizer.md#elec-perfboard
def realize_perfboard(
    netlist: PerfboardNetlist,
) -> Result[RealizedBoardAssignment, PerfboardAssignmentError]:
    """The full v1 perf-board realize step: assign jumpers, run the
    duplicate-hole DFM check, and package the result as a
    `RealizedBoardAssignment` (`substrate_kind="perfboard"`) -- the
    `board_assignment.realized` payload this WO's capability
    registration and demo both consume."""
    wires_result = assign_jumpers(netlist)
    if wires_result.is_err:
        return Err(wires_result.danger_err)
    assignment = RealizedBoardAssignment(
        netlist_hash=netlist.netlist_hash,
        board_outline_ref=netlist.board_outline_ref,
        substrate_kind=SUBSTRATE_KIND_PERFBOARD,
        components=netlist.components,
        wires=wires_result.danger_ok,
    )
    dfm_result = check_no_shared_holes(assignment)
    if dfm_result.is_err:
        return Err(dfm_result.danger_err)
    return Ok(assignment)
