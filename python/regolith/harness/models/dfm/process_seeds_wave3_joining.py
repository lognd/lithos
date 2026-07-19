"""WO-171 wave-3 population: the joining family (procres/joining.md
#55-67, DIN 8580 Fuegen) -- TIG, MIG, stick, resistance spot, brazing,
soldering, adhesive bonding, threaded fasteners, riveting, press fits,
FSW, laser welding, ultrasonic welding.

Hemming/seaming (sheet.md #29) is explicitly a joining-capable process
when used as a double-seam but is counted ONCE in sheet.md per the
dossier's own NO-DUPLICATION note -- not re-recorded here."""

from __future__ import annotations

from regolith.backends.quantity import DimensionedValue
from regolith.harness.models.dfm.process_records import (
    CostDriver,
    DfmCheckEntry,
    DfmCheckSet,
    ProcessRecord,
    ProvenanceNote,
    SizeLimit,
    ToleranceGrade,
)


def _gek(detail: str) -> ProvenanceNote:
    return ProvenanceNote(posture="gek", scope="record", detail=detail)


_AWS_ASME_REFUSAL = ProvenanceNote(
    posture="named_refusal",
    scope="tolerance_grades",
    detail="AWS D1.1 / ASME BPVC Section IX verbatim weld-procedure "
    "tables are omitted (procres/joining.md standing refusal)",
    refused_source="AWS D1.1 (structural welding code) / ASME BPVC "
    "Section IX (welding qualification)",
    lift_condition="a licensed copy of AWS D1.1 or ASME BPVC Sec.IX is "
    "obtained and its rows are transcribed with in-row citation",
)


def _gap_record(
    key: str,
    name: str,
    din: str,
    min_gap: str,
    max_gap: str,
    tol_condition: str,
    cost_note: str,
    lead: str,
    detail: str,
    extra_provenance: tuple[ProvenanceNote, ...] = (),
) -> ProcessRecord:
    """Shared shape for the joint-fit-up-gap-governed welding entries
    (TIG/MIG/stick/brazing/soldering/adhesive/laser/press-fit-adjacent)
    -- factored ONCE rather than duplicated per record (NO-DUPLICATION)."""
    return ProcessRecord(
        key=key,
        name=name,
        din_8580_class=din,
        materials=(),
        size_limits=(
            SizeLimit(
                dimension="joint_gap",
                min=DimensionedValue.of(min_gap, "mm"),
                max=DimensionedValue.of(max_gap, "mm"),
            ),
        ),
        tolerance_grades=(
            ToleranceGrade(
                condition=tol_condition, achievable=DimensionedValue.of(max_gap, "mm")
            ),
        ),
        surface_finish=(),
        min_features=(),
        cost_drivers=(CostDriver(driver="joining_cost", driver_class=cost_note),),
        lead_class=lead,
        provenance=(_gek(detail), *extra_provenance),
        dfm_check_ids=("regolith.harness.models.dfm.checks:check_value_window",),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
TIG_RECORD = _gap_record(
    "std.process/tig_welding",
    "TIG welding (GTAW)",
    "4.1.1",
    "0.1",
    "0.3",
    "best-results fit-up, TIG is fit-up-sensitive",
    "slow, labor-intensive, highest quality/control",
    "precision/thin/exotic-alloy welds, low-to-mid volume",
    "joint fit-up gap and thickness-class values are uncited "
    "engineering-consensus ranges (procres/joining.md #55)",
    (_AWS_ASME_REFUSAL,),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
MIG_RECORD = _gap_record(
    "std.process/mig_welding",
    "MIG welding (GMAW)",
    "4.1.2",
    "0.1",
    "1.0",
    "more forgiving than TIG, can bridge small gaps via wire feed",
    "fast deposition, good automation economics",
    "production-volume structural/sheet welding",
    "joint fit-up window (wider/looser than TIG) is uncited "
    "engineering-consensus (procres/joining.md #56)",
    (_AWS_ASME_REFUSAL,),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
STICK_RECORD = _gap_record(
    "std.process/stick_welding",
    "Stick welding (SMAW)",
    "4.1.3",
    "0.2",
    "1.5",
    "roughest weld appearance/lowest precision of the arc trio",
    "lowest equipment cost, slowest, portable",
    "field repair, heavy structural steel, low volume",
    "min-thickness floor and fit-up values are uncited engineering-"
    "consensus (procres/joining.md #57)",
    (_AWS_ASME_REFUSAL,),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
RESISTANCE_SPOT_WELDING_RECORD = ProcessRecord(
    key="std.process/resistance_spot_welding",
    name="Resistance spot welding",
    din_8580_class="4.1.4",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="sheet_thickness",
            min=DimensionedValue.of("0.5", "mm"),
            max=DimensionedValue.of("3", "mm"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="joining_cost",
            driver_class="very fast per-weld cycle (seconds), minimal "
            "consumable cost (no filler)",
            note="high-volume sheet-metal assembly (procres/joining.md "
            "#58); direct composition partner to the sheet family",
        ),
    ),
    lead_class="high-volume sheet-metal assembly",
    provenance=(
        _gek(
            "nugget-diameter-vs-thickness relationship and spacing/edge-"
            "distance minimums are uncited engineering-consensus "
            "(procres/joining.md #58)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_value_window",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
BRAZING_RECORD = _gap_record(
    "std.process/brazing",
    "Brazing",
    "4.2.1",
    "0.025",
    "0.25",
    "capillary window, too wide or too tight both degrade strength",
    "moderate equipment cost, good for dissimilar-metal joints",
    "tool-tip attachment, HVAC tubing, dissimilar-metal assemblies, any volume",
    "joint-gap capillary window is uncited engineering-consensus "
    "(procres/joining.md #59); the two-sided window (too tight ALSO "
    "fails) is a real, distinct predicate kind from welding fit-up",
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SOLDERING_RECORD = _gap_record(
    "std.process/soldering",
    "Soldering",
    "4.2.2",
    "0.05",
    "0.15",
    "component-to-pad capillary gap, finer scale than brazing",
    "very low per-joint cost, fast (reflow ovens)",
    "electronics assembly, any volume",
    "joint-gap capillary window is uncited engineering-consensus "
    "(procres/joining.md #60); same predicate KIND as brazing at a "
    "tighter numeric range",
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ADHESIVE_BONDING_RECORD = _gap_record(
    "std.process/adhesive_bonding",
    "Adhesive bonding",
    "4.3.1",
    "0.1",
    "0.5",
    "adhesive-specific bond-line-thickness window",
    "LOW tooling cost, enables dissimilar-material assembly",
    "composite/dissimilar-material assembly, any volume",
    "bond-line-thickness window is uncited engineering-consensus "
    "(procres/joining.md #61); the shear-strength x area sizing "
    "formula is a closed-form GEK relation, safe as physics",
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
THREADED_FASTENERS_RECORD = ProcessRecord(
    key="std.process/threaded_fasteners",
    name="Threaded fasteners (bolted joints)",
    din_8580_class="4.4.1",
    materials=("std.fasteners",),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="joining_cost",
            driver_class="LOWEST fixed-cost joining method here (off-"
            "the-shelf catalog parts, zero custom tooling)",
            note="fully reusable/serviceable; any volume, especially "
            "where disassembly/maintenance access matters (procres/"
            "joining.md #62); direct primary joining method for the "
            "D268 die-set program",
        ),
    ),
    lead_class="any volume, reusable/serviceable assemblies",
    provenance=(
        _gek(
            "K*T=F*d torque-to-preload relation FORM is a closed-form "
            "GEK relation; catalog bounds come from std.fasteners "
            "[HAVE] (procres/joining.md #62)"
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="tolerance_grades",
            detail="precise per-coating/lubricant K-factor tables "
            "(fastener handbooks) and ISO 965/286 verbatim fit-class "
            "tables are omitted",
            refused_source="fastener handbook K-factor tables / ISO 965 and 286",
            lift_condition="a licensed copy of the fastener handbook or "
            "ISO 965/286 is obtained and its rows are transcribed with "
            "in-row citation",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_value_window",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
RIVETING_RECORD = ProcessRecord(
    key="std.process/riveting",
    name="Riveting",
    din_8580_class="4.4.2",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="hole_clearance_over_rivet_diameter",
            min=DimensionedValue.of("0.05", "mm"),
            max=DimensionedValue.of("0.15", "mm"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="joining_cost",
            driver_class="low per-joint cost, permanent, fast for blind "
            "rivets (one-sided access)",
            note="permanent sheet-metal/structural assembly, any volume, "
            "especially one-sided-access assemblies (procres/"
            "joining.md #63)",
        ),
    ),
    lead_class="permanent sheet-metal/structural assembly, any volume",
    provenance=(
        _gek(
            "hole-clearance, spacing, and edge-distance minimums (2-3x "
            "diameter from edge, 3-4x between rivets) are uncited "
            "engineering-consensus (procres/joining.md #63)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PRESS_FITS_RECORD = ProcessRecord(
    key="std.process/press_fits",
    name="Press fits",
    din_8580_class="4.4.3",
    materials=("std.bearings",),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="joining_cost",
            driver_class="no fastener/consumable cost, fast assembly "
            "(thermal-assist adds cycle time)",
            note="bearing/bushing/pin retention, any volume (procres/"
            "joining.md #64); confirms the earlier ISO-fit-vocabulary "
            "gap flag as a real, load-bearing missing piece",
        ),
    ),
    lead_class="bearing/bushing/pin retention, any volume",
    provenance=(
        _gek(
            "press-force-vs-interference is a closed-form-derivable "
            "relation, safe as GEK physics; fit-class names (e.g. "
            "H7/p6) are cited by NAME only (procres/joining.md #64)"
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="tolerance_grades",
            detail="ISO 286 H7/p6-style verbatim per-diameter "
            "interference-value tables are omitted, cited by fit-class "
            "NAME only",
            refused_source="ISO 286 fit-class interference tables",
            lift_condition="a licensed copy of ISO 286 is obtained and "
            "its rows are transcribed with in-row citation",
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_boolean_gate",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
FSW_RECORD = ProcessRecord(
    key="std.process/friction_stir_welding",
    name="Friction stir welding (FSW)",
    din_8580_class="4.1.5",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="joining_cost",
            driver_class="high equipment cost (rigid, high-thrust "
            "machine), no filler/consumable cost",
            note="aluminum structural assembly (aerospace/rail/marine), "
            "mid-to-high volume (procres/joining.md #65)",
        ),
    ),
    lead_class="aluminum structural assembly, mid-to-high volume",
    provenance=(
        _gek(
            "linear-traverse-path geometric constraint and fixture-"
            "clamp-force requirement are uncited engineering-consensus "
            "(procres/joining.md #65); solid-state process avoids melt-"
            "related porosity/cracking defects, a real positive claim"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_boolean_gate",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
LASER_WELDING_RECORD = _gap_record(
    "std.process/laser_welding",
    "Laser welding",
    "4.1.6",
    "0.0",
    "0.1",
    "CRITICAL and tight, very little gap-bridging ability",
    "high equipment cost, very fast cycle, minimal distortion",
    "high-volume precision automated welding (automotive/electronics)",
    "tight joint-fit-up-gap threshold is uncited engineering-consensus "
    "(procres/joining.md #66); aluminum reflectivity is a real, named "
    "process challenge",
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ULTRASONIC_WELDING_RECORD = ProcessRecord(
    key="std.process/ultrasonic_welding",
    name="Ultrasonic welding (plastics + metal foil)",
    din_8580_class="4.1.7",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="joining_cost",
            driver_class="extremely fast cycle (fractions of a second), "
            "moderate tooling cost (custom horn per joint geometry)",
            note="high-volume plastic-part and battery-tab assembly "
            "(procres/joining.md #67)",
        ),
    ),
    lead_class="high-volume plastic-part and battery-tab assembly",
    provenance=(
        _gek(
            "energy-director joint-geometry requirement is a real, "
            "named design requirement unique to this process (procres/"
            "joining.md #67)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_boolean_gate",),
)

# --- check sets ---------------------------------------------------------


def _window_checks(family: str, detail: str) -> DfmCheckSet:
    return DfmCheckSet(
        family=family,
        checks=(
            DfmCheckEntry(
                check_id="regolith.harness.models.dfm.checks:check_value_window",
                provenance=_gek(detail),
            ),
        ),
    )


def _bool_checks(family: str, detail: str) -> DfmCheckSet:
    return DfmCheckSet(
        family=family,
        checks=(
            DfmCheckEntry(
                check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
                provenance=_gek(detail),
            ),
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
TIG_CHECKS = _window_checks(
    "tig_welding",
    "joint fit-up gap <= declared max for the process/thickness "
    "(procres/joining.md #55 DFM rule 1)",
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
MIG_CHECKS = _window_checks(
    "mig_welding",
    "joint fit-up gap window, wider/looser than TIG (procres/"
    "joining.md #56 DFM rule 1)",
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
STICK_CHECKS = _window_checks(
    "stick_welding",
    "min thickness floor, thin material burns through easily "
    "(procres/joining.md #57 DFM rule 1)",
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
RESISTANCE_SPOT_WELDING_CHECKS = DfmCheckSet(
    family="resistance_spot_welding",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "electrode two-sided access declared/verified, a hard "
                "geometric gate (procres/joining.md #58 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "weld-spot spacing >= declared minimum, shunting-"
                "current risk (procres/joining.md #58 DFM rule 2)"
            ),
        ),
    ),
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
BRAZING_CHECKS = _window_checks(
    "brazing",
    "joint_gap within declared min/max capillary window, the "
    "signature brazing DFM rule (procres/joining.md #59 DFM rule 1)",
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
SOLDERING_CHECKS = _window_checks(
    "soldering",
    "joint_gap within declared capillary window, same predicate KIND "
    "as brazing (procres/joining.md #60 DFM rule 1)",
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
ADHESIVE_BONDING_CHECKS = _window_checks(
    "adhesive_bonding",
    "bond_line_thickness within declared adhesive-specific window "
    "(procres/joining.md #61 DFM rule 1)",
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
THREADED_FASTENERS_CHECKS = DfmCheckSet(
    family="threaded_fasteners",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "bolt-hole clearance diameter matches declared fastener "
                "size + clearance class (procres/joining.md #62 DFM "
                "rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "bolt-circle/edge-distance spacing >= declared minimum "
                "(procres/joining.md #62 DFM rule 2)"
            ),
        ),
    ),
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
RIVETING_CHECKS = DfmCheckSet(
    family="riveting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "hole diameter matches declared rivet size + clearance "
                "class (procres/joining.md #63 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "one-sided vs two-sided access declared, gating solid-"
                "vs-blind rivet selection (procres/joining.md #63 DFM "
                "rule 3)"
            ),
        ),
    ),
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
PRESS_FITS_CHECKS = _bool_checks(
    "press_fits",
    "bore and shaft tolerance CLASSES declared, a fit-class "
    "containment predicate (procres/joining.md #64 DFM rule 1)",
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
FSW_CHECKS = _bool_checks(
    "friction_stir_welding",
    "joint path must be accessible to a linear (or curved-but-"
    "traversable) tool path (procres/joining.md #65 DFM rule 1)",
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
LASER_WELDING_CHECKS = _window_checks(
    "laser_welding",
    "joint fit-up gap <= declared max, tighter threshold than MIG "
    "(procres/joining.md #66 DFM rule 1)",
)
# frob:doc docs/modules/py-harness.md#models-dfm-process
ULTRASONIC_WELDING_CHECKS = _bool_checks(
    "ultrasonic_welding",
    "energy-director geometry declared present at the joint line, a "
    "hard design-requirement gate (procres/joining.md #67 DFM rule 1)",
)

__all__ = [
    "ADHESIVE_BONDING_CHECKS",
    "ADHESIVE_BONDING_RECORD",
    "BRAZING_CHECKS",
    "BRAZING_RECORD",
    "FSW_CHECKS",
    "FSW_RECORD",
    "LASER_WELDING_CHECKS",
    "LASER_WELDING_RECORD",
    "MIG_CHECKS",
    "MIG_RECORD",
    "PRESS_FITS_CHECKS",
    "PRESS_FITS_RECORD",
    "RESISTANCE_SPOT_WELDING_CHECKS",
    "RESISTANCE_SPOT_WELDING_RECORD",
    "RIVETING_CHECKS",
    "RIVETING_RECORD",
    "SOLDERING_CHECKS",
    "SOLDERING_RECORD",
    "STICK_CHECKS",
    "STICK_RECORD",
    "THREADED_FASTENERS_CHECKS",
    "THREADED_FASTENERS_RECORD",
    "TIG_CHECKS",
    "TIG_RECORD",
    "ULTRASONIC_WELDING_CHECKS",
    "ULTRASONIC_WELDING_RECORD",
]
