"""std.cam's four post-parse check-mode arithmetics (WO-67 deliverables
3-6): envelope/reach, coarse collision, conservative removal, coverage.

Each function is pure (IR + records in, :class:`CamOutcome` out) so the
harness `Model` wrappers in `models.py` stay thin marshalling, matching
`Model.discharge`'s single shared margin path (`regolith.harness.model`):
a `CamOutcome` maps onto `value`/`eps`/`limit=0.0` (upper-bound sense --
"excess stays at or below zero"), so `value=0, eps=0` is a clean pass,
any positive ``excess`` is a violation, and ``indeterminate`` short-
circuits the model to `Err(DomainError)` before that mapping ever runs
(model.py's discharge path renders an `Err` as indeterminate evidence).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from regolith.harness.models.cam.ir import Move, Toolpath, line_citations
from regolith.harness.models.cam.records import (
    Aabb,
    MachineRecord,
    StockTarget,
    ToolRecord,
)
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


# frob:doc docs/modules/py-harness.md#models-cam
class CamOutcome(BaseModel):
    """One check's verdict: an excess (>0 = violated), or indeterminate."""

    model_config = ConfigDict(frozen=True)

    excess: float = 0.0
    eps: float = 0.0
    indeterminate: bool = False
    citations: tuple[int, ...] = ()
    note: str = ""

    @property
    # frob:doc docs/modules/py-harness.md#models-cam
    def violated(self) -> bool:
        """True iff a real (non-indeterminate) excess was found."""
        return not self.indeterminate and self.excess > 0.0


def _parse_indeterminate(toolpath: Toolpath) -> CamOutcome | None:
    """Shared guard: a plan with parse issues cannot ground ANY later
    check honestly (conservative-or-silent, charter D3)."""
    if toolpath.issues:
        return CamOutcome(
            indeterminate=True,
            citations=tuple(i.line for i in toolpath.issues),
            note=f"plan did not fully parse: {line_citations(toolpath.issues)}",
        )
    return None


# --- cam.envelope ------------------------------------------------------


# frob:doc docs/modules/py-harness.md#models-cam
# frob:waive TEST001 reason="CAM helper, tested transitively via cam model tests"
def check_envelope(
    toolpath: Toolpath, machine: MachineRecord, tool: ToolRecord | None
) -> CamOutcome:
    """Every commanded position must stay within the machine's travel,
    accounting for tool stickout on the Z axis (reach arithmetic).

    Violation names the worst offending line/axis/excess (charter D2);
    ties are broken by line order so the result is deterministic.
    """
    guard = _parse_indeterminate(toolpath)
    if guard is not None:
        return guard

    travel = machine.travel
    stickout = tool.stickout_mm if tool is not None else 0.0
    worst_excess = 0.0
    worst_line: int | None = None
    worst_axis = ""
    for move in toolpath.moves:
        for axis, value, lo, hi in (
            ("X", move.x, travel.x_min, travel.x_max),
            ("Y", move.y, travel.y_min, travel.y_max),
            ("Z", move.z, travel.z_min - stickout, travel.z_max),
        ):
            if value is None:
                continue
            excess = max(0.0, lo - value, value - hi)
            if excess > worst_excess:
                worst_excess = excess
                worst_line = move.line
                worst_axis = axis
    if worst_line is None:
        return CamOutcome(excess=0.0, note="all commanded positions within travel")
    return CamOutcome(
        excess=worst_excess,
        citations=(worst_line,),
        note=(
            f"line {worst_line}: axis {worst_axis} exceeds travel by {worst_excess:g}mm"
        ),
    )


# --- cam.collision_coarse -----------------------------------------------


# frob:doc docs/modules/py-harness.md#models-cam
# frob:waive TEST001 reason="CAM helper, tested transitively via cam model tests"
def check_collision_coarse(toolpath: Toolpath, stock: Aabb) -> CamOutcome:
    """Rapids (G0) must not pass through the uncut-stock AABB below the
    stock's top face -- the classic "rapid plunges into stock" catch.

    Conservative voxel/AABB tier (charter D2): a rapid segment whose
    endpoint lies inside the stock box (and below its top face, so a
    rapid retract/approach above stock is not flagged) is a collision.
    Segment sampling is coarse (endpoints only) -- declared as the
    model's resolution/exclusion in its evidence note.
    """
    guard = _parse_indeterminate(toolpath)
    if guard is not None:
        return guard

    for move in toolpath.moves:
        if move.kind.value != "rapid":
            continue
        if move.x is None or move.y is None or move.z is None:
            continue
        if move.z >= stock.z_max:
            continue  # rapid above stock top face: never a collision
        if stock.contains_point(move.x, move.y, move.z):
            return CamOutcome(
                excess=stock.z_max - move.z,
                citations=(move.line,),
                note=(
                    f"line {move.line}: rapid move to "
                    f"({move.x:g},{move.y:g},{move.z:g}) passes through uncut stock"
                ),
            )
    return CamOutcome(
        excess=0.0, note="no rapid intersects uncut stock (coarse AABB tier)"
    )


# --- cam.removal ---------------------------------------------------------


def _cutting_z_extent(moves: tuple[Move, ...]) -> tuple[float | None, float | None]:
    """The min/max Z any linear/arc (cutting) move reaches."""
    zs = [m.z for m in moves if m.kind.value != "rapid" and m.z is not None]
    if not zs:
        return None, None
    return min(zs), max(zs)


# frob:doc docs/modules/py-harness.md#models-cam
def check_removal(
    toolpath: Toolpath, target: StockTarget, resolution_mm: float
) -> CamOutcome:
    """Conservative voxel stock-removal check vs the target's finished
    envelope: undercut (material left where none is wanted) / overcut
    (part body removed) against ``target.margin_mm``.

    v1's removal simulation is a bounding-envelope approximation (a
    full voxel raster is future depth): the deepest cutting Z reached
    is compared against the target's finished envelope, and the result
    carries ``resolution_mm`` as its declared error term (charter D3).
    Conservative honesty: when ``resolution_mm`` is not strictly less
    than ``target.margin_mm``, the result stays INDETERMINATE rather
    than claiming a pass or fail the resolution cannot support --
    exactly the "thin margin -> finer tier or indeterminate" rule.
    """
    guard = _parse_indeterminate(toolpath)
    if guard is not None:
        return guard

    if resolution_mm >= target.margin_mm:
        return CamOutcome(
            indeterminate=True,
            note=(
                f"voxel resolution {resolution_mm:g}mm is not finer than the "
                f"target margin {target.margin_mm:g}mm: removal claim stays "
                "indeterminate (conservative-honesty rule, charter D3)"
            ),
        )

    min_z, _max_z = _cutting_z_extent(toolpath.moves)
    if min_z is None:
        return CamOutcome(
            indeterminate=True,
            note="plan carries no cutting moves; removal cannot be assessed",
        )

    # `min_z` is the deepest Z any cutting move reached: the primary
    # "was enough material removed" measure against the target floor
    # (`finished.z_min`). `depth_error > 0` means the plan never cut
    # down that far -- material remains (undercut); `depth_error < 0`
    # means the plan cut past the floor -- the part body was removed
    # (overcut/gouge). `max_z` is unused here (v1 cut: no separate
    # top-surface/facing check -- see the close-out ledger).
    finished = target.finished
    depth_error = min_z - finished.z_min
    excess = abs(depth_error)
    if excess <= 0.0:
        return CamOutcome(
            excess=0.0, eps=resolution_mm, note="stock removal within tolerance"
        )
    kind = "undercut" if depth_error > 0 else "overcut"
    return CamOutcome(
        excess=excess,
        eps=resolution_mm,
        note=(
            f"{kind} of {excess:g}mm vs finished floor (resolution {resolution_mm:g}mm)"
        ),
    )


# --- cam.coverage ----------------------------------------------------------


# frob:doc docs/modules/py-harness.md#models-cam
# frob:waive TEST001 reason="CAM helper, tested transitively via cam model tests"
def check_coverage(toolpath: Toolpath, target: StockTarget) -> CamOutcome:
    """Every FeatureProgram-declared feature must be touched by some
    cutting move (charter D2's completeness model)."""
    guard = _parse_indeterminate(toolpath)
    if guard is not None:
        return guard

    cutting = [m for m in toolpath.moves if m.kind.value != "rapid"]
    missing: list[str] = []
    for feature in target.features:
        touched = any(
            m.x is not None
            and m.y is not None
            and m.z is not None
            and feature.touch_zone.contains_point(m.x, m.y, m.z)
            for m in cutting
        )
        if not touched:
            missing.append(feature.name)
    if not missing:
        return CamOutcome(
            excess=0.0, note=f"all {len(target.features)} feature(s) covered"
        )
    return CamOutcome(
        excess=float(len(missing)),
        note=f"missing feature coverage: {', '.join(missing)}",
    )
