"""WO-169 (process population wave 1: EDM, heat-treat, stamping,
grinding, shot-peen) -- proves every wave-1 check function fires on
both a positive (passing) and a violation case, that every wave-1
`ProcessRecord`/`DfmCheckSet` round-trips and carries a required
`provenance` tuple, and the acceptance criterion that at least one
check is invoked the same way an existing DFM invocation path
(`ManufacturableModel.estimate`, `models.py`) invokes `check_stock_fit`/
`check_tool_fit`: pure declared-data in, worst-excess-governs verdict
out, with a concrete fixture proving a real violation fires.
"""

from __future__ import annotations

import pytest

from regolith.harness.models.dfm.checks import (
    check_grinding_stock_allowance,
    check_press_brake_bend_radius,
    check_press_tonnage,
    check_process_sequencing,
    check_punch_die_clearance,
    check_quench_section_uniformity,
    check_shot_peen_recast_remediation,
    check_sinker_edm_corner_radius,
    check_wire_edm_corner_radius,
    check_wire_edm_start_hole,
)
from regolith.harness.models.dfm.process_records import DfmCheckSet, ProcessRecord
from regolith.harness.models.dfm.process_seeds_wave1_heat_treat import (
    ANNEAL_CHECKS,
    ANNEAL_RECORD,
    AUSTEMPER_MARTEMPER_CHECKS,
    AUSTEMPER_MARTEMPER_RECORD,
    CASE_HARDEN_CHECKS,
    CASE_HARDEN_RECORD,
    INDUCTION_HARDEN_CHECKS,
    INDUCTION_HARDEN_RECORD,
    NITRIDE_CHECKS,
    NITRIDE_RECORD,
    NORMALIZE_CHECKS,
    NORMALIZE_RECORD,
    SOLUTION_TREAT_AGE_CHECKS,
    SOLUTION_TREAT_AGE_RECORD,
    STRESS_RELIEVE_CHECKS,
    STRESS_RELIEVE_RECORD,
)
from regolith.harness.models.dfm.process_seeds_wave1_sheet import (
    PRESS_BRAKE_BEND_CHECKS,
    PRESS_BRAKE_BEND_RECORD,
    STAMPING_BLANKING_CHECKS,
    STAMPING_BLANKING_RECORD,
)
from regolith.harness.models.dfm.process_seeds_wave1_subtractive import (
    GRINDING_CHECKS,
    GRINDING_RECORD,
    SINKER_EDM_CHECKS,
    SINKER_EDM_RECORD,
)
from regolith.harness.models.dfm.process_seeds_wave1_surface import (
    SHOT_PEENING_CHECKS,
    SHOT_PEENING_RECORD,
)

ALL_WAVE1_RECORDS = (
    SINKER_EDM_RECORD,
    GRINDING_RECORD,
    ANNEAL_RECORD,
    NORMALIZE_RECORD,
    CASE_HARDEN_RECORD,
    NITRIDE_RECORD,
    STRESS_RELIEVE_RECORD,
    INDUCTION_HARDEN_RECORD,
    AUSTEMPER_MARTEMPER_RECORD,
    SOLUTION_TREAT_AGE_RECORD,
    STAMPING_BLANKING_RECORD,
    PRESS_BRAKE_BEND_RECORD,
    SHOT_PEENING_RECORD,
)

ALL_WAVE1_CHECK_SETS = (
    SINKER_EDM_CHECKS,
    GRINDING_CHECKS,
    ANNEAL_CHECKS,
    NORMALIZE_CHECKS,
    CASE_HARDEN_CHECKS,
    NITRIDE_CHECKS,
    STRESS_RELIEVE_CHECKS,
    INDUCTION_HARDEN_CHECKS,
    AUSTEMPER_MARTEMPER_CHECKS,
    SOLUTION_TREAT_AGE_CHECKS,
    STAMPING_BLANKING_CHECKS,
    PRESS_BRAKE_BEND_CHECKS,
    SHOT_PEENING_CHECKS,
)


# --- record/check-set schema conformance (WO-168 round-trip pattern) --


@pytest.mark.parametrize("record", ALL_WAVE1_RECORDS)
def test_wave1_record_round_trips(record: ProcessRecord) -> None:
    dumped = record.model_dump()
    restored = ProcessRecord(**dumped)
    assert restored == record


@pytest.mark.parametrize("record", ALL_WAVE1_RECORDS)
def test_wave1_record_carries_provenance(record: ProcessRecord) -> None:
    assert record.provenance, f"{record.key} must carry provenance"


@pytest.mark.parametrize("check_set", ALL_WAVE1_CHECK_SETS)
def test_wave1_check_set_round_trips(check_set: DfmCheckSet) -> None:
    dumped = check_set.model_dump()
    restored = DfmCheckSet(**dumped)
    assert restored == check_set


def test_wave1_covers_thirteen_named_processes() -> None:
    """WO-169 deliverable 1 names 13 processes beyond the two WO-168
    seeds (wire EDM, Q&T already landed): sinker_edm, anneal,
    normalize, case_harden, nitride, stress_relieve, induction_harden,
    austemper_martemper, solution_treat_age, stamping_blanking,
    press_brake_bend, grinding, shot_peening."""
    assert len(ALL_WAVE1_RECORDS) == 13
    keys = {r.key for r in ALL_WAVE1_RECORDS}
    assert len(keys) == 13, "record keys must be unique"


# --- named-refusal spot checks (a sample, not exhaustive) -------------


def test_stamping_blanking_carries_named_refusal_for_punch_die_clearance() -> None:
    refusals = [
        n for n in STAMPING_BLANKING_RECORD.provenance if n.posture == "named_refusal"
    ]
    assert refusals
    assert "clearance" in refusals[0].refused_source.lower()


def test_case_harden_carries_named_refusal_for_materials_gap() -> None:
    refusals = [
        n for n in CASE_HARDEN_RECORD.provenance if n.posture == "named_refusal"
    ]
    assert refusals


def test_anneal_and_normalize_and_stress_relieve_carry_pd_gov() -> None:
    """MIL-H-6875 names exactly annealing, normalizing, stress-
    relieving (and hardening/tempering, already the WO-168 Q&T seed) as
    its four covered processes -- these three must carry `pd_gov`, not
    a downgraded `gek`."""
    for record in (ANNEAL_RECORD, NORMALIZE_RECORD, STRESS_RELIEVE_RECORD):
        postures = {n.posture for n in record.provenance}
        assert "pd_gov" in postures, f"{record.key} must carry pd_gov"


def test_induction_harden_and_nitride_are_gek_not_upgraded() -> None:
    """No independently-verified PD-GOV anchor for these two -- must
    stay `gek`, never dressed up as cited."""
    for record in (INDUCTION_HARDEN_RECORD, NITRIDE_RECORD):
        postures = {n.posture for n in record.provenance}
        assert postures == {"gek"}, f"{record.key} must be gek-only"


# --- wire EDM checks (already-referenced-but-unimplemented WO-168 debt,
# closed here) -----------------------------------------------------


def test_check_wire_edm_corner_radius_passes() -> None:
    outcome = check_wire_edm_corner_radius(
        internal_corner_radius_mm=0.5, kerf_width_mm=0.3, spark_gap_mm=0.02
    )
    assert outcome.excess <= 0.0


def test_check_wire_edm_corner_radius_violates() -> None:
    outcome = check_wire_edm_corner_radius(
        internal_corner_radius_mm=0.05, kerf_width_mm=0.3, spark_gap_mm=0.02
    )
    assert outcome.excess > 0.0
    assert "below" in outcome.note


def test_check_wire_edm_start_hole_passes_open_profile() -> None:
    outcome = check_wire_edm_start_hole(
        is_fully_enclosed_profile=False, has_declared_start_hole=False
    )
    assert outcome.excess == 0.0


def test_check_wire_edm_start_hole_violates_enclosed_without_start_hole() -> None:
    outcome = check_wire_edm_start_hole(
        is_fully_enclosed_profile=True, has_declared_start_hole=False
    )
    assert outcome.excess == 1.0
    assert "no declared wire start hole" in outcome.note


# --- sinker EDM --------------------------------------------------------


def test_check_sinker_edm_corner_radius_passes() -> None:
    outcome = check_sinker_edm_corner_radius(
        internal_corner_radius_mm=0.3,
        electrode_corner_radius_mm=0.1,
        spark_gap_mm=0.02,
    )
    assert outcome.excess <= 0.0


def test_check_sinker_edm_corner_radius_violates() -> None:
    outcome = check_sinker_edm_corner_radius(
        internal_corner_radius_mm=0.05,
        electrode_corner_radius_mm=0.1,
        spark_gap_mm=0.02,
    )
    assert outcome.excess > 0.0


# --- Q&T section uniformity (rollup priority 2) ------------------------


def test_check_quench_section_uniformity_passes() -> None:
    outcome = check_quench_section_uniformity(
        section_thicknesses_mm=(5.0, 6.0), max_ratio=2.0
    )
    assert outcome.excess <= 0.0


def test_check_quench_section_uniformity_violates() -> None:
    outcome = check_quench_section_uniformity(
        section_thicknesses_mm=(1.0, 10.0), max_ratio=2.0
    )
    assert outcome.excess > 0.0
    assert "exceeds" in outcome.note


def test_check_quench_section_uniformity_indeterminate_single_section() -> None:
    outcome = check_quench_section_uniformity(
        section_thicknesses_mm=(5.0,), max_ratio=2.0
    )
    assert outcome.indeterminate


# --- generic sequencing check (shared by 8 heat-treat records) --------


def test_check_process_sequencing_passes() -> None:
    outcome = check_process_sequencing(
        required_upstream="normalize", declared_upstream=("normalize", "anneal")
    )
    assert outcome.excess == 0.0


def test_check_process_sequencing_violates() -> None:
    outcome = check_process_sequencing(
        required_upstream="normalize", declared_upstream=("anneal",)
    )
    assert outcome.excess == 1.0
    assert "not among" in outcome.note


@pytest.mark.parametrize(
    "record",
    (
        ANNEAL_RECORD,
        NORMALIZE_RECORD,
        CASE_HARDEN_RECORD,
        NITRIDE_RECORD,
        STRESS_RELIEVE_RECORD,
        INDUCTION_HARDEN_RECORD,
        AUSTEMPER_MARTEMPER_RECORD,
        SOLUTION_TREAT_AGE_RECORD,
    ),
)
def test_heat_treat_records_cite_shared_sequencing_check(record: ProcessRecord) -> None:
    assert record.dfm_check_ids == (
        "regolith.harness.models.dfm.checks:check_process_sequencing",
    )


# --- punch-die clearance + press tonnage (rollup priority 3) ----------


def test_check_punch_die_clearance_passes() -> None:
    outcome = check_punch_die_clearance(
        clearance_mm=0.1, thickness_mm=2.0, min_pct=5.0, max_pct=10.0
    )
    assert outcome.excess <= 0.0


def test_check_punch_die_clearance_violates_too_tight() -> None:
    outcome = check_punch_die_clearance(
        clearance_mm=0.01, thickness_mm=2.0, min_pct=5.0, max_pct=10.0
    )
    assert outcome.excess > 0.0
    assert "below minimum" in outcome.note


def test_check_punch_die_clearance_violates_too_loose() -> None:
    outcome = check_punch_die_clearance(
        clearance_mm=0.5, thickness_mm=2.0, min_pct=5.0, max_pct=10.0
    )
    assert outcome.excess > 0.0
    assert "above maximum" in outcome.note


def test_check_press_tonnage_passes() -> None:
    outcome = check_press_tonnage(required_tonnage=50.0, press_capacity_tonnage=100.0)
    assert outcome.excess <= 0.0


def test_check_press_tonnage_violates() -> None:
    outcome = check_press_tonnage(required_tonnage=150.0, press_capacity_tonnage=100.0)
    assert outcome.excess > 0.0


# --- press-brake bend radius --------------------------------------------


def test_check_press_brake_bend_radius_passes() -> None:
    outcome = check_press_brake_bend_radius(
        bend_radius_mm=2.0, thickness_mm=2.0, min_radius_factor=1.0
    )
    assert outcome.excess <= 0.0


def test_check_press_brake_bend_radius_violates() -> None:
    outcome = check_press_brake_bend_radius(
        bend_radius_mm=0.5, thickness_mm=2.0, min_radius_factor=1.0
    )
    assert outcome.excess > 0.0


# --- grinding post-heat-treat finish (rollup priority 4) ---------------


def test_check_grinding_stock_allowance_passes() -> None:
    outcome = check_grinding_stock_allowance(
        stock_allowance_mm=0.02, min_removal_mm=0.005, max_removal_mm=0.05
    )
    assert outcome.excess <= 0.0


def test_check_grinding_stock_allowance_violates_too_little() -> None:
    outcome = check_grinding_stock_allowance(
        stock_allowance_mm=0.001, min_removal_mm=0.005, max_removal_mm=0.05
    )
    assert outcome.excess > 0.0
    assert "skip-cut floor" in outcome.note


def test_check_grinding_stock_allowance_violates_too_much() -> None:
    outcome = check_grinding_stock_allowance(
        stock_allowance_mm=0.5, min_removal_mm=0.005, max_removal_mm=0.05
    )
    assert outcome.excess > 0.0
    assert "per-pass ceiling" in outcome.note


# --- shot peen recast remediation (rollup priority 5) ------------------


def test_check_shot_peen_recast_remediation_passes() -> None:
    outcome = check_shot_peen_recast_remediation(
        upstream_process="wire_edm",
        required_upstream="wire_edm",
        compressive_depth_mm=0.3,
        min_depth_mm=0.1,
    )
    assert outcome.excess <= 0.0


def test_check_shot_peen_recast_remediation_violates_wrong_sequencing() -> None:
    outcome = check_shot_peen_recast_remediation(
        upstream_process="milling",
        required_upstream="wire_edm",
        compressive_depth_mm=0.3,
        min_depth_mm=0.1,
    )
    assert outcome.excess == 1.0
    assert "not the required" in outcome.note


def test_check_shot_peen_recast_remediation_violates_shallow_depth() -> None:
    outcome = check_shot_peen_recast_remediation(
        upstream_process="wire_edm",
        required_upstream="wire_edm",
        compressive_depth_mm=0.02,
        min_depth_mm=0.1,
    )
    assert outcome.excess > 0.0
    assert "below the declared fatigue-remediation floor" in outcome.note


# --- demo-exercised-check acceptance: mirrors ManufacturableModel's
# own worst-excess-governs invocation pattern (models.py:143's
# `max(stock.excess, tool.excess)`) over a die-set-plausible D268
# fixture: a wire-EDM'd die plate whose declared corner radius is too
# sharp for its own kerf/spark-gap AND whose punch-die clearance is out
# of the declared envelope -- proving TWO wave-1 checks fire together
# on one realistic fixture, the same "worst feature governs" shape the
# existing invocation path already uses. ---------------------------


def test_die_set_fixture_fires_wire_edm_and_punch_die_checks_together() -> None:
    """A D268-plausible die-plate fixture: sharp internal corner (below
    the kerf/spark-gap floor) AND out-of-envelope punch-die clearance.
    Mirrors `ManufacturableModel.estimate`'s own pattern (models.py)
    of running multiple checks and reporting the worst excess."""
    corner = check_wire_edm_corner_radius(
        internal_corner_radius_mm=0.05, kerf_width_mm=0.3, spark_gap_mm=0.02
    )
    clearance = check_punch_die_clearance(
        clearance_mm=0.01, thickness_mm=2.0, min_pct=5.0, max_pct=10.0
    )
    outcomes = (corner, clearance)
    assert all(o.excess > 0.0 for o in outcomes), (
        "both checks must fire as real violations on this fixture"
    )
    worst = max(o.excess for o in outcomes)
    assert worst > 0.0

    # Now the passing counterpart of the SAME fixture shape, proving
    # the checks are genuinely two-sided (not vacuously-always-fail).
    corner_ok = check_wire_edm_corner_radius(
        internal_corner_radius_mm=0.5, kerf_width_mm=0.3, spark_gap_mm=0.02
    )
    clearance_ok = check_punch_die_clearance(
        clearance_mm=0.15, thickness_mm=2.0, min_pct=5.0, max_pct=10.0
    )
    assert all(o.excess <= 0.0 for o in (corner_ok, clearance_ok))
