"""WO-155 (D264) acceptance criterion: a second identical
(src, stimulus, tool-version) `hdl.sim_assert` discharge is a cache
LOOKUP, not a re-invocation of verilator (charter 37 sec. 1.4's cache
rule, applied one layer down -- D264 ruling 2's gate economics)."""

from __future__ import annotations

import json
from pathlib import Path

from regolith._schema.models import Claim, ClaimForm1, Form, Given, Obligation
from regolith.harness import ModelRegistry
from regolith.harness.models.hdl import register_hdl_models
from regolith.orchestrator.cache import EvidenceStore
from regolith.orchestrator.discharge import discharge_one
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.plan_staging import PlanContext
from typani.result import Result

_MUX_SRC = (
    "module mux2(input sel, input [7:0] a, input [7:0] b, "
    "output [7:0] y);\n  assign y = sel ? b : a;\nendmodule\n"
)
_MUX_STIMULUS = {
    "top_module": "mux2",
    "ports": [
        {"name": "sel", "width": 1, "direction": "in"},
        {"name": "a", "width": 8, "direction": "in"},
        {"name": "b", "width": 8, "direction": "in"},
        {"name": "y", "width": 8, "direction": "out"},
    ],
    "vectors": [
        {
            "name": "v0",
            "inputs": [
                {"signal": "sel", "value": "1'b0"},
                {"signal": "a", "value": "8'h11"},
                {"signal": "b", "value": "8'h22"},
            ],
            "expect": [{"signal": "y", "expected": "8'h11"}],
        }
    ],
    "method": "hand-typed",
    "trust_tier": "authored",
}


# frob:ticket T-0025
def test_second_identical_sim_assert_discharge_is_a_cache_hit_no_reverilate(
    tmp_path, monkeypatch
) -> None:
    (tmp_path / "mux2.v").write_text(_MUX_SRC)
    (tmp_path / "mux_directed_vectors").write_text(json.dumps(_MUX_STIMULUS))

    registry = ModelRegistry(version="test-registry")
    register_hdl_models(registry)
    payload_store = PayloadStore(str(tmp_path))
    plan_context = PlanContext(
        project_root=str(tmp_path), records={}, store=payload_store
    )
    evidence_store = EvidenceStore()

    calls = {"n": 0}
    import regolith.harness.models.hdl.models as hdl_models
    from regolith.procio import ToolArgs, ToolFailure, ToolOutput

    real_run_verilator = hdl_models.run_verilator

    def _counting_run_verilator(
        args: ToolArgs, *, cwd: Path, timeout_s: float = 120.0
    ) -> Result[ToolOutput, ToolFailure]:
        calls["n"] += 1
        return real_run_verilator(args, cwd=cwd, timeout_s=timeout_s)

    monkeypatch.setattr(hdl_models, "run_verilator", _counting_run_verilator)

    obligation = Obligation(
        claim=Claim(
            name="hdl.sim_assert",
            form=ClaimForm1(
                form=Form.comparison, lhs="hdl.sim_assert", op="<=", rhs="0"
            ),
            forall=[],
            hints=[],
        ),
        subject_ref="blake3:mux2",
        given=Given(
            materials=[],
            loads=[
                "hdl_src_ref: mux2.v",
                "hdl_regime: verilog2001",
                "stimulus_ref: mux_directed_vectors",
            ],
            backing=[],
        ),
        hints=[],
    )

    first = discharge_one(
        obligation,
        registry=registry,
        store=evidence_store,
        payload_store=payload_store,
        plan_context=plan_context,
    )
    assert first.evidence is not None, first
    assert first.evidence.status.value == "discharged"
    assert not first.from_cache
    calls_after_first = calls["n"]
    assert calls_after_first >= 1, "the cold run must actually invoke verilator"

    second = discharge_one(
        obligation,
        registry=registry,
        store=evidence_store,
        payload_store=payload_store,
        plan_context=plan_context,
    )
    assert second.from_cache, second
    assert calls["n"] == calls_after_first, (
        "a second identical (src, stimulus, tool-version) discharge must "
        "be a pure cache lookup -- verilator must not run again"
    )
