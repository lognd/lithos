"""The `mfg.manufacturable` envelope-check arithmetics (WO-110
deliverable 1's check half).

Each function is pure (records in, :class:`CamOutcome` out -- the
outcome shape is REUSED from `regolith.harness.models.cam.checks`, the
one home for the excess/eps/indeterminate verdict record, exactly as
the cam family's own four checks use it): a positive ``excess`` (mm) is
a genuine manufacturability violation, zero is a clean pass, and an
``indeterminate`` outcome names what could not be grounded.

The checks are DECLARED-DATA containment/feasibility comparisons only
(charter 39 sec. 4's pad-check bar):

- :func:`check_stock_fit` -- the realized part's bounding-box EXTENTS
  must fit inside the machine's travel extents (a necessary condition
  for any fixturing: travel is position-free, so extents compare, not
  absolute coordinates). Same Aabb vocabulary as `cam.envelope`, but
  over the realized part rather than commanded toolpath positions --
  the two checks are complementary, not duplicates (a part can fit the
  travel while its G-code overruns it, and vice versa).
- :func:`check_tool_fit` -- for every hole feature there must EXIST a
  declared tool that (a) is no larger than the hole (a cutter cannot
  produce a feature smaller than itself -- the min-feature-vs-tool
  floor) and (b) reaches the hole's depth within its stickout (the
  tool-access/depth check; depth-to-diameter adequacy is grounded in
  the DECLARED tooling rather than a bare ratio constant, so the
  threshold is always a cited shop record, never an invented number).

Both checks read only spelled/realized values; ``eps`` is zero
throughout (no model-side estimate term -- the same posture as
`fluid_pressure_drop`'s declared-datum eps).
"""

from __future__ import annotations

from regolith.harness.models.cam.checks import CamOutcome
from regolith.harness.models.cam.records import Aabb, ToolRecord
from regolith.harness.models.dfm.records import DfmFeature
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


def _extent(box: Aabb) -> tuple[float, float, float]:
    """The box's (dx, dy, dz) extents in mm."""
    return (
        box.x_max - box.x_min,
        box.y_max - box.y_min,
        box.z_max - box.z_min,
    )


def check_stock_fit(part_bbox: Aabb, travel: Aabb) -> CamOutcome:
    """Part bounding-box extents vs machine travel extents.

    Axis-order-preserving (no rotation search): the part is compared as
    realized, which is conservative for a shop that would re-orient it
    -- a fit found here is real, and a miss is reported with the axis
    excesses so the D224.3 fix (or a re-orientation) is obvious.
    """
    part = _extent(part_bbox)
    trav = _extent(travel)
    excesses = [p - t for p, t in zip(part, trav, strict=True)]
    worst = max(excesses)
    axes = "xyz"
    detail = ", ".join(
        f"{axes[i]}: part {part[i]:.3f}mm vs travel {trav[i]:.3f}mm"
        for i in range(3)
        if excesses[i] > 0.0
    )
    _log.debug("stock fit: part=%s travel=%s worst_excess=%.3f", part, trav, worst)
    if worst > 0.0:
        return CamOutcome(
            excess=worst,
            note=f"part extents exceed machine travel ({detail})",
        )
    # Report the TRUE (negative) worst excess: a passing part carries
    # its real fit margin into the evidence (the calc-book posture,
    # D221), not a clamped zero.
    return CamOutcome(
        excess=worst,
        note=f"part extents fit machine travel (margin {-worst:.3f}mm)",
    )


def check_tool_fit(
    features: tuple[DfmFeature, ...], tools: tuple[ToolRecord, ...]
) -> CamOutcome:
    """Every hole must be producible by SOME declared tool.

    Per hole, each tool's infeasibility is ``max(tool_dia - hole_dia,
    depth - stickout)`` (mm; both terms must be <= 0 for that tool to
    both fit the hole and reach its bottom); the hole's excess is the
    MINIMUM over tools (the best tool governs -- an exists-quantifier),
    and the part's excess is the MAXIMUM over holes (the worst feature
    governs -- a forall-quantifier). A part with no hole features
    passes vacuously (nothing for a tool to fail on -- stock fit still
    ran); an empty TOOL set is indeterminate, not violated (the caller
    defers naming the missing `[[tool]]` records before ever reaching
    this function -- this guard is the honest in-model backstop).
    """
    if not tools:
        return CamOutcome(
            indeterminate=True,
            note="no [[tool]] records declared; tool fit cannot be grounded",
        )
    if not features:
        return CamOutcome(note="no hole features; tool fit passes vacuously")
    # Track the TRUE worst infeasibility (may be negative: a passing
    # part reports its real margin, not a clamped zero -- the calc-book
    # posture, D221).
    worst = float("-inf")
    worst_note = ""
    unchecked_depth: list[str] = []
    for feat in features:
        best = float("inf")
        best_tool = ""
        for tool in tools:
            terms = [tool.diameter_mm - feat.dia_mm]
            if feat.depth_mm is not None:
                terms.append(feat.depth_mm - tool.stickout_mm)
            infeasibility = max(terms)
            if infeasibility < best:
                best = infeasibility
                best_tool = f"tool_id={tool.tool_id} dia={tool.diameter_mm}mm"
        if feat.depth_mm is None:
            unchecked_depth.append(feat.name)
        if best > worst:
            worst = best
            worst_note = (
                f"hole {feat.name!r} (dia {feat.dia_mm}mm"
                + (f", depth {feat.depth_mm}mm" if feat.depth_mm is not None else "")
                + f") vs best declared tool ({best_tool}): excess {best:.3f}mm"
            )
        _log.debug(
            "tool fit: feature=%s dia=%.3f depth=%s best_excess=%.3f",
            feat.name,
            feat.dia_mm,
            feat.depth_mm,
            best,
        )
    if unchecked_depth:
        # A hole with no resolvable depth cannot ground the reach term;
        # conservative-or-silent (charter D3) forbids passing it
        # silently, so the whole check stays indeterminate NAMING the
        # features (the translate layer's derivation from a spelled
        # blank thickness usually prevents this).
        return CamOutcome(
            indeterminate=True,
            note=(
                "hole(s) with no resolvable depth (spell depth= or a "
                f"blank thickness): {', '.join(sorted(unchecked_depth))}"
            ),
        )
    if worst > 0.0:
        return CamOutcome(excess=worst, note=worst_note)
    return CamOutcome(
        excess=worst,
        note=(
            f"{len(features)} hole feature(s) all tool-feasible "
            f"(tightest margin {-worst:.3f}mm: {worst_note})"
        ),
    )


__all__ = ["check_stock_fit", "check_tool_fit"]
