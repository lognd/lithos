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


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_min_trace_space(
    trace_width_mm: float,
    spacing_mm: float,
    min_trace_mm: float,
    min_space_mm: float,
) -> CamOutcome:
    """PCB fab trace-width/spacing containment (procres/pcb.md #93 DFM
    rule 1): declared trace width and inter-trace spacing must each meet
    the fab house's declared minimums (a per-side containment predicate,
    worst side reported, mirroring `check_punch_die_clearance`'s
    two-sided-envelope shape)."""
    width_excess = min_trace_mm - trace_width_mm
    space_excess = min_space_mm - spacing_mm
    excess = max(width_excess, space_excess)
    _log.debug(
        "pcb trace/space: width=%.4f space=%.4f min_width=%.4f min_space=%.4f "
        "excess=%.4f",
        trace_width_mm,
        spacing_mm,
        min_trace_mm,
        min_space_mm,
        excess,
    )
    if excess > 0.0:
        side = "trace width" if width_excess > space_excess else "spacing"
        return CamOutcome(
            excess=excess,
            note=(
                f"declared {side} is below the fab-house minimum "
                f"(width {trace_width_mm:.4f}mm >= {min_trace_mm:.4f}mm, "
                f"space {spacing_mm:.4f}mm >= {min_space_mm:.4f}mm)"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"trace width {trace_width_mm:.4f}mm and spacing {spacing_mm:.4f}mm "
            f"both meet the fab-house minimum (margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_annular_ring(annular_ring_mm: float, min_annular_ring_mm: float) -> CamOutcome:
    """PCB fab annular-ring (copper pad around a via) containment
    (procres/pcb.md #93 DFM rule 3): the declared annular ring must
    clear the fab house's drill-registration-tolerance-derived
    minimum."""
    excess = min_annular_ring_mm - annular_ring_mm
    _log.debug(
        "pcb annular ring: declared=%.4f min=%.4f excess=%.4f",
        annular_ring_mm,
        min_annular_ring_mm,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"annular ring {annular_ring_mm:.4f}mm is below the declared "
                f"minimum {min_annular_ring_mm:.4f}mm"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"annular ring {annular_ring_mm:.4f}mm clears the declared "
            f"minimum {min_annular_ring_mm:.4f}mm (margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_via_drill_range(
    via_dia_mm: float, min_dia_mm: float, max_dia_mm: float
) -> CamOutcome:
    """PCB fab via-diameter containment within the declared mechanical-
    vs-laser drill-capability range (procres/pcb.md #93 DFM rule 2)."""
    low_excess = min_dia_mm - via_dia_mm
    high_excess = via_dia_mm - max_dia_mm
    excess = max(low_excess, high_excess)
    _log.debug(
        "pcb via drill: dia=%.4f min=%.4f max=%.4f excess=%.4f",
        via_dia_mm,
        min_dia_mm,
        max_dia_mm,
        excess,
    )
    if excess > 0.0:
        side = "below the minimum drill diameter" if low_excess > high_excess else (
            "above the maximum drill diameter"
        )
        return CamOutcome(
            excess=excess,
            note=(
                f"via diameter {via_dia_mm:.4f}mm is {side} of the declared "
                f"[{min_dia_mm:.4f}, {max_dia_mm:.4f}]mm drill-capability range"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"via diameter {via_dia_mm:.4f}mm is within the declared "
            f"[{min_dia_mm:.4f}, {max_dia_mm:.4f}]mm drill-capability range "
            f"(margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_copper_edge_clearance(
    edge_clearance_mm: float, min_edge_clearance_mm: float
) -> CamOutcome:
    """PCB fab copper-to-board-edge clearance containment (procres/
    pcb.md #93 DFM rule 6)."""
    excess = min_edge_clearance_mm - edge_clearance_mm
    _log.debug(
        "pcb copper edge clearance: declared=%.4f min=%.4f excess=%.4f",
        edge_clearance_mm,
        min_edge_clearance_mm,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"copper-to-edge clearance {edge_clearance_mm:.4f}mm is below "
                f"the declared minimum {min_edge_clearance_mm:.4f}mm"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"copper-to-edge clearance {edge_clearance_mm:.4f}mm clears the "
            f"declared minimum {min_edge_clearance_mm:.4f}mm (margin "
            f"{-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_reflow_thermal_compat(
    component_max_temp_c: tuple[float, ...], profile_peak_temp_c: float
) -> CamOutcome:
    """SMT assembly board-level reflow-profile compatibility (procres/
    pcb.md #94 DFM rule 3): the LOWEST-tolerance component on the board
    gates the maximum reflow peak temperature -- a forall-quantifier
    over declared component thermal ratings, mirroring `check_tool_fit`'s
    worst-feature-governs shape. An empty component set is
    indeterminate (nothing to gate against)."""
    if not component_max_temp_c:
        return CamOutcome(
            indeterminate=True,
            note="no declared component thermal ratings; reflow compatibility "
            "cannot be grounded",
        )
    weakest = min(component_max_temp_c)
    excess = profile_peak_temp_c - weakest
    _log.debug(
        "reflow thermal compat: weakest=%.2f profile_peak=%.2f excess=%.4f",
        weakest,
        profile_peak_temp_c,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"reflow profile peak {profile_peak_temp_c:.2f}C exceeds the "
                f"lowest-tolerance declared component rating {weakest:.2f}C"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"reflow profile peak {profile_peak_temp_c:.2f}C is within the "
            f"lowest-tolerance declared component rating {weakest:.2f}C "
            f"(margin {-excess:.4f}C)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_placement_pad_spacing(
    pad_pitch_mm: float, placement_accuracy_mm: float, min_margin_mm: float
) -> CamOutcome:
    """SMT fine-pitch pad-to-pad spacing containment (procres/pcb.md
    #94 DFM rule 2): declared pad pitch must clear the pick-and-place
    accuracy plus a declared solder-bridge margin."""
    required = placement_accuracy_mm + min_margin_mm
    excess = required - pad_pitch_mm
    _log.debug(
        "smt pad spacing: pitch=%.4f accuracy=%.4f margin=%.4f excess=%.4f",
        pad_pitch_mm,
        placement_accuracy_mm,
        min_margin_mm,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"pad pitch {pad_pitch_mm:.4f}mm is below the declared "
                f"placement-accuracy + solder-bridge-margin floor "
                f"{required:.4f}mm"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"pad pitch {pad_pitch_mm:.4f}mm clears the declared "
            f"placement-accuracy + solder-bridge-margin floor {required:.4f}mm "
            f"(margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_hole_lead_clearance(
    hole_dia_mm: float, lead_dia_mm: float, min_gap_mm: float, max_gap_mm: float
) -> CamOutcome:
    """Through-hole/wave-solder hole-to-lead solderability-window
    containment (procres/pcb.md #95 DFM rule 1): the annular gap
    between hole and lead diameter must fall within the declared
    solder-fill window (too tight starves capillary fill, too loose
    starves fillet strength -- both-sided, mirrors
    `check_punch_die_clearance`'s two-sided envelope)."""
    if hole_dia_mm <= lead_dia_mm:
        return CamOutcome(
            indeterminate=True,
            note="declared hole diameter does not exceed the lead diameter; "
            "no annular gap to check",
        )
    gap_mm = hole_dia_mm - lead_dia_mm
    low_excess = min_gap_mm - gap_mm
    high_excess = gap_mm - max_gap_mm
    excess = max(low_excess, high_excess)
    _log.debug(
        "hole/lead clearance: gap=%.4f min=%.4f max=%.4f excess=%.4f",
        gap_mm,
        min_gap_mm,
        max_gap_mm,
        excess,
    )
    if excess > 0.0:
        side = "below the capillary-fill floor" if low_excess > high_excess else (
            "above the fillet-strength ceiling"
        )
        return CamOutcome(
            excess=excess,
            note=(
                f"hole/lead gap {gap_mm:.4f}mm is {side} of the declared "
                f"[{min_gap_mm:.4f}, {max_gap_mm:.4f}]mm solderability window"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"hole/lead gap {gap_mm:.4f}mm is within the declared "
            f"[{min_gap_mm:.4f}, {max_gap_mm:.4f}]mm solderability window "
            f"(margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_masked_area_declared(
    declared_masks: tuple[str, ...], required_masks: tuple[str, ...]
) -> CamOutcome:
    """Conformal-coating masked-area exclusion-zone predicate (procres/
    pcb.md #96 DFM rule 1): every required mask area (connectors, test
    points, thermal-interface surfaces) must appear in the declared
    mask list -- a set-containment predicate, boolean excess (1.0
    violated, 0.0 satisfied), naming the missing areas."""
    missing = tuple(sorted(set(required_masks) - set(declared_masks)))
    if missing:
        return CamOutcome(
            excess=1.0,
            note=f"required mask area(s) not declared: {', '.join(missing)}",
        )
    return CamOutcome(
        excess=0.0,
        note=f"all {len(required_masks)} required mask area(s) declared",
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_perfboard_grid_pitch(
    lead_pitch_mm: float, grid_pitch_mm: float, tolerance_mm: float
) -> CamOutcome:
    """Perf-board lead-pitch-vs-grid predicate (procres/pcb.md #97 DFM
    rule 1): a component's lead pitch must be an integer multiple of
    the fixed hole grid (within a declared manufacturing tolerance), or
    a breakout adapter is required -- reports the nearest-multiple
    residual as the excess (0.0 = an exact or within-tolerance
    multiple)."""
    if grid_pitch_mm <= 0.0:
        return CamOutcome(indeterminate=True, note="declared grid pitch is non-positive")
    ratio = lead_pitch_mm / grid_pitch_mm
    nearest = round(ratio)
    residual_mm = abs(ratio - nearest) * grid_pitch_mm
    excess = residual_mm - tolerance_mm
    _log.debug(
        "perfboard grid pitch: lead=%.4f grid=%.4f residual=%.4f excess=%.4f",
        lead_pitch_mm,
        grid_pitch_mm,
        residual_mm,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"lead pitch {lead_pitch_mm:.4f}mm is not an integer multiple "
                f"of the {grid_pitch_mm:.4f}mm grid within the declared "
                f"{tolerance_mm:.4f}mm tolerance (residual {residual_mm:.4f}mm); "
                "a breakout adapter is required"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"lead pitch {lead_pitch_mm:.4f}mm is an integer multiple of the "
            f"{grid_pitch_mm:.4f}mm grid within tolerance "
            f"(residual {residual_mm:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_ampacity_containment(
    derated_ampacity_a: float, declared_load_a: float
) -> CamOutcome:
    """Branch-circuit conductor ampacity (with NEC 310.15 derating)
    containment (procres/elec_install.md #98 DFM rule 1): the same
    containment shape as `check_press_tonnage`, over a current rating
    instead of a force -- the derating arithmetic itself is
    `AmpacityModel` (`harness/models/power.py`, WO-134, NEC 310.15
    cited there); this check consumes ITS output as declared data."""
    excess = declared_load_a - derated_ampacity_a
    _log.debug(
        "branch-circuit ampacity: derated=%.3f load=%.3f excess=%.4f",
        derated_ampacity_a,
        declared_load_a,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"declared load {declared_load_a:.3f}A exceeds the derated "
                f"conductor ampacity {derated_ampacity_a:.3f}A"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"declared load {declared_load_a:.3f}A fits the derated conductor "
            f"ampacity {derated_ampacity_a:.3f}A (margin {-excess:.3f}A)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_voltage_drop_limit(voltage_drop_pct: float, max_pct: float) -> CamOutcome:
    """Branch-circuit voltage-drop-percent containment (procres/
    elec_install.md #98 DFM rule 2); the drop itself is computed by
    `VoltageDropModel` (`harness/models/power.py`, IEEE Std 141-1993
    cited there) -- this check consumes its output as declared
    percent-of-nominal data against a declared threshold."""
    excess = voltage_drop_pct - max_pct
    _log.debug(
        "voltage drop: pct=%.4f max=%.4f excess=%.4f", voltage_drop_pct, max_pct, excess
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"voltage drop {voltage_drop_pct:.4f}% exceeds the declared "
                f"maximum {max_pct:.4f}%"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"voltage drop {voltage_drop_pct:.4f}% is within the declared "
            f"maximum {max_pct:.4f}% (margin {-excess:.4f}%)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_working_clearance(clearance_mm: float, min_clearance_mm: float) -> CamOutcome:
    """Panel/service-equipment working-clearance containment (procres/
    elec_install.md #98 DFM rule 5, NEC 110.26-class): declared physical
    clearance in front of electrical equipment must meet the declared
    code minimum -- a calcite (building space) cross-domain link, per
    the dossier."""
    excess = min_clearance_mm - clearance_mm
    _log.debug(
        "working clearance: declared=%.2f min=%.2f excess=%.4f",
        clearance_mm,
        min_clearance_mm,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"working clearance {clearance_mm:.2f}mm is below the "
                f"declared NEC 110.26-class minimum {min_clearance_mm:.2f}mm"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"working clearance {clearance_mm:.2f}mm meets the declared NEC "
            f"110.26-class minimum {min_clearance_mm:.2f}mm (margin "
            f"{-excess:.2f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_conduit_fill(fill_pct: float, max_fill_pct: float) -> CamOutcome:
    """Conduit/raceway conductor-fill-percentage containment (procres/
    elec_install.md #100 DFM rule 1, NEC Ch.9 Table 1-class): the exact
    verbatim fill-percentage-by-conductor-count table is a NAMED
    REFUSAL (dossier #100) -- `max_fill_pct` is a declared caller
    parameter (e.g. the well-known 40%-for-3-plus-conductors GEK-tier
    figure), never a hard-coded constant here."""
    excess = fill_pct - max_fill_pct
    _log.debug(
        "conduit fill: pct=%.3f max=%.3f excess=%.4f", fill_pct, max_fill_pct, excess
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"conduit fill {fill_pct:.3f}% exceeds the declared maximum "
                f"{max_fill_pct:.3f}%"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"conduit fill {fill_pct:.3f}% is within the declared maximum "
            f"{max_fill_pct:.3f}% (margin {-excess:.3f}%)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_conduit_bend_radius(
    bend_radius_mm: float, conduit_dia_mm: float, min_radius_factor: float
) -> CamOutcome:
    """Conduit/raceway minimum bend-radius-as-a-multiple-of-diameter
    containment (procres/elec_install.md #100 DFM rule 2, NEC
    358.24-class): same shape as `check_press_brake_bend_radius`, over
    conduit diameter instead of sheet thickness -- `min_radius_factor`
    is a declared caller parameter (the exact NEC 358.24 table is a
    named refusal for verbatim transcription)."""
    required = min_radius_factor * conduit_dia_mm
    excess = required - bend_radius_mm
    _log.debug(
        "conduit bend radius: declared=%.4f required=%.4f excess=%.4f",
        bend_radius_mm,
        required,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"bend radius {bend_radius_mm:.4f}mm is below the declared "
                f"minimum {required:.4f}mm ({min_radius_factor}x diameter)"
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
def check_value_window(
    value_mm: float, min_mm: float, max_mm: float, quantity_name: str = "value"
) -> CamOutcome:
    """The GENERIC declared-value-within-a-declared-window containment
    predicate (WO-171 wave 3): reused across every family whose own DFM
    rule is "this dimension must sit inside a declared [min, max] band"
    rather than a family-specific arithmetic shape (casting/molding/
    powder wall thickness, joining joint-gap/bond-line-thickness
    windows, and any other family sharing this SAME shape) -- the same
    NO-DUPLICATION reasoning `check_punch_die_clearance`/
    `check_grinding_stock_allowance` already apply to their own narrower
    cases, generalized here so wave-3's many new families do not each
    duplicate the worst-side-excess arithmetic. `quantity_name` is
    caller-declared only for the note text, never a hidden default
    threshold."""
    low_excess = min_mm - value_mm
    high_excess = value_mm - max_mm
    excess = max(low_excess, high_excess)
    _log.debug(
        "%s window: declared=%.4f min=%.4f max=%.4f excess=%.4f",
        quantity_name,
        value_mm,
        min_mm,
        max_mm,
        excess,
    )
    if excess > 0.0:
        side = "below minimum" if low_excess > high_excess else "above maximum"
        return CamOutcome(
            excess=excess,
            note=(
                f"{quantity_name} {value_mm:.4f}mm is {side} of the declared "
                f"[{min_mm:.4f}, {max_mm:.4f}]mm window"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"{quantity_name} {value_mm:.4f}mm is within the declared "
            f"[{min_mm:.4f}, {max_mm:.4f}]mm window (margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_draft_angle_min(draft_deg: float, min_draft_deg: float) -> CamOutcome:
    """The GENERIC die/mold-release draft-angle floor (WO-171 wave 3):
    every casting/molding/forging family whose DFM rule is "declared
    draft angle must meet or exceed a process-class minimum" reuses
    this ONE callable (die casting, permanent mold, injection molding,
    compression/transfer molding, closed-die forging) rather than each
    duplicating the same single-sided containment arithmetic."""
    excess = min_draft_deg - draft_deg
    _log.debug(
        "draft angle: declared=%.4f min=%.4f excess=%.4f", draft_deg, min_draft_deg, excess
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"draft angle {draft_deg:.4f}deg is below the declared "
                f"minimum {min_draft_deg:.4f}deg for die/mold release"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"draft angle {draft_deg:.4f}deg meets the declared minimum "
            f"{min_draft_deg:.4f}deg (margin {-excess:.4f}deg)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_ratio_max(
    numerator_mm: float,
    denominator_mm: float,
    max_ratio: float,
    ratio_name: str = "ratio",
) -> CamOutcome:
    """The GENERIC declared-ratio-must-not-exceed-a-process-limit
    predicate (WO-171 wave 3): reused for every family whose DFM rule
    is a dimensionless containment on two declared lengths (injection
    molding's rib/nominal-wall sink-mark ratio, thermoforming's draw-
    depth/opening ratio, cold heading's upset ratio per station, wire/
    bar-drawing-class per-pass diameter-reduction limits) -- the SAME
    single-sided containment shape as `check_draft_angle_min`, over a
    ratio instead of an angle."""
    if denominator_mm <= 0.0:
        return CamOutcome(
            indeterminate=True, note=f"declared denominator for {ratio_name} is non-positive"
        )
    ratio = numerator_mm / denominator_mm
    excess = ratio - max_ratio
    _log.debug("%s: ratio=%.4f max=%.4f excess=%.4f", ratio_name, ratio, max_ratio, excess)
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"{ratio_name} {ratio:.4f} exceeds the declared maximum "
                f"{max_ratio:.4f}"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"{ratio_name} {ratio:.4f} is within the declared maximum "
            f"{max_ratio:.4f} (margin {-excess:.4f})"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_min_floor(value_mm: float, min_mm: float, quantity_name: str = "value") -> CamOutcome:
    """The GENERIC single-sided declared-minimum containment predicate
    (WO-171 wave 4: subtractive/sheet/surface remainder): reused for
    every family whose DFM rule is "this dimension must be no smaller
    than a declared floor" (milling corner radius vs tool radius,
    drilling edge distance, tapping engagement length, sawing kerf-
    downstream-finish allowance, sheet minimum flange length/web width)
    rather than each duplicating the same one-sided arithmetic --
    `check_draft_angle_min`/`check_press_brake_bend_radius` already
    apply this exact shape to their own narrower cases (an angle, a
    thickness-multiple); this callable generalizes it to any declared
    minimum, mirroring `check_value_window`'s own generalization of the
    two-sided case. `min_mm` is ALWAYS caller-computed (e.g. a declared
    material-class multiplier times thickness), never a hidden
    constant here."""
    excess = min_mm - value_mm
    _log.debug(
        "%s min floor: declared=%.4f min=%.4f excess=%.4f",
        quantity_name,
        value_mm,
        min_mm,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"{quantity_name} {value_mm:.4f}mm is below the declared "
                f"minimum {min_mm:.4f}mm"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"{quantity_name} {value_mm:.4f}mm meets the declared minimum "
            f"{min_mm:.4f}mm (margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_max_ceiling(value_mm: float, max_mm: float, quantity_name: str = "value") -> CamOutcome:
    """The GENERIC single-sided declared-maximum containment predicate
    (WO-171 wave 4), the mirror-image complement of `check_min_floor`:
    reused for every family whose DFM rule is "this dimension must not
    exceed a declared ceiling" (oxy-fuel/plasma/laser thickness
    envelopes, sawing tolerance excluded from a final-dimension claim
    read as a ceiling on claimed precision, shearing thickness
    capacity) rather than each duplicating the same one-sided
    arithmetic."""
    excess = value_mm - max_mm
    _log.debug(
        "%s max ceiling: declared=%.4f max=%.4f excess=%.4f",
        quantity_name,
        value_mm,
        max_mm,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"{quantity_name} {value_mm:.4f}mm exceeds the declared "
                f"maximum {max_mm:.4f}mm"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"{quantity_name} {value_mm:.4f}mm is within the declared "
            f"maximum {max_mm:.4f}mm (margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_coating_dimensional_growth(
    coating_thickness_mm: float,
    growth_factor: float,
    declared_compensation_mm: float,
) -> CamOutcome:
    """Surface-treatment dimensional-growth compensation gate (procres/
    surface.md #84 DFM rule 1 / #85 DFM rule 3, WO-171 wave 4): a
    coating that grows or adds dimension must have its declared
    tight-tolerance-feature compensation meet or exceed
    ``growth_factor * coating_thickness_mm`` -- `growth_factor` is a
    declared PER-PROCESS caller parameter (anodizing's oxide grows
    roughly half the coating thickness per side, ``growth_factor~0.5``;
    electroplating adds ~fully to the dimension on exposed surfaces,
    ``growth_factor~1.0``), never a hard-coded constant here, so the
    SAME callable serves both processes' distinct growth mechanisms
    (procres/surface.md #84/#85) without duplicating the arithmetic."""
    required = growth_factor * coating_thickness_mm
    excess = required - declared_compensation_mm
    _log.debug(
        "coating growth: thickness=%.4f factor=%.4f required=%.4f "
        "declared_comp=%.4f excess=%.4f",
        coating_thickness_mm,
        growth_factor,
        required,
        declared_compensation_mm,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"declared compensation {declared_compensation_mm:.4f}mm is "
                f"below the required {required:.4f}mm (growth_factor "
                f"{growth_factor:.4f} x coating thickness "
                f"{coating_thickness_mm:.4f}mm)"
            ),
        )
    return CamOutcome(
        excess=excess,
        note=(
            f"declared compensation {declared_compensation_mm:.4f}mm meets "
            f"the required {required:.4f}mm (growth_factor "
            f"{growth_factor:.4f} x coating thickness "
            f"{coating_thickness_mm:.4f}mm, margin {-excess:.4f}mm)"
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def check_boolean_gate(condition_ok: bool, note: str) -> CamOutcome:
    """The GENERIC hard boolean design-rule gate (WO-171 wave 3): reused
    for every family whose DFM rule is a plain yes/no geometric/process
    predicate rather than a numeric containment (PM's uniaxial press-
    and-eject-without-undercuts gate, centrifugal casting's axisymmetric-
    hollow-only gate, rotational molding's no-fine-detail gate, cold
    heading's no-undercut-perpendicular-to-upset-axis gate). `excess` is
    1.0 (violated) or 0.0 (satisfied); `note` is ALWAYS caller-supplied
    (never a hidden default message) so the specific predicate that
    failed/passed is always named."""
    if condition_ok:
        return CamOutcome(excess=0.0, note=note)
    return CamOutcome(excess=1.0, note=note)


__all__ = [
    "check_ampacity_containment",
    "check_annular_ring",
    "check_boolean_gate",
    "check_coating_dimensional_growth",
    "check_conduit_bend_radius",
    "check_conduit_fill",
    "check_copper_edge_clearance",
    "check_draft_angle_min",
    "check_grinding_stock_allowance",
    "check_hole_lead_clearance",
    "check_masked_area_declared",
    "check_max_ceiling",
    "check_min_floor",
    "check_min_trace_space",
    "check_perfboard_grid_pitch",
    "check_placement_pad_spacing",
    "check_press_brake_bend_radius",
    "check_press_tonnage",
    "check_process_sequencing",
    "check_punch_die_clearance",
    "check_quench_section_uniformity",
    "check_ratio_max",
    "check_reflow_thermal_compat",
    "check_shot_peen_recast_remediation",
    "check_sinker_edm_corner_radius",
    "check_stock_fit",
    "check_tool_fit",
    "check_value_window",
    "check_via_drill_range",
    "check_voltage_drop_limit",
    "check_wire_edm_corner_radius",
    "check_wire_edm_start_hole",
    "check_working_clearance",
]
