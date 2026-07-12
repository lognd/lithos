"""Tests for the `regolith ship` driver.

`staged_build` is monkeypatched here rather than driven end to end: no
`.hema`/`.cupr` corpus source in this repo yet reaches T3 `RELEASE`
with a realized-geometry input wired through (WO-22's own "STILL
BLOCKED" upstream wall -- see its Progress note); these tests instead
prove `ship()`'s OWN contract (gate refusal, backend wiring, manifest
signing, file layout) against a fake `StagedBuildReport`, the same
dependency-injection discipline the realizer/harness test suites use
for their own unreachable-in-sandbox tools.
"""

from __future__ import annotations

import json

import regolith.backends.ship as ship_mod
from regolith._schema.models import (
    AssemblyPart,
    CopperSummary,
    EdgeParams1,
    FlowEdge,
    FlownetPayload,
    FramePayload,
    MediumRef,
    RealizedAssembly,
    RealizedLayout,
    RecordRef,
    Reference,
    ScalarInterval,
)
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.elec import ElecBackend
from regolith.backends.instructions import InstructionsBackend
from regolith.backends.mech import AssemblyLine as MechLine
from regolith.backends.mech import MechBackend
from regolith.compiler import RealizedInput
from regolith.errors import OrchestratorError
from regolith.magnetite.trust import (
    KeyDesignation,
    TrustKeySet,
    TrustTier,
    generate_signing_key,
)
from regolith.orchestrator.discharge import ObligationResult
from regolith.orchestrator.lockfile import Lockfile
from regolith.orchestrator.orchestrate import BuildReport, StagedBuildReport
from regolith.orchestrator.tiers import BuildTier
from regolith.realizer.mech.interpreter import realize_feature_program
from typani.result import Err, Ok

from tests.realizer.mech.fixtures import plate_program


def _clean_report(realized_inputs=()) -> StagedBuildReport:
    final = BuildReport(tier=BuildTier.RELEASE, ok=True, release_ok=True)
    return StagedBuildReport(final=final, iterations=1, realized_inputs=realized_inputs)


def _dirty_report() -> StagedBuildReport:
    final = BuildReport(
        tier=BuildTier.RELEASE,
        ok=True,
        release_ok=False,
        unresolved=(ObligationResult(key="k", subject_ref="s"),),
    )
    return StagedBuildReport(final=final, iterations=1)


def test_ship_refuses_when_release_gate_not_clean(tmp_path, monkeypatch):
    monkeypatch.setattr(ship_mod, "staged_build", lambda *a, **k: Ok(_dirty_report()))
    result = ship_mod.ship(
        (str(tmp_path),),
        {},
        str(tmp_path / "out"),
        lockfile=Lockfile(tool_version="0.1.0"),
    )
    assert result.is_err
    assert result.danger_err.kind == "release_not_ready"


def test_ship_refuses_when_staged_build_errs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ship_mod,
        "staged_build",
        lambda *a, **k: Err(OrchestratorError(kind="x", message="boom")),
    )
    result = ship_mod.ship(
        (str(tmp_path),),
        {},
        str(tmp_path / "out"),
        lockfile=Lockfile(tool_version="0.1.0"),
    )
    assert result.is_err
    assert result.danger_err.kind == "build_failed"


def test_ship_manifest_only_when_no_backends(tmp_path, monkeypatch):
    monkeypatch.setattr(ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report()))
    out = tmp_path / "out"
    result = ship_mod.ship(
        (str(tmp_path),), {}, str(out), lockfile=Lockfile(tool_version="0.1.0")
    )
    assert result.is_ok
    manifest = result.danger_ok
    # WO-99 d4: even with zero backends the package carries its one
    # layout -- the deterministic index + gate/parity/acceptance ledgers
    # (no per-family artifact files, but never an empty package).
    assert {f.relpath for f in manifest.files} == {
        "index.md",
        "gate_summary.json",
        "parity_ledger.json",
        "acceptance_ledger.json",
    }
    assert (out / "manifest.json").is_file()
    assert (out / "index.md").is_file()


def test_ship_writes_mech_backend_files_under_namespaced_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report()))
    realized = realize_feature_program(plate_program()).danger_ok
    native = NativeArtifactStore(str(tmp_path))
    native.put_at(realized.geometry.step_content_hash, realized.step_bytes)

    backend = MechBackend(
        (
            MechLine(
                subject="flat_plate",
                part_number="PN-1",
                description="Plate",
                material="AISI_304",
                quantity=1,
            ),
        )
    )
    out = tmp_path / "out"
    result = ship_mod.ship(
        (str(tmp_path),),
        {"mech": backend},
        str(out),
        lockfile=Lockfile(tool_version="0.1.0"),
        geometry={"flat_plate": realized.geometry},
        native=native,
    )
    assert result.is_ok
    manifest = result.danger_ok
    relpaths = {f.relpath for f in manifest.files}
    assert "mech/step/flat_plate.step" in relpaths
    assert "mech/bom.csv" in relpaths
    assert (
        out / "mech" / "step" / "flat_plate.step"
    ).read_bytes() == realized.step_bytes


def test_ship_writes_instructions_backend_files_never_stamped(tmp_path, monkeypatch):
    """WO-96: `ship`'s `InstructionsBackend` consumer never carries a
    D197 preview stamp (the release gate is already clean at this
    point, unlike `preview`)."""
    monkeypatch.setattr(ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report()))
    assembly = RealizedAssembly(
        com_m=[0.0, 0.0, 0.0],
        dof_states={"Base": "fixed"},
        interferences=[],
        mass_kg=1.0,
        mating_graph_hash="blake3:ship_wo96",
        parts=[
            AssemblyPart(
                id="Base",
                geometry_digest="blake3:base",
                transform={
                    "translation_m": [0.0, 0.0, 0.0],
                    "rotation_deg": [0.0, 0.0, 0.0],
                },
            )
        ],
    )
    out = tmp_path / "out"
    result = ship_mod.ship(
        (str(tmp_path),),
        {"instructions": InstructionsBackend()},
        str(out),
        lockfile=Lockfile(tool_version="0.1.0"),
        assemblies={"gantry": assembly},
    )
    assert result.is_ok
    manifest = result.danger_ok
    relpaths = {f.relpath for f in manifest.files}
    assert "instructions/instructions/gantry.steps.json" in relpaths
    steps_json = json.loads(
        (out / "instructions" / "instructions" / "gantry.steps.json").read_text()
    )
    assert steps_json["stamp"] is None


def test_ship_derives_geometry_from_realized_inputs(tmp_path, monkeypatch):
    realized = realize_feature_program(plate_program()).danger_ok
    ri = RealizedInput(
        digest="blake3:whatever",
        kind="geometry.realized",
        subject="flat_plate",
        payload_bytes=realized.geometry.model_dump_json().encode("ascii"),
    )
    monkeypatch.setattr(
        ship_mod,
        "staged_build",
        lambda *a, **k: Ok(_clean_report(realized_inputs=(ri,))),
    )
    native = NativeArtifactStore(str(tmp_path))
    native.put_at(realized.geometry.step_content_hash, realized.step_bytes)
    backend = MechBackend(
        (
            MechLine(
                subject="flat_plate",
                part_number="PN-1",
                description="Plate",
                material="AISI_304",
                quantity=1,
            ),
        )
    )
    out = tmp_path / "out"
    result = ship_mod.ship(
        (str(tmp_path),),
        {"mech": backend},
        str(out),
        lockfile=Lockfile(tool_version="0.1.0"),
        native=native,
    )
    assert result.is_ok


def test_ship_signs_manifest_when_signer_given(tmp_path, monkeypatch):
    monkeypatch.setattr(ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report()))
    key = generate_signing_key(str(tmp_path), "ship-key").danger_ok
    out = tmp_path / "out"
    result = ship_mod.ship(
        (str(tmp_path),),
        {},
        str(out),
        lockfile=Lockfile(tool_version="0.1.0"),
        signer=key,
    )
    assert result.is_ok
    manifest = result.danger_ok
    assert manifest.signature is not None
    assert manifest.signature.key_id == "ship-key"


def test_ship_backend_failure_propagates(tmp_path, monkeypatch):
    monkeypatch.setattr(ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report()))
    layout = RealizedLayout(
        board_outline_ref="board",
        copper=CopperSummary(copper_areas_mm2=[], net_lengths_mm=[]),
        kicad_pcb_content_hash="ff" * 32,
        netlist_hash="ee" * 32,
        parasitics=[],
        placements=[],
        routed_segments=[],
    )
    backend = ElecBackend("board", (), available=lambda: False)
    out = tmp_path / "out"
    result = ship_mod.ship(
        (str(tmp_path),),
        {"elec": backend},
        str(out),
        lockfile=Lockfile(tool_version="0.1.0"),
        layouts={"board": layout},
    )
    assert result.is_err
    assert result.danger_err.kind == "tool_unavailable"


def test_verify_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report()))
    key = generate_signing_key(str(tmp_path), "verify-key").danger_ok
    out = tmp_path / "out"
    shipped = ship_mod.ship(
        (str(tmp_path),),
        {},
        str(out),
        lockfile=Lockfile(tool_version="0.1.0"),
        signer=key,
    )
    assert shipped.is_ok
    keys = TrustKeySet(
        designations=(
            KeyDesignation(
                key_id=key.key_id,
                public_key_base64=key.public_key_base64(),
                confers=TrustTier.COMMUNITY,
            ),
        )
    )
    verified = ship_mod.verify(str(out), keys)
    assert verified.is_ok


def test_verify_detects_tampered_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report()))
    realized = realize_feature_program(plate_program()).danger_ok
    native = NativeArtifactStore(str(tmp_path))
    native.put_at(realized.geometry.step_content_hash, realized.step_bytes)
    backend = MechBackend(
        (
            MechLine(
                subject="flat_plate",
                part_number="PN-1",
                description="Plate",
                material="AISI_304",
                quantity=1,
            ),
        )
    )
    key = generate_signing_key(str(tmp_path), "tamper-key").danger_ok
    out = tmp_path / "out"
    ship_mod.ship(
        (str(tmp_path),),
        {"mech": backend},
        str(out),
        lockfile=Lockfile(tool_version="0.1.0"),
        geometry={"flat_plate": realized.geometry},
        native=native,
        signer=key,
    )
    (out / "mech" / "bom.csv").write_bytes(b"tampered,,,,")
    keys = TrustKeySet(
        designations=(
            KeyDesignation(
                key_id=key.key_id,
                public_key_base64=key.public_key_base64(),
                confers=TrustTier.COMMUNITY,
            ),
        )
    )
    verified = ship_mod.verify(str(out), keys)
    assert verified.is_err
    assert verified.danger_err.kind == "hash_mismatch"


def _flownet() -> FlownetPayload:
    return FlownetPayload(
        edges=[
            FlowEdge(
                a="n1",
                b="n2",
                compliance=None,
                curves=[],
                id="e1",
                kind="pipe",
                params=EdgeParams1(source="scalars", values={}),
            )
        ],
        medium=MediumRef(records=[]),
        nodes=["n1", "n2"],
        reference=Reference(
            node="n1",
            p=ScalarInterval(lo=0.0, hi=0.0, unit="Pa"),
            t=ScalarInterval(lo=293.0, hi=293.0, unit="K"),
        ),
        states=[],
    )


def test_derive_producer_inputs_falls_back_to_payload_json_flownets(tmp_path) -> None:
    """WO-94 (D196.1): a fluorite flownet has no `PayloadRef` reaching
    `report.realized_inputs` the way mech/elec geometry does -- its
    `PayloadRef{kind:"flownet"}` resolves through the SEPARATE
    `PayloadStore`/`_put_flownet_payloads` channel instead. Without the
    `payload_json["flownets"]` fallback (mirroring the existing
    harnesses/contract_graph fallback), `derive_producer_inputs` would
    NEVER populate `BackendInputs.flownets` for any real build,
    silently making the fluid P&ID sheet unreachable through
    `regolith preview`/`ship --spec`."""
    flownet = _flownet()
    payload = json.dumps({"flownets": {"BrewPath": flownet.model_dump(mode="json")}})
    final = BuildReport(
        tier=BuildTier.BUILD,
        ok=True,
        payload_json=payload.encode("utf-8"),
    )
    report = StagedBuildReport(final=final, iterations=1)
    inputs = ship_mod.derive_producer_inputs(
        report,
        lockfile=Lockfile(tool_version="test"),
        native=NativeArtifactStore(str(tmp_path)),
    )
    assert "BrewPath" in inputs.flownets
    assert inputs.flownets["BrewPath"] == flownet


def test_derive_producer_inputs_explicit_flownets_override_payload_json(
    tmp_path,
) -> None:
    """An explicit `flownets=` argument still wins over the
    `payload_json` fallback (the existing `.update()` precedence every
    other derived map already has)."""
    from_payload = _flownet()
    payload = json.dumps(
        {"flownets": {"BrewPath": from_payload.model_dump(mode="json")}}
    )
    final = BuildReport(
        tier=BuildTier.BUILD,
        ok=True,
        payload_json=payload.encode("utf-8"),
    )
    report = StagedBuildReport(final=final, iterations=1)
    override = FlownetPayload(
        edges=[],
        medium=MediumRef(records=[]),
        nodes=["only"],
        reference=Reference(
            node="only",
            p=ScalarInterval(lo=0.0, hi=0.0, unit="Pa"),
            t=ScalarInterval(lo=293.0, hi=293.0, unit="K"),
        ),
        states=[],
    )
    inputs = ship_mod.derive_producer_inputs(
        report,
        lockfile=Lockfile(tool_version="test"),
        native=NativeArtifactStore(str(tmp_path)),
        flownets={"BrewPath": override},
    )
    assert inputs.flownets["BrewPath"] == override


def _frame() -> FramePayload:
    return FramePayload(
        combinations=RecordRef(digest="blake3:frame-combo", name="combo"),
        joints=[],
        loads=[],
        members=[],
        supports=[],
        transfers=[],
    )


def test_derive_producer_inputs_falls_back_to_payload_json_frames(tmp_path) -> None:
    """WO-94 close-out follow-up: a calcite/civil frame has no
    `PayloadRef` reaching `report.realized_inputs` the way mech/elec
    geometry does -- its `PayloadRef{kind:"frame"}` resolves through
    the SEPARATE discharge-time `PayloadStore` channel instead (same
    posture as a fluorite flownet, WO-94/D196.1). Without the
    `payload_json["frames"]` fallback (mirroring the existing
    flownets/harnesses/contract_graph fallback), `derive_producer_
    inputs` would NEVER populate `BackendInputs.frames` for any real
    build, silently making the civil plan/frame sheet unreachable
    through `regolith preview`/`ship --spec` -- confirmed live against
    `examples/flagships/timber_pavilion`: a real `staged_build` at
    `BuildTier.BUILD` leaves `report.realized_inputs` EMPTY while
    `payload_json["frames"]` carries the resolved `PavilionFrame`."""
    frame = _frame()
    payload = json.dumps({"frames": {"PavilionFrame": frame.model_dump(mode="json")}})
    final = BuildReport(
        tier=BuildTier.BUILD,
        ok=True,
        payload_json=payload.encode("utf-8"),
    )
    report = StagedBuildReport(final=final, iterations=1)
    inputs = ship_mod.derive_producer_inputs(
        report,
        lockfile=Lockfile(tool_version="test"),
        native=NativeArtifactStore(str(tmp_path)),
    )
    assert "PavilionFrame" in inputs.frames
    assert inputs.frames["PavilionFrame"] == frame


def test_derive_producer_inputs_explicit_frames_override_payload_json(
    tmp_path,
) -> None:
    """An explicit `frames=` argument still wins over the
    `payload_json` fallback (the existing `.update()` precedence every
    other derived map already has)."""
    from_payload = _frame()
    payload = json.dumps(
        {"frames": {"PavilionFrame": from_payload.model_dump(mode="json")}}
    )
    final = BuildReport(
        tier=BuildTier.BUILD,
        ok=True,
        payload_json=payload.encode("utf-8"),
    )
    report = StagedBuildReport(final=final, iterations=1)
    override = FramePayload(
        combinations=RecordRef(digest="blake3:override-combo", name="override"),
        joints=[],
        loads=[],
        members=[],
        supports=[],
        transfers=[],
    )
    inputs = ship_mod.derive_producer_inputs(
        report,
        lockfile=Lockfile(tool_version="test"),
        native=NativeArtifactStore(str(tmp_path)),
        frames={"PavilionFrame": override},
    )
    assert inputs.frames["PavilionFrame"] == override
