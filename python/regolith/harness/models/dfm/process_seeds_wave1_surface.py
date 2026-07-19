"""WO-169 wave-1 population: shot peening (procres/surface.md #92),
the rollup's own priority-5 addition -- a real, concrete recast-layer
remediation for wire EDM's own named recast-layer residual TENSILE
stress concern (subtractive.md #13), a genuine cross-family finding
this recon surfaced that D268's own ruling text did not name."""

from __future__ import annotations

from regolith.backends.quantity import DimensionedValue
from regolith.harness.models.dfm.process_records import (
    CostDriver,
    DfmCheckEntry,
    DfmCheckSet,
    MinFeature,
    ProcessRecord,
    ProvenanceNote,
    SurfaceFinishEntry,
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SHOT_PEENING_RECORD = ProcessRecord(
    key="std.process/shot_peening",
    name="Shot peening",
    din_8580_class="4.4",
    materials=("std.materials/tool_steel_d2", "std.materials/tool_steel_a2"),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(
        SurfaceFinishEntry(
            condition="post-peen roughness increase over pre-peen surface",
            ra=DimensionedValue.of("+0.2-2", "um"),
        ),
    ),
    min_features=(
        MinFeature(
            feature="compressive residual-stress layer depth",
            value=DimensionedValue.of("0.1-0.5", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="low-to-moderate per-part cost, fast blast-cabinet cycle",
            note="sweet spot = fatigue-critical metal parts, any volume "
            "(procres/surface.md #92)",
        ),
    ),
    lead_class="fast cycle (blast-cabinet or automated peening cell)",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="compressive-layer depth and roughness-increase "
            "ranges are uncited engineering-consensus values; the "
            "qualitative existence of Almen intensity as a controlled "
            "process parameter is safe GEK-tier knowledge (procres/"
            "surface.md #92)",
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="tolerance_grades",
            detail="the Almen strip specification itself (intensity-vs-"
            "arc-height calibration tables) is omitted",
            refused_source="SAE J442/J443 Almen strip specification standards",
            lift_condition="a licensed copy of SAE J442/J443 is obtained "
            "and its calibration tables are transcribed with in-row "
            "citation",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_shot_peen_recast_remediation",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SHOT_PEENING_CHECKS = DfmCheckSet(
    family="shot_peening",
    checks=(
        DfmCheckEntry(
            check_id=(
                "regolith.harness.models.dfm.checks:check_shot_peen_recast_remediation"
            ),
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="peening must follow the recast-bearing process "
                "(wire/sinker EDM) and its achieved compressive-layer "
                "depth must meet the declared fatigue-remediation floor "
                "-- the rollup's own priority-5 cross-family finding "
                "(procres/surface.md #92, direct remediation for "
                "procres/subtractive.md #13's named recast-layer "
                "tensile-stress concern)",
            ),
        ),
    ),
)

__all__ = ["SHOT_PEENING_CHECKS", "SHOT_PEENING_RECORD"]
