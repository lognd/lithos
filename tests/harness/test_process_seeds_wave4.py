"""WO-171 (process population wave 4, the subtractive/sheet/surface
remainder) -- proves every wave-4 record/check-set round-trips and
carries required provenance, and that each NEW generic check callable
(`check_min_floor`, `check_max_ceiling`, `check_coating_dimensional_
growth`) fires correctly on both a positive and a violation fixture.
This wave covers: subtractive remainder (17: milling, turning,
drilling, reaming, boring, tapping, honing, lapping, superfinishing,
sawing, broaching, waterjet, laser cutting, plasma cutting, oxy-fuel
cutting, ECM, gear hobbing/shaping), sheet remainder (8: shearing,
stamping/progressive-die, deep drawing, roll forming, spinning,
hydroforming, hemming/seaming, ISF), surface remainder (8: anodizing,
electroplating, electroless plating, passivation, painting, powder
coating, black oxide, PVD/CVD) -- 33 records total, closing the
100-entry rollup denominator to 100/100."""

from __future__ import annotations

import pytest
from regolith.harness.models.dfm.checks import (
    check_coating_dimensional_growth,
    check_max_ceiling,
    check_min_floor,
)
from regolith.harness.models.dfm.process_records import DfmCheckSet, ProcessRecord
from regolith.harness.models.dfm.process_seeds_wave4_sheet import (
    DEEP_DRAWING_CHECKS,
    DEEP_DRAWING_RECORD,
    HEMMING_SEAMING_CHECKS,
    HEMMING_SEAMING_RECORD,
    HYDROFORMING_CHECKS,
    HYDROFORMING_RECORD,
    ISF_CHECKS,
    ISF_RECORD,
    ROLL_FORMING_CHECKS,
    ROLL_FORMING_RECORD,
    SHEARING_CHECKS,
    SHEARING_RECORD,
    SPINNING_CHECKS,
    SPINNING_RECORD,
    STAMPING_PROGRESSIVE_CHECKS,
    STAMPING_PROGRESSIVE_RECORD,
)
from regolith.harness.models.dfm.process_seeds_wave4_subtractive import (
    BORING_CHECKS,
    BORING_RECORD,
    BROACHING_CHECKS,
    BROACHING_RECORD,
    DRILLING_CHECKS,
    DRILLING_RECORD,
    ECM_CHECKS,
    ECM_RECORD,
    GEAR_HOBBING_SHAPING_CHECKS,
    GEAR_HOBBING_SHAPING_RECORD,
    HONING_CHECKS,
    HONING_RECORD,
    LAPPING_CHECKS,
    LAPPING_RECORD,
    LASER_CUTTING_CHECKS,
    LASER_CUTTING_RECORD,
    MILLING_CHECKS,
    MILLING_RECORD,
    OXY_FUEL_CUTTING_CHECKS,
    OXY_FUEL_CUTTING_RECORD,
    PLASMA_CUTTING_CHECKS,
    PLASMA_CUTTING_RECORD,
    REAMING_CHECKS,
    REAMING_RECORD,
    SAWING_CHECKS,
    SAWING_RECORD,
    SUPERFINISHING_CHECKS,
    SUPERFINISHING_RECORD,
    TAPPING_CHECKS,
    TAPPING_RECORD,
    TURNING_CHECKS,
    TURNING_RECORD,
    WATERJET_CHECKS,
    WATERJET_RECORD,
)
from regolith.harness.models.dfm.process_seeds_wave4_surface import (
    ANODIZING_CHECKS,
    ANODIZING_RECORD,
    BLACK_OXIDE_CHECKS,
    BLACK_OXIDE_RECORD,
    ELECTROLESS_PLATING_CHECKS,
    ELECTROLESS_PLATING_RECORD,
    ELECTROPLATING_CHECKS,
    ELECTROPLATING_RECORD,
    PAINTING_CHECKS,
    PAINTING_RECORD,
    PASSIVATION_CHECKS,
    PASSIVATION_RECORD,
    POWDER_COATING_CHECKS,
    POWDER_COATING_RECORD,
    PVD_CVD_CHECKS,
    PVD_CVD_RECORD,
)

ALL_WAVE4_RECORDS = (
    # subtractive remainder (17)
    MILLING_RECORD,
    TURNING_RECORD,
    DRILLING_RECORD,
    REAMING_RECORD,
    BORING_RECORD,
    TAPPING_RECORD,
    HONING_RECORD,
    LAPPING_RECORD,
    SUPERFINISHING_RECORD,
    SAWING_RECORD,
    BROACHING_RECORD,
    WATERJET_RECORD,
    LASER_CUTTING_RECORD,
    PLASMA_CUTTING_RECORD,
    OXY_FUEL_CUTTING_RECORD,
    ECM_RECORD,
    GEAR_HOBBING_SHAPING_RECORD,
    # sheet remainder (8)
    SHEARING_RECORD,
    STAMPING_PROGRESSIVE_RECORD,
    DEEP_DRAWING_RECORD,
    ROLL_FORMING_RECORD,
    SPINNING_RECORD,
    HYDROFORMING_RECORD,
    HEMMING_SEAMING_RECORD,
    ISF_RECORD,
    # surface remainder (8)
    ANODIZING_RECORD,
    ELECTROPLATING_RECORD,
    ELECTROLESS_PLATING_RECORD,
    PASSIVATION_RECORD,
    PAINTING_RECORD,
    POWDER_COATING_RECORD,
    BLACK_OXIDE_RECORD,
    PVD_CVD_RECORD,
)

ALL_WAVE4_CHECK_SETS = (
    MILLING_CHECKS,
    TURNING_CHECKS,
    DRILLING_CHECKS,
    REAMING_CHECKS,
    BORING_CHECKS,
    TAPPING_CHECKS,
    HONING_CHECKS,
    LAPPING_CHECKS,
    SUPERFINISHING_CHECKS,
    SAWING_CHECKS,
    BROACHING_CHECKS,
    WATERJET_CHECKS,
    LASER_CUTTING_CHECKS,
    PLASMA_CUTTING_CHECKS,
    OXY_FUEL_CUTTING_CHECKS,
    ECM_CHECKS,
    GEAR_HOBBING_SHAPING_CHECKS,
    SHEARING_CHECKS,
    STAMPING_PROGRESSIVE_CHECKS,
    DEEP_DRAWING_CHECKS,
    ROLL_FORMING_CHECKS,
    SPINNING_CHECKS,
    HYDROFORMING_CHECKS,
    HEMMING_SEAMING_CHECKS,
    ISF_CHECKS,
    ANODIZING_CHECKS,
    ELECTROPLATING_CHECKS,
    ELECTROLESS_PLATING_CHECKS,
    PASSIVATION_CHECKS,
    PAINTING_CHECKS,
    POWDER_COATING_CHECKS,
    BLACK_OXIDE_CHECKS,
    PVD_CVD_CHECKS,
)


# --- record/check-set schema conformance (WO-168 round-trip pattern) ----


@pytest.mark.parametrize("record", ALL_WAVE4_RECORDS)
def test_wave4_record_round_trips(record: ProcessRecord) -> None:
    dumped = record.model_dump()
    restored = ProcessRecord(**dumped)
    assert restored == record


@pytest.mark.parametrize("record", ALL_WAVE4_RECORDS)
def test_wave4_record_carries_provenance(record: ProcessRecord) -> None:
    assert record.provenance, f"{record.key} must carry provenance"


@pytest.mark.parametrize("check_set", ALL_WAVE4_CHECK_SETS)
def test_wave4_check_set_round_trips(check_set: DfmCheckSet) -> None:
    dumped = check_set.model_dump()
    restored = DfmCheckSet(**dumped)
    assert restored == check_set


def test_wave4_covers_thirty_three_named_processes() -> None:
    """subtractive(17) + sheet(8) + surface(8) = 33 dossier entries,
    closing the rollup's 100-entry denominator (67 done pre-wave-4 +
    33 = 100/100)."""
    assert len(ALL_WAVE4_RECORDS) == 33
    keys = {r.key for r in ALL_WAVE4_RECORDS}
    assert len(keys) == 33, "record keys must be unique"
    assert len(ALL_WAVE4_CHECK_SETS) == 33


# --- check_min_floor (generic) -------------------------------------------


def test_check_min_floor_passes() -> None:
    outcome = check_min_floor(value_mm=2.0, min_mm=1.0)
    assert outcome.excess <= 0.0


def test_check_min_floor_violates() -> None:
    outcome = check_min_floor(value_mm=0.5, min_mm=1.0, quantity_name="corner radius")
    assert outcome.excess > 0.0
    assert "corner radius" in outcome.note
    assert "below the declared minimum" in outcome.note


# --- check_max_ceiling (generic) -----------------------------------------


def test_check_max_ceiling_passes() -> None:
    outcome = check_max_ceiling(value_mm=2.0, max_mm=5.0)
    assert outcome.excess <= 0.0


def test_check_max_ceiling_violates() -> None:
    outcome = check_max_ceiling(value_mm=10.0, max_mm=5.0, quantity_name="thickness")
    assert outcome.excess > 0.0
    assert "thickness" in outcome.note
    assert "exceeds the declared maximum" in outcome.note


# --- check_coating_dimensional_growth (generic) --------------------------


def test_check_coating_dimensional_growth_passes() -> None:
    outcome = check_coating_dimensional_growth(
        coating_thickness_mm=0.02, growth_factor=0.5, declared_compensation_mm=0.02
    )
    assert outcome.excess <= 0.0


def test_check_coating_dimensional_growth_violates() -> None:
    outcome = check_coating_dimensional_growth(
        coating_thickness_mm=0.05, growth_factor=1.0, declared_compensation_mm=0.01
    )
    assert outcome.excess > 0.0
    assert "below the required" in outcome.note


def test_check_coating_dimensional_growth_anodize_vs_plate_factor() -> None:
    """SAME callable, distinct growth_factor per process (procres/
    surface.md #84 anodizing ~0.5 vs #85 electroplating ~1.0) -- proves
    no duplication of the arithmetic across the two records."""
    anodize = check_coating_dimensional_growth(
        coating_thickness_mm=0.05, growth_factor=0.5, declared_compensation_mm=0.03
    )
    plate = check_coating_dimensional_growth(
        coating_thickness_mm=0.05, growth_factor=1.0, declared_compensation_mm=0.03
    )
    assert anodize.excess <= 0.0
    assert plate.excess > 0.0


# --- a representative die-set-adjacent fixture, mirroring wave1/wave3's
# own "worst excess governs" acceptance-criterion shape -------------------


def test_milling_fixture_fires_corner_radius_and_reach_checks_together() -> None:
    """A milling fixture with both an undersized corner radius AND an
    excessive pocket-depth/tool-diameter reach ratio -- proving two
    wave-4 generic checks fire together on one realistic fixture."""
    corner = check_min_floor(value_mm=1.0, min_mm=3.0, quantity_name="corner radius")
    reach = check_max_ceiling(value_mm=6.0, max_mm=5.0, quantity_name="reach ratio")
    outcomes = (corner, reach)
    assert all(o.excess > 0.0 for o in outcomes)
    worst = max(o.excess for o in outcomes)
    assert worst > 0.0

    corner_ok = check_min_floor(value_mm=4.0, min_mm=3.0, quantity_name="corner radius")
    reach_ok = check_max_ceiling(value_mm=4.0, max_mm=5.0, quantity_name="reach ratio")
    assert all(o.excess <= 0.0 for o in (corner_ok, reach_ok))
