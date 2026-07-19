"""WO-171 wave-3 population: the bulk-forming family (procres/
bulk_forming.md #68-74, DIN 8580 Umformen bulk-forming branch) --
open-die forging, closed-die forging, extrusion, rolling, wire/bar
drawing, cold heading, swaging. Rolling (#71) and wire/bar drawing
(#72) are explicitly flagged OUT OF SCOPE for a per-part DFM gate per
the dossier's own framing (upstream stock-supply processes), same
class of flag as casting.md's continuous casting (#36)."""

from __future__ import annotations

from regolith.backends.quantity import DimensionedValue
from regolith.harness.models.dfm.process_records import (
    CostDriver,
    DfmCheckEntry,
    DfmCheckSet,
    MinFeature,
    ProcessRecord,
    ProvenanceNote,
    ToleranceGrade,
)


def _gek(detail: str) -> ProvenanceNote:
    return ProvenanceNote(posture="gek", scope="record", detail=detail)


_ASM_VOL14_REFUSAL = ProvenanceNote(
    posture="named_refusal",
    scope="tolerance_grades",
    detail="ASM Metals Handbook Vol.14 (Forming) precise flow-stress/"
    "forging-load tables are omitted (procres/bulk_forming.md standing "
    "refusal)",
    refused_source="ASM Metals Handbook Vol.14 (Forming)",
    lift_condition="a licensed copy of ASM Metals Handbook Vol.14 is "
    "obtained and its rows are transcribed with in-row citation",
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
OPEN_DIE_FORGING_RECORD = ProcessRecord(
    key="std.process/open_die_forging",
    name="Open-die forging",
    din_8580_class="2.1.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="always finish-machined after",
            achievable=DimensionedValue.of("+/-1-5", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="LOW tooling cost (simple flat/V dies, no "
            "part-specific tooling), labor/skill-intensive, slow",
            note="large one-off or low-volume high-integrity parts "
            "(procres/bulk_forming.md #68)",
        ),
    ),
    lead_class="large one-off or low-volume high-integrity parts",
    provenance=(
        _gek(
            "tolerance and grain-flow-improvement values are uncited "
            "engineering-consensus (procres/bulk_forming.md #68)"
        ),
        _ASM_VOL14_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_process_sequencing",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
CLOSED_DIE_FORGING_RECORD = ProcessRecord(
    key="std.process/closed_die_forging",
    name="Closed-die (drop) forging",
    din_8580_class="2.1.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(condition="as-forged, trimmed after", achievable=DimensionedValue.of("+/-0.3-1", "mm")),
    ),
    surface_finish=(),
    min_features=(
        MinFeature(feature="draft_angle", value=DimensionedValue.of("3-7", "deg")),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="HIGH tooling cost (impression die set), fast "
            "cycle, excellent strength-to-weight",
            note="high-volume, high-strength parts, uneconomical at low "
            "volume (procres/bulk_forming.md #69)",
        ),
    ),
    lead_class="high-volume, high-strength structural parts",
    provenance=(
        _gek(
            "draft-angle and tolerance values are uncited engineering-"
            "consensus (procres/bulk_forming.md #69)"
        ),
        _ASM_VOL14_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_draft_angle_min",
        "regolith.harness.models.dfm.checks:check_value_window",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
EXTRUSION_RECORD = ProcessRecord(
    key="std.process/metal_extrusion",
    name="Extrusion (forward/backward, metal)",
    din_8580_class="2.2.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="moderate-to-high tooling cost (one die, "
            "cheaper than a matched stamping/forging die pair), very "
            "fast/continuous production",
            note="long-run constant-section profiles, structural "
            "aluminum framing (procres/bulk_forming.md #70); calcite/"
            "civil cross-domain relevance",
        ),
    ),
    lead_class="long-run constant-section profiles",
    provenance=(
        _gek(
            "constant-cross-section hard gate and wall-thickness-"
            "capability values are uncited engineering-consensus "
            "(procres/bulk_forming.md #70)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_value_window",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ROLLING_RECORD = ProcessRecord(
    key="std.process/rolling",
    name="Rolling (flat/shape)",
    din_8580_class="2.3.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="cold flat-rolled, gauge-dependent",
            achievable=DimensionedValue.of("+/-0.02-0.1", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="out_of_scope",
            driver_class="upstream stock-supply process, NOT per-part "
            "cost-modeled",
            note="converts cast ingot/billet into wrought mill products "
            "(procres/bulk_forming.md #71) -- explicitly flagged OUT OF "
            "SCOPE for a per-part DFM gate, IN SCOPE only as a std."
            "materials stock-catalog source",
        ),
    ),
    lead_class="OUT OF SCOPE for per-part manufacture; std.materials "
    "stock-catalog concern",
    provenance=(
        _gek(
            "cold-rolled tolerance and rolling-direction anisotropy are "
            "uncited engineering-consensus (procres/bulk_forming.md #71)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
WIRE_BAR_DRAWING_RECORD = ProcessRecord(
    key="std.process/wire_bar_drawing",
    name="Wire/bar drawing",
    din_8580_class="2.3.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(condition="die-sizing process, tight", achievable=DimensionedValue.of("+/-0.01-0.05", "mm")),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="out_of_scope",
            driver_class="upstream stock-supply process, NOT per-part "
            "cost-modeled",
            note="fine wire and precision round bar / final sizing step "
            "for cold-finished bar (procres/bulk_forming.md #72) -- "
            "explicitly OUT OF SCOPE for a per-part DFM gate, same flag "
            "class as rolling (#71) and continuous casting (casting.md "
            "#36)",
        ),
    ),
    lead_class="OUT OF SCOPE for per-part manufacture; std.materials "
    "stock-catalog concern",
    provenance=(
        _gek(
            "per-pass area-reduction limit (~20-30%) and tolerance are "
            "uncited engineering-consensus (procres/bulk_forming.md #72)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_ratio_max",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
COLD_HEADING_RECORD = ProcessRecord(
    key="std.process/cold_heading",
    name="Cold heading",
    din_8580_class="2.1.3",
    materials=("std.fasteners",),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="VERY HIGH tooling cost (progressive header "
            "dies), extremely low marginal cost at true production "
            "volume",
            note="fastener manufacturing, volumes in the millions "
            "(procres/bulk_forming.md #73); this IS how std.fasteners "
            "catalog parts are actually manufactured",
        ),
    ),
    lead_class="fastener manufacturing, millions of units",
    provenance=(
        _gek(
            "upset-ratio-per-station limit is uncited engineering-"
            "consensus (procres/bulk_forming.md #73)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_ratio_max",
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SWAGING_RECORD = ProcessRecord(
    key="std.process/swaging",
    name="Swaging",
    din_8580_class="2.1.4",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="moderate tooling cost (swage dies), fast "
            "cycle, no material waste",
            note="tube-end forming, cable-fitting attachment, mid-to-"
            "high volume (procres/bulk_forming.md #74); cable/fitting-"
            "attachment use case is a joining-forming overlap similar "
            "in kind to hemming/seaming's cross-family status",
        ),
    ),
    lead_class="tube-end forming, cable-fitting attachment",
    provenance=(
        _gek(
            "diameter-reduction-per-pass limit is uncited engineering-"
            "consensus (procres/bulk_forming.md #74)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_ratio_max",
    ),
)

# --- check sets ---------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
OPEN_DIE_FORGING_CHECKS = DfmCheckSet(
    family="open_die_forging",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "this process's tolerance is never the final-dimension "
                "claim, finish-machining allowance required, a "
                "sequencing predicate (procres/bulk_forming.md #68 DFM "
                "rule 1)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
CLOSED_DIE_FORGING_CHECKS = DfmCheckSet(
    family="closed_die_forging",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_draft_angle_min",
            provenance=_gek(
                "draft_angle >= declared min (procres/bulk_forming.md "
                "#69 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "rib/web thickness within declared die-fill minimum "
                "(procres/bulk_forming.md #69 DFM rule 3)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
EXTRUSION_CHECKS = DfmCheckSet(
    family="metal_extrusion",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "cross-section constant along length, a hard gate "
                "(procres/bulk_forming.md #70 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=_gek(
                "min wall thickness within declared die-capability "
                "window (procres/bulk_forming.md #70 DFM rule 2)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ROLLING_CHECKS = DfmCheckSet(
    family="rolling",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "declared sheet/plate/section product matches an "
                "available mill catalog size, a stock-quality predicate "
                "OUT OF SCOPE for per-part DFM (procres/bulk_forming.md "
                "#71 DFM rule 1)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
WIRE_BAR_DRAWING_CHECKS = DfmCheckSet(
    family="wire_bar_drawing",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "diameter reduction per pass limited (~20-30% area "
                "reduction before annealing needed), a stock-process "
                "limit (procres/bulk_forming.md #72 DFM rule -- process "
                "limitation, not a per-part feature gate)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
COLD_HEADING_CHECKS = DfmCheckSet(
    family="cold_heading",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "upset_ratio_per_station <= declared max else require "
                "declared multi-station progressive sequence (procres/"
                "bulk_forming.md #73 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "head geometry must be die-formable without undercuts "
                "perpendicular to the upset axis (procres/"
                "bulk_forming.md #73 DFM rule 2)"
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SWAGING_CHECKS = DfmCheckSet(
    family="swaging",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_ratio_max",
            provenance=_gek(
                "diameter_reduction_per_pass <= declared max else "
                "require multi-pass declared sequence (procres/"
                "bulk_forming.md #74 DFM rule 1)"
            ),
        ),
    ),
)

__all__ = [
    "CLOSED_DIE_FORGING_CHECKS",
    "CLOSED_DIE_FORGING_RECORD",
    "COLD_HEADING_CHECKS",
    "COLD_HEADING_RECORD",
    "EXTRUSION_CHECKS",
    "EXTRUSION_RECORD",
    "OPEN_DIE_FORGING_CHECKS",
    "OPEN_DIE_FORGING_RECORD",
    "ROLLING_CHECKS",
    "ROLLING_RECORD",
    "SWAGING_CHECKS",
    "SWAGING_RECORD",
    "WIRE_BAR_DRAWING_CHECKS",
    "WIRE_BAR_DRAWING_RECORD",
]
