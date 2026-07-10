"""WO-81 acceptance: the riscv_hart_rv1 flagship's contract-graph
sheet (WO-61's `diagram.contract_graph` producer) renders the phase-A
extension catalog + microarchitecture-boundary system legibly at L2
-- mirrors `tests/test_flagship_printer_contract_graph.py` (WO-64's
own template) and `tests/test_flagship_mainboard_contract_graph.py`
(WO-71's), driving the real `regolith check` output over
`examples/flagships/riscv_hart_rv1/` (not a synthetic fixture) so
this golden moves if the flagship's own contract graph ever drifts.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest
from regolith import compiler
from regolith._schema.models import ContractGraphPayload
from regolith.backends.drawings.audit import run_drafting_rules
from regolith.backends.drawings.producers import contract_graph
from regolith.backends.drawings.renderer import render_svg


def _riscv_contract_graph() -> ContractGraphPayload:
    """Check the real flagship project and pull its `ContractGraphPayload`
    straight off `BuildOutcome.payload_json` (WO-61 D2: one graph per
    build, the whole build's L2 surface)."""
    result = compiler.check(("examples/flagships/riscv_hart_rv1",))
    assert result.is_ok, f"riscv_hart_rv1: check itself failed: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    graph_raw = payload.get("contract_graph")
    assert graph_raw is not None, "riscv_hart_rv1: no contract_graph in payload"
    return ContractGraphPayload.model_validate(graph_raw)


@pytest.fixture(scope="module")
def riscv_graph() -> ContractGraphPayload:
    return _riscv_contract_graph()


class TestRiscvHartContractGraph:
    def test_graph_is_non_trivial(self, riscv_graph: ContractGraphPayload) -> None:
        # The top-level system wires 11 microarchitecture-boundary
        # parts (uarch.cupr) -- a real machine-scale graph, not a toy.
        assert len(riscv_graph.nodes) >= 5

    def test_deterministic_across_two_runs(self) -> None:
        g1 = _riscv_contract_graph()
        g2 = _riscv_contract_graph()
        m1 = contract_graph("RiscvHartRv1", g1)
        m2 = contract_graph("RiscvHartRv1", g2)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_svg_is_valid_ascii_xml(self, riscv_graph: ContractGraphPayload) -> None:
        model = contract_graph("RiscvHartRv1", riscv_graph)
        svg = render_svg(model)
        ET.fromstring(svg)
        svg.decode("ascii")  # ASCII-only, repo-wide rule

    def test_one_symbol_per_node_one_polyline_per_edge(
        self, riscv_graph: ContractGraphPayload
    ) -> None:
        model = contract_graph("RiscvHartRv1", riscv_graph)
        sheet = model.sheets[0]
        symbols = [e for e in sheet.entities if e.kind == "symbol"]
        segments = [e for e in sheet.entities if e.kind == "segment"]
        assert len(symbols) == len(riscv_graph.nodes)
        assert len(segments) == len(riscv_graph.edges) * 3

    def test_passes_the_drafting_audit(self, riscv_graph: ContractGraphPayload) -> None:
        model = contract_graph("RiscvHartRv1", riscv_graph)
        results = list(run_drafting_rules(model))
        failures = [r for r in results if not r.passed]
        assert not failures, f"drafting audit failures: {failures}"
