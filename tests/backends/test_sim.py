"""Tests for `SimBackend` (WO-155 deliverable 7, T-0068): the `sim/`
manufacturing package -- `trace.vcd` (when the discharge captured one)
+ `sim_report.json`, both tagged `model_derived` provenance citing the
stimulus ref, plus artifact-index registration."""

from __future__ import annotations

import json

from regolith.backends.artifact_index import build_index, check_index_consistency
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.framework import BackendInputs
from regolith.backends.sim import SimBackend, SimMismatchRow, SimProducts
from regolith.orchestrator.lockfile import Lockfile


def _inputs(*, sim: dict[str, SimProducts]) -> BackendInputs:
    return BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore("/tmp/unused-sim-native"),
        sim=sim,
    )


def _products(**overrides: object) -> SimProducts:
    base: dict[str, object] = dict(
        tool_version="5.047",
        src_digest="blake3:src",
        stimulus_digest="blake3:stim",
        stimulus_ref="mux_directed_vectors",
        content_address="blake3:key",
        vectors_run=2,
        vectors_passed=2,
        mismatches=(),
        trace_present=True,
        trace_absent_reason=None,
        trace_vcd=b"$enddefinitions $end\n",
    )
    base.update(overrides)
    return SimProducts(**base)  # type: ignore[arg-type]


def test_sim_backend_ships_trace_and_report_with_model_derived_tier() -> None:
    products = _products()
    inputs = _inputs(sim={"mux2": products})
    produced = SimBackend().produce(inputs)
    assert produced.is_ok, produced
    files = {f.relpath: f for f in produced.danger_ok}

    trace = files["sim/mux2/trace.vcd"]
    assert trace.content == b"$enddefinitions $end\n"
    assert trace.provenance is not None
    assert trace.provenance.tier == "model_derived"
    assert trace.provenance.tool is not None
    assert trace.provenance.tool.name == "verilator"
    assert trace.provenance.tool.version_digest == "5.047"

    report = json.loads(files["sim/mux2/sim_report.json"].content)
    assert report["subject"] == "mux2"
    assert report["stimulus_ref"] == "mux_directed_vectors"
    assert report["content_address"] == "blake3:key"
    assert report["vectors_run"] == 2
    assert report["vectors_passed"] == 2
    assert report["trace"] == {"present": True, "reason": None}


def test_sim_backend_honest_absence_when_trace_unavailable() -> None:
    """D264 ruling 2: no `--trace` support in this tool environment is a
    NAMED absence recorded in `sim_report.json` -- never a fabricated
    trace.vcd, and no trace.vcd file ships at all."""
    products = _products(
        trace_present=False,
        trace_absent_reason="verilator --trace did not produce trace.vcd",
        trace_vcd=None,
    )
    inputs = _inputs(sim={"mux2": products})
    produced = SimBackend().produce(inputs)
    assert produced.is_ok, produced
    files = {f.relpath: f for f in produced.danger_ok}
    assert "sim/mux2/trace.vcd" not in files
    report = json.loads(files["sim/mux2/sim_report.json"].content)
    assert report["trace"]["present"] is False
    assert "did not produce" in report["trace"]["reason"]


def test_sim_backend_reports_full_mismatch_table() -> None:
    products = _products(
        vectors_passed=1,
        mismatches=(
            SimMismatchRow(vector="v1", cycle=2, expected="8'h22", got="8'h00"),
        ),
    )
    inputs = _inputs(sim={"mux2": products})
    produced = SimBackend().produce(inputs)
    files = {f.relpath: f for f in produced.danger_ok}
    report = json.loads(files["sim/mux2/sim_report.json"].content)
    assert report["mismatches"] == [
        {"vector": "v1", "cycle": 2, "expected": "8'h22", "got": "8'h00"}
    ]


def test_sim_backend_no_subjects_ships_nothing() -> None:
    produced = SimBackend().produce(_inputs(sim={}))
    assert produced.is_ok
    assert produced.danger_ok == ()


def test_sim_backend_output_registers_in_the_artifact_index() -> None:
    """Acceptance criterion 3: the emitted family registers in the
    universal artifact index (family=`sim`, model_derived tier, stimulus
    ref carried in the report -- source_refs cite it via the caller's
    own `source_refs` map, matching `build_index`'s existing contract)."""
    products = _products()
    inputs = _inputs(sim={"mux2": products})
    produced = SimBackend().produce(inputs).danger_ok
    index = build_index(
        "proj",
        produced,
        source_refs={f.relpath: (products.stimulus_ref,) for f in produced},
    ).danger_ok
    assert check_index_consistency(index, produced).is_ok
    rows = {r.relpath: r for r in index.rows}
    assert rows["sim/mux2/trace.vcd"].family == "sim"
    assert rows["sim/mux2/trace.vcd"].provenance.tier == "model_derived"
    assert rows["sim/mux2/trace.vcd"].source_refs == ("mux_directed_vectors",)
    assert rows["sim/mux2/sim_report.json"].source_refs == ("mux_directed_vectors",)
