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

WO-169 (process population wave 1: EDM, heat-treat, stamping, grinding,
shot-peen) adds the family-specific checks below, all conforming to the
SAME uniform contract (declared-data in, :class:`CamOutcome` out, a
positive ``excess`` a genuine violation, zero a clean pass). Each check's
own citation/provenance lives in its `DfmCheckEntry.provenance` in
`process_seeds_wave1*.py`, not here (this module states arithmetic only,
per the module docstring above); GEK-tier engineering-consensus
thresholds (e.g. containment margins, clearance-percent bounds) are
passed in as DECLARED parameters, never hard-coded constants, so a
future owner-sourced update only touches the calling record's data.

- :func:`check_wire_edm_corner_radius` / :func:`check_sinker_edm_corner_radius`
  -- kerf/electrode-geometry corner-radius containment (rollup priority
  1: procres/subtractive.md #13/#14).
- :func:`check_wire_edm_start_hole` -- a sequencing predicate (a fully
  enclosed internal profile needs a declared start hole for wire
  threading).
- :func:`check_quench_section_uniformity` -- Q&T's material-state
  distortion/cracking-risk gate (rollup priority 2: procres/
  heat_treatment.md #77).
- :func:`check_process_sequencing` -- the GENERIC state/sequencing
  predicate shared by every heat-treat family member that gates "does
  a declared upstream process/state satisfy this process's
  precondition" (anneal/normalize/case-harden/nitride/induction-harden/
  austemper-martemper/solution-treat-age/stress-relieve all reuse this
  ONE callable rather than each duplicating the same boolean-membership
  arithmetic -- NO DUPLICATION).
- :func:`check_punch_die_clearance` -- punch/die clearance as a percent
  of stock thickness within a declared envelope (rollup priority 3:
  procres/sheet.md #22).
- :func:`check_press_tonnage` -- required vs available press tonnage
  containment (rollup priority 3 companion, procres/sheet.md #22/#24).
- :func:`check_press_brake_bend_radius` -- bend-radius-vs-thickness
  cracking-risk gate (procres/sheet.md #23).
- :func:`check_grinding_stock_allowance` -- post-heat-treat finishing
  stock-removal-window gate (rollup priority 4: procres/subtractive.md
  #7).
- :func:`check_shot_peen_recast_remediation` -- shot-peen-after-EDM
  recast-layer remediation sequencing + compressive-depth gate (rollup
  priority 5: procres/surface.md #92).
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


# frob:doc docs/modules/py-harness.md#models-dfm
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


# frob:doc docs/modules/py-harness.md#models-dfm
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
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


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_wire_edm_corner_radius(
    internal_corner_radius_mm: float, kerf_width_mm: float, spark_gap_mm: float
) -> CamOutcome:
    """Wire EDM internal-corner containment (procres/subtractive.md #13
    DFM rule 2): a wire cannot cut a sharper internal corner than its
    own kerf half-width plus the spark gap it rides in -- the same
    containment-predicate shape as `check_tool_fit`'s cutter-vs-hole
    floor, applied to kerf geometry instead of a tool diameter."""
    required = kerf_width_mm / 2.0 + spark_gap_mm
    excess = required - internal_corner_radius_mm
    _log.debug(
        "wire edm corner radius: declared=%.4f required=%.4f excess=%.4f",
        internal_corner_radius_mm,
        required,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"internal corner radius {internal_corner_radius_mm:.4f}mm is "
                f"below the kerf/2 + spark-gap floor ({required:.4f}mm)"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"internal corner radius {internal_corner_radius_mm:.4f}mm clears "
            f"the kerf/2 + spark-gap floor (margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_wire_edm_start_hole(
    is_fully_enclosed_profile: bool, has_declared_start_hole: bool
) -> CamOutcome:
    """Wire-threading sequencing predicate (procres/subtractive.md #13
    DFM rule 8): a fully enclosed internal profile cannot be wire-EDM'd
    without a pre-drilled start hole for the wire to thread through --
    a boolean sequencing gate, not a numeric containment one, so
    ``excess`` is 1.0 (violated) or 0.0 (satisfied/vacuous)."""
    if is_fully_enclosed_profile and not has_declared_start_hole:
        return CamOutcome(
            excess=1.0,
            note="fully enclosed profile has no declared wire start hole",
        )
    return CamOutcome(
        excess=0.0,
        note=(
            "no start hole required (open profile)"
            if not is_fully_enclosed_profile
            else "start hole declared for the enclosed profile"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_sinker_edm_corner_radius(
    internal_corner_radius_mm: float,
    electrode_corner_radius_mm: float,
    spark_gap_mm: float,
) -> CamOutcome:
    """Sinker EDM's electrode-geometry corner-radius containment
    (procres/subtractive.md #14 DFM rule 3): the electrode's own corner
    radius plus the spark gap floors the cavity's achievable internal
    corner radius -- same predicate shape as the wire-EDM check, over a
    rigid-electrode geometry term instead of a kerf term."""
    required = electrode_corner_radius_mm + spark_gap_mm
    excess = required - internal_corner_radius_mm
    _log.debug(
        "sinker edm corner radius: declared=%.4f required=%.4f excess=%.4f",
        internal_corner_radius_mm,
        required,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"internal corner radius {internal_corner_radius_mm:.4f}mm is "
                f"below the electrode-radius + spark-gap floor ({required:.4f}mm)"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"internal corner radius {internal_corner_radius_mm:.4f}mm clears "
            f"the electrode-radius + spark-gap floor (margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_quench_section_uniformity(
    section_thicknesses_mm: tuple[float, ...], max_ratio: float
) -> CamOutcome:
    """Q&T's distortion/cracking-risk gate (procres/heat_treatment.md
    #77 DFM rule 2): quench-induced distortion/cracking risk scales
    with section-thickness NON-uniformity (MIL-H-6875 names this risk
    qualitatively). ``max_ratio`` is the declared max thickest/thinnest
    ratio the process/alloy combination tolerates; an empty or
    single-entry thickness set is indeterminate (nothing to compare)."""
    if len(section_thicknesses_mm) < 2:
        return CamOutcome(
            indeterminate=True,
            note="fewer than two declared section thicknesses; "
            "uniformity ratio cannot be grounded",
        )
    thinnest = min(section_thicknesses_mm)
    thickest = max(section_thicknesses_mm)
    if thinnest <= 0.0:
        return CamOutcome(
            indeterminate=True,
            note="a declared section thickness is non-positive; "
            "uniformity ratio cannot be grounded",
        )
    ratio = thickest / thinnest
    excess = ratio - max_ratio
    _log.debug(
        "quench uniformity: thinnest=%.4f thickest=%.4f ratio=%.4f max=%.4f",
        thinnest,
        thickest,
        ratio,
        max_ratio,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"section thickness ratio {ratio:.3f} exceeds the declared "
                f"quench-uniformity ceiling {max_ratio:.3f} "
                f"(thinnest {thinnest:.3f}mm, thickest {thickest:.3f}mm)"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"section thickness ratio {ratio:.3f} within the declared "
            f"quench-uniformity ceiling {max_ratio:.3f} (margin {-excess:.3f})"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_process_sequencing(
    required_upstream: str, declared_upstream: tuple[str, ...]
) -> CamOutcome:
    """The GENERIC material-state/process-sequencing predicate shared
    by every heat-treat family member whose own DFM rule is a
    sequencing/composition check rather than a geometric one (anneal
    #75, normalize #76, case-harden #78, nitride #79, stress-relieve
    #80, induction-harden #81, austemper/martemper #82, solution-
    treat-age #83 -- each cites this SAME callable with its own
    ``required_upstream``/``declared_upstream`` values rather than
    duplicating the boolean-membership arithmetic per process, per the
    NO-DUPLICATION rule). ``excess`` is 1.0 (violated, required state
    absent) or 0.0 (satisfied)."""
    if required_upstream in declared_upstream:
        return CamOutcome(
            excess=0.0,
            note=f"required upstream state {required_upstream!r} is declared",
        )
    return CamOutcome(
        excess=1.0,
        note=(
            f"required upstream state {required_upstream!r} is not among "
            f"the declared upstream states {declared_upstream!r}"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_punch_die_clearance(
    clearance_mm: float, thickness_mm: float, min_pct: float, max_pct: float
) -> CamOutcome:
    """Punch/die clearance as a percent of stock thickness within a
    declared process envelope (procres/sheet.md #22 DFM rule 4; the
    Machinery's Handbook/ASM Sheet Metal Forming Handbook verbatim
    clearance-percent-by-material tables are a NAMED REFUSAL --
    `min_pct`/`max_pct` are DECLARED per-material-class bounds passed
    in by the caller, never a hard-coded constant here). Reports the
    worst-side excess (too tight OR too loose is a violation)."""
    if thickness_mm <= 0.0:
        return CamOutcome(indeterminate=True, note="declared thickness is non-positive")
    pct = (clearance_mm / thickness_mm) * 100.0
    low_excess = min_pct - pct
    high_excess = pct - max_pct
    excess = max(low_excess, high_excess)
    _log.debug(
        "punch/die clearance: pct=%.3f min=%.3f max=%.3f excess=%.3f",
        pct,
        min_pct,
        max_pct,
        excess,
    )
    if excess > 0.0:
        side = "below minimum" if low_excess > high_excess else "above maximum"
        return CamOutcome(
            excess=excess,
            note=(
                f"clearance {pct:.3f}% of thickness is {side} of the "
                f"declared [{min_pct:.3f}%, {max_pct:.3f}%] envelope"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"clearance {pct:.3f}% of thickness is within the declared "
            f"[{min_pct:.3f}%, {max_pct:.3f}%] envelope (margin {-excess:.3f})"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_press_tonnage(
    required_tonnage: float, press_capacity_tonnage: float
) -> CamOutcome:
    """Required vs available press tonnage containment (procres/
    sheet.md #22 DFM rule 5): a part whose perimeter x material
    shear-strength implies more force than the declared press's
    capacity is a genuine violation -- the same containment-predicate
    shape as `check_stock_fit`'s extents-vs-travel comparison, over a
    force scalar instead of a geometric extent."""
    excess = required_tonnage - press_capacity_tonnage
    _log.debug(
        "press tonnage: required=%.3f capacity=%.3f excess=%.3f",
        required_tonnage,
        press_capacity_tonnage,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"required tonnage {required_tonnage:.3f} exceeds declared "
                f"press capacity {press_capacity_tonnage:.3f}"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"required tonnage {required_tonnage:.3f} fits declared press "
            f"capacity {press_capacity_tonnage:.3f} (margin {-excess:.3f})"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_press_brake_bend_radius(
    bend_radius_mm: float, thickness_mm: float, min_radius_factor: float
) -> CamOutcome:
    """Bend-radius-vs-thickness cracking-risk gate (procres/sheet.md
    #23 DFM rule 1): the minimum bend radius before outer-fiber
    cracking is a declared material-class multiple of thickness
    (`min_radius_factor`, e.g. ~1x for ductile steel/aluminum per the
    dossier -- passed in, never hard-coded)."""
    required = min_radius_factor * thickness_mm
    excess = required - bend_radius_mm
    _log.debug(
        "press brake bend radius: declared=%.4f required=%.4f excess=%.4f",
        bend_radius_mm,
        required,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"bend radius {bend_radius_mm:.4f}mm is below the declared "
                f"minimum {required:.4f}mm ({min_radius_factor}x thickness)"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"bend radius {bend_radius_mm:.4f}mm clears the declared "
            f"minimum {required:.4f}mm (margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_grinding_stock_allowance(
    stock_allowance_mm: float, min_removal_mm: float, max_removal_mm: float
) -> CamOutcome:
    """Post-heat-treat finishing stock-removal-window gate (procres/
    subtractive.md #7 DFM rule 2): stock left for grinding after a
    prior op must fall within the wheel's per-pass removal window --
    too little risks skip-cutting, too much means excess grind time.
    Reports the worst-side excess (too little OR too much)."""
    low_excess = min_removal_mm - stock_allowance_mm
    high_excess = stock_allowance_mm - max_removal_mm
    excess = max(low_excess, high_excess)
    _log.debug(
        "grinding stock allowance: declared=%.4f min=%.4f max=%.4f excess=%.4f",
        stock_allowance_mm,
        min_removal_mm,
        max_removal_mm,
        excess,
    )
    if excess > 0.0:
        side = (
            "below the skip-cut floor"
            if low_excess > high_excess
            else ("above the per-pass ceiling")
        )
        return CamOutcome(
            excess=excess,
            note=(
                f"stock allowance {stock_allowance_mm:.4f}mm is {side} of "
                f"the declared [{min_removal_mm:.4f}, {max_removal_mm:.4f}]mm "
                "grinding window"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"stock allowance {stock_allowance_mm:.4f}mm is within the "
            f"declared [{min_removal_mm:.4f}, {max_removal_mm:.4f}]mm "
            f"grinding window (margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_shot_peen_recast_remediation(
    upstream_process: str,
    required_upstream: str,
    compressive_depth_mm: float,
    min_depth_mm: float,
) -> CamOutcome:
    """Shot-peen-after-EDM recast-layer remediation gate (procres/
    surface.md #92): peening must follow the recast-bearing process
    (a sequencing predicate) AND its achieved compressive-layer depth
    must meet the declared fatigue-improvement floor (a numeric
    predicate) -- both folded into one check since the dossier frames
    them as one remediation claim. A sequencing miss is reported as a
    unit violation (excess 1.0); a depth miss reports the real mm
    shortfall so the two failure modes stay distinguishable in the
    note text."""
    if upstream_process != required_upstream:
        return CamOutcome(
            excess=1.0,
            note=(
                f"declared upstream process {upstream_process!r} is not the "
                f"required recast-bearing process {required_upstream!r}"
            ),
        )
    excess = min_depth_mm - compressive_depth_mm
    _log.debug(
        "shot peen remediation: depth=%.4f min=%.4f excess=%.4f",
        compressive_depth_mm,
        min_depth_mm,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"compressive layer depth {compressive_depth_mm:.4f}mm is "
                f"below the declared fatigue-remediation floor "
                f"{min_depth_mm:.4f}mm"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"compressive layer depth {compressive_depth_mm:.4f}mm meets the "
            f"declared fatigue-remediation floor {min_depth_mm:.4f}mm "
            f"(margin {-excess:.4f}mm)"
        ),
    )


__all__ = [
    "check_grinding_stock_allowance",
    "check_press_brake_bend_radius",
    "check_press_tonnage",
    "check_process_sequencing",
    "check_punch_die_clearance",
    "check_quench_section_uniformity",
    "check_shot_peen_recast_remediation",
    "check_sinker_edm_corner_radius",
    "check_stock_fit",
    "check_tool_fit",
    "check_wire_edm_corner_radius",
    "check_wire_edm_start_hole",
]
