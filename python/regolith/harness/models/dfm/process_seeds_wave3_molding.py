"""WO-171 wave-3 population: the molding family (procres/molding.md
#38-44, DIN 8580 Urformen polymer branch) -- injection, blow,
rotational, thermoforming, compression, transfer, RIM.

Every numeric value here is transcribed from the named dossier entry
with its provenance class preserved verbatim. Reuses the wave-3
GENERIC checks (`check_value_window`, `check_draft_angle_min`,
`check_ratio_max`, `check_boolean_gate`) rather than duplicating
per-family arithmetic (NO-DUPLICATION)."""

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

_SPI_REFUSAL = ProvenanceNote(
    posture="named_refusal",
    scope="tolerance_grades",
    detail="per-resin shrinkage/tolerance tables (SPI/SPE mold-design "
    "guides) are omitted (procres/molding.md standing refusal)",
    refused_source="SPI/SPE mold-design guide shrinkage tables",
    lift_condition="a licensed copy of the SPI/SPE mold-design guide is "
    "obtained and its rows are transcribed with in-row citation",
)


def _gek(detail: str) -> ProvenanceNote:
    return ProvenanceNote(posture="gek", scope="record", detail=detail)


# frob:doc docs/modules/py-harness.md#models-dfm-process
INJECTION_MOLDING_RECORD = ProcessRecord(
    key="std.process/injection_molding",
    name="Injection molding",
    din_8580_class="1.3.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("0.5", "mm"),
            max=DimensionedValue.of("5", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="resin-shrinkage-rate dependent",
            achievable=DimensionedValue.of("+/-0.05-0.3", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(
        MinFeature(feature="draft_angle", value=DimensionedValue.of("0.5-2", "deg")),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="VERY HIGH tooling cost (hardened steel mold)",
            note="extremely low marginal cost/very fast cycle at volume "
            "(procres/molding.md #38); high volume ONLY sweet spot, same "
            "fixed/marginal profile as stamping/die-casting",
        ),
    ),
    lead_class="high volume only",
    provenance=(
        _gek(
            "wall/tolerance/draft/rib-ratio values are uncited "
            "engineering-consensus ranges (procres/molding.md #38)"
        ),
        _SPI_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_draft_angle_min",
        "regolith.harness.models.dfm.checks:check_ratio_max",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
BLOW_MOLDING_RECORD = ProcessRecord(
    key="std.process/blow_molding",
    name="Blow molding",
    din_8580_class="1.3.2",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("1", "mm"),
            max=DimensionedValue.of("4", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="looser than injection molding, parison draw-down dependent",
            achievable=DimensionedValue.of("+/-0.3-1", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="moderate tooling cost, cheaper than an "
            "equivalent injection mold (no core needed)",
            note="hollow thin-wall containers sweet spot (procres/molding.md #39)",
        ),
    ),
    lead_class="hollow thin-wall containers, mid-to-high volume",
    provenance=(
        _gek(
            "wall-thickness-variation and tolerance values are uncited "
            "engineering-consensus ranges (procres/molding.md #39)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ROTATIONAL_MOLDING_RECORD = ProcessRecord(
    key="std.process/rotational_molding",
    name="Rotational molding",
    din_8580_class="1.3.3",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("3", "mm"),
            max=DimensionedValue.of("10", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="large-part-scale, loosest of the molding family",
            achievable=DimensionedValue.of("+/-1-3", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="LOW tooling cost (cast aluminum mold, no injection pressure)",
            note="slow cycle time, large parts at low-to-mid volume "
            "(procres/molding.md #40); no residual stress, a real "
            "positive capability",
        ),
    ),
    lead_class="large hollow parts, low-to-mid volume",
    provenance=(
        _gek(
            "wall-thickness achievable range is uncited engineering-"
            "consensus (procres/molding.md #40)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
THERMOFORMING_RECORD = ProcessRecord(
    key="std.process/thermoforming",
    name="Thermoforming",
    din_8580_class="1.3.4",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="sheet_thickness",
            min=DimensionedValue.of("0.5", "mm"),
            max=DimensionedValue.of("25", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="single-sided tooling, loose",
            achievable=DimensionedValue.of("+/-0.5-2", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="corner_radius", value=DimensionedValue.of("declared-min", "mm")
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="LOW tooling cost (single-sided mold)",
            note="much cheaper than injection molding; large thin-wall "
            "low-to-mid volume sweet spot (procres/molding.md #41)",
        ),
    ),
    lead_class="large, thin-wall, low-to-mid volume parts",
    provenance=(
        _gek(
            "draw-ratio and tolerance values are uncited engineering-"
            "consensus ranges (procres/molding.md #41)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_ratio_max",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
COMPRESSION_MOLDING_RECORD = ProcessRecord(
    key="std.process/compression_molding",
    name="Compression molding",
    din_8580_class="1.3.5",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("0.5", "mm"),
            max=DimensionedValue.of("25", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="typical", achievable=DimensionedValue.of("+/-0.1-0.5", "mm")
        ),
    ),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="draft_angle",
            value=DimensionedValue.of("similar-to-injection", "deg"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="moderate tooling cost (simpler than injection, "
            "no runner/gate system)",
            note="thermoset/composite parts, mid volume (procres/molding.md #42)",
        ),
    ),
    lead_class="thermoset and composite parts, mid volume",
    provenance=(
        _gek(
            "wall-thickness/tolerance values are uncited engineering-"
            "consensus ranges (procres/molding.md #42)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_draft_angle_min",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
TRANSFER_MOLDING_RECORD = ProcessRecord(
    key="std.process/transfer_molding",
    name="Transfer molding",
    din_8580_class="1.3.6",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="better than compression, runner-fed cavity fill",
            achievable=DimensionedValue.of("+/-0.05-0.2", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="tooling cost between compression and injection molding",
            note="insert encapsulation (electronics packaging), mid "
            "volume (procres/molding.md #43)",
        ),
    ),
    lead_class="insert encapsulation, electronics packaging, mid volume",
    provenance=(
        _gek(
            "tolerance values are uncited engineering-consensus "
            "(procres/molding.md #43)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_boolean_gate",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
RIM_RECORD = ProcessRecord(
    key="std.process/reaction_injection_molding",
    name="Reaction injection molding (RIM)",
    din_8580_class="1.3.7",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="looser than thermoplastic injection molding",
            achievable=DimensionedValue.of("+/-0.3-1", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="LOWER tooling cost than thermoplastic injection "
            "molding for equivalent large-part size (low clamp tonnage)",
            note="large, low-to-mid-volume parts (automotive exterior/"
            "structural foam) (procres/molding.md #44)",
        ),
    ),
    lead_class="large, low-to-mid-volume parts",
    provenance=(
        _gek(
            "tolerance values are uncited engineering-consensus "
            "(procres/molding.md #44)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_value_window",),
)


def _cs(family: str, check_id: str, detail: str) -> DfmCheckSet:
    return DfmCheckSet(
        family=family,
        checks=(
            DfmCheckEntry(
                check_id=check_id,
                provenance=_gek(detail),
            ),
        ),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
INJECTION_MOLDING_CHECKS = DfmCheckSet(
    family="injection_molding",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "wall_thickness within declared uniform window per resin "
                "class (procres/molding.md #38 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_draft_angle_min",
            provenance=_gek(
                "draft_angle >= declared min on core/cavity-pull surfaces "
                "(procres/molding.md #38 DFM rule 2)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "rib_thickness <= k*nominal_wall sink-mark threshold "
                "(procres/molding.md #38 DFM rule 3)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
BLOW_MOLDING_CHECKS = DfmCheckSet(
    family="blow_molding",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "wall_thickness_variation declared window (procres/"
                "molding.md #39 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "undercuts generally NOT achievable, a hard geometric "
                "limitation (procres/molding.md #39 DFM rule 3)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ROTATIONAL_MOLDING_CHECKS = DfmCheckSet(
    family="rotational_molding",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "wall_thickness achievable range declared (procres/"
                "molding.md #40 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "sharp corners/fine detail NOT achievable, a hard "
                "resolution-limit gate (procres/molding.md #40 DFM rule 3)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
THERMOFORMING_CHECKS = _cs(
    "thermoforming",
    "regolith.harness.models.dfm.checks:check_ratio_max",
    "draw_depth/opening_size ratio <= declared max, thinning-risk "
    "threshold (procres/molding.md #41 DFM rule 1)",
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
COMPRESSION_MOLDING_CHECKS = DfmCheckSet(
    family="compression_molding",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "wall_thickness within declared cure-uniformity window "
                "(procres/molding.md #42 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_draft_angle_min",
            provenance=_gek(
                "draft angle requirement for mold release, similar "
                "magnitude to injection molding (procres/molding.md #42 "
                "DFM rule 2)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
TRANSFER_MOLDING_CHECKS = _cs(
    "transfer_molding",
    "regolith.harness.models.dfm.checks:check_boolean_gate",
    "insert must be secured against declared transfer pressure/flow "
    "force, insert-shift risk (procres/molding.md #43 DFM rule 1)",
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
RIM_CHECKS = _cs(
    "reaction_injection_molding",
    "regolith.harness.models.dfm.checks:check_value_window",
    "wall_thickness within the reactive-chemistry's flow/cure window "
    "(procres/molding.md #44 DFM rule 1)",
)

__all__ = [
    "BLOW_MOLDING_CHECKS",
    "BLOW_MOLDING_RECORD",
    "COMPRESSION_MOLDING_CHECKS",
    "COMPRESSION_MOLDING_RECORD",
    "INJECTION_MOLDING_CHECKS",
    "INJECTION_MOLDING_RECORD",
    "RIM_CHECKS",
    "RIM_RECORD",
    "ROTATIONAL_MOLDING_CHECKS",
    "ROTATIONAL_MOLDING_RECORD",
    "THERMOFORMING_CHECKS",
    "THERMOFORMING_RECORD",
    "TRANSFER_MOLDING_CHECKS",
    "TRANSFER_MOLDING_RECORD",
]
