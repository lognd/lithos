"""WO-166 slice (c): die-set assembly composition + stamping DFM
(`regolith.realizer.mech.die_set`)."""

from __future__ import annotations

from regolith.harness.models.material_state import HeatTreatState
from regolith.realizer.mech.die_set import (
    DiePlate,
    DieSetAssembly,
    GuidePin,
    NamedRefusal,
    check_die_set_alignment,
    check_die_set_press_tonnage,
    check_die_set_punch_die_clearance,
    check_die_set_shot_peen_remediation,
    check_die_set_shut_height,
    guide_pin_alignment_tolerance_stack_mm,
    newtons_to_us_tons,
    required_tonnage_blanking_n,
    shut_height_mm,
)


def _assembly() -> DieSetAssembly:
    return DieSetAssembly(
        plates=(
            DiePlate(
                name="punch_plate",
                material_ref="std.materials/tool_steel_d2",
                heat_treat=HeatTreatState(
                    kind="quenched_and_tempered", temper_temp_c=205.0
                ),
                thickness_mm=20.0,
            ),
            DiePlate(
                name="die_plate",
                material_ref="std.materials/tool_steel_a2",
                heat_treat=HeatTreatState(
                    kind="quenched_and_tempered", temper_temp_c=205.0
                ),
                thickness_mm=25.0,
            ),
            DiePlate(
                name="backing_plate",
                material_ref="std.materials/plate_1018",
                heat_treat=HeatTreatState(kind="as_rolled"),
                thickness_mm=12.0,
            ),
        ),
        guide_pins=(
            GuidePin(diameter_mm=12.0, bushing_radial_clearance_mm=0.01),
            GuidePin(diameter_mm=12.0, bushing_radial_clearance_mm=0.01),
        ),
        fastener_refs=("std.fasteners/socket_head_cap_screw_m8x30",),
    )


def test_shut_height_sums_plate_thicknesses() -> None:
    assert shut_height_mm(_assembly()) == 57.0


def test_shut_height_within_press_window_passes() -> None:
    outcome = check_die_set_shut_height(_assembly(), 40.0, 80.0)
    assert not outcome.violated


def test_shut_height_outside_press_window_violates() -> None:
    outcome = check_die_set_shut_height(_assembly(), 60.0, 80.0)
    assert outcome.violated


def test_alignment_stack_sums_worst_case_clearances() -> None:
    assert guide_pin_alignment_tolerance_stack_mm(_assembly()) == 0.02


def test_alignment_within_budget_passes() -> None:
    outcome = check_die_set_alignment(_assembly(), 0.05)
    assert not outcome.violated


def test_alignment_over_budget_violates() -> None:
    outcome = check_die_set_alignment(_assembly(), 0.01)
    assert outcome.violated


def test_required_tonnage_blanking_formula() -> None:
    # perimeter(mm) * thickness(mm) * shear_strength(MPa) = force(N)
    force_n = required_tonnage_blanking_n(100.0, 2.0, 300.0)
    assert force_n == 100.0 * 2.0 * 300.0
    tons = newtons_to_us_tons(force_n)
    assert tons == force_n / 8896.44


def test_press_tonnage_check_passes_when_capacity_sufficient() -> None:
    required, outcome = check_die_set_press_tonnage(100.0, 2.0, 300.0, 100.0)
    assert required < 100.0
    assert not outcome.violated


def test_press_tonnage_check_violates_when_capacity_insufficient() -> None:
    required, outcome = check_die_set_press_tonnage(1000.0, 10.0, 400.0, 1.0)
    assert required > 1.0
    assert outcome.violated


def test_punch_die_clearance_refuses_without_a_cited_bound() -> None:
    result = check_die_set_punch_die_clearance(0.1, 2.0)
    assert isinstance(result, NamedRefusal)
    assert "Machinery's Handbook" in result.refused_source


def test_punch_die_clearance_runs_when_caller_supplies_a_cited_bound() -> None:
    result = check_die_set_punch_die_clearance(0.02, 2.0, min_pct=5.0, max_pct=10.0)
    assert not isinstance(result, NamedRefusal)
    assert result.violated  # 0.02/2.0=1% is below the declared 5% floor


def test_shot_peen_remediation_gate_after_wire_edm_passes() -> None:
    outcome = check_die_set_shot_peen_remediation(
        upstream_process="wire_edm", compressive_depth_mm=0.05, min_depth_mm=0.02
    )
    assert not outcome.violated


def test_shot_peen_remediation_gate_wrong_upstream_violates() -> None:
    outcome = check_die_set_shot_peen_remediation(
        upstream_process="milling", compressive_depth_mm=0.05, min_depth_mm=0.02
    )
    assert outcome.violated
