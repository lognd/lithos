"""WO-155 (D264): `_translate_hdl` forms a real `hdl.sim_assert`
`DischargeRequest` -- including a second `sim_stimulus` payload -- from
an obligation carrying the `stimulus_ref` given-field
`regolith_lower::claims::sim` emits. Closes the gap the WO-155 recon
named: translate wiring existed (WO-82) but no obligation ever carried
the field, so a real request never formed."""

from __future__ import annotations

import json

from regolith._schema.models import Claim, ClaimForm1, Form, Given, Obligation
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.plan_staging import PlanContext
from regolith.orchestrator.translate import _translate_hdl


# frob:ticket T-0025
def _obligation(*loads: str) -> Obligation:
    return Obligation(
        claim=Claim(
            name="hdl.sim_assert",
            form=ClaimForm1(
                form=Form.comparison, lhs="hdl.sim_assert", op="<=", rhs="0"
            ),
            forall=[],
            hints=[],
        ),
        subject_ref="blake3:deadbeef",
        given=Given(materials=[], loads=list(loads), backing=[]),
        hints=[],
    )


# frob:ticket T-0025
def _plan_context(tmp_path) -> PlanContext:
    return PlanContext(
        project_root=str(tmp_path), records={}, store=PayloadStore(str(tmp_path))
    )


# frob:ticket T-0025
def test_translate_hdl_forms_a_sim_assert_request_with_stimulus_payload(
    tmp_path,
) -> None:
    (tmp_path / "mux2.v").write_text("module mux2(); endmodule\n")
    stimulus = {
        "top_module": "mux2",
        "ports": [],
        "vectors": [{"name": "v0", "inputs": [], "expect": []}],
        "method": "hand-typed",
        "trust_tier": "authored",
    }
    (tmp_path / "mux_directed_vectors").write_text(json.dumps(stimulus))
    ob = _obligation(
        "hdl_src_ref: mux2.v",
        "hdl_regime: verilog2001",
        "stimulus_ref: mux_directed_vectors",
    )
    ctx = _plan_context(tmp_path)
    result = _translate_hdl(ob, "hdl.sim_assert", ctx)
    assert result.is_ok, result
    req = result.danger_ok
    assert req.claim_kind == "hdl.sim_assert"
    assert req.regimes == ("verilog2001",)
    assert "hdl_src" in req.payloads
    assert "sim_stimulus" in req.payloads
    assert req.payloads["sim_stimulus"].kind == "signal_table"


# frob:ticket T-0025
def test_translate_hdl_defers_on_unresolvable_stimulus_ref(tmp_path) -> None:
    """E1106's orchestrator-side leg: a `stimulus_ref` naming no file in
    the build is a named Deferral, never a silent skip."""
    (tmp_path / "mux2.v").write_text("module mux2(); endmodule\n")
    ob = _obligation(
        "hdl_src_ref: mux2.v",
        "hdl_regime: verilog2001",
        "stimulus_ref: does_not_exist",
    )
    ctx = _plan_context(tmp_path)
    result = _translate_hdl(ob, "hdl.sim_assert", ctx)
    assert result.is_err
    assert result.danger_err.reason == "stimulus_ref_unresolved"
    assert "E1106" in result.danger_err.detail


# frob:ticket T-0025
def test_translate_hdl_build_unaffected_with_no_stimulus_ref(tmp_path) -> None:
    """`hdl.build` (and any obligation with no declared stimulus) forms
    a request exactly as before -- the new payload port is additive."""
    (tmp_path / "mux2.v").write_text("module mux2(); endmodule\n")
    ob = _obligation("hdl_src_ref: mux2.v", "hdl_regime: verilog2001")
    ctx = _plan_context(tmp_path)
    result = _translate_hdl(ob, "hdl.build", ctx)
    assert result.is_ok, result
    assert "sim_stimulus" not in result.danger_ok.payloads
