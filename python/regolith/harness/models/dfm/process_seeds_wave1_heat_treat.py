"""WO-169 wave-1 population: the heat-treatment family remainder
(quench+temper already landed as a WO-168 seed,
`process_seeds.py:QUENCH_TEMPER_RECORD`). This module adds the other
eight named processes (procres/heat_treatment.md #75-76, #78-83):
anneal, normalize, case-harden, nitride, stress-relieve, induction-
harden, austemper/martemper, solution-treat-age.

Every dossier entry in this family frames its OWN DFM rule as a
material-state/process-SEQUENCING predicate ("does the claimed
downstream operation require this state as a precondition"), not a
geometric one -- so all eight records cite the SAME generic
`check_process_sequencing` callable (`checks.py`) rather than each
inventing its own boolean-membership arithmetic (NO DUPLICATION). Two
records (case-harden, solution-treat-age) ALSO name a material-
composition gate in their dossier text; that composition check is
named as a WO-169 non-goal deferral in the record's own provenance
note (composition validation belongs to `std.materials`'s own record
schema, T-0038's scope, not this DFM check-set), consistent with
WO-169's own non-goal ("no re-deriving of dossier numbers ... a named
gap for this WO's close-out, not a license to estimate").

Provenance: MIL-H-6875 (spot-verified real, DTIC/everyspec-hosted)
names annealing, normalizing, and stress-relieving directly as three
of its four covered processes -- those three carry `pd_gov` per the
dossier's own finding; the rest are `gek`, preserved verbatim (no
downgrade of the real anchor, no upgrade of the uncited ones)."""

from __future__ import annotations

from regolith.backends.quantity import DimensionedValue
from regolith.harness.models.dfm.process_records import (
    CostDriver,
    DfmCheckEntry,
    DfmCheckSet,
    MinFeature,
    ProcessRecord,
    ProvenanceNote,
)

_SEQ_CHECK_ID = "regolith.harness.models.dfm.checks:check_process_sequencing"

# frob:doc docs/modules/py-harness.md#models-dfm-process
ANNEAL_RECORD = ProcessRecord(
    key="std.process/anneal",
    name="Annealing (full / process anneal)",
    din_8580_class="4.2",
    materials=("std.materials/tool_steel_d2", "std.materials/tool_steel_a2"),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="furnace-time-dominated batch process",
            note="lead-time class hours-to-a-day including furnace cool "
            "(procres/heat_treatment.md #75)",
        ),
    ),
    lead_class="hours-to-a-day (slow furnace cool)",
    provenance=(
        ProvenanceNote(
            posture="pd_gov",
            scope="record",
            detail="MIL-H-6875 names annealing as one of its four "
            "covered processes, spot-verified real this recon pass "
            "(procres/heat_treatment.md #75)",
        ),
    ),
    dfm_check_ids=(_SEQ_CHECK_ID,),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
NORMALIZE_RECORD = ProcessRecord(
    key="std.process/normalize",
    name="Normalizing",
    din_8580_class="4.2",
    materials=("std.materials/tool_steel_d2", "std.materials/tool_steel_a2"),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="furnace-time-dominated, faster cycle than anneal",
            note="no extended furnace-cool hold; air-cool instead "
            "(procres/heat_treatment.md #76)",
        ),
    ),
    lead_class="hours (air-cool, faster than annealing)",
    provenance=(
        ProvenanceNote(
            posture="pd_gov",
            scope="record",
            detail="MIL-H-6875 names normalizing directly (procres/"
            "heat_treatment.md #76)",
        ),
    ),
    dfm_check_ids=(_SEQ_CHECK_ID,),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
CASE_HARDEN_RECORD = ProcessRecord(
    key="std.process/case_harden",
    name="Case hardening (carburizing)",
    din_8580_class="4.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="case depth",
            value=DimensionedValue.of("0.3-2", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="furnace-time proportional to desired case depth",
            note="deeper case = longer diffusion cycle (procres/heat_treatment.md #78)",
        ),
    ),
    lead_class="hours (diffusion-time-dominated)",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="case-depth range and hardness values are uncited "
            "engineering-consensus figures (procres/heat_treatment.md "
            "#78); no PD-GOV anchor independently verified for "
            "carburizing specifically",
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="materials",
            detail="the low-carbon case-hardening-grade composition gate "
            "(e.g. 8620-class) is a `std.materials` record-population "
            "concern (T-0038's scope), not this DFM check-set -- "
            "deferred as a WO-169 non-goal (no dossier-number "
            "re-derivation without a citable source), a genuine "
            "materials-record population gap named explicitly rather "
            "than estimated here",
            refused_source="ASM Metals Handbook case-hardening-grade "
            "composition tables",
            lift_condition="std.materials gains a case-hardening-grade "
            "steel record (e.g. std.materials/steel_8620) this record's "
            "`materials` field can then cite",
        ),
    ),
    dfm_check_ids=(_SEQ_CHECK_ID,),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
NITRIDE_RECORD = ProcessRecord(
    key="std.process/nitride",
    name="Nitriding",
    din_8580_class="4.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(feature="case depth", value=DimensionedValue.of("0.1-0.5", "mm")),
    ),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="long diffusion cycle (tens of hours)",
            note="lower distortion-related rework cost than Q&T/"
            "carburizing (no quench step); requires a special nitriding-"
            "grade alloy (procres/heat_treatment.md #79)",
        ),
    ),
    lead_class="tens of hours (long diffusion time, no quench)",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="case-depth and hardness ranges are uncited "
            "engineering-consensus figures (procres/heat_treatment.md "
            "#79)",
        ),
    ),
    dfm_check_ids=(_SEQ_CHECK_ID,),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
STRESS_RELIEVE_RECORD = ProcessRecord(
    key="std.process/stress_relieve",
    name="Stress relief",
    din_8580_class="4.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="low added cost, simple furnace hold, no quench",
            note="cheap insurance against distortion in downstream "
            "precision operations (procres/heat_treatment.md #80)",
        ),
    ),
    lead_class="hours (simple furnace hold, no quench)",
    provenance=(
        ProvenanceNote(
            posture="pd_gov",
            scope="record",
            detail="MIL-H-6875 names stress-relieving as one of its four "
            "covered processes (procres/heat_treatment.md #80)",
        ),
    ),
    dfm_check_ids=(_SEQ_CHECK_ID,),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
INDUCTION_HARDEN_RECORD = ProcessRecord(
    key="std.process/induction_harden",
    name="Induction hardening",
    din_8580_class="4.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="fast cycle (seconds-to-minutes), custom coil "
            "per part feature",
            note="very economical at production volume for selective "
            "surface hardening (procres/heat_treatment.md #81)",
        ),
    ),
    lead_class="seconds-to-minutes per part (very fast cycle)",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="case-depth-vs-frequency and cycle-time figures are "
            "uncited engineering-consensus values (procres/"
            "heat_treatment.md #81); no PD-GOV anchor independently "
            "verified for induction hardening specifically",
        ),
    ),
    dfm_check_ids=(_SEQ_CHECK_ID,),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
AUSTEMPER_MARTEMPER_RECORD = ProcessRecord(
    key="std.process/austemper_martemper",
    name="Austempering / martempering (interrupted quench)",
    din_8580_class="4.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="specialized molten-salt/hot-oil quench bath",
            note="higher equipment/process complexity cost than plain "
            "Q&T, justified where toughness-at-hardness or reduced "
            "distortion is worth it (procres/heat_treatment.md #82)",
        ),
    ),
    lead_class="batch process, hours (interrupted quench + hold)",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="applicability and toughness-advantage claims are "
            "uncited engineering-consensus statements, DIRECTLY "
            "dependent on feldspar T-0018's forthcoming TTT/CCT model "
            "for any quantitative (non-hand-wavy) process-window "
            "prediction -- the clearest GEK-only-pending-a-model entry "
            "in this dossier (procres/heat_treatment.md #82)",
        ),
    ),
    dfm_check_ids=(_SEQ_CHECK_ID,),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SOLUTION_TREAT_AGE_RECORD = ProcessRecord(
    key="std.process/solution_treat_age",
    name="Solution treat + age (precipitation hardening)",
    din_8580_class="4.2",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="furnace-time-dominated (solution treat + quench + age)",
            note="similar overall cost class to steel Q&T (procres/"
            "heat_treatment.md #83)",
        ),
    ),
    lead_class="hours (solution treat + quench + age)",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="applicable ONLY to age-hardenable non-ferrous "
            "alloys (aluminum 2xxx/6xxx/7xxx, titanium, some nickel "
            "superalloys) -- a mechanistically distinct hardening "
            "family from steel Q&T, not overlapping it (procres/"
            "heat_treatment.md #83)",
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="min_features",
            detail="precise per-alloy aging-curve (time/temperature vs "
            "strength) values are omitted; only the GEK-tier "
            "Hollomon-Jaffe-class curve SHAPE is stated",
            refused_source="ASM Metals Handbook aging-curve charts "
            "(per-alloy, e.g. 7075/6061)",
            lift_condition="feldspar T-0018's Hollomon-Jaffe model lands "
            "and predicts the curve directly, or a licensed ASM Handbook "
            "excerpt is transcribed with in-row citation",
        ),
    ),
    dfm_check_ids=(_SEQ_CHECK_ID,),
)


def _sequencing_entry(dossier_note: str) -> DfmCheckEntry:
    """One `DfmCheckEntry` citing the shared `check_process_sequencing`
    callable with a process-specific dossier note (avoids repeating
    the same provenance detail text eight times with no distinguishing
    citation)."""
    return DfmCheckEntry(
        check_id=_SEQ_CHECK_ID,
        provenance=ProvenanceNote(posture="gek", scope="record", detail=dossier_note),
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
ANNEAL_CHECKS = DfmCheckSet(
    family="anneal",
    checks=(
        _sequencing_entry(
            "state-precondition sequencing predicate (procres/"
            "heat_treatment.md #75 DFM rule 1: does a claimed downstream "
            "cold-forming/machining step require this material state)"
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
NORMALIZE_CHECKS = DfmCheckSet(
    family="normalize",
    checks=(
        _sequencing_entry(
            "state-precondition sequencing predicate (procres/"
            "heat_treatment.md #76 DFM rule 1: refined-grain precondition "
            "for a downstream hardening/machining step)"
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
CASE_HARDEN_CHECKS = DfmCheckSet(
    family="case_harden",
    checks=(
        _sequencing_entry(
            "case-hardening-grade material precondition (procres/"
            "heat_treatment.md #78 DFM rule 1: distinct low-carbon "
            "composition class from Q&T's hardenable-alloy gate)"
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
NITRIDE_CHECKS = DfmCheckSet(
    family="nitride",
    checks=(
        _sequencing_entry(
            "nitriding-grade material precondition (procres/"
            "heat_treatment.md #79 DFM rule 1: composition-specific "
            "alloy-class gate distinct from Q&T/carburizing)"
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
STRESS_RELIEVE_CHECKS = DfmCheckSet(
    family="stress_relieve",
    checks=(
        _sequencing_entry(
            "heavy-removal-or-welding-then-finish sequencing predicate "
            "(procres/heat_treatment.md #80 DFM rule 1)"
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
INDUCTION_HARDEN_CHECKS = DfmCheckSet(
    family="induction_harden",
    checks=(
        _sequencing_entry(
            "hardenable-base-composition precondition (procres/"
            "heat_treatment.md #81 DFM rule 1: same material class as "
            "Q&T, distinct from carburizing's low-carbon gate)"
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
AUSTEMPER_MARTEMPER_CHECKS = DfmCheckSet(
    family="austemper_martemper",
    checks=(
        _sequencing_entry(
            "TTT/CCT-reachable-bainite-window precondition (procres/"
            "heat_treatment.md #82 DFM rule 1: a materials-selection "
            "predicate, currently GEK-only pending feldspar T-0018)"
        ),
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SOLUTION_TREAT_AGE_CHECKS = DfmCheckSet(
    family="solution_treat_age",
    checks=(
        _sequencing_entry(
            "age-hardenable-alloy composition precondition (procres/"
            "heat_treatment.md #83 DFM rule 1: distinct from and NOT "
            "overlapping Q&T's ferrous hardenable-alloy gate)"
        ),
    ),
)

__all__ = [
    "ANNEAL_CHECKS",
    "ANNEAL_RECORD",
    "AUSTEMPER_MARTEMPER_CHECKS",
    "AUSTEMPER_MARTEMPER_RECORD",
    "CASE_HARDEN_CHECKS",
    "CASE_HARDEN_RECORD",
    "INDUCTION_HARDEN_CHECKS",
    "INDUCTION_HARDEN_RECORD",
    "NITRIDE_CHECKS",
    "NITRIDE_RECORD",
    "NORMALIZE_CHECKS",
    "NORMALIZE_RECORD",
    "SOLUTION_TREAT_AGE_CHECKS",
    "SOLUTION_TREAT_AGE_RECORD",
    "STRESS_RELIEVE_CHECKS",
    "STRESS_RELIEVE_RECORD",
]
