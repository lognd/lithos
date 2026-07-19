"""WO-171 wave-3 population: the additive-manufacturing family
(procres/additive.md #48-54, DIN-8580-adjacent since AM postdates DIN
8580's base standard -- ISO/ASTM 52900's verbatim 7-category text is a
NAMED REFUSAL, its category names are usable as plain descriptive
English) -- FDM/FFF, SLA/DLP, SLS, DMLS/SLM, binder jetting, DED,
material jetting."""

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


_ISO_52900_REFUSAL = ProvenanceNote(
    posture="named_refusal",
    scope="record",
    detail="ISO/ASTM 52900's verbatim 7-process-category defining "
    "clauses are omitted; category NAMES are used as plain descriptive "
    "English only (procres/additive.md standing refusal)",
    refused_source="ISO/ASTM 52900",
    lift_condition="a licensed copy of ISO/ASTM 52900 is obtained and "
    "its defining clauses are transcribed with in-row citation",
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
FDM_RECORD = ProcessRecord(
    key="std.process/fdm_fff",
    name="FDM / FFF (material extrusion)",
    din_8580_class="1.5.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("0.8", "mm"),
            max=DimensionedValue.of("1.2", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="depending on machine class (desktop vs industrial)",
            achievable=DimensionedValue.of("+/-0.1-0.5", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="overhang_angle_without_support",
            value=DimensionedValue.of("45", "deg"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="LOWEST tooling cost of any process in this "
            "dossier (zero tooling)",
            note="one-off/prototype/very-low-volume sweet spot, "
            "uneconomical at real production volume (procres/"
            "additive.md #48)",
        ),
    ),
    lead_class="one-off/prototype/very-low-volume",
    provenance=(
        _gek(
            "layer height, tolerance, min wall (2x nozzle diameter), and "
            "overhang-angle values are uncited engineering-consensus "
            "ranges (procres/additive.md #48)"
        ),
        _ISO_52900_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_ratio_max",
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SLA_DLP_RECORD = ProcessRecord(
    key="std.process/sla_dlp",
    name="SLA / DLP (vat photopolymerization)",
    din_8580_class="1.5.2",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("0.3", "mm"),
            max=DimensionedValue.of("0.5", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical", achievable=DimensionedValue.of("+/-0.05-0.15", "mm")
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="as-printed, near-injection-molding-like",
            ra=DimensionedValue.of("1-5", "um"),
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="LOW tooling cost (no tooling), moderate material cost",
            note="high-detail prototypes, casting patterns (investment-"
            "casting burnout resin cross-links casting.md #32), low-"
            "volume end-use parts (procres/additive.md #49)",
        ),
    ),
    lead_class="high-detail prototypes and low-volume end-use parts",
    provenance=(
        _gek(
            "layer height, tolerance, min wall, and Ra values are "
            "uncited engineering-consensus ranges (procres/additive.md "
            "#49)"
        ),
        _ISO_52900_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SLS_RECORD = ProcessRecord(
    key="std.process/sls",
    name="SLS (powder-bed fusion, polymer)",
    din_8580_class="1.5.3",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("0.7", "mm"),
            max=DimensionedValue.of("1", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="percentage-of-dimension class",
            achievable=DimensionedValue.of("+/-0.2-0.3", "pct"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="as-printed, grainy/powder-texture-imparted",
            ra=DimensionedValue.of("6-12", "um"),
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="no tooling, moderate-to-high material cost "
            "(powder, partially reusable across builds)",
            note="functional prototypes and low-volume end-use parts "
            "with complex geometry (procres/additive.md #50)",
        ),
    ),
    lead_class="functional prototypes, low-volume complex-geometry parts",
    provenance=(
        _gek(
            "tolerance, Ra, and min-wall values are uncited engineering-"
            "consensus (procres/additive.md #50); NO SUPPORT STRUCTURES "
            "needed is a real, stated capability distinction from FDM/"
            "SLA, not a fabricated claim"
        ),
        _ISO_52900_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
DMLS_SLM_RECORD = ProcessRecord(
    key="std.process/dmls_slm",
    name="DMLS / SLM (powder-bed fusion, metal)",
    din_8580_class="1.5.4",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("0.4", "mm"),
            max=DimensionedValue.of("0.5", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="as-built, often finish-machined on critical features",
            achievable=DimensionedValue.of("+/-0.05-0.2", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="overhang_angle_without_support",
            value=DimensionedValue.of("45", "deg"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="capital_and_machine_time",
            driver_class="HIGH capital/machine-time cost per part, ZERO "
            "part-specific tooling",
            note="low-volume, high-complexity, high-value parts where "
            "internal geometry (cooling channels, lattices) justifies "
            "per-part cost (procres/additive.md #51); a plausible "
            "unexploited cross-link to the D268 EDM die-set program "
            "(DMLS mold inserts with conformal cooling)",
        ),
    ),
    lead_class="low-volume high-complexity high-value parts",
    provenance=(
        _gek(
            "overhang, wall, tolerance values are uncited engineering-"
            "consensus (procres/additive.md #51); residual-stress-relief "
            "and porosity/HIP characteristics are well-documented AM-"
            "metal facts, not fabricated numbers"
        ),
        ProvenanceNote(
            posture="gek",
            scope="tolerance_grades",
            detail="MIL-HDBK-5-class aerospace metallic allowables "
            "increasingly include AM-metal supplements, plausible "
            "PD-GOV extension NOT independently verified this pass -- "
            "named open follow-up (procres/additive.md #51)",
        ),
        _ISO_52900_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_process_sequencing",
        "regolith.harness.models.dfm.checks:check_value_window",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
BINDER_JETTING_RECORD = ProcessRecord(
    key="std.process/binder_jetting",
    name="Binder jetting",
    din_8580_class="1.5.5",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="linear_sinter_shrinkage",
            value=DimensionedValue.of("15-20", "pct"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="build_speed",
            driver_class="no PART tooling, moderate build speed (faster "
            "than powder-bed fusion, no melting)",
            note="mid-volume metal parts where DMLS's per-part cost is "
            "too high, OR rapid sand-mold/core production for casting "
            "(procres/additive.md #52, direct cross-link to casting.md "
            "#31)",
        ),
    ),
    lead_class="mid-volume metal parts; rapid sand-mold/core production",
    provenance=(
        _gek(
            "shrinkage and density-tradeoff values are uncited "
            "engineering-consensus (procres/additive.md #52)"
        ),
        _ISO_52900_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_process_sequencing",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
DED_RECORD = ProcessRecord(
    key="std.process/ded",
    name="Directed energy deposition (DED)",
    din_8580_class="1.5.6",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="deposition_rate",
            driver_class="high machine cost, fast deposition rate (kg/hour class)",
            note="economical for large parts or high-value repairs "
            "(procres/additive.md #53); the REPAIR use case is a "
            "genuinely novel capability relative to every other process "
            "in this dossier, none of which modify an existing part in "
            "place",
        ),
    ),
    lead_class="large parts and high-value repair/cladding",
    provenance=(
        _gek(
            "as-deposited resolution and build-rate values are uncited "
            "engineering-consensus (procres/additive.md #53)"
        ),
        ProvenanceNote(
            posture="gek",
            scope="tolerance_grades",
            detail="MIL-HDBK/DoD interest in DED for field repair is "
            "real and well-documented in public defense-acquisition "
            "literature, a candidate PD-GOV source NOT independently "
            "verified this pass (procres/additive.md #53)",
        ),
        _ISO_52900_REFUSAL,
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_process_sequencing",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
MATERIAL_JETTING_RECORD = ProcessRecord(
    key="std.process/material_jetting",
    name="Material jetting (PolyJet / MultiJet)",
    din_8580_class="1.5.7",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("0.3", "mm"),
            max=DimensionedValue.of("0.5", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical", achievable=DimensionedValue.of("+/-0.05-0.1", "mm")
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="smoothest AM surface, near-molded quality",
            ra=DimensionedValue.of("<1-2", "um"),
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="material_cost",
            driver_class="no tooling, HIGH material cost (photopolymer "
            "+ support material both consumed)",
            note="visual/form-fit prototypes and multi-material "
            "demonstrators, rarely functional end-use parts (procres/"
            "additive.md #54)",
        ),
    ),
    lead_class="visual prototypes and multi-material demonstrators",
    provenance=(
        _gek(
            "layer height, tolerance, Ra, and wall-thickness values are "
            "uncited engineering-consensus (procres/additive.md #54)"
        ),
        _ISO_52900_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
FDM_CHECKS = DfmCheckSet(
    family="fdm_fff",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "wall_thickness >= k*nozzle_diameter (procres/"
                "additive.md #48 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "overhang_angle <= declared max unsupported angle else "
                "require support declaration (procres/additive.md #48 "
                "DFM rule 2)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SLA_DLP_CHECKS = DfmCheckSet(
    family="sla_dlp",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "wall_thickness >= declared min (procres/additive.md #49 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "trapped-volume (hollow enclosed cavities) must have "
                "declared drain holes (procres/additive.md #49 DFM "
                "rule 2)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SLS_CHECKS = DfmCheckSet(
    family="sls",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "min wall thickness containment (procres/additive.md #50 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "trapped powder in fully enclosed cavities must have "
                "declared escape holes (procres/additive.md #50 DFM "
                "rule 2)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
DMLS_SLM_CHECKS = DfmCheckSet(
    family="dmls_slm",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "overhang_angle <= declared max else require support "
                "(procres/additive.md #51 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "residual-stress-relief heat treat REQUIRED as a "
                "declared downstream step above a size/complexity "
                "threshold (procres/additive.md #51 DFM rule 3)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "thin-wall minimum containment (procres/additive.md #51 DFM rule 2)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
BINDER_JETTING_CHECKS = DfmCheckSet(
    family="binder_jetting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "green-part handling fragility flagged, thin unsupported "
                "green-state features may not survive depowder/handling "
                "(procres/additive.md #52 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "density-fraction caveat on strength claims may require "
                "declared HIP for full density (procres/additive.md #52 "
                "DFM rule 3, shares predicate class with PM/MIM and "
                "powder.md #47's HIP)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
DED_CHECKS = DfmCheckSet(
    family="ded",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "as-deposited surface always requires downstream finish-"
                "machining allowance declared, a sequencing predicate "
                "like sawing's rough-cut caveat (procres/additive.md #53 "
                "DFM rule 1)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
MATERIAL_JETTING_CHECKS = DfmCheckSet(
    family="material_jetting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "wall_thickness minimum finer than SLA (procres/"
                "additive.md #54 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "support-material removal access declared for fully "
                "enclosed internal cavities (procres/additive.md #54 "
                "DFM rule 3)"
            ),
        ),
    ),
)

__all__ = [
    "BINDER_JETTING_CHECKS",
    "BINDER_JETTING_RECORD",
    "DED_CHECKS",
    "DED_RECORD",
    "DMLS_SLM_CHECKS",
    "DMLS_SLM_RECORD",
    "FDM_CHECKS",
    "FDM_RECORD",
    "MATERIAL_JETTING_CHECKS",
    "MATERIAL_JETTING_RECORD",
    "SLA_DLP_CHECKS",
    "SLA_DLP_RECORD",
    "SLS_CHECKS",
    "SLS_RECORD",
]
