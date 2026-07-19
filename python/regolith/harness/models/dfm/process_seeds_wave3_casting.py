"""WO-171 wave-3 population: the casting family (procres/casting.md
#31-37, DIN 8580 Urformen liquid-state branch) -- sand, investment,
die (HPDC/LPDC), permanent mold, centrifugal, continuous, lost foam.

Every numeric value here is transcribed from the named dossier entry
with its provenance class preserved verbatim (this module invents no
citation and does not upgrade a GEK value to look cited). Continuous
casting (#36) is explicitly flagged OUT OF SCOPE for a per-part DFM
gate per the dossier's own framing (a stock-supply process, not a
part-shape process) -- its record is still populated (taxonomy
completeness, D269 sec.3/DIN 8580 coverage) but its `dfm_check_ids`
cite the sequencing/containment predicate over the STOCK, not a part
feature, and its `cost_drivers` name the out-of-scope flag explicitly
rather than silently omitting it.

New checks used here (`checks.py`, WO-171 wave 3): the GENERIC
`check_value_window` (wall-thickness/min-fill-thickness containment)
and `check_draft_angle_min` (die/mold-release draft-angle floor),
reused rather than duplicated per family (NO-DUPLICATION)."""

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

_ASM_HANDBOOK_REFUSAL = ProvenanceNote(
    posture="named_refusal",
    scope="tolerance_grades",
    detail="ASM Metals Handbook Vol.15 (Casting) per-alloy shrinkage/"
    "tolerance tables are omitted (procres/casting.md standing refusal)",
    refused_source="ASM Metals Handbook Vol.15 (Casting)",
    lift_condition="a licensed copy of ASM Metals Handbook Vol.15 is "
    "obtained and its rows are transcribed with in-row citation",
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SAND_CASTING_RECORD = ProcessRecord(
    key="std.process/sand_casting",
    name="Sand casting",
    din_8580_class="1.2.1",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("3", "mm"),
            max=DimensionedValue.of("5", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="as-cast, loosest of the casting family",
            achievable=DimensionedValue.of("+/-1-3", "mm"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="as-cast, sand-texture-imparted",
            ra=DimensionedValue.of("6.3-25", "um"),
        ),
    ),
    min_features=(
        MinFeature(feature="draft_angle", value=DimensionedValue.of("1-3", "deg")),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="lowest tooling cost of the casting family",
            note="wood/plastic pattern, reusable, cheap relative to a die "
            "(procres/casting.md #31); highest labor/cycle time per part",
        ),
    ),
    lead_class="low-volume, large/heavy parts, prototypes sweet spot",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="all numeric envelope values (tolerance, wall, Ra, "
            "draft) are uncited engineering-consensus ranges (procres/"
            "casting.md #31)",
        ),
        _ASM_HANDBOOK_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_draft_angle_min",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
INVESTMENT_CASTING_RECORD = ProcessRecord(
    key="std.process/investment_casting",
    name="Investment casting (lost wax)",
    din_8580_class="1.2.2",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("1", "mm"),
            max=DimensionedValue.of("2", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="as-cast, much tighter than sand",
            achievable=DimensionedValue.of("+/-0.1-0.5", "mm"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(
            condition="as-cast, best of the casting family",
            ra=DimensionedValue.of("1.6-6.3", "um"),
        ),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="wax-pattern secondary tooling, HIGH per-part cost",
            note="labor-intensive multi-step process; wax pattern may "
            "itself need an injection die (procres/casting.md #32)",
        ),
    ),
    lead_class="mid-complexity, near-net-shape, low-to-mid volume "
    "(aerospace/jewelry/dental)",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="all numeric envelope values are uncited engineering-"
            "consensus ranges (procres/casting.md #32)",
        ),
        _ASM_HANDBOOK_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
DIE_CASTING_RECORD = ProcessRecord(
    key="std.process/die_casting",
    name="Die casting (HPDC / LPDC)",
    din_8580_class="1.2.3",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("0.5", "mm"),
            max=DimensionedValue.of("2", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="as-cast, tightest of the casting family",
            achievable=DimensionedValue.of("+/-0.1-0.3", "mm"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(condition="as-cast", ra=DimensionedValue.of("0.8-3.2", "um")),
    ),
    min_features=(
        MinFeature(feature="draft_angle", value=DimensionedValue.of("1-2", "deg")),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="VERY HIGH tooling cost (hardened steel die)",
            note="extremely fast cycle, lowest marginal cost at volume; "
            "high volume ONLY sweet spot (procres/casting.md #33), same "
            "fixed/marginal profile as stamping",
        ),
    ),
    lead_class="high volume only (thousands-millions)",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="all numeric envelope values are uncited engineering-"
            "consensus ranges (procres/casting.md #33)",
        ),
        _ASM_HANDBOOK_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_draft_angle_min",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PERMANENT_MOLD_CASTING_RECORD = ProcessRecord(
    key="std.process/permanent_mold_casting",
    name="Permanent mold (gravity) casting",
    din_8580_class="1.2.4",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("3", "mm"),
            max=DimensionedValue.of("6", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(condition="as-cast", achievable=DimensionedValue.of("+/-0.3-0.8", "mm")),
    ),
    surface_finish=(
        SurfaceFinishEntry(condition="as-cast", ra=DimensionedValue.of("3.2-6.3", "um")),
    ),
    min_features=(
        MinFeature(feature="draft_angle", value=DimensionedValue.of("2-3", "deg")),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="moderate tooling cost (reusable metal mold)",
            note="middle ground between sand (cheap/coarse) and die "
            "casting (expensive/fine) (procres/casting.md #34)",
        ),
    ),
    lead_class="mid-volume non-ferrous parts",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="all numeric envelope values are uncited engineering-"
            "consensus ranges (procres/casting.md #34)",
        ),
        _ASM_HANDBOOK_REFUSAL,
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
        "regolith.harness.models.dfm.checks:check_draft_angle_min",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
CENTRIFUGAL_CASTING_RECORD = ProcessRecord(
    key="std.process/centrifugal_casting",
    name="Centrifugal casting",
    din_8580_class="1.2.5",
    materials=(),
    size_limits=(),
    tolerance_grades=(
        ToleranceGrade(
            condition="OD, as-cast (ID often machined after)",
            achievable=DimensionedValue.of("+/-0.5-1.5", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="moderate tooling (rotating mold, no die cavity "
            "for the bore)",
            note="cheaper than an equivalent solid-cast-then-bored part "
            "in material use (procres/casting.md #35)",
        ),
    ),
    lead_class="pipe/ring/bushing/cylinder-liner class parts, mid volume",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="axisymmetric-hollow-only geometry gate and density/"
            "tolerance values are uncited engineering-consensus facts "
            "(procres/casting.md #35)",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
CONTINUOUS_CASTING_RECORD = ProcessRecord(
    key="std.process/continuous_casting",
    name="Continuous casting",
    din_8580_class="1.2.6",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="out_of_scope",
            driver_class="upstream stock-supply process, NOT per-part "
            "cost-modeled",
            note="produces raw billet/slab/strand stock, not a near-net-"
            "shape final-part process (procres/casting.md #36) -- "
            "explicitly flagged OUT OF SCOPE for a per-part DFM gate, "
            "IN SCOPE only as a std.materials stock-catalog source",
        ),
    ),
    lead_class="OUT OF SCOPE for per-part manufacture; std.materials "
    "stock-catalog concern",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="billet/slab/strand catalog-size containment and "
            "centerline-porosity/segregation metallurgical facts are "
            "uncited engineering consensus (procres/casting.md #36)",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
LOST_FOAM_CASTING_RECORD = ProcessRecord(
    key="std.process/lost_foam_casting",
    name="Lost foam casting",
    din_8580_class="1.2.7",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="wall_thickness",
            min=DimensionedValue.of("3", "mm"),
            max=DimensionedValue.of("5", "mm"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="as-cast, finer than sand, coarser than investment",
            achievable=DimensionedValue.of("+/-0.5-1", "mm"),
        ),
    ),
    surface_finish=(
        SurfaceFinishEntry(condition="as-cast", ra=DimensionedValue.of("6.3-12.5", "um")),
    ),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="moderate tooling (EPS foam-pattern mold, often "
            "injection-molded foam beads)",
            note="single-piece complex geometry without core-assembly "
            "labor (procres/casting.md #37); no draft angle needed, foam "
            "is consumed not withdrawn",
        ),
    ),
    lead_class="complex one-piece castings (engine-block class), mid-to-"
    "high volume",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="all numeric envelope values are uncited engineering-"
            "consensus ranges (procres/casting.md #37)",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_value_window",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SAND_CASTING_CHECKS = DfmCheckSet(
    family="sand_casting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="wall_thickness >= min-fill-thickness for the "
                "declared alloy is a GEK-tier fluidity-threshold "
                "containment (procres/casting.md #31 DFM rule 1)",
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_draft_angle_min",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="draft_angle >= declared minimum on pattern-"
                "parting surfaces is GEK-tier pattern-withdrawal physics "
                "(procres/casting.md #31 DFM rule 2)",
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
INVESTMENT_CASTING_CHECKS = DfmCheckSet(
    family="investment_casting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="min_wall_thickness containment, finer window "
                "than sand casting (procres/casting.md #32 DFM rule 1)",
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
DIE_CASTING_CHECKS = DfmCheckSet(
    family="die_casting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="wall_thickness within declared min/max window, "
                "too thin=short-fill too thick=porosity (procres/"
                "casting.md #33 DFM rule 2)",
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_draft_angle_min",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="draft_angle >= declared min on die-pull surfaces, "
                "hard die-release gate (procres/casting.md #33 DFM rule 1)",
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PERMANENT_MOLD_CASTING_CHECKS = DfmCheckSet(
    family="permanent_mold_casting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="wall_thickness >= gravity-fill minimum for the "
                "alloy (procres/casting.md #34 DFM rule 2)",
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_draft_angle_min",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="draft_angle >= declared min (procres/casting.md "
                "#34 DFM rule 1)",
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
CENTRIFUGAL_CASTING_CHECKS = DfmCheckSet(
    family="centrifugal_casting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="geometry must be axisymmetric hollow, a hard "
                "gate like turning/spinning (procres/casting.md #35 DFM "
                "rule 1)",
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
CONTINUOUS_CASTING_CHECKS = DfmCheckSet(
    family="continuous_casting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="declared billet/slab cross-section must match an "
                "available mill product size (catalog containment, "
                "procres/casting.md #36 DFM rule 1) -- a stock-quality "
                "predicate, OUT OF SCOPE for per-part DFM per the "
                "dossier's own framing",
            ),
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
LOST_FOAM_CASTING_CHECKS = DfmCheckSet(
    family="lost_foam_casting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_value_window",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="min wall similar order to sand casting, fill-"
                "ability via metal-vaporizing-foam front (procres/"
                "casting.md #37 DFM rule 2)",
            ),
        ),
    ),
)

__all__ = [
    "CENTRIFUGAL_CASTING_CHECKS",
    "CENTRIFUGAL_CASTING_RECORD",
    "CONTINUOUS_CASTING_CHECKS",
    "CONTINUOUS_CASTING_RECORD",
    "DIE_CASTING_CHECKS",
    "DIE_CASTING_RECORD",
    "INVESTMENT_CASTING_CHECKS",
    "INVESTMENT_CASTING_RECORD",
    "LOST_FOAM_CASTING_CHECKS",
    "LOST_FOAM_CASTING_RECORD",
    "PERMANENT_MOLD_CASTING_CHECKS",
    "PERMANENT_MOLD_CASTING_RECORD",
    "SAND_CASTING_CHECKS",
    "SAND_CASTING_RECORD",
]
