"""WO-171 wave-3 population: the powder-metallurgy family (procres/
powder.md #45-47, DIN 8580 Urformen powder-consolidation branch) --
PM press+sinter, MIM, HIP. This family was ADDED by the rollup recon
(D269 sec.3 omitted it entirely despite DIN 8580 naming it as a
distinct Urformen sub-branch) -- see procres/rollup.md sec. "Delta
against DIN 8580"."""

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


_MPIF_REFUSAL = ProvenanceNote(
    posture="named_refusal",
    scope="tolerance_grades",
    detail="MPIF (Metal Powder Industries Federation) standard density/"
    "property tables are omitted (procres/powder.md standing refusal)",
    refused_source="MPIF standard density/property tables",
    lift_condition="a licensed copy of the MPIF standards is obtained "
    "and its rows are transcribed with in-row citation",
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PM_PRESS_SINTER_RECORD = ProcessRecord(
    key="std.process/pm_press_sinter",
    name="Powder metallurgy pressing + sintering (PM)",
    din_8580_class="1.4.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("declared-fill-uniformity-min", "mm"),
            max=DimensionedValue.of("unbounded", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="as-pressed, sizing/coining can tighten further",
            achievable=DimensionedValue.of("+/-0.1-0.2", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="density_fraction_of_theoretical",
            value=DimensionedValue.of("85-95", "pct"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="HIGH tooling cost (hardened die set), similar "
            "class to stamping/die-casting",
            note="very fast cycle, low material waste; high volume ONLY, "
            "small-to-medium structural/bearing/gear parts (procres/"
            "powder.md #45)",
        ),
    ),
    lead_class="high volume only, small-to-medium structural parts",
    provenance=(
        _gek(
            "density fraction (85-95% theoretical), tolerance, and L/D "
            "aspect-ratio limits are uncited engineering-consensus "
            "values (procres/powder.md #45)"
        ),
        _MPIF_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_ratio_max",
        "regolith.harness.models.dfm.checks:check_value_window",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
MIM_RECORD = ProcessRecord(
    key="std.process/mim",
    name="Metal injection molding (MIM)",
    din_8580_class="1.4.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="percentage-of-dimension, large-shrinkage class",
            achievable=DimensionedValue.of("+/-0.3-0.5", "pct"),
        ),
    ),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="linear_sinter_shrinkage",
            value=DimensionedValue.of("15-20", "pct"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="tooling cost similar to plastic injection "
            "molding (machined mold, NOT a hardened compaction die)",
            note="debind+sinter stages add days not minutes; small, "
            "geometrically complex, mid-to-high-volume metal parts "
            "(procres/powder.md #46)",
        ),
    ),
    lead_class="small geometrically complex metal parts, mid-to-high "
    "volume",
    provenance=(
        _gek(
            "shrinkage (15-20% linear), tolerance, and density values "
            "are uncited engineering-consensus (procres/powder.md #46)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
HIP_RECORD = ProcessRecord(
    key="std.process/hip",
    name="Hot isostatic pressing (HIP)",
    din_8580_class="1.4.3",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="post_process",
            driver_class="added post-process cost (specialized pressure-"
            "vessel furnace cycle, batch-processed)",
            note="fatigue/pressure-boundary-critical castings and AM "
            "parts where porosity closure justifies the added cost "
            "(procres/powder.md #47)",
        ),
    ),
    lead_class="post-process densification step, not a shape-forming "
    "process in its own right",
    provenance=(
        _gek(
            "near-100% theoretical density achieved by closing internal "
            "voids (does not correct external dimensional defects) is "
            "uncited engineering consensus (procres/powder.md #47)"
        ),
        ProvenanceNote(
            posture="gek",
            scope="tolerance_grades",
            detail="MIL-HDBK-5 HIP-cycle allowables for some material "
            "systems are a plausible PD-GOV candidate, NOT independently "
            "re-verified this pass -- named open follow-up, not "
            "upgraded to pd_gov (procres/powder.md #47)",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_process_sequencing",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PM_PRESS_SINTER_CHECKS = DfmCheckSet(
    family="pm_press_sinter",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "part must be press-and-eject along a SINGLE axis, no "
                "undercuts perpendicular to press direction, a hard "
                "geometric gate (procres/powder.md #45 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "length-to-diameter (press-direction aspect ratio) "
                "limited, density gradient grows with L/D (procres/"
                "powder.md #45 DFM rule 2)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "wall_thickness >= declared minimum fill-uniformity "
                "threshold (procres/powder.md #45 DFM rule 4)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
MIM_CHECKS = DfmCheckSet(
    family="mim",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "wall_thickness within a narrower uniform-wall window "
                "than plastic injection molding, slumping/distortion "
                "risk (procres/powder.md #46 DFM rule 2)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "mold cavity dimensions must include the declared "
                "shrinkage-compensation factor (procres/powder.md #46 "
                "DFM rule 1)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
HIP_CHECKS = DfmCheckSet(
    family="hip",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "internal-porosity-sensitive strength/fatigue claim "
                "requires a declared HIP step, a composition/sequencing "
                "predicate across the process chain (procres/powder.md "
                "#47 DFM rule 1); shared with DMLS/SLM's own HIP "
                "cross-link (procres/additive.md #51)"
            ),
        ),
    ),
)

__all__ = [
    "HIP_CHECKS",
    "HIP_RECORD",
    "MIM_CHECKS",
    "MIM_RECORD",
    "PM_PRESS_SINTER_CHECKS",
    "PM_PRESS_SINTER_RECORD",
]
