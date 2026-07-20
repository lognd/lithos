"""`harness/models/hdl/sim_artifacts.py` unit tests (WO-155 deliverable
7/8, T-0068): the `SimReport`/`sim_report.json` shape, the content-
address cache key law, and the in-process `SimArtifactCache` lookup."""

from __future__ import annotations

import json
from pathlib import Path

from regolith.harness.models.hdl.sim_artifacts import (
    SimArtifactCache,
    SimArtifactFamily,
    SimMismatch,
    SimReport,
    VerilatorTraceBinaryArgs,
    default_sim_artifact_cache,
    parse_mismatches,
    read_trace_file,
    render_sim_report_json,
    sim_artifact_cache_key,
    trace_dump_statements,
)


def _report(**overrides: object) -> SimReport:
    base = dict(
        subject="mux2",
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
    )
    base.update(overrides)
    return SimReport(**base)  # type: ignore[arg-type]


# frob:tests python/regolith/harness/models/hdl/sim_artifacts.py::sim_artifact_cache_key kind="unit"
def test_sim_artifact_cache_key_is_deterministic_and_domain_separated() -> None:
    key_a = sim_artifact_cache_key("blake3:src", "blake3:stim", "1+verilator5.047")
    key_b = sim_artifact_cache_key("blake3:src", "blake3:stim", "1+verilator5.047")
    assert key_a == key_b
    assert key_a.startswith("blake3:")


# frob:tests python/regolith/harness/models/hdl/sim_artifacts.py::sim_artifact_cache_key kind="unit"
def test_sim_artifact_cache_key_changes_with_any_digest_or_version() -> None:
    base = sim_artifact_cache_key("blake3:src", "blake3:stim", "1+verilator5.047")
    assert base != sim_artifact_cache_key("blake3:other", "blake3:stim", "1+verilator5.047")
    assert base != sim_artifact_cache_key("blake3:src", "blake3:other", "1+verilator5.047")
    assert base != sim_artifact_cache_key("blake3:src", "blake3:stim", "1+verilator5.048")


# frob:tests python/regolith/harness/models/hdl/sim_artifacts.py::render_sim_report_json kind="unit"
def test_render_sim_report_json_shape_and_determinism() -> None:
    report = _report(
        vectors_passed=1,
        mismatches=(
            SimMismatch(vector="v0", cycle=1, expected="8'h11", got="8'h00"),
        ),
    )
    first = render_sim_report_json(report)
    second = render_sim_report_json(report)
    assert first == second, "identical report must render byte-identical JSON"
    doc = json.loads(first)
    assert doc["subject"] == "mux2"
    assert doc["tool"] == "verilator"
    assert doc["tool_version"] == "5.047"
    assert doc["vectors_run"] == 2
    assert doc["vectors_passed"] == 1
    assert doc["content_address"] == "blake3:key"
    assert doc["stimulus_ref"] == "mux_directed_vectors"
    assert doc["mismatches"] == [
        {"vector": "v0", "cycle": 1, "expected": "8'h11", "got": "8'h00"}
    ]
    assert doc["trace"] == {"present": True, "reason": None}


# frob:tests python/regolith/harness/models/hdl/sim_artifacts.py::SimArtifactCache kind="unit"
def test_sim_artifact_cache_get_put_roundtrip() -> None:
    cache = SimArtifactCache()
    key = sim_artifact_cache_key("blake3:src", "blake3:stim", "1+verilator5.047")
    assert cache.get(key) is None
    family = SimArtifactFamily(subject="mux2", report=_report(), trace_vcd=b"$end\n")
    cache.put(key, family)
    fetched = cache.get(key)
    assert fetched is not None
    assert fetched.report.content_address == "blake3:key"
    assert fetched.trace_vcd == b"$end\n"


# frob:tests python/regolith/harness/models/hdl/sim_artifacts.py::default_sim_artifact_cache kind="unit"
def test_default_sim_artifact_cache_is_a_shared_singleton() -> None:
    assert default_sim_artifact_cache() is default_sim_artifact_cache()


# frob:tests python/regolith/harness/models/hdl/sim_artifacts.py::parse_mismatches kind="unit"
def test_parse_mismatches_collects_every_assert_fail_line() -> None:
    stdout = (
        "PASS v0 cycle=1 value=17\n"
        "ASSERT FAIL v1 cycle=2 expected=34 got=0\n"
        "ASSERT FAIL v2 cycle=3 expected=1 got=2\n"
        "SIM_FAIL vectors=3 errors=2\n"
    )
    rows = parse_mismatches(stdout)
    assert [r.vector for r in rows] == ["v1", "v2"]
    assert rows[0].cycle == 2
    assert rows[0].expected == "34"
    assert rows[0].got == "0"


# frob:tests python/regolith/harness/models/hdl/sim_artifacts.py::read_trace_file kind="unit"
def test_read_trace_file_present(tmp_path: Path) -> None:
    (tmp_path / "trace.vcd").write_bytes(b"$dumpvars\n$end\n")
    result = read_trace_file(tmp_path)
    assert result.is_ok
    assert result.danger_ok == b"$dumpvars\n$end\n"


# frob:tests python/regolith/harness/models/hdl/sim_artifacts.py::read_trace_file kind="unit"
def test_read_trace_file_absent_is_a_named_reason_not_a_crash(tmp_path: Path) -> None:
    result = read_trace_file(tmp_path)
    assert result.is_err
    assert "named absence" in result.danger_err


# frob:tests python/regolith/harness/models/hdl/sim_artifacts.py::trace_dump_statements kind="unit"
def test_trace_dump_statements_names_the_trace_file_and_top() -> None:
    text = trace_dump_statements("tb")
    assert '$dumpfile("trace.vcd")' in text
    assert "$dumpvars(0, tb)" in text


# frob:tests python/regolith/harness/models/hdl/sim_artifacts.py::VerilatorTraceBinaryArgs.emit kind="unit"
def test_verilator_trace_binary_args_emit_adds_trace_flag() -> None:
    args = VerilatorTraceBinaryArgs(
        top_module="tb", tb_filename="tb.sv", hdl_filename="mux2.v"
    )
    argv = args.emit()
    assert "--trace" in argv
    assert argv[-2:] == ("tb.sv", "mux2.v")

