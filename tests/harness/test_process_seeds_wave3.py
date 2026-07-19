"""WO-171 (process population wave 3, the long tail) -- proves every
wave-3 record/check-set round-trips and carries required provenance,
and that each NEW generic check callable (`check_value_window`,
`check_draft_angle_min`, `check_ratio_max`, `check_boolean_gate`) fires
correctly on both a positive and a violation fixture. This wave covers
the entirely-new families the rollup denominator names: casting (7),
molding (7), powder (3), additive (7), joining (13), bulk forming (7)
-- 44 records total. The subtractive/sheet/surface remainders are NOT
in this wave (named explicitly in the wave-3 dispatch report as
remaining work)."""

from __future__ import annotations

import pytest
from regolith.harness.models.dfm.checks import (
    check_boolean_gate,
    check_draft_angle_min,
    check_ratio_max,
    check_value_window,
)
from regolith.harness.models.dfm.process_records import DfmCheckSet, ProcessRecord
from regolith.harness.models.dfm.process_seeds_wave3_additive import (
    BINDER_JETTING_CHECKS,
    BINDER_JETTING_RECORD,
    DED_CHECKS,
    DED_RECORD,
    DMLS_SLM_CHECKS,
    DMLS_SLM_RECORD,
    FDM_CHECKS,
    FDM_RECORD,
    MATERIAL_JETTING_CHECKS,
    MATERIAL_JETTING_RECORD,
    SLA_DLP_CHECKS,
    SLA_DLP_RECORD,
    SLS_CHECKS,
    SLS_RECORD,
)
from regolith.harness.models.dfm.process_seeds_wave3_bulk_forming import (
    CLOSED_DIE_FORGING_CHECKS,
    CLOSED_DIE_FORGING_RECORD,
    COLD_HEADING_CHECKS,
    COLD_HEADING_RECORD,
    EXTRUSION_CHECKS,
    EXTRUSION_RECORD,
    OPEN_DIE_FORGING_CHECKS,
    OPEN_DIE_FORGING_RECORD,
    ROLLING_CHECKS,
    ROLLING_RECORD,
    SWAGING_CHECKS,
    SWAGING_RECORD,
    WIRE_BAR_DRAWING_CHECKS,
    WIRE_BAR_DRAWING_RECORD,
)
from regolith.harness.models.dfm.process_seeds_wave3_casting import (
    CENTRIFUGAL_CASTING_CHECKS,
    CENTRIFUGAL_CASTING_RECORD,
    CONTINUOUS_CASTING_CHECKS,
    CONTINUOUS_CASTING_RECORD,
    DIE_CASTING_CHECKS,
    DIE_CASTING_RECORD,
    INVESTMENT_CASTING_CHECKS,
    INVESTMENT_CASTING_RECORD,
    LOST_FOAM_CASTING_CHECKS,
    LOST_FOAM_CASTING_RECORD,
    PERMANENT_MOLD_CASTING_CHECKS,
    PERMANENT_MOLD_CASTING_RECORD,
    SAND_CASTING_CHECKS,
    SAND_CASTING_RECORD,
)
from regolith.harness.models.dfm.process_seeds_wave3_joining import (
    ADHESIVE_BONDING_CHECKS,
    ADHESIVE_BONDING_RECORD,
    BRAZING_CHECKS,
    BRAZING_RECORD,
    FSW_CHECKS,
    FSW_RECORD,
    LASER_WELDING_CHECKS,
    LASER_WELDING_RECORD,
    MIG_CHECKS,
    MIG_RECORD,
    PRESS_FITS_CHECKS,
    PRESS_FITS_RECORD,
    RESISTANCE_SPOT_WELDING_CHECKS,
    RESISTANCE_SPOT_WELDING_RECORD,
    RIVETING_CHECKS,
    RIVETING_RECORD,
    SOLDERING_CHECKS,
    SOLDERING_RECORD,
    STICK_CHECKS,
    STICK_RECORD,
    THREADED_FASTENERS_CHECKS,
    THREADED_FASTENERS_RECORD,
    TIG_CHECKS,
    TIG_RECORD,
    ULTRASONIC_WELDING_CHECKS,
    ULTRASONIC_WELDING_RECORD,
)
from regolith.harness.models.dfm.process_seeds_wave3_molding import (
    BLOW_MOLDING_CHECKS,
    BLOW_MOLDING_RECORD,
    COMPRESSION_MOLDING_CHECKS,
    COMPRESSION_MOLDING_RECORD,
    INJECTION_MOLDING_CHECKS,
    INJECTION_MOLDING_RECORD,
    RIM_CHECKS,
    RIM_RECORD,
    ROTATIONAL_MOLDING_CHECKS,
    ROTATIONAL_MOLDING_RECORD,
    THERMOFORMING_CHECKS,
    THERMOFORMING_RECORD,
    TRANSFER_MOLDING_CHECKS,
    TRANSFER_MOLDING_RECORD,
)
from regolith.harness.models.dfm.process_seeds_wave3_powder import (
    HIP_CHECKS,
    HIP_RECORD,
    MIM_CHECKS,
    MIM_RECORD,
    PM_PRESS_SINTER_CHECKS,
    PM_PRESS_SINTER_RECORD,
)

ALL_WAVE3_RECORDS = (
    # casting (7)
    SAND_CASTING_RECORD,
    INVESTMENT_CASTING_RECORD,
    DIE_CASTING_RECORD,
    PERMANENT_MOLD_CASTING_RECORD,
    CENTRIFUGAL_CASTING_RECORD,
    CONTINUOUS_CASTING_RECORD,
    LOST_FOAM_CASTING_RECORD,
    # molding (7)
    INJECTION_MOLDING_RECORD,
    BLOW_MOLDING_RECORD,
    ROTATIONAL_MOLDING_RECORD,
    THERMOFORMING_RECORD,
    COMPRESSION_MOLDING_RECORD,
    TRANSFER_MOLDING_RECORD,
    RIM_RECORD,
    # powder (3)
    PM_PRESS_SINTER_RECORD,
    MIM_RECORD,
    HIP_RECORD,
    # additive (7)
    FDM_RECORD,
    SLA_DLP_RECORD,
    SLS_RECORD,
    DMLS_SLM_RECORD,
    BINDER_JETTING_RECORD,
    DED_RECORD,
    MATERIAL_JETTING_RECORD,
    # joining (13)
    TIG_RECORD,
    MIG_RECORD,
    STICK_RECORD,
    RESISTANCE_SPOT_WELDING_RECORD,
    BRAZING_RECORD,
    SOLDERING_RECORD,
    ADHESIVE_BONDING_RECORD,
    THREADED_FASTENERS_RECORD,
    RIVETING_RECORD,
    PRESS_FITS_RECORD,
    FSW_RECORD,
    LASER_WELDING_RECORD,
    ULTRASONIC_WELDING_RECORD,
    # bulk forming (7)
    OPEN_DIE_FORGING_RECORD,
    CLOSED_DIE_FORGING_RECORD,
    EXTRUSION_RECORD,
    ROLLING_RECORD,
    WIRE_BAR_DRAWING_RECORD,
    COLD_HEADING_RECORD,
    SWAGING_RECORD,
)

ALL_WAVE3_CHECK_SETS = (
    SAND_CASTING_CHECKS,
    INVESTMENT_CASTING_CHECKS,
    DIE_CASTING_CHECKS,
    PERMANENT_MOLD_CASTING_CHECKS,
    CENTRIFUGAL_CASTING_CHECKS,
    CONTINUOUS_CASTING_CHECKS,
    LOST_FOAM_CASTING_CHECKS,
    INJECTION_MOLDING_CHECKS,
    BLOW_MOLDING_CHECKS,
    ROTATIONAL_MOLDING_CHECKS,
    THERMOFORMING_CHECKS,
    COMPRESSION_MOLDING_CHECKS,
    TRANSFER_MOLDING_CHECKS,
    RIM_CHECKS,
    PM_PRESS_SINTER_CHECKS,
    MIM_CHECKS,
    HIP_CHECKS,
    FDM_CHECKS,
    SLA_DLP_CHECKS,
    SLS_CHECKS,
    DMLS_SLM_CHECKS,
    BINDER_JETTING_CHECKS,
    DED_CHECKS,
    MATERIAL_JETTING_CHECKS,
    TIG_CHECKS,
    MIG_CHECKS,
    STICK_CHECKS,
    RESISTANCE_SPOT_WELDING_CHECKS,
    BRAZING_CHECKS,
    SOLDERING_CHECKS,
    ADHESIVE_BONDING_CHECKS,
    THREADED_FASTENERS_CHECKS,
    RIVETING_CHECKS,
    PRESS_FITS_CHECKS,
    FSW_CHECKS,
    LASER_WELDING_CHECKS,
    ULTRASONIC_WELDING_CHECKS,
    OPEN_DIE_FORGING_CHECKS,
    CLOSED_DIE_FORGING_CHECKS,
    EXTRUSION_CHECKS,
    ROLLING_CHECKS,
    WIRE_BAR_DRAWING_CHECKS,
    COLD_HEADING_CHECKS,
    SWAGING_CHECKS,
)


# --- record/check-set schema conformance (WO-168 round-trip pattern) --


@pytest.mark.parametrize("record", ALL_WAVE3_RECORDS)
def test_wave3_record_round_trips(record: ProcessRecord) -> None:
    dumped = record.model_dump()
    restored = ProcessRecord(**dumped)
    assert restored == record


@pytest.mark.parametrize("record", ALL_WAVE3_RECORDS)
def test_wave3_record_carries_provenance(record: ProcessRecord) -> None:
    assert record.provenance, f"{record.key} must carry provenance"


@pytest.mark.parametrize("check_set", ALL_WAVE3_CHECK_SETS)
def test_wave3_check_set_round_trips(check_set: DfmCheckSet) -> None:
    dumped = check_set.model_dump()
    restored = DfmCheckSet(**dumped)
    assert restored == check_set


def test_wave3_covers_forty_four_named_processes() -> None:
    """casting(7) + molding(7) + powder(3) + additive(7) + joining(13)
    + bulk_forming(7) = 44 dossier entries for this wave."""
    assert len(ALL_WAVE3_RECORDS) == 44
    keys = {r.key for r in ALL_WAVE3_RECORDS}
    assert len(keys) == 44, "record keys must be unique"


def test_wave3_out_of_scope_stock_processes_flagged() -> None:
    """continuous casting, rolling, wire/bar drawing are the three
    upstream stock-supply entries the rollup names as explicitly OUT OF
    SCOPE for per-part DFM -- each cost_drivers entry must name it."""
    for record in (CONTINUOUS_CASTING_RECORD, ROLLING_RECORD, WIRE_BAR_DRAWING_RECORD):
        assert any(
            "out of scope" in cd.note.lower() or "out_of_scope" in cd.driver
            for cd in record.cost_drivers
        ), f"{record.key} must name its out-of-scope status"


# --- check_value_window (generic) --------------------------------------


def test_check_value_window_passes() -> None:
    outcome = check_value_window(value_mm=2.0, min_mm=1.0, max_mm=5.0)
    assert outcome.excess <= 0.0


def test_check_value_window_violates_below_min() -> None:
    outcome = check_value_window(value_mm=0.1, min_mm=1.0, max_mm=5.0)
    assert outcome.excess > 0.0
    assert "below minimum" in outcome.note


def test_check_value_window_violates_above_max() -> None:
    outcome = check_value_window(value_mm=10.0, min_mm=1.0, max_mm=5.0)
    assert outcome.excess > 0.0
    assert "above maximum" in outcome.note


# --- check_draft_angle_min (generic) ------------------------------------


def test_check_draft_angle_min_passes() -> None:
    outcome = check_draft_angle_min(draft_deg=2.0, min_draft_deg=1.0)
    assert outcome.excess <= 0.0


def test_check_draft_angle_min_violates() -> None:
    outcome = check_draft_angle_min(draft_deg=0.2, min_draft_deg=1.0)
    assert outcome.excess > 0.0
    assert "below the declared minimum" in outcome.note


# --- check_ratio_max (generic) ------------------------------------------


def test_check_ratio_max_passes() -> None:
    outcome = check_ratio_max(numerator_mm=1.0, denominator_mm=2.0, max_ratio=0.6)
    assert outcome.excess <= 0.0


def test_check_ratio_max_violates() -> None:
    outcome = check_ratio_max(numerator_mm=1.8, denominator_mm=2.0, max_ratio=0.6)
    assert outcome.excess > 0.0
    assert "exceeds" in outcome.note


def test_check_ratio_max_indeterminate_zero_denominator() -> None:
    outcome = check_ratio_max(numerator_mm=1.0, denominator_mm=0.0, max_ratio=0.6)
    assert outcome.indeterminate


# --- check_boolean_gate (generic) ---------------------------------------


def test_check_boolean_gate_passes() -> None:
    outcome = check_boolean_gate(
        condition_ok=True, note="axisymmetric hollow geometry declared"
    )
    assert outcome.excess == 0.0
    assert outcome.note == "axisymmetric hollow geometry declared"


def test_check_boolean_gate_violates() -> None:
    outcome = check_boolean_gate(
        condition_ok=False, note="undercut perpendicular to press axis"
    )
    assert outcome.excess == 1.0
    assert outcome.note == "undercut perpendicular to press axis"


# --- a representative die-casting fixture, mirroring wave1's own
# "worst excess governs" acceptance-criterion shape ----------------------


def test_die_casting_fixture_fires_draft_and_wall_checks_together() -> None:
    """A die-casting fixture with both an undersized draft angle AND an
    out-of-window wall thickness -- proving two wave-3 generic checks
    fire together on one realistic fixture (mirrors wave1's own
    `test_die_set_fixture_fires_wire_edm_and_punch_die_checks_together`)."""
    draft = check_draft_angle_min(draft_deg=0.3, min_draft_deg=1.0)
    wall = check_value_window(value_mm=3.5, min_mm=0.5, max_mm=2.0)
    outcomes = (draft, wall)
    assert all(o.excess > 0.0 for o in outcomes)
    worst = max(o.excess for o in outcomes)
    assert worst > 0.0

    draft_ok = check_draft_angle_min(draft_deg=1.5, min_draft_deg=1.0)
    wall_ok = check_value_window(value_mm=1.0, min_mm=0.5, max_mm=2.0)
    assert all(o.excess <= 0.0 for o in (draft_ok, wall_ok))
