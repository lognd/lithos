"""Tests for the mech manufacturing backend against a real realized part."""

from __future__ import annotations

from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.framework import BackendInputs
from regolith.backends.mech import AssemblyLine, FabNoteSpec, MechBackend, ToleranceRow
from regolith.orchestrator.lockfile import Lockfile
from regolith.realizer.mech.interpreter import realize_feature_program

from tests.realizer.mech.fixtures import plate_program


def _plate_inputs(tmp_path):
    realized = realize_feature_program(plate_program()).danger_ok
    native = NativeArtifactStore(str(tmp_path))
    native.put_at(realized.geometry.step_content_hash, realized.step_bytes)
    return realized, native


def test_mech_backend_emits_step_bom_and_fab_notes(tmp_path):
    realized, native = _plate_inputs(tmp_path)
    assembly = (
        AssemblyLine(
            subject="flat_plate",
            part_number="PN-001",
            description="Flat plate",
            material="AISI_304",
            quantity=2,
        ),
    )
    fab_notes = (
        FabNoteSpec(
            subject="flat_plate",
            material="AISI 304",
            finish="bead blast",
            quantity=2,
            tolerances=(
                ToleranceRow(
                    feature="thickness", nominal_mm=1.5, plus_mm=0.1, minus_mm=0.1
                ),
            ),
        ),
    )
    backend = MechBackend(assembly, fab_notes)
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={"flat_plate": realized.geometry},
        layouts={},
        native=native,
    )
    produced = backend.produce(inputs)
    assert produced.is_ok
    files = {f.relpath: f for f in produced.danger_ok}
    assert files["step/flat_plate.step"].content == realized.step_bytes
    assert "bom.csv" in files
    assert "bom.json" in files
    assert "fab_notes.json" in files
    assert b"PN-001" in files["bom.csv"].content
    assert b"bead blast" in files["fab_notes.json"].content


def test_mech_backend_honest_error_when_geometry_missing(tmp_path):
    native = NativeArtifactStore(str(tmp_path))
    assembly = (
        AssemblyLine(
            subject="missing_part",
            part_number="PN-002",
            description="Missing",
            material="AISI_304",
            quantity=1,
        ),
    )
    backend = MechBackend(assembly)
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={},
        layouts={},
        native=native,
    )
    produced = backend.produce(inputs)
    assert produced.is_err
    assert produced.danger_err.kind == "geometry_ir_unavailable"


def test_mech_backend_output_is_deterministic(tmp_path):
    realized, native = _plate_inputs(tmp_path)
    assembly = (
        AssemblyLine(
            subject="flat_plate",
            part_number="PN-001",
            description="Flat plate",
            material="AISI_304",
            quantity=1,
        ),
    )
    backend = MechBackend(assembly)
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={"flat_plate": realized.geometry},
        layouts={},
        native=native,
    )
    first = backend.produce(inputs).danger_ok
    second = backend.produce(inputs).danger_ok
    assert first == second
