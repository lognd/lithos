"""WO-170 (process population wave 2: PCB fab/assembly + perf-board +
elec-install) -- proves every wave-2 check function fires on both a
positive (passing) and a violation case, that every wave-2
`ProcessRecord`/`DfmCheckSet` round-trips and carries a required
`provenance` tuple, and that the perf-board check-set composes with
WO-165's real `check_no_shared_holes` capability check without
duplicating its arithmetic.
"""

from __future__ import annotations

import pytest
from regolith.harness.models.dfm.checks import (
    check_ampacity_containment,
    check_annular_ring,
    check_conduit_bend_radius,
    check_conduit_fill,
    check_copper_edge_clearance,
    check_hole_lead_clearance,
    check_masked_area_declared,
    check_min_trace_space,
    check_perfboard_grid_pitch,
    check_placement_pad_spacing,
    check_reflow_thermal_compat,
    check_via_drill_range,
    check_voltage_drop_limit,
    check_working_clearance,
)
from regolith.harness.models.dfm.process_records import DfmCheckSet, ProcessRecord
from regolith.harness.models.dfm.process_seeds_wave2_pcb_elec import (
    BRANCH_CIRCUIT_CHECKS,
    BRANCH_CIRCUIT_RECORD,
    CONDUIT_RACEWAY_CHECKS,
    CONDUIT_RACEWAY_RECORD,
    CONFORMAL_COATING_CHECKS,
    CONFORMAL_COATING_RECORD,
    PANEL_SERVICE_CHECKS,
    PANEL_SERVICE_RECORD,
    PCB_FAB_CHECKS,
    PCB_FAB_RECORD,
    PERFBOARD_ASSEMBLY_CHECKS,
    PERFBOARD_ASSEMBLY_RECORD,
    SMT_ASSEMBLY_CHECKS,
    SMT_ASSEMBLY_RECORD,
    THROUGH_HOLE_WAVE_SOLDER_CHECKS,
    THROUGH_HOLE_WAVE_SOLDER_RECORD,
)
from regolith.realizer.elec.board_assignment import (
    ComponentAssignment,
    RealizedBoardAssignment,
    WireAssignment,
)
from regolith.realizer.elec.perfboard import check_no_shared_holes

ALL_WAVE2_RECORDS = (
    PCB_FAB_RECORD,
    SMT_ASSEMBLY_RECORD,
    THROUGH_HOLE_WAVE_SOLDER_RECORD,
    CONFORMAL_COATING_RECORD,
    PERFBOARD_ASSEMBLY_RECORD,
    BRANCH_CIRCUIT_RECORD,
    PANEL_SERVICE_RECORD,
    CONDUIT_RACEWAY_RECORD,
)

ALL_WAVE2_CHECK_SETS = (
    PCB_FAB_CHECKS,
    SMT_ASSEMBLY_CHECKS,
    THROUGH_HOLE_WAVE_SOLDER_CHECKS,
    CONFORMAL_COATING_CHECKS,
    PERFBOARD_ASSEMBLY_CHECKS,
    BRANCH_CIRCUIT_CHECKS,
    PANEL_SERVICE_CHECKS,
    CONDUIT_RACEWAY_CHECKS,
)


# --- record/check-set schema conformance --------------------------------


@pytest.mark.parametrize("record", ALL_WAVE2_RECORDS)
def test_wave2_record_round_trips(record: ProcessRecord) -> None:
    dumped = record.model_dump()
    restored = ProcessRecord(**dumped)
    assert restored == record


@pytest.mark.parametrize("record", ALL_WAVE2_RECORDS)
def test_wave2_record_carries_provenance(record: ProcessRecord) -> None:
    assert record.provenance, f"{record.key} must carry provenance"


@pytest.mark.parametrize("check_set", ALL_WAVE2_CHECK_SETS)
def test_wave2_check_set_round_trips(check_set: DfmCheckSet) -> None:
    dumped = check_set.model_dump()
    restored = DfmCheckSet(**dumped)
    assert restored == check_set


def test_wave2_covers_eight_named_processes() -> None:
    """WO-170 names six process families (PCB fab, SMT assembly,
    through-hole/wave solder, conformal coating, perf-board assembly,
    elec-install) -- elec-install expands to three named entries
    (branch-circuit, panel/service, conduit/raceway) per procres/
    elec_install.md, giving 8 total records."""
    assert len(ALL_WAVE2_RECORDS) == 8
    assert len(ALL_WAVE2_CHECK_SETS) == 8


def test_panel_service_record_is_named_refusal() -> None:
    """The clearest missing entry in the elec-install family: panel/
    breaker catalog content is refused (D250 sec.3)."""
    postures = {note.posture for note in PANEL_SERVICE_RECORD.provenance}
    assert "named_refusal" in postures


# --- check callables: positive + violation cases ------------------------


def test_check_min_trace_space_pass() -> None:
    outcome = check_min_trace_space(0.15, 0.15, 0.1, 0.1)
    assert outcome.excess <= 0.0


def test_check_min_trace_space_violation() -> None:
    outcome = check_min_trace_space(0.05, 0.15, 0.1, 0.1)
    assert outcome.excess > 0.0


def test_check_annular_ring_pass() -> None:
    assert check_annular_ring(0.15, 0.1).excess <= 0.0


def test_check_annular_ring_violation() -> None:
    assert check_annular_ring(0.05, 0.1).excess > 0.0


def test_check_via_drill_range_pass() -> None:
    assert check_via_drill_range(0.2, 0.05, 0.3).excess <= 0.0


def test_check_via_drill_range_violation() -> None:
    assert check_via_drill_range(0.4, 0.05, 0.3).excess > 0.0


def test_check_copper_edge_clearance_pass() -> None:
    assert check_copper_edge_clearance(0.5, 0.3).excess <= 0.0


def test_check_copper_edge_clearance_violation() -> None:
    assert check_copper_edge_clearance(0.1, 0.3).excess > 0.0


def test_check_reflow_thermal_compat_pass() -> None:
    assert check_reflow_thermal_compat((255.0, 260.0), 250.0).excess <= 0.0


def test_check_reflow_thermal_compat_violation() -> None:
    assert check_reflow_thermal_compat((85.0, 260.0), 250.0).excess > 0.0


def test_check_reflow_thermal_compat_indeterminate() -> None:
    assert check_reflow_thermal_compat((), 250.0).indeterminate


def test_check_placement_pad_spacing_pass() -> None:
    assert check_placement_pad_spacing(0.5, 0.1, 0.1).excess <= 0.0


def test_check_placement_pad_spacing_violation() -> None:
    assert check_placement_pad_spacing(0.15, 0.1, 0.1).excess > 0.0


def test_check_hole_lead_clearance_pass() -> None:
    assert check_hole_lead_clearance(1.0, 0.8, 0.1, 0.4).excess <= 0.0


def test_check_hole_lead_clearance_violation_too_tight() -> None:
    assert check_hole_lead_clearance(0.85, 0.8, 0.1, 0.4).excess > 0.0


def test_check_hole_lead_clearance_indeterminate() -> None:
    assert check_hole_lead_clearance(0.5, 0.8, 0.1, 0.4).indeterminate


def test_check_masked_area_declared_pass() -> None:
    outcome = check_masked_area_declared(("connector1", "test_point1"), ("connector1",))
    assert outcome.excess == 0.0


def test_check_masked_area_declared_violation() -> None:
    outcome = check_masked_area_declared((), ("connector1",))
    assert outcome.excess == 1.0
    assert "connector1" in outcome.note


def test_check_perfboard_grid_pitch_pass() -> None:
    assert check_perfboard_grid_pitch(5.08, 2.54, 0.05).excess <= 0.0


def test_check_perfboard_grid_pitch_violation() -> None:
    assert check_perfboard_grid_pitch(3.0, 2.54, 0.05).excess > 0.0


def test_check_ampacity_containment_pass() -> None:
    assert check_ampacity_containment(20.0, 15.0).excess <= 0.0


def test_check_ampacity_containment_violation() -> None:
    assert check_ampacity_containment(15.0, 20.0).excess > 0.0


def test_check_voltage_drop_limit_pass() -> None:
    assert check_voltage_drop_limit(2.0, 3.0).excess <= 0.0


def test_check_voltage_drop_limit_violation() -> None:
    assert check_voltage_drop_limit(4.0, 3.0).excess > 0.0


def test_check_working_clearance_pass() -> None:
    assert check_working_clearance(1000.0, 900.0).excess <= 0.0


def test_check_working_clearance_violation() -> None:
    assert check_working_clearance(700.0, 900.0).excess > 0.0


def test_check_conduit_fill_pass() -> None:
    assert check_conduit_fill(35.0, 40.0).excess <= 0.0


def test_check_conduit_fill_violation() -> None:
    assert check_conduit_fill(45.0, 40.0).excess > 0.0


def test_check_conduit_bend_radius_pass() -> None:
    assert check_conduit_bend_radius(60.0, 20.0, 2.0).excess <= 0.0


def test_check_conduit_bend_radius_violation() -> None:
    assert check_conduit_bend_radius(20.0, 20.0, 2.0).excess > 0.0


# --- perf-board composes with WO-165's real check, no duplication ------


def test_perfboard_checkset_composes_with_capability_check() -> None:
    """The perf-board `DfmCheckSet` names the SAME
    `check_no_shared_holes` callable WO-165 deliverable 5 landed --
    proves composition rather than a duplicate arithmetic copy."""
    check_ids = {entry.check_id for entry in PERFBOARD_ASSEMBLY_CHECKS.checks}
    assert "regolith.realizer.elec.perfboard:check_no_shared_holes" in check_ids

    assignment = RealizedBoardAssignment(
        netlist_hash="deadbeef",
        board_outline_ref="std.process/perfboard_assembly",
        substrate_kind="perfboard",
        components=(
            ComponentAssignment(reference="R1", footprint="R0805", anchor_hole="0,0"),
            ComponentAssignment(reference="R2", footprint="R0805", anchor_hole="0,0"),
        ),
        wires=(
            WireAssignment(net="n1", from_hole="0,0", to_hole="0,1", length_mm=2.54),
        ),
    )
    result = check_no_shared_holes(assignment)
    assert result.is_err
