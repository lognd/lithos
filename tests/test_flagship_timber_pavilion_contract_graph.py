"""WO-74's contract-graph sheet golden (the WO-74 acceptance shape,
inherited from WO-64's ledger discipline): `examples/flagships/
timber_pavilion/`'s `ContractGraphPayload` (WO-61's `diagram.
contract_graph` producer) rendered via `compiler.check(...)`'s own
build payload -- the same real-project-not-a-fixture idiom `tests/
test_flagship_printer_contract_graph.py` establishes.

Honest note: this flagship declares no `interface`/`mates` contracts
(it is a civil-only pavilion -- posts/girders/purlin joined by
`Bearing`/`Pinned`/`EmbeddedPost` structural transfers, WO-48's frame
surface, not WO-61's contract-graph surface). The graph is therefore
correctly EMPTY (0 nodes, 0 edges) -- these tests pin that emptiness
as the golden and verify the producer still degrades gracefully (a
valid, deterministic, ASCII sheet) rather than skipping the surface
outright.
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


def _pavilion_contract_graph() -> ContractGraphPayload:
    result = compiler.check(("examples/flagships/timber_pavilion",))
    assert result.is_ok, f"timber_pavilion: check itself failed: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    graph_raw = payload.get("contract_graph")
    assert graph_raw is not None, "timber_pavilion: no contract_graph in payload"
    return ContractGraphPayload.model_validate(graph_raw)


@pytest.fixture(scope="module")
def pavilion_graph() -> ContractGraphPayload:
    return _pavilion_contract_graph()


class TestTimberPavilionContractGraph:
    def test_graph_is_empty_no_mating_contracts_declared(
        self, pavilion_graph: ContractGraphPayload
    ) -> None:
        # Golden: a civil-only flagship with no interface/mates
        # declarations legitimately produces zero nodes/edges.
        assert len(pavilion_graph.nodes) == 0
        assert len(pavilion_graph.edges) == 0

    def test_deterministic_across_two_runs(self) -> None:
        g1 = _pavilion_contract_graph()
        g2 = _pavilion_contract_graph()
        m1 = contract_graph("TimberPavilion", g1)
        m2 = contract_graph("TimberPavilion", g2)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_svg_is_valid_ascii_xml(self, pavilion_graph: ContractGraphPayload) -> None:
        model = contract_graph("TimberPavilion", pavilion_graph)
        svg = render_svg(model)
        ET.fromstring(svg)
        svg.decode("ascii")

    def test_passes_the_drafting_audit(
        self, pavilion_graph: ContractGraphPayload
    ) -> None:
        model = contract_graph("TimberPavilion", pavilion_graph)
        results = list(run_drafting_rules(model))
        failed = [r for r in results if not r.passed]
        assert not failed, failed
