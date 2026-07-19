"""WO-166 slice (a): the plain-pydantic material-state representation
(`regolith.harness.models.material_state`) -- state-kind field
validation and the quench+temper transition gate."""

from __future__ import annotations

import pytest
from regolith.harness.models.dfm.process_seeds import QUENCH_TEMPER_RECORD
from regolith.harness.models.material_state import (
    HeatTreatState,
    HeatTreatStep,
    check_heat_treat_transition,
)


# frob:tests python/regolith/harness/models/material_state.py::check_heat_treat_transition kind="unit"
def test_as_rolled_state_takes_no_extra_fields() -> None:
    state = HeatTreatState(kind="as_rolled")
    assert state.temper_temp_c is None
    assert state.target_hrc is None


def test_quenched_and_tempered_requires_temper_temp() -> None:
    with pytest.raises(ValueError, match="temper_temp_c"):
        HeatTreatState(kind="quenched_and_tempered")


def test_quenched_and_tempered_rejects_target_hrc() -> None:
    with pytest.raises(ValueError, match="target_hrc"):
        HeatTreatState(
            kind="quenched_and_tempered", temper_temp_c=200.0, target_hrc=60.0
        )


def test_through_hardened_requires_target_hrc() -> None:
    with pytest.raises(ValueError, match="target_hrc"):
        HeatTreatState(kind="through_hardened")


def test_through_hardened_rejects_temper_temp() -> None:
    with pytest.raises(ValueError, match="temper_temp_c"):
        HeatTreatState(kind="through_hardened", target_hrc=60.0, temper_temp_c=200.0)


def _qt_step(process_record_key: str = QUENCH_TEMPER_RECORD.key) -> HeatTreatStep:
    return HeatTreatStep(
        material_ref="std.materials/tool_steel_d2",
        from_state=HeatTreatState(kind="as_rolled"),
        to_state=HeatTreatState(kind="quenched_and_tempered", temper_temp_c=205.0),
        process_record_key=process_record_key,
    )


def test_transition_to_non_qt_state_passes_vacuously() -> None:
    step = HeatTreatStep(
        material_ref="std.materials/plate_1018",
        from_state=HeatTreatState(kind="as_rolled"),
        to_state=HeatTreatState(kind="as_rolled"),
        process_record_key="",
    )
    outcome = check_heat_treat_transition(step)
    assert not outcome.violated


def test_qt_transition_with_declared_record_and_uniform_sections_passes() -> None:
    outcome = check_heat_treat_transition(
        _qt_step(), section_thicknesses_mm=(20.0, 22.0), max_ratio=3.0
    )
    assert not outcome.violated


def test_qt_transition_missing_declared_process_key_is_violated() -> None:
    outcome = check_heat_treat_transition(
        _qt_step(process_record_key="std.process/some_other_step"),
        section_thicknesses_mm=(20.0, 22.0),
    )
    assert outcome.violated


def test_qt_transition_from_through_hardened_is_refused() -> None:
    step = HeatTreatStep(
        material_ref="std.materials/tool_steel_d2",
        from_state=HeatTreatState(kind="through_hardened", target_hrc=60.0),
        to_state=HeatTreatState(kind="quenched_and_tempered", temper_temp_c=205.0),
        process_record_key=QUENCH_TEMPER_RECORD.key,
    )
    outcome = check_heat_treat_transition(step, section_thicknesses_mm=(20.0, 22.0))
    assert outcome.violated


def test_qt_transition_with_non_uniform_sections_is_violated() -> None:
    outcome = check_heat_treat_transition(
        _qt_step(), section_thicknesses_mm=(5.0, 50.0), max_ratio=3.0
    )
    assert outcome.violated
