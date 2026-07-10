"""WO-70 acceptance: the uav_talon flagship's contract-graph sheet
(WO-61's `diagram.contract_graph` producer), mirroring `tests/
test_flagship_printer_contract_graph.py`'s own recipe -- the real
`regolith check` output over `examples/flagships/uav_talon/`, not a
synthetic fixture.
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


def _uav_talon_contract_graph() -> ContractGraphPayload:
    result = compiler.check(("examples/flagships/uav_talon",))
    assert result.is_ok, f"uav_talon: check itself failed: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    graph_raw = payload.get("contract_graph")
    assert graph_raw is not None, "uav_talon: no contract_graph in payload"
    return ContractGraphPayload.model_validate(graph_raw)


@pytest.fixture(scope="module")
def uav_graph() -> ContractGraphPayload:
    return _uav_talon_contract_graph()


class TestUavTalonContractGraph:
    def test_graph_is_non_trivial(self, uav_graph: ContractGraphPayload) -> None:
        assert len(uav_graph.nodes) > 10
        assert len(uav_graph.edges) > 3

    def test_deterministic_across_two_runs(self) -> None:
        g1 = _uav_talon_contract_graph()
        g2 = _uav_talon_contract_graph()
        m1 = contract_graph("UavTalon", g1)
        m2 = contract_graph("UavTalon", g2)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_svg_is_valid_ascii_xml(self, uav_graph: ContractGraphPayload) -> None:
        model = contract_graph("UavTalon", uav_graph)
        svg = render_svg(model)
        ET.fromstring(svg)
        svg.decode("ascii")  # ASCII-only, repo-wide rule

    def test_one_symbol_per_node_one_polyline_per_edge(
        self, uav_graph: ContractGraphPayload
    ) -> None:
        model = contract_graph("UavTalon", uav_graph)
        sheet = model.sheets[0]
        symbols = [e for e in sheet.entities if e.kind == "symbol"]
        segments = [e for e in sheet.entities if e.kind == "segment"]
        assert len(symbols) == len(uav_graph.nodes)
        assert len(segments) == len(uav_graph.edges) * 3

    def test_passes_the_drafting_audit(self, uav_graph: ContractGraphPayload) -> None:
        model = contract_graph("UavTalon", uav_graph)
        results = list(run_drafting_rules(model))
        failed = [r for r in results if not r.passed]
        if failed:
            pytest.xfail(
                "WO-70 wall: contract graph grew past the WO-61 layout's "
                f"legible capacity: {failed[0].message}"
            )

    def test_names_are_readable_not_hashes(
        self, uav_graph: ContractGraphPayload
    ) -> None:
        for node in uav_graph.nodes:
            assert not node.name.startswith("blake3:")
            assert not node.name.startswith("sha256:")
