"""WO-64 phase A acceptance: the printer_k1 flagship's contract-graph
sheet (WO-61's `diagram.contract_graph` producer, WO-58's D2 mention)
renders the WHOLE machine legibly at L2 -- the flagship-1 charter's
own "machine-scale test" for the WO-61 producer
(`docs/spec/toolchain/31-flagships.md` sec. 5). Drives the real
`regolith check` output over `examples/flagships/printer_k1/` (not a
synthetic fixture, unlike `tests/backends/test_drawings.py`'s
`bearing_assembly` shape) so this golden moves if the flagship's own
contract graph ever drifts.
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


def _printer_contract_graph() -> ContractGraphPayload:
    """Check the real flagship project and pull its `ContractGraphPayload`
    straight off `BuildOutcome.payload_json` (WO-61 D2: one graph per
    build, the whole build's L2 surface)."""
    result = compiler.check(("examples/flagships/printer_k1",))
    assert result.is_ok, f"printer_k1: check itself failed: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    graph_raw = payload.get("contract_graph")
    assert graph_raw is not None, "printer_k1: no contract_graph in payload"
    return ContractGraphPayload.model_validate(graph_raw)


@pytest.fixture(scope="module")
def printer_graph() -> ContractGraphPayload:
    return _printer_contract_graph()


class TestPrinterContractGraph:
    def test_graph_is_non_trivial(self, printer_graph: ContractGraphPayload) -> None:
        # Every interface (RailMount, LeadscrewMount, StepperMount,
        # CardBay/BoardOutline, HotendPocket, BuildPlatformMount,
        # PanelSeal, FanDrive, HeaterDrive, BedHeater, FeederThroat,
        # ControllerMcu's ports) plus every artifact (parts/board/
        # system nodes) shows up as a node; every mating/connection as
        # an edge -- a real machine, not a toy fixture.
        assert len(printer_graph.nodes) > 10
        assert len(printer_graph.edges) > 3

    def test_deterministic_across_two_runs(self) -> None:
        g1 = _printer_contract_graph()
        g2 = _printer_contract_graph()
        m1 = contract_graph("PrinterK1", g1)
        m2 = contract_graph("PrinterK1", g2)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_svg_is_valid_ascii_xml(self, printer_graph: ContractGraphPayload) -> None:
        model = contract_graph("PrinterK1", printer_graph)
        svg = render_svg(model)
        ET.fromstring(svg)
        svg.decode("ascii")  # ASCII-only, repo-wide rule

    def test_one_symbol_per_node_one_polyline_per_edge(
        self, printer_graph: ContractGraphPayload
    ) -> None:
        model = contract_graph("PrinterK1", printer_graph)
        sheet = model.sheets[0]
        symbols = [e for e in sheet.entities if e.kind == "symbol"]
        segments = [e for e in sheet.entities if e.kind == "segment"]
        assert len(symbols) == len(printer_graph.nodes)
        assert len(segments) == len(printer_graph.edges) * 3

    def test_passes_the_drafting_audit(
        self, printer_graph: ContractGraphPayload
    ) -> None:
        model = contract_graph("PrinterK1", printer_graph)
        for result in run_drafting_rules(model):
            assert result.passed, result.message

    def test_names_are_readable_not_hashes(
        self, printer_graph: ContractGraphPayload
    ) -> None:
        # WO-61 acceptance: "names are readable, not hashes."
        for node in printer_graph.nodes:
            assert not node.name.startswith("blake3:")
            assert not node.name.startswith("sha256:")
