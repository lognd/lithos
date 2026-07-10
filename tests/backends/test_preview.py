"""Unit tests for `regolith.backends.preview` (D197): the shared
producer set, the honesty stamp applied through the `DrawingModel`
(never a rendered-file post-edit), `auto_specs`'s no-``--spec``
derivation, and `run_preview`'s file layout.
"""

from __future__ import annotations

import json

from regolith._schema.models import (
    AssemblyPart,
    ContractEdge,
    ContractGraphPayload,
    ContractNode,
    RealizedAssembly,
)
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.drawings.backend import DrawingSpec, model_for_spec, stamp_model
from regolith.backends.framework import BackendInputs
from regolith.backends.preview import auto_specs, run_preview
from regolith.orchestrator.discharge import ObligationResult
from regolith.orchestrator.lockfile import Lockfile
from regolith.orchestrator.orchestrate import BuildReport, StagedBuildReport
from regolith.orchestrator.tiers import BuildTier


def _contract_graph() -> ContractGraphPayload:
    return ContractGraphPayload(
        nodes=[
            ContractNode(name="Bore", kind="interface", promise_slots=2),
            ContractNode(name="housing", kind="artifact", promise_slots=0),
        ],
        edges=[ContractEdge(name="press_fit", kind="load", a="housing", b="Bore")],
    )


def _report_with_contract_graph(*, clean: bool) -> StagedBuildReport:
    payload = json.dumps({"contract_graph": _contract_graph().model_dump(mode="json")})
    results = () if clean else (ObligationResult(key="k", subject_ref="s"),)
    final = BuildReport(
        tier=BuildTier.BUILD,
        ok=True,
        results=results,
        unresolved=results,
        payload_json=payload.encode("utf-8"),
    )
    return StagedBuildReport(final=final, iterations=1)


def test_stamp_model_adds_a_visible_annotation_on_every_sheet() -> None:
    graph = _contract_graph()
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="test"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore("."),
        contract_graph=graph,
    )
    spec = DrawingSpec(subject="g", track="contract_graph")
    model = model_for_spec(spec, inputs).danger_ok
    stamped = stamp_model(model, "PREVIEW -- NOT RELEASED: 3 unresolved")
    for sheet in stamped.sheets:
        texts = [a.text for a in sheet.annotations]
        assert "PREVIEW -- NOT RELEASED: 3 unresolved" in texts
    # the original model is untouched (frozen pydantic, never mutated)
    for sheet in model.sheets:
        assert "PREVIEW -- NOT RELEASED: 3 unresolved" not in [
            a.text for a in sheet.annotations
        ]


def test_auto_specs_derives_contract_graph_with_no_spec() -> None:
    graph = _contract_graph()
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="test"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore("."),
        contract_graph=graph,
    )
    specs = auto_specs(inputs)
    assert DrawingSpec(subject="contract_graph", track="contract_graph") in specs


def test_auto_specs_empty_when_nothing_derivable() -> None:
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="test"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore("."),
    )
    assert auto_specs(inputs) == ()


def test_run_preview_dirty_gate_writes_stamped_artifacts_and_gate_summary(
    tmp_path,
) -> None:
    report = _report_with_contract_graph(clean=False)
    out_dir = tmp_path / "preview"
    outcome = run_preview(
        report, None, str(out_dir), project_root=str(tmp_path)
    ).danger_ok

    assert outcome.gate.release_ok is False
    assert "gate_summary.json" in outcome.files
    assert any(f.endswith(".drawing.json") for f in outcome.files)

    gate_json = json.loads((out_dir / "gate_summary.json").read_text())
    assert gate_json["release_ok"] is False

    model_file = next(p for p in (out_dir / "drawings").glob("*.drawing.json"))
    model_data = json.loads(model_file.read_text())
    texts = [a["text"] for a in model_data["sheets"][0]["annotations"]]
    assert any(t.startswith("PREVIEW -- NOT RELEASED:") for t in texts)

    # ship-only artifacts never appear
    assert not (out_dir / "manifest.json").exists()


def test_run_preview_clean_gate_stamps_release_clean(tmp_path) -> None:
    report = _report_with_contract_graph(clean=True)
    out_dir = tmp_path / "preview"
    outcome = run_preview(
        report, None, str(out_dir), project_root=str(tmp_path)
    ).danger_ok

    assert outcome.gate.release_ok is True
    model_file = next((out_dir / "drawings").glob("*.drawing.json"))
    model_data = json.loads(model_file.read_text())
    texts = [a["text"] for a in model_data["sheets"][0]["annotations"]]
    assert "RELEASE-CLEAN" in texts


def test_run_preview_skips_a_spec_with_no_matching_ir_instead_of_crashing(
    tmp_path,
) -> None:
    report = _report_with_contract_graph(clean=True)
    out_dir = tmp_path / "preview"
    bad_spec = (DrawingSpec(subject="nope", track="mech"),)
    outcome = run_preview(
        report, bad_spec, str(out_dir), project_root=str(tmp_path)
    ).danger_ok

    assert "nope:mech" in outcome.skipped
    assert outcome.files == ("gate_summary.json",)


def _one_part_realized_assembly() -> RealizedAssembly:
    return RealizedAssembly(
        com_m=[0.0, 0.0, 0.0],
        dof_states={"Base": "fixed"},
        interferences=[],
        mass_kg=1.0,
        mating_graph_hash="blake3:preview_wo96",
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


def test_run_preview_writes_instructions_when_assemblies_supplied(tmp_path) -> None:
    report = _report_with_contract_graph(clean=False)
    out_dir = tmp_path / "preview"
    assemblies = {"gantry": _one_part_realized_assembly()}
    outcome = run_preview(
        report,
        None,
        str(out_dir),
        project_root=str(tmp_path),
        assemblies=assemblies,
    ).danger_ok

    assert "instructions/gantry.steps.json" in outcome.files
    assert "instructions/gantry.instructions.md" in outcome.files

    steps_json = json.loads(
        (out_dir / "instructions" / "gantry.steps.json").read_text()
    )
    assert steps_json["stamp"].startswith("PREVIEW -- NOT RELEASED:")
    assert [s["part_ref"] for s in steps_json["steps"]] == ["Base"]
