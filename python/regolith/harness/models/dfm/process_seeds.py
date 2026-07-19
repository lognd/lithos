"""Two seed `std.process` records exercising the WO-168 schema end to
end (deliverable 4): wire EDM and quench+temper (Q&T), the D269
Tier-1 priority pair, values transcribed from the process-research
recon dossiers (`procres/subtractive.md` #13, `procres/heat_treatment.
md` #77) with their provenance classes PRESERVED verbatim -- neither
seed invents a citation the dossier did not already carry.

Bulk population across the rest of the priority list is WO-169/170/
171's scope (non-goal here); these two exist only to prove the schema
is populatable and that a `named_refusal` entry round-trips as a real
schema citizen, per WO-168 acceptance.
"""

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

# frob:doc docs/modules/py-harness.md#models-dfm-process
WIRE_EDM_RECORD = ProcessRecord(
    key="std.process/wire_edm",
    name="Wire EDM (traveling-wire electrical discharge machining)",
    din_8580_class="3.2.3",
    materials=("std.materials/tool_steel_d2", "std.materials/tool_steel_a2"),
    size_limits=(
        SizeLimit(
            dimension="part_thickness",
            min=DimensionedValue.of("1", "mm"),
            max=DimensionedValue.of("300", "mm"),
        ),
        SizeLimit(
            dimension="kerf_width",
            min=DimensionedValue.of("0.02", "mm"),
            max=DimensionedValue.of("0.3", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="multi-pass skim cut",
            achievable=DimensionedValue.of("+/-0.002-0.01", "mm"),
        ),
        ToleranceGrade(
            condition="single-pass rough cut",
            achievable=DimensionedValue.of("+/-0.02-0.05", "mm"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="first rough pass",
            ra=DimensionedValue.of("3.2+", "um"),
        ),
        SurfaceFinishEntry(
            condition="final skim pass",
            ra=DimensionedValue.of("0.2-0.4", "um"),
        ),
    ),
    min_features=(
        MinFeature(
            feature="internal corner radius",
            value=DimensionedValue.of("kerf_width/2 + spark_gap", "mm"),
        ),
        MinFeature(
            feature="recast layer depth (single rough pass)",
            value=DimensionedValue.of("10-15", "um"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="fixturing + CAM program time",
            note="one-time per profile; no per-part tool wear",
        ),
        CostDriver(
            driver="tooling_amortization",
            driver_class="near-zero fixed tooling",
            note="wire is a cheap consumable, no dedicated per-part tool "
            "-- the reason the D268 die-set program prefers this process "
            "for hardened profile cutting over grinding a profile by hand",
        ),
    ),
    lead_class="hours-to-a-day per part, scaling with perimeter x thickness "
    "x skim-pass count",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="all numeric envelope values (kerf, tolerance, Ra, "
            "recast layer, taper) are uncited engineering-consensus "
            "ranges corroborated by vendor technical pages this recon "
            "pass; no PD-GOV source was independently verified for wire "
            "EDM process parameters specifically (procres/subtractive.md "
            "#13)",
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="tolerance_grades",
            detail="vendor EDM parameter tables (speeds/feeds/Ra-vs-"
            "parameter lookups) are omitted; only physics-level GEK "
            "ranges are stated",
            refused_source="vendor EDM application-data tables (e.g. "
            "Sodick/Mitsubishi/Fanuc) and the ASM Machining Data Handbook "
            "class of source",
            lift_condition="a licensed copy of the vendor tables or ASM "
            "Machining Data Handbook is obtained and its rows are "
            "transcribed with in-row citation",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_wire_edm_corner_radius",
        "regolith.harness.models.dfm.checks:check_wire_edm_start_hole",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
QUENCH_TEMPER_RECORD = ProcessRecord(
    key="std.process/quench_temper",
    name="Quench + temper (Q&T)",
    din_8580_class="4.2",
    materials=("std.materials/tool_steel_d2", "std.materials/tool_steel_a2"),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="hardness after quench, before temper (tool steel)",
            value=DimensionedValue.of("58-65+", "HRC"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="furnace + quench-media batch process",
            note="cycle time on the order of hours",
        ),
        CostDriver(
            driver="rework_risk",
            driver_class="distortion-driven finishing step",
            note="quench distortion sometimes requires a post-heat-"
            "treat straightening or finish-grinding step (cross-link: "
            "procres/subtractive.md #7 grinding)",
        ),
    ),
    lead_class="batch process, cycle time on the order of hours",
    provenance=(
        ProvenanceNote(
            posture="pd_gov",
            scope="record",
            detail="MIL-H-6875 covers hardening + tempering qualitatively, "
            "spot-verified real and DTIC/everyspec-hosted this recon pass "
            "(procres/heat_treatment.md #77)",
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="tolerance_grades",
            detail="precise per-alloy hardness-vs-temper-temperature "
            "curves (the ASM Handbook tempering-curve charts) are "
            "omitted; only the GEK-tier qualitative curve SHAPE is "
            "stated -- the sanctioned path to a predicted (not "
            "transcribed) curve is feldspar T-0018's Hollomon-Jaffe-"
            "class model per D270 ruling 1",
            refused_source="ASM Metals Handbook tempering-curve charts "
            "(per-alloy, e.g. D2/A2 tool steel)",
            lift_condition="feldspar T-0018's Hollomon-Jaffe model lands "
            "and predicts the curve directly, or a licensed ASM Handbook "
            "excerpt is transcribed with in-row citation",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_quench_section_uniformity",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
WIRE_EDM_CHECKS = DfmCheckSet(
    family="wire_edm",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_wire_edm_corner_radius",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="internal_corner_radius >= kerf_width/2 + "
                "declared_spark_gap is a containment predicate derived "
                "from the GEK-tier kerf/spark-gap geometry (procres/"
                "subtractive.md #13 DFM rule 2), analogous to "
                "check_tool_fit's containment logic",
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_wire_edm_start_hole",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="a pre-drilled start hole for wire threading is "
                "required for any fully-enclosed internal profile "
                "(procres/subtractive.md #13 DFM rule 8); a sequencing "
                "predicate, not a numeric threshold",
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
QUENCH_TEMPER_CHECKS = DfmCheckSet(
    family="quench_temper",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_quench_section_uniformity",
            provenance=ProvenanceNote(
                posture="pd_gov",
                scope="record",
                detail="MIL-H-6875 names quench-induced distortion/"
                "cracking risk from section-thickness non-uniformity as "
                "a real, documented heat-treat risk (procres/"
                "heat_treatment.md #77 DFM rule 2)",
            ),
        ),
    ),
)

__all__ = [
    "QUENCH_TEMPER_CHECKS",
    "QUENCH_TEMPER_RECORD",
    "WIRE_EDM_CHECKS",
    "WIRE_EDM_RECORD",
]
