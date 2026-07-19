"""WO-171 wave-4 population: the surface-family remainder (procres/
surface.md #84-91 -- anodizing, electroplating, electroless plating,
passivation, painting, powder coating, black oxide, PVD/CVD). Shot
peening (#92) already landed in `process_seeds_wave1_surface.py`; this
wave closes the family to 9/9.

New this wave: `check_coating_dimensional_growth` (checks.py) grounds
anodizing's partial-growth and electroplating's additive-growth
mechanisms with the SAME callable (a declared `growth_factor`
distinguishes the two processes rather than duplicating the
arithmetic) -- the task's own named example of a distinctly-checkable
rule warranting a new callable this wave."""

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
)


def _gek(detail: str) -> ProvenanceNote:
    return ProvenanceNote(posture="gek", scope="record", detail=detail)


def _refuse(scope: str, detail: str, refused_source: str, lift_condition: str) -> ProvenanceNote:
    return ProvenanceNote(
        posture="named_refusal",
        scope=scope,
        detail=detail,
        refused_source=refused_source,
        lift_condition=lift_condition,
    )


# --- 84. Anodizing ---------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
ANODIZING_RECORD = ProcessRecord(
    key="std.process/anodizing",
    name="Anodizing",
    din_8580_class="5.3",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="coating_thickness_hardcoat",
            min=DimensionedValue.of("25", "um"),
            max=DimensionedValue.of("100", "um"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="dimensional growth per side (fraction of coating thickness)",
            value=DimensionedValue.of("~0.5", "ratio"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="LOW-to-moderate per-part cost (batch electrolytic bath), fast",
            note="sweet spot = any volume, standard finish for aluminum "
            "parts needing corrosion/wear resistance or color (procres/"
            "surface.md #84)",
        ),
    ),
    lead_class="fast batch electrolytic process",
    provenance=(
        _gek(
            "coating-thickness/growth-fraction values are uncited "
            "engineering-consensus (procres/surface.md #84)"
        ),
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="MIL-A-8625 is a plausible PD-GOV candidate for "
            "anodize coating classes, NOT independently re-verified this "
            "pass beyond the general MIL-spec-hosting pattern -- named "
            "open follow-up, not upgraded to pd_gov",
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_coating_dimensional_growth",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ANODIZING_CHECKS = DfmCheckSet(
    family="anodizing",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_coating_dimensional_growth",
            provenance=_gek(
                "dimensional growth allowance must be declared and "
                "compensated on any tight-tolerance mating feature -- "
                "the oxide grows roughly half the coating thickness per "
                "side (growth_factor~0.5), procres/surface.md #84 DFM "
                "rule 1"
            ),
        ),
    ),
)


# --- 85. Electroplating ----------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
ELECTROPLATING_RECORD = ProcessRecord(
    key="std.process/electroplating",
    name="Electroplating",
    din_8580_class="5.3",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="coating_thickness",
            min=DimensionedValue.of("2", "um"),
            max=DimensionedValue.of("50", "um"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="LOW-to-moderate per-part cost (batch "
            "electrolytic bath, similar cost class to anodizing)",
            note="precious-metal plating driven heavily by material cost, "
            "not process cost (procres/surface.md #85)",
        ),
    ),
    lead_class="fast batch electrolytic process",
    provenance=(
        _gek(
            "coating-thickness/throwing-power values are uncited "
            "engineering-consensus (procres/surface.md #85)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_coating_dimensional_growth",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ELECTROPLATING_CHECKS = DfmCheckSet(
    family="electroplating",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "substrate must be electrically conductive -- the same "
                "hard gate class as EDM/ECM (procres/surface.md #85 DFM "
                "rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_coating_dimensional_growth",
            provenance=_gek(
                "coating thickness adds ~fully to nominal dimension on "
                "exposed surfaces (growth_factor~1.0), the SAME callable "
                "as anodizing's #84 with a distinct declared growth "
                "factor (procres/surface.md #85 DFM rule 3)"
            ),
        ),
    ),
)


# --- 86. Electroless (chemical) plating -----------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
ELECTROLESS_PLATING_RECORD = ProcessRecord(
    key="std.process/electroless_plating",
    name="Electroless (chemical) plating",
    din_8580_class="5.2",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="coating_thickness",
            min=DimensionedValue.of("5", "um"),
            max=DimensionedValue.of("25", "um"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="HIGHER per-part material cost than "
            "electroplating (chemical bath consumption less efficient "
            "than electrolytic current)",
            note="sweet spot = complex internal-geometry parts (valves, "
            "hydraulic components, wire-EDM'd die cavities) needing "
            "uniform wear/corrosion coating (procres/surface.md #86)",
        ),
    ),
    lead_class="fast batch chemical process, no throwing-power limitation",
    provenance=(
        _gek(
            "coating-thickness/uniformity values are uncited engineering-"
            "consensus (procres/surface.md #86)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_coating_dimensional_growth",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
ELECTROLESS_PLATING_CHECKS = DfmCheckSet(
    family="electroless_plating",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_coating_dimensional_growth",
            provenance=_gek(
                "coating thickness adds to nominal dimension UNIFORMLY "
                "regardless of geometry (growth_factor~1.0, no throwing-"
                "power non-uniformity unlike electroplating's #85 rule "
                "2), procres/surface.md #86 DFM rule 3"
            ),
        ),
    ),
)


# --- 87. Passivation --------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
PASSIVATION_RECORD = ProcessRecord(
    key="std.process/passivation",
    name="Passivation",
    din_8580_class="5.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="LOW per-part cost (chemical bath dip, fast)",
            note="sweet spot = any volume of machined stainless parts "
            "(procres/surface.md #87)",
        ),
    ),
    lead_class="fast chemical bath dip",
    provenance=(
        _gek(
            "no measurable dimensional impact is uncited engineering-"
            "consensus (procres/surface.md #87)"
        ),
        _refuse(
            scope="record",
            detail="ASTM A967/A380 and AMS 2700 (the standard passivation "
            "specs) are omitted; no clean PD-GOV anchor found for "
            "passivation specifically this pass",
            refused_source="ASTM A967/A380, AMS 2700 passivation specs",
            lift_condition="a licensed copy of ASTM A967/A380 or AMS 2700 "
            "is obtained and its requirements transcribed with in-row "
            "citation",
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_process_sequencing",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PASSIVATION_CHECKS = DfmCheckSet(
    family="passivation",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "material class must be stainless steel -- a hard "
                "composition gate (procres/surface.md #87 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "passivation is typically a REQUIRED final step after "
                "any machining of stainless parts intended for "
                "corrosion-critical service -- a claim-eligibility/"
                "sequencing predicate (procres/surface.md #87 DFM rule 3)"
            ),
        ),
    ),
)


# --- 88. Painting (liquid) --------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
PAINTING_RECORD = ProcessRecord(
    key="std.process/painting",
    name="Painting (liquid)",
    din_8580_class="5.4",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="dry_film_thickness_per_coat",
            min=DimensionedValue.of("25", "um"),
            max=DimensionedValue.of("100", "um"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="LOW-to-moderate per-part cost, scales with "
            "coating complexity",
            note="sweet spot = any volume, cosmetic/corrosion finish for "
            "exposed parts (procres/surface.md #88)",
        ),
    ),
    lead_class="spray/dip + air-dry or bake cure",
    provenance=(
        _gek(
            "film-thickness/line-of-sight values are uncited engineering-"
            "consensus (procres/surface.md #88)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_process_sequencing",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PAINTING_CHECKS = DfmCheckSet(
    family="painting",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "line-of-sight coverage caveat must be declared for "
                "spray-applied coatings -- recessed features flagged "
                "unless e-coat or a masking/secondary-spray step is "
                "declared (procres/surface.md #88 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "cure/bake temperature compatibility must be declared "
                "against the substrate's prior heat-treat state -- a "
                "cross-family interaction with an over-aging risk on "
                "precipitation-hardened aluminum (procres/surface.md #88 "
                "DFM rule 3)"
            ),
        ),
    ),
)


# --- 89. Powder coating -----------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
POWDER_COATING_RECORD = ProcessRecord(
    key="std.process/powder_coating",
    name="Powder coating",
    din_8580_class="5.4",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="film_thickness",
            min=DimensionedValue.of("50", "um"),
            max=DimensionedValue.of("150", "um"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="LOW per-part material cost (unused powder "
            "largely reclaimable/reusable), moderate equipment cost",
            note="sweet spot = any volume, durable finish for conductive "
            "metal parts (procres/surface.md #89)",
        ),
    ),
    lead_class="electrostatic spray + oven bake",
    provenance=(
        _gek(
            "film-thickness/Faraday-cage values are uncited engineering-"
            "consensus (procres/surface.md #89)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_process_sequencing",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
POWDER_COATING_CHECKS = DfmCheckSet(
    family="powder_coating",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "substrate must be electrically conductive/groundable -- "
                "a hard gate (procres/surface.md #89 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "bake-temperature compatibility with the substrate's "
                "prior heat-treat state must be declared, the SAME "
                "cross-family predicate as liquid paint's #88 rule 3 "
                "(procres/surface.md #89 DFM rule 3)"
            ),
        ),
    ),
)


# --- 90. Black oxide ----------------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
BLACK_OXIDE_RECORD = ProcessRecord(
    key="std.process/black_oxide",
    name="Black oxide",
    din_8580_class="5.1",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(SurfaceFinishEntry(condition="as-applied", ra=DimensionedValue.of("negligible", "um")),),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="per_part",
            driver_class="very LOW per-part cost (a simple chemical dip, fast, cheap)",
            note="sweet spot = precision tooling, fasteners, firearms "
            "components needing zero dimensional change (procres/"
            "surface.md #90); the most dimensionally-safe cosmetic "
            "finish option for the D268 die-set program's hardened "
            "working surfaces",
        ),
    ),
    lead_class="fast chemical dip",
    provenance=(
        _gek(
            "sub-micron coating thickness (effectively zero dimensional "
            "impact) and modest corrosion-protection-without-topcoat "
            "values are uncited engineering-consensus (procres/"
            "surface.md #90)"
        ),
    ),
    dfm_check_ids=(
        "regolith.harness.models.dfm.checks:check_boolean_gate",
        "regolith.harness.models.dfm.checks:check_process_sequencing",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
BLACK_OXIDE_CHECKS = DfmCheckSet(
    family="black_oxide",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_boolean_gate",
            provenance=_gek(
                "material class must be ferrous -- a hard composition "
                "gate (procres/surface.md #90 DFM rule 1)"
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "an oil/wax topcoat must be declared if a genuine "
                "corrosion-resistance claim (beyond cosmetic) is made -- "
                "a claim-provenance predicate (procres/surface.md #90 DFM "
                "rule 3)"
            ),
        ),
    ),
)


# --- 91. PVD / CVD coating --------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
PVD_CVD_RECORD = ProcessRecord(
    key="std.process/pvd_cvd",
    name="PVD / CVD coating",
    din_8580_class="5.3",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="coating_thickness",
            min=DimensionedValue.of("1", "um"),
            max=DimensionedValue.of("10", "um"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(feature="coating hardness (common tool coatings)", value=DimensionedValue.of("2000-3500+", "HV")),
    ),
    cost_drivers=(
        CostDriver(
            driver="capital",
            driver_class="HIGH capital equipment cost (vacuum chamber), "
            "moderate per-part cost at batch scale",
            note="sweet spot = any volume of cutting tools or wear/"
            "decorative-critical parts (procres/surface.md #91); tool "
            "coating data is a real, currently-ABSENT enrichment to the "
            "existing std.tooling drill/end-mill records",
        ),
    ),
    lead_class="vacuum-chamber batch process",
    provenance=(
        _gek(
            "coating-thickness/hardness values are uncited engineering-"
            "consensus (procres/surface.md #91)"
        ),
    ),
    dfm_check_ids=("regolith.harness.models.dfm.checks:check_process_sequencing",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PVD_CVD_CHECKS = DfmCheckSet(
    family="pvd_cvd",
    checks=(
        DfmCheckEntry(
            check_id="regolith.harness.models.dfm.checks:check_process_sequencing",
            provenance=_gek(
                "substrate thermal budget (existing temper state) must "
                "be declared compatible with the chosen PVD (lower-temp) "
                "vs CVD (higher-temp) process -- a direct cross-link to "
                "the heat_treatment.md tempering-curve concern (procres/"
                "surface.md #91 DFM rule 1)"
            ),
        ),
    ),
)


__all__ = [
    "ANODIZING_CHECKS",
    "ANODIZING_RECORD",
    "BLACK_OXIDE_CHECKS",
    "BLACK_OXIDE_RECORD",
    "ELECTROLESS_PLATING_CHECKS",
    "ELECTROLESS_PLATING_RECORD",
    "ELECTROPLATING_CHECKS",
    "ELECTROPLATING_RECORD",
    "PAINTING_CHECKS",
    "PAINTING_RECORD",
    "PASSIVATION_CHECKS",
    "PASSIVATION_RECORD",
    "POWDER_COATING_CHECKS",
    "POWDER_COATING_RECORD",
    "PVD_CVD_CHECKS",
    "PVD_CVD_RECORD",
]
