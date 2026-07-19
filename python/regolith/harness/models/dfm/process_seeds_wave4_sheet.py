"""WO-171 wave-4 population: the sheet-family remainder (procres/
sheet.md #21, #24-30 -- shearing, stamping/progressive-die, deep
drawing, roll forming, spinning, hydroforming, hemming/seaming,
incremental sheet forming). Blanking/punching (#22) and press-brake
bending (#23) already landed in `process_seeds_wave1_sheet.py`; this
wave closes the family to 10/10.

Every numeric value here is transcribed from the named dossier entry
with its provenance class preserved verbatim."""

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


# --- 21. Shearing ----------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
SHEARING_RECORD = ProcessRecord(
    key="std.process/shearing",
    name="Shearing (straight-blade guillotine)",
    din_8580_class="3.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="part_thickness",
            min=DimensionedValue.of("0.5", "mm"),
            max=DimensionedValue.of("25", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical", achievable=DimensionedValue.of("+/-0.1-0.3", "mm")
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="cheapest sheet-separation op, fast, minimal tooling",
            note="sweet spot = rectangular blanks off coil/sheet stock "
            "(procres/sheet.md #21)",
        ),
    ),
    lead_class="fast, feeds stamping/bend ops as the blanking-before-forming step",
    provenance=(
        _gek(
            "thickness/tolerance ranges are uncited engineering-consensus "
            "(procres/sheet.md #21)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_max_ceiling",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SHEARING_CHECKS = DfmCheckSet(
    family="shearing",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "cut must be a straight line only -- profile cuts require "
                "punching/laser instead (procres/sheet.md #21 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_max_ceiling",
            provenance=_gek(
                "material thickness must not exceed the declared shear "
                "capacity (procres/sheet.md #21 DFM rule 2)"
            ),
        ),
    ),
)


# --- 24. Stamping (progressive die) ---------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
STAMPING_PROGRESSIVE_RECORD = ProcessRecord(
    key="std.process/stamping_progressive",
    name="Stamping (progressive die)",
    din_8580_class="3.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="carrier-strip width (connecting web between stations)",
            value=DimensionedValue.of("declared-min-feed-strength", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="highest fixed tooling cost of the sheet family "
            "(multi-station custom die)",
            note="lowest marginal per-part cost at true production volume; "
            "sweet spot = 10,000s-millions (procres/sheet.md #24); this "
            "IS the D268 die-set program's ultimate production intent",
        ),
    ),
    lead_class="high-volume-only, per-station tooling complexity compounds",
    provenance=(
        _gek(
            "carrier-strip and station-sequence values are uncited "
            "engineering-consensus (procres/sheet.md #24); composes the "
            "per-stage envelopes of blanking/punching (#22) and press-"
            "brake bending (#23)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_min_floor",
        "regolith.harness.models.dfm.checks:check_process_sequencing",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
STAMPING_PROGRESSIVE_CHECKS = DfmCheckSet(
    family="stamping_progressive",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_min_floor",
            provenance=_gek(
                "carrier-strip width must be >= a declared minimum for "
                "feed-strength -- the strip must not tear while being "
                "indexed through the die (procres/sheet.md #24 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "station sequence must respect feature-dependency order "
                "(a piercing station's hole must exist before a "
                "downstream forming station bends across it), a "
                "sequencing/composition predicate (procres/sheet.md #24 "
                "DFM rule 2)"
            ),
        ),
    ),
)


# --- 25. Deep drawing --------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
DEEP_DRAWING_RECORD = ProcessRecord(
    key="std.process/deep_drawing",
    name="Deep drawing",
    din_8580_class="3.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="punch/die corner radius",
            value=DimensionedValue.of("4-10x thickness", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="moderate-to-high tooling cost (punch+die+blankholder set)",
            note="sweet spot = cans, cups, enclosures, mid-to-high volume "
            "(procres/sheet.md #25)",
        ),
    ),
    lead_class="single or multi-stage, moderate cycle time",
    provenance=(
        _gek(
            "draw-ratio limit and corner-radius-vs-thickness values are "
            "uncited engineering-consensus (procres/sheet.md #25)"
        ),
        _refuse(
            scope="min_features",
            detail="draw-ratio limit-of-draw tables for precise per-alloy "
            "numbers are omitted",
            refused_source="ASM Sheet Metal Forming Handbook draw-ratio tables",
            lift_condition="a licensed copy is obtained and its per-alloy "
            "rows transcribed with in-row citation",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_ratio_max",
        "regolith.harness.models.dfm.checks:check_min_floor",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
DEEP_DRAWING_CHECKS = DfmCheckSet(
    family="deep_drawing",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "draw ratio (blank diameter / punch diameter) must not "
                "exceed the material-class max-single-draw-ratio (~2.0-"
                "2.2) else require a declared multi-stage/redraw sequence "
                "(procres/sheet.md #25 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_min_floor",
            provenance=_gek(
                "punch/die corner radius must be >= a declared multiple "
                "of thickness (tearing-risk threshold), procres/sheet.md "
                "#25 DFM rule 2"
            ),
        ),
    ),
)


# --- 26. Roll forming ----------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
ROLL_FORMING_RECORD = ProcessRecord(
    key="std.process/roll_forming",
    name="Roll forming",
    din_8580_class="3.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="part_thickness",
            min=DimensionedValue.of("0.3", "mm"),
            max=DimensionedValue.of("6", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="cross-section dimensions",
            achievable=DimensionedValue.of("+/-0.1-0.3", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="very high tooling cost (custom roll-station "
            "tooling per profile), extremely low marginal cost per "
            "linear meter once tooled",
            note="sweet spot = long-run constant-section structural "
            "members (procres/sheet.md #26)",
        ),
    ),
    lead_class="continuous, essentially unlimited length",
    provenance=(
        _gek(
            "thickness/tolerance/station-count values are uncited "
            "engineering-consensus (procres/sheet.md #26)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_boolean_gate",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ROLL_FORMING_CHECKS = DfmCheckSet(
    family="roll_forming",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "cross-section must be constant along the part's length "
                "-- a hard geometric gate, unlike press-brake which can "
                "bend a pre-cut blank into any planar shape per bend "
                "(procres/sheet.md #26 DFM rule 1)"
            ),
        ),
    ),
)


# --- 27. Spinning ---------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
SPINNING_RECORD = ProcessRecord(
    key="std.process/spinning",
    name="Spinning (metal spinning)",
    din_8580_class="3.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="wall thickness after spinning (sine-law, simple cone)",
            value=DimensionedValue.of("t0*sin(half_angle)", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="LOW tooling cost (a mandrel, often simpler/"
            "cheaper than a full draw die)",
            note="sweet spot = low-to-mid volume round parts, especially "
            "large-diameter parts (procres/sheet.md #27)",
        ),
    ),
    lead_class="labor/skill-intensive, moderate cycle time",
    provenance=(
        _gek(
            "sine-law thinning relation is a derivable closed-form "
            "geometric relation, safe to state as physics (procres/"
            "sheet.md #27)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_min_floor",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SPINNING_CHECKS = DfmCheckSet(
    family="spinning",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "geometry must be a body of revolution -- the same hard "
                "gate as turning (procres/sheet.md #27 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_min_floor",
            provenance=_gek(
                "predicted wall thickness (sine-law) at the thinnest "
                "point must be >= a declared minimum structural "
                "thickness (procres/sheet.md #27 DFM rule 3)"
            ),
        ),
    ),
)


# --- 28. Hydroforming (sheet) --------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
HYDROFORMING_RECORD = ProcessRecord(
    key="std.process/hydroforming_sheet",
    name="Hydroforming (sheet)",
    din_8580_class="3.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="lower tooling cost than matched-die stamping "
            "(single-sided die only, fluid acts as the other tool)",
            note="slower cycle time; favors low-to-mid volume complex-"
            "contour sheet parts (procres/sheet.md #28)",
        ),
    ),
    lead_class="slower than mechanical stamping (fluid pressurization)",
    provenance=(
        _gek(
            "pressure/thickness-uniformity values are uncited "
            "engineering-consensus (procres/sheet.md #28); tube "
            "hydroforming is a related-but-distinct bulk-forming-adjacent "
            "variant not separately enumerated this pass"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_boolean_gate",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
HYDROFORMING_CHECKS = DfmCheckSet(
    family="hydroforming_sheet",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "only one hard die surface is required -- a cost/"
                "tooling-class predicate, not geometric (procres/"
                "sheet.md #28 DFM rule 1)"
            ),
        ),
    ),
)


# --- 29. Hemming / seaming ------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
HEMMING_SEAMING_RECORD = ProcessRecord(
    key="std.process/hemming_seaming",
    name="Hemming / seaming",
    din_8580_class="3.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="hem radius", value=DimensionedValue.of("~1x thickness", "mm")
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="low incremental cost added to an existing bend operation",
            note="sweet spot = edge safety/finish and light mechanical "
            "joining of two thin panels without rivets/welds (procres/"
            "sheet.md #29); a genuinely cross-family process (forming "
            "AND joining, see joining.md cross-link)",
        ),
    ),
    lead_class="incremental to an existing bend op",
    provenance=(
        _gek(
            "hem-radius/flange-length values are uncited engineering-"
            "consensus (procres/sheet.md #29)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_min_floor",
        "regolith.harness.models.dfm.checks:check_press_brake_bend_radius",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
HEMMING_SEAMING_CHECKS = DfmCheckSet(
    family="hemming_seaming",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_min_floor",
            provenance=_gek(
                "flange length beyond the hem line must be >= a declared "
                "minimum for tooling clearance (procres/sheet.md #29 DFM "
                "rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_press_brake_bend_radius",
            provenance=_gek(
                "hem-bend material must tolerate the tight closing radius "
                "without cracking -- the SAME bend-radius-vs-material-"
                "class threshold shape as press-brake bending (procres/"
                "sheet.md #29 DFM rule 2)"
            ),
        ),
    ),
)


# --- 30. Incremental sheet forming (ISF) ----------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
ISF_RECORD = ProcessRecord(
    key="std.process/isf",
    name="Incremental sheet forming (ISF)",
    din_8580_class="3.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="max formable wall angle", value=DimensionedValue.of("50-70", "deg")
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="zero dedicated tooling, CNC-time-dominated cost "
            "(opposite economics from stamping)",
            note="sweet spot = one-off/prototype/very-low-volume complex "
            "sheet shapes (procres/sheet.md #30)",
        ),
    ),
    lead_class="slow, point-by-point toolpath",
    provenance=(
        _gek(
            "wall-angle/thinning values are drawn from published academic-"
            "research consensus ('academic-GEK'), still uncited in this "
            "dossier, same owner-visible posture as other GEK entries "
            "(procres/sheet.md #30)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_max_ceiling",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ISF_CHECKS = DfmCheckSet(
    family="isf",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_max_ceiling",
            provenance=_gek(
                "wall angle must not exceed the declared max-formable-"
                "angle (fracture-risk threshold), procres/sheet.md #30 "
                "DFM rule 1"
            ),
        ),
    ),
)


__all__ = [
    "DEEP_DRAWING_CHECKS",
    "DEEP_DRAWING_RECORD",
    "HEMMING_SEAMING_CHECKS",
    "HEMMING_SEAMING_RECORD",
    "HYDROFORMING_CHECKS",
    "HYDROFORMING_RECORD",
    "ISF_CHECKS",
    "ISF_RECORD",
    "ROLL_FORMING_CHECKS",
    "ROLL_FORMING_RECORD",
    "SHEARING_CHECKS",
    "SHEARING_RECORD",
    "SPINNING_CHECKS",
    "SPINNING_RECORD",
    "STAMPING_PROGRESSIVE_CHECKS",
    "STAMPING_PROGRESSIVE_RECORD",
]
