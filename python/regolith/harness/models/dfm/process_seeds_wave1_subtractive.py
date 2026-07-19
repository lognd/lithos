"""WO-169 wave-1 population: sinker EDM + grinding (the subtractive-
family remainder of D269's EDM/heat-treat/stamping priority list).
Wire EDM itself already landed as a WO-168 seed
(`process_seeds.py:WIRE_EDM_RECORD`); this module adds sinker EDM
(procres/subtractive.md #14, a cheap-to-include sibling per WO-169's
own deliverable-1 phrasing) and grinding (procres/subtractive.md #7,
the rollup's own priority-4 addition -- the standard post-heat-treat
finishing process for hardened die-plate faces).

Every numeric value here is transcribed from the named dossier entry
with its provenance class preserved verbatim (this module invents no
citation and does not upgrade a GEK value to look cited)."""

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
SINKER_EDM_RECORD = ProcessRecord(
    key="std.process/sinker_edm",
    name="Sinker EDM (ram / die-sink electrical discharge machining)",
    din_8580_class="3.2.3",
    materials=("std.materials/tool_steel_d2", "std.materials/tool_steel_a2"),
    size_limits=(
        SizeLimit(
            dimension="cavity_depth_to_electrode_min_dimension_ratio",
            min=DimensionedValue.of("0", "ratio"),
            max=DimensionedValue.of(
                "flushing-limited, alloy/electrode-dependent", "ratio"
            ),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical, finer with fine-finish electrode/settings",
            achievable=DimensionedValue.of("+/-0.01-0.02", "mm"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(condition="rough pass", ra=DimensionedValue.of("3", "um")),
        SurfaceFinishEntry(
            condition="fine finish pass (multi-electrode)",
            ra=DimensionedValue.of("0.2-0.4", "um"),
        ),
    ),
    min_features=(
        MinFeature(
            feature="internal corner radius",
            value=DimensionedValue.of("electrode_corner_radius + spark_gap", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="per-cavity electrode fabrication cost",
            note="electrode is itself often machined or wire-EDM'd -- a "
            "real added fixed cost per cavity shape, higher than wire "
            "EDM's near-zero tooling (procres/subtractive.md #14)",
        ),
        CostDriver(
            driver="setup",
            driver_class="multi-electrode roughing+finishing sequence",
            note="electrode wear (unlike continuously-fed wire) usually "
            "requires multiple electrodes per cavity",
        ),
    ),
    lead_class="cycle time driven by cavity volume and flushing "
    "constraints; slow for deep narrow cavities",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="all numeric envelope values (tolerance, Ra, aspect "
            "ratio) are uncited engineering-consensus ranges, same "
            "posture class as wire EDM (procres/subtractive.md #14)",
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="tolerance_grades",
            detail="vendor EDM parameter tables are omitted, same "
            "refusal as wire EDM's own posture",
            refused_source="vendor EDM application-data tables and the "
            "ASM Machining Data Handbook class of source",
            lift_condition="a licensed copy of the vendor tables or ASM "
            "Machining Data Handbook is obtained and its rows are "
            "transcribed with in-row citation",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_sinker_edm_corner_radius",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
GRINDING_RECORD = ProcessRecord(
    key="std.process/grinding",
    name="Grinding (surface / cylindrical / centerless)",
    din_8580_class="3.2.2",
    materials=("std.materials/tool_steel_d2", "std.materials/tool_steel_a2"),
    size_limits=(
        SizeLimit(
            dimension="stock_removal_per_pass",
            min=DimensionedValue.of("0.005", "mm"),
            max=DimensionedValue.of("0.05", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical precision grind",
            achievable=DimensionedValue.of("+/-0.002-0.01", "mm"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="typical grind", ra=DimensionedValue.of("0.1-0.8", "um")
        ),
        SurfaceFinishEntry(
            condition="precision grind", ra=DimensionedValue.of("0.05", "um")
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="high per-part cost (slow removal rate)",
            note="justified only where tolerance/hardness demands it "
            "(procres/subtractive.md #7)",
        ),
    ),
    lead_class="lead-time class similar to milling",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="tolerance/Ra/stock-removal-window values are "
            "uncited engineering-consensus ranges (procres/"
            "subtractive.md #7); MIL-H-6875-adjacent workmanship specs "
            "may reference post-heat-treat grinding allowances but were "
            "not independently verified this pass -- named open "
            "follow-up, not upgraded to pd_gov",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_grinding_stock_allowance",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SINKER_EDM_CHECKS = DfmCheckSet(
    family="sinker_edm",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_sinker_edm_corner_radius",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="internal_corner_radius >= electrode_corner_radius "
                "+ spark_gap is a containment predicate derived from the "
                "GEK-tier electrode-geometry/spark-gap physics (procres/"
                "subtractive.md #14 DFM rule 3), analogous to wire EDM's "
                "own corner-radius check",
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
GRINDING_CHECKS = DfmCheckSet(
    family="grinding",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_grinding_stock_allowance",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="stock allowance within the wheel's per-pass "
                "removal window is the rollup's own priority-4 "
                "post-heat-treat-finish DFM rule (procres/subtractive.md "
                "#7 DFM rule 2)",
            ),
        ),
    ),
)

__all__ = [
    "GRINDING_CHECKS",
    "GRINDING_RECORD",
    "SINKER_EDM_CHECKS",
    "SINKER_EDM_RECORD",
]
