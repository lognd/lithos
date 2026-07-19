"""WO-169 wave-1 population: the stamping-relevant sheet family
(procres/sheet.md #22 blanking/punching, #23 press-brake bending) --
the D268 die-set program's END PRODUCT (the die set wire-EDM'd + heat-
treated elsewhere in this WO ultimately performs blanking/punching in
production).

Punch-die clearance-percent-by-material tables (Machinery's Handbook/
ASM Sheet Metal Forming Handbook class) are a NAMED REFUSAL per the
dossier's own finding -- the record still lands with the qualitative
existence of a thickness-percent relationship stated, and the actual
per-material clearance bounds passed as DECLARED caller data to
`check_punch_die_clearance` rather than a hard-coded constant."""

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

# frob:doc docs/modules/py-harness.md#models-dfm-process
STAMPING_BLANKING_RECORD = ProcessRecord(
    key="std.process/stamping_blanking",
    name="Blanking / punching (stamping)",
    din_8580_class="3.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="part_thickness",
            min=DimensionedValue.of("0.2", "mm"),
            max=DimensionedValue.of("13", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical stamped profile",
            achievable=DimensionedValue.of("+/-0.05-0.15", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="minimum hole diameter",
            value=DimensionedValue.of("1x thickness", "mm"),
        ),
        MinFeature(
            feature="minimum web/edge distance",
            value=DimensionedValue.of("1.5-2x thickness", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="high fixed tooling cost (dedicated punch+die per profile)",
            note="extremely low marginal cost per part once tooled -- "
            "the archetypal progressive-die economics (procres/"
            "sheet.md #22)",
        ),
    ),
    lead_class="high-volume-only (1000s-millions); uneconomical below "
    "a few hundred units unless amortized across a multi-feature "
    "progressive die",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="thickness/tolerance/min-feature ranges are uncited "
            "engineering-consensus values (procres/sheet.md #22)",
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="min_features",
            detail="punch-die clearance-percent-by-material tables are "
            "omitted; only the qualitative existence of a "
            "thickness-percent relationship is stated",
            refused_source="Machinery's Handbook / ASM Sheet Metal "
            "Forming Handbook punch-die clearance tables",
            lift_condition="a licensed copy of Machinery's Handbook or "
            "the ASM Sheet Metal Forming Handbook is obtained and its "
            "clearance-percent-by-material rows are transcribed with "
            "in-row citation",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_punch_die_clearance",
        "regolith.harness.models.dfm.checks:check_press_tonnage",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PRESS_BRAKE_BEND_RECORD = ProcessRecord(
    key="std.process/press_brake_bend",
    name="Press-brake bending",
    din_8580_class="3.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="part_thickness",
            min=DimensionedValue.of("0.5", "mm"),
            max=DimensionedValue.of("25", "mm"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="minimum bend radius (ductile steel/aluminum)",
            value=DimensionedValue.of("1x thickness", "mm"),
        ),
        MinFeature(
            feature="minimum flange length",
            value=DimensionedValue.of("3-4x thickness + bend radius", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="low-to-moderate tooling cost (generic V-die + "
            "punch, reusable across many part profiles)",
            note="setup dominated by bend-sequence planning (procres/sheet.md #23)",
        ),
    ),
    lead_class="low-to-mid volume (prototype through several thousand units)",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="bend-radius/flange-length/springback figures are "
            "uncited engineering-consensus values (procres/sheet.md "
            "#23); the K-factor/flat-pattern math itself is already "
            "modeled as real OCCT geometry in this repo's schema.py:242, "
            "a distinct, already-real component this record's provenance "
            "note does not re-derive",
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="min_features",
            detail="exact per-alloy-temper bend-radius minimums are "
            "omitted; only the GEK-tier 1x-thickness rule of thumb is "
            "stated",
            refused_source="ASM Sheet Metal Forming Handbook bend-radius tables",
            lift_condition="a licensed copy of the ASM Sheet Metal "
            "Forming Handbook is obtained and its per-alloy-temper rows "
            "are transcribed with in-row citation",
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_press_brake_bend_radius",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
STAMPING_BLANKING_CHECKS = DfmCheckSet(
    family="stamping_blanking",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_punch_die_clearance",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="clearance as a percent of thickness within a "
                "declared material-class envelope is the rollup's own "
                "priority-3 DFM rule (procres/sheet.md #22 DFM rule 4); "
                "the verbatim clearance-percent-by-material table is a "
                "NAMED REFUSAL (Machinery's Handbook/ASM class), only "
                "the qualitative relationship is encoded as arithmetic",
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_press_tonnage",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="part perimeter x material shear-strength vs "
                "declared press tonnage is a press-capacity containment "
                "check, analogous to check_stock_fit (procres/sheet.md "
                "#22 DFM rule 5)",
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PRESS_BRAKE_BEND_CHECKS = DfmCheckSet(
    family="press_brake_bend",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_press_brake_bend_radius",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="bend_radius >= material-class minimum-bend-"
                "radius-per-thickness is procres/sheet.md #23 DFM rule 1 "
                "(cracking-risk threshold); the per-alloy-temper minimum "
                "itself is a declared caller parameter, not hard-coded",
            ),
        ),
    ),
)

__all__ = [
    "PRESS_BRAKE_BEND_CHECKS",
    "PRESS_BRAKE_BEND_RECORD",
    "STAMPING_BLANKING_CHECKS",
    "STAMPING_BLANKING_RECORD",
]
