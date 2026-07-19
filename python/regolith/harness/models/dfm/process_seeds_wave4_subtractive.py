"""WO-171 wave-4 population: the subtractive-family remainder (procres/
subtractive.md #1-6, #8-12, #15-20 -- milling, turning, drilling,
reaming, boring, tapping/threading, honing, lapping, superfinishing,
sawing, broaching, waterjet, laser cutting, plasma cutting, oxy-fuel
cutting, ECM, gear hobbing/shaping). Wire EDM (#13), sinker EDM (#14),
and grinding (#7) already landed in wave 0/1 (`process_seeds.py`,
`process_seeds_wave1_subtractive.py`); this wave closes the family to
20/20.

Every numeric value here is transcribed from the named dossier entry
with its provenance class preserved verbatim (this module invents no
citation and does not upgrade a GEK value to look cited). Three
generic check callables new this wave (`check_min_floor`,
`check_max_ceiling`, WO-171 wave 4) generalize the single-sided
containment shape `check_draft_angle_min`/`check_press_brake_bend_
radius` already apply narrowly, so this family's many "must be no
smaller/larger than a declared bound" rules reuse ONE callable each
rather than inventing a bespoke arithmetic per process."""

from __future__ import annotations

from regolith.backends.quantity import DimensionedValue
from regolith.harness.models.dfm.process_records import (
    CostDriver,
    DfmCheckEntry,
    DfmCheckSet,
    MinFeature,
    ProcessRecord,
    ProvenanceNote,
    SizeLimit,
    SurfaceFinishEntry,
    ToleranceGrade,
)


def _gek(detail: str) -> ProvenanceNote:
    return ProvenanceNote(posture="gek", scope="record", detail=detail)


def _refuse(
    scope: str, detail: str, refused_source: str, lift_condition: str
) -> ProvenanceNote:
    return ProvenanceNote(
        posture="named_refusal",
        scope=scope,
        detail=detail,
        refused_source=refused_source,
        lift_condition=lift_condition,
    )


# --- 1. Milling ----------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
MILLING_RECORD = ProcessRecord(
    key="std.process/milling",
    name="Milling (face / peripheral / slab / slotting)",
    din_8580_class="3.2.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="general_tolerance",
            min=DimensionedValue.of("0.01", "mm"),
            max=DimensionedValue.of("0.1", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="general-purpose 3-axis, routine",
            achievable=DimensionedValue.of("+/-0.05-0.1", "mm"),
        ),
        ToleranceGrade(
            condition="rigid setup + finishing passes",
            achievable=DimensionedValue.of("+/-0.01", "mm"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="finish milling pass", ra=DimensionedValue.of("0.8-6.3", "um")
        ),
    ),
    min_features=(
        MinFeature(
            feature="pocket corner radius",
            value=DimensionedValue.of("tool_radius", "mm"),
        ),
        MinFeature(
            feature="minimum wall (aluminum)", value=DimensionedValue.of("0.5", "mm")
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="moderate fixturing + program time, amortized over batch",
            note="sweet spot = prototype-to-low-volume (1-500 units) before "
            "dedicated tooling wins economically (procres/subtractive.md #1)",
        ),
    ),
    lead_class="days (job-shop) to hours (in-house CNC)",
    provenance=(
        _gek(
            "tolerance/Ra/min-wall/aspect-ratio ranges are uncited "
            "engineering-consensus values (procres/subtractive.md #1)"
        ),
        _refuse(
            scope="surface_finish",
            detail="exact chip-load-to-Ra correlation tables are omitted",
            refused_source="Machinery's Handbook / ASM Machining Data "
            "Handbook Ra-vs-feed/speed tables",
            lift_condition="a licensed copy is obtained and its rows "
            "transcribed with in-row citation",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_min_floor",
        "regolith.harness.models.dfm.checks:check_ratio_max",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
MILLING_CHECKS = DfmCheckSet(
    family="milling",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_min_floor",
            provenance=_gek(
                "pocket corner radius must be >= the smallest declared "
                "tool radius, a hard tool-geometry containment predicate "
                "(procres/subtractive.md #1 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "pocket depth / tool diameter must not exceed a declared "
                "max_stickout_ratio, a reach/deflection check (procres/"
                "subtractive.md #1 DFM rule 2)"
            ),
        ),
    ),
)


# --- 2. Turning ------------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
TURNING_RECORD = ProcessRecord(
    key="std.process/turning",
    name="Turning (OD / ID boring on a lathe / facing)",
    din_8580_class="3.2.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="routine", achievable=DimensionedValue.of("+/-0.02-0.05", "mm")
        ),
        ToleranceGrade(
            condition="precision/CNC with live tooling",
            achievable=DimensionedValue.of("+/-0.005", "mm"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="typical finish turn", ra=DimensionedValue.of("0.4-3.2", "um")
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="similar to milling; live tooling blurs into mill-turn",
            note="sweet spot = 1-1000 units of round/tubular geometry "
            "(procres/subtractive.md #2)",
        ),
    ),
    lead_class="similar to milling",
    provenance=(
        _gek(
            "dimensional tolerance ranges are uncited engineering-"
            "consensus; Ra=f^2/(8r) is a derivable closed-form geometric "
            "relation, safe to state as physics not a transcribed table "
            "(procres/subtractive.md #2)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_ratio_max",
        "regolith.harness.models.dfm.checks:check_min_floor",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
TURNING_CHECKS = DfmCheckSet(
    family="turning",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "length-to-diameter ratio for unsupported turning must not "
                "exceed a declared max_unsupported_ratio (~10:1) else "
                "require tailstock/steady-rest declaration (procres/"
                "subtractive.md #2 DFM rule 2)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_min_floor",
            provenance=_gek(
                "internal (ID) corner radius must be >= the declared tool "
                "nose radius (procres/subtractive.md #2 DFM rule 3)"
            ),
        ),
    ),
)


# --- 3. Drilling -----------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
DRILLING_RECORD = ProcessRecord(
    key="std.process/drilling",
    name="Drilling",
    din_8580_class="3.2.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical jig/CNC drilling",
            achievable=DimensionedValue.of("+/-0.05-0.15", "mm"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="as-drilled hole", ra=DimensionedValue.of("3.2-12.5", "um")
        ),
    ),
    min_features=(
        MinFeature(
            feature="min edge distance (hole center to part edge)",
            value=DimensionedValue.of("1.5x diameter", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="cheapest per-hole subtractive op, near-zero incremental setup",
            note="sweet spot = any batch size, always alongside another "
            "primary process (procres/subtractive.md #3)",
        ),
    ),
    lead_class="near-instant per hole once the machine is set",
    provenance=(
        _gek(
            "diameter/aspect-ratio/tolerance/Ra ranges are uncited "
            "engineering-consensus values (procres/subtractive.md #3)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_ratio_max",
        "regolith.harness.models.dfm.checks:check_min_floor",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
DRILLING_CHECKS = DfmCheckSet(
    family="drilling",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "depth/diameter must not exceed a declared aspect-ratio "
                "limit (3-8:1 standard twist drills) else require a gun-"
                "drill/EDM alternative flag (procres/subtractive.md #3 "
                "DFM rule 2)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_min_floor",
            provenance=_gek(
                "minimum edge distance (hole center to part edge) must be "
                ">= 1.5x diameter (breakout risk), procres/subtractive.md "
                "#3 DFM rule 4"
            ),
        ),
    ),
)


# --- 4. Reaming --------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
REAMING_RECORD = ProcessRecord(
    key="std.process/reaming",
    name="Reaming",
    din_8580_class="3.2.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="pre_ream_stock_allowance",
            min=DimensionedValue.of("0.1", "mm"),
            max=DimensionedValue.of("0.3", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="H7-class fits",
            achievable=DimensionedValue.of("+/-0.01-0.02", "mm"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="reamed bore", ra=DimensionedValue.of("0.4-1.6", "um")
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="secondary op cost per hole",
            note="sweet spot = precision dowel/bearing bores (procres/subtractive.md #4)",
        ),
    ),
    lead_class="secondary op, adds to a prior drilling/boring op",
    provenance=(
        _gek(
            "stock-removal allowance/tolerance/Ra ranges are uncited "
            "engineering-consensus values (procres/subtractive.md #4)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_value_window",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
REAMING_CHECKS = DfmCheckSet(
    family="reaming",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "pre-hole diameter must fall within the declared reamer's "
                "stock-removal window -- too little or too much both fail "
                "(procres/subtractive.md #4 DFM rule 1)"
            ),
        ),
    ),
)


# --- 5. Boring ---------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
BORING_RECORD = ProcessRecord(
    key="std.process/boring",
    name="Boring (single-point, lathe / boring mill / jig borer)",
    din_8580_class="3.2.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="best positional accuracy of any hole process; jig-boring",
            achievable=DimensionedValue.of("+/-0.005-0.03", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="highest per-hole precision, highest per-hole cost of hole ops",
            note="sweet spot = bearing bores, engine-block-class precision "
            "holes (procres/subtractive.md #5)",
        ),
    ),
    lead_class="slow relative to drilling; precision-driven",
    provenance=(
        _gek(
            "diameter range/tolerance/L-D ratio values are uncited "
            "engineering-consensus (procres/subtractive.md #5)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_ratio_max",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
BORING_CHECKS = DfmCheckSet(
    family="boring",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "bore L/D must not exceed the declared boring-bar stickout "
                "ratio (~4-6:1), mirrors check_tool_fit's reach logic "
                "(procres/subtractive.md #5 DFM rule 1)"
            ),
        ),
    ),
)


# --- 6. Tapping / threading ---------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
TAPPING_RECORD = ProcessRecord(
    key="std.process/tapping",
    name="Tapping / threading (single-point + tap-and-die)",
    din_8580_class="3.2.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="minimum thread engagement length",
            value=DimensionedValue.of("1.5x diameter", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="cheap per-hole unless the tap breaks (then a scrapped part)",
            note="risk-weighted cost driver unlike other ops (procres/subtractive.md #6)",
        ),
    ),
    lead_class="near-instant per hole, risk-weighted by breakage",
    provenance=(
        _gek(
            "standard tap sizes/engagement-length/breakage-risk values are "
            "uncited engineering-consensus (procres/subtractive.md #6)"
        ),
        _refuse(
            scope="tolerance_grades",
            detail="thread tolerance class tables (6H/6g etc.) are omitted; "
            "classes are cited by name only",
            refused_source="ISO 965 thread tolerance class tables",
            lift_condition="a licensed copy of ISO 965 is obtained and its "
            "class tables transcribed with in-row citation",
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_min_floor",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
TAPPING_CHECKS = DfmCheckSet(
    family="tapping",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_min_floor",
            provenance=_gek(
                "thread engagement length must be >= a declared minimum "
                "(~1.5x diameter for full strength in ductile metals), "
                "procres/subtractive.md #6 DFM rule 2"
            ),
        ),
    ),
)


# --- 8. Honing -----------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
HONING_RECORD = ProcessRecord(
    key="std.process/honing",
    name="Honing",
    din_8580_class="3.2.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical", achievable=DimensionedValue.of("+/-0.005-0.01", "mm")
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="controlled crosshatch (oil retention)",
            ra=DimensionedValue.of("0.1-0.4", "um"),
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="secondary finishing op, moderate cost, low removal volume",
            note="engine-cylinder-class bore finishing (procres/subtractive.md #8)",
        ),
    ),
    lead_class="secondary finishing op",
    provenance=(
        _gek(
            "bore diameter range/tolerance/Ra values are uncited "
            "engineering-consensus (procres/subtractive.md #8)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_ratio_max",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
HONING_CHECKS = DfmCheckSet(
    family="honing",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "bore must be a through or long blind bore -- L/D must be "
                ">= a declared minimum for tool stroke engagement (procres/"
                "subtractive.md #8 DFM rule 1)"
            ),
        ),
    ),
)


# --- 9. Lapping ----------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
LAPPING_RECORD = ProcessRecord(
    key="std.process/lapping",
    name="Lapping",
    din_8580_class="3.2.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(
        SurfaceFinishEntry(
            condition="achievable", ra=DimensionedValue.of("< 0.05", "um")
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="highest per-area cost of any finishing process here",
            note="sweet spot = seal faces, gauge blocks, optical/precision "
            "mating surfaces (procres/subtractive.md #9)",
        ),
    ),
    lead_class="extremely slow (microns per pass)",
    provenance=(
        _gek(
            "flatness/Ra achievable values are uncited engineering-"
            "consensus (procres/subtractive.md #9)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_boolean_gate",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
LAPPING_CHECKS = DfmCheckSet(
    family="lapping",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "the declared flatness spec must justify lapping over "
                "grinding (a cost/tolerance trade predicate), procres/"
                "subtractive.md #9 DFM rule 2"
            ),
        ),
    ),
)


# --- 10. Superfinishing --------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
SUPERFINISHING_RECORD = ProcessRecord(
    key="std.process/superfinishing",
    name="Superfinishing (microfinishing)",
    din_8580_class="3.2.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(
        SurfaceFinishEntry(
            condition="achievable", ra=DimensionedValue.of("0.025-0.1", "um")
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="post_process",
            driver_class="added finishing cost for fatigue/wear-critical rotating surfaces",
            note="bearing races, crankshaft journals (procres/subtractive.md #10)",
        ),
    ),
    lead_class="finish-only secondary op, removes only microns",
    provenance=(
        _gek(
            "Ra achievable and removal-depth values are uncited "
            "engineering-consensus (procres/subtractive.md #10)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_process_sequencing",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SUPERFINISHING_CHECKS = DfmCheckSet(
    family="superfinishing",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "the prior op (typically grinding) must already meet "
                "dimensional tolerance -- superfinishing is finish-only, "
                "a sequencing predicate (procres/subtractive.md #10 DFM rule)"
            ),
        ),
    ),
)


# --- 11. Sawing ----------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
SAWING_RECORD = ProcessRecord(
    key="std.process/sawing",
    name="Sawing (band / circular / hack)",
    din_8580_class="3.2.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="kerf_width",
            min=DimensionedValue.of("0.5", "mm"),
            max=DimensionedValue.of("3", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="rough blank, band saw",
            achievable=DimensionedValue.of("+/-0.5-1", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="cheapest bulk-separation op, material-utilization driven (kerf loss)",
            note="produces rough blanks for subsequent precision ops "
            "(procres/subtractive.md #11)",
        ),
    ),
    lead_class="fast, bulk-separation only",
    provenance=(
        _gek(
            "kerf width and tolerance ranges are uncited engineering-"
            "consensus (procres/subtractive.md #11)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_process_sequencing",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SAWING_CHECKS = DfmCheckSet(
    family="sawing",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "this op's output tolerance must not be the part's final-"
                "dimension claim -- a sawn face needs a downstream "
                "finishing op declared (procres/subtractive.md #11 DFM "
                "rule 1, a sequencing/composition predicate)"
            ),
        ),
    ),
)


# --- 12. Broaching -------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
BROACHING_RECORD = ProcessRecord(
    key="std.process/broaching",
    name="Broaching",
    din_8580_class="3.2.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical", achievable=DimensionedValue.of("+/-0.02-0.05", "mm")
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="highest tooling-amortization class of any subtractive "
            "process here (dedicated custom tool per feature)",
            note="sweet spot ONLY high-volume (1000s+), fast per-part cycle "
            "once tooled (procres/subtractive.md #12)",
        ),
    ),
    lead_class="very fast per-part once tooled; high fixed tooling lead time",
    provenance=(
        _gek(
            "tolerance and profile-constancy requirements are uncited "
            "engineering-consensus (procres/subtractive.md #12)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_boolean_gate",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
BROACHING_CHECKS = DfmCheckSet(
    family="broaching",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "feature profile must be constant along the pull direction "
                "(no draft/taper unless a taper broach is specifically "
                "tooled), a hard geometric gate (procres/subtractive.md "
                "#12 DFM rule 1)"
            ),
        ),
    ),
)


# --- 15. Waterjet cutting --------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
WATERJET_RECORD = ProcessRecord(
    key="std.process/waterjet",
    name="Waterjet cutting (abrasive + pure)",
    din_8580_class="3.2.3",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="kerf_width",
            min=DimensionedValue.of("0.1", "mm"),
            max=DimensionedValue.of("1.5", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical", achievable=DimensionedValue.of("+/-0.1-0.25", "mm")
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="no tooling cost; moderate per-cut cost driven by "
            "abrasive consumption + cut time",
            note="sweet spot = one-off to low-volume thick/hard/heat-"
            "sensitive material cutting (procres/subtractive.md #15)",
        ),
    ),
    lead_class="no per-part tooling change; scales with thickness x perimeter",
    provenance=(
        _gek(
            "kerf/thickness/tolerance ranges are uncited engineering-"
            "consensus (procres/subtractive.md #15)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_min_floor",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
WATERJET_CHECKS = DfmCheckSet(
    family="waterjet",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_min_floor",
            provenance=_gek(
                "min feature size (internal corner, slot width) must be >= "
                "kerf_width + jet taper allowance at the given thickness "
                "(procres/subtractive.md #15 DFM rule 1)"
            ),
        ),
    ),
)


# --- 16. Laser cutting -----------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
LASER_CUTTING_RECORD = ProcessRecord(
    key="std.process/laser_cutting",
    name="Laser cutting",
    din_8580_class="3.2.3",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="part_thickness",
            min=DimensionedValue.of("0", "mm"),
            max=DimensionedValue.of("25-30", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical", achievable=DimensionedValue.of("+/-0.05-0.15", "mm")
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="cut edge", ra=DimensionedValue.of("1.6-6.3", "um")
        ),
    ),
    min_features=(
        MinFeature(
            feature="min hole diameter (clean piercing)",
            value=DimensionedValue.of("1x thickness", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="no tooling cost; fast cycle scaling inversely with thickness",
            note="sweet spot = sheet-metal blanks/2D profiles, prototype "
            "through high volume (procres/subtractive.md #16)",
        ),
    ),
    lead_class="no per-part tooling change, nesting-efficient",
    provenance=(
        _gek(
            "kerf/tolerance/HAZ/Ra ranges are uncited engineering-"
            "consensus (procres/subtractive.md #16)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_min_floor",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
LASER_CUTTING_CHECKS = DfmCheckSet(
    family="laser_cutting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_min_floor",
            provenance=_gek(
                "min hole diameter must be >= a declared multiple of "
                "thickness (pierce-quality containment), procres/"
                "subtractive.md #16 DFM rule 1"
            ),
        ),
    ),
)


# --- 17. Plasma cutting -----------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
PLASMA_CUTTING_RECORD = ProcessRecord(
    key="std.process/plasma_cutting",
    name="Plasma cutting",
    din_8580_class="3.2.3",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="part_thickness",
            min=DimensionedValue.of("0", "mm"),
            max=DimensionedValue.of("50+", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical", achievable=DimensionedValue.of("+/-0.5-1", "mm")
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="cut edge", ra=DimensionedValue.of("6.3-12.5", "um")
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="capital",
            driver_class="lowest capital cost of the thermal-cutting trio; fast on thick plate",
            note="sweet spot = structural steel plate, thick low-precision "
            "blanks (procres/subtractive.md #17)",
        ),
    ),
    lead_class="fast on thick plate; rougher edge often needs finishing",
    provenance=(
        _gek(
            "kerf/tolerance/HAZ/Ra ranges are uncited engineering-"
            "consensus (procres/subtractive.md #17)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_boolean_gate",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PLASMA_CUTTING_CHECKS = DfmCheckSet(
    family="plasma_cutting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "bevel/dross allowance must be declared on cut edges "
                "feeding a subsequent finishing op -- this process is "
                "rarely the final-dimension op for precision features "
                "(procres/subtractive.md #17 DFM rule 2)"
            ),
        ),
    ),
)


# --- 18. Oxy-fuel cutting ----------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
OXY_FUEL_CUTTING_RECORD = ProcessRecord(
    key="std.process/oxy_fuel_cutting",
    name="Oxy-fuel cutting",
    din_8580_class="3.2.3",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="part_thickness",
            min=DimensionedValue.of("3", "mm"),
            max=DimensionedValue.of("300+", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical", achievable=DimensionedValue.of("+/-1-2", "mm")
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="capital",
            driver_class="cheapest thick-plate cutting method, minimal equipment cost",
            note="sweet spot = heavy structural steel rough-cutting "
            "(procres/subtractive.md #18)",
        ),
    ),
    lead_class="slow relative to plasma/laser on thin material; economical on thick plate",
    provenance=(
        _gek(
            "thickness/kerf/tolerance ranges are uncited engineering-"
            "consensus (procres/subtractive.md #18)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_min_floor",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
OXY_FUEL_CUTTING_CHECKS = DfmCheckSet(
    family="oxy_fuel_cutting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "material class must be carbon or low-alloy steel -- a "
                "hard oxidation-chemistry gate (procres/subtractive.md "
                "#18 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_min_floor",
            provenance=_gek(
                "thickness must be >= a declared minimum practical "
                "thickness -- very thin sheet warps/burns through "
                "uncontrolled at this process's flame size (procres/"
                "subtractive.md #18 DFM rule 3)"
            ),
        ),
    ),
)


# --- 19. Electrochemical machining (ECM) ------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
ECM_RECORD = ProcessRecord(
    key="std.process/ecm",
    name="Electrochemical machining (ECM)",
    din_8580_class="3.2.3",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical", achievable=DimensionedValue.of("+/-0.02-0.1", "mm")
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="typical", ra=DimensionedValue.of("0.2-1.6", "um")
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="cathode tooling cost similar fixed-cost class to "
            "sinker EDM electrodes, but ZERO tool wear -- very long tool life",
            note="favors high-volume repeat cavities (turbine blade "
            "cooling holes, gun barrel rifling), procres/subtractive.md #19",
        ),
    ),
    lead_class="no tool wear once tooled; high-volume repeat-cavity economics",
    provenance=(
        _gek(
            "tolerance/Ra/no-HAZ values are uncited engineering-consensus "
            "(procres/subtractive.md #19); D269 sec.3's own taxonomy "
            "OMITTED this DIN-8580-named process family entirely"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_process_sequencing",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ECM_CHECKS = DfmCheckSet(
    family="ecm",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "material must be electrically conductive -- the same "
                "hard gate class as EDM (procres/subtractive.md #19 DFM "
                "rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "electrolyte flushing path must be declared for deep/"
                "narrow cavities, mirroring EDM's flushing-aspect-ratio "
                "concern as a process precondition (procres/"
                "subtractive.md #19 DFM rule 3)"
            ),
        ),
    ),
)


# --- 20. Gear hobbing / gear shaping ----------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
GEAR_HOBBING_SHAPING_RECORD = ProcessRecord(
    key="std.process/gear_hobbing_shaping",
    name="Gear hobbing / gear shaping",
    din_8580_class="3.2.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="gear_module",
            min=DimensionedValue.of("0.5", "mm"),
            max=DimensionedValue.of("25", "mm"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(
        SurfaceFinishEntry(
            condition="generated tooth flank", ra=DimensionedValue.of("0.4-1.6", "um")
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="high tooling cost (dedicated hob per module/"
            "pressure-angle); very fast per-part once tooled",
            note="sweet spot = production gear volumes, uneconomical for "
            "one-off gears (procres/subtractive.md #20)",
        ),
    ),
    lead_class="classic high-fixed/low-marginal economics, like broaching",
    provenance=(
        _gek(
            "module range and Ra values are uncited engineering-consensus; "
            "D269 sec.3 named only generic milling/turning/drilling/"
            "grinding without a gear-generating process (procres/"
            "subtractive.md #20)"
        ),
        _refuse(
            scope="tolerance_grades",
            detail="AGMA/ISO 1328 gear-quality-class tolerance tables are "
            "omitted; classes are cited by grade NAME only",
            refused_source="AGMA/ISO 1328 gear tolerance tables",
            lift_condition="a licensed copy of AGMA/ISO 1328 is obtained "
            "and its grade tables transcribed with in-row citation",
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_boolean_gate",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
GEAR_HOBBING_SHAPING_CHECKS = DfmCheckSet(
    family="gear_hobbing_shaping",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "internal gears require shaping (hobbing cannot cut "
                "internal teeth) -- a hard kinematic process-selection "
                "gate (procres/subtractive.md #20 DFM rule 2)"
            ),
        ),
    ),
)


__all__ = [
    "BORING_CHECKS",
    "BORING_RECORD",
    "BROACHING_CHECKS",
    "BROACHING_RECORD",
    "DRILLING_CHECKS",
    "DRILLING_RECORD",
    "ECM_CHECKS",
    "ECM_RECORD",
    "GEAR_HOBBING_SHAPING_CHECKS",
    "GEAR_HOBBING_SHAPING_RECORD",
    "HONING_CHECKS",
    "HONING_RECORD",
    "LAPPING_CHECKS",
    "LAPPING_RECORD",
    "LASER_CUTTING_CHECKS",
    "LASER_CUTTING_RECORD",
    "MILLING_CHECKS",
    "MILLING_RECORD",
    "OXY_FUEL_CUTTING_CHECKS",
    "OXY_FUEL_CUTTING_RECORD",
    "PLASMA_CUTTING_CHECKS",
    "PLASMA_CUTTING_RECORD",
    "REAMING_CHECKS",
    "REAMING_RECORD",
    "SAWING_CHECKS",
    "SAWING_RECORD",
    "SUPERFINISHING_CHECKS",
    "SUPERFINISHING_RECORD",
    "TAPPING_CHECKS",
    "TAPPING_RECORD",
    "TURNING_CHECKS",
    "TURNING_RECORD",
    "WATERJET_CHECKS",
    "WATERJET_RECORD",
]
