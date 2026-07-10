"""WO-93 acceptance: cubesat's contract-graph sheet renders the
machine's L2 surface (WO-61's `diagram.contract_graph` producer),
mirroring `test_flagship_hydro_press_contract_graph.py`'s own
real-check recipe for the flagship-wave-2 promotion.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest
from regolith import compiler
from regolith._schema.models import ContractGraphPayload
from regolith.backends.drawings.producers import contract_graph
from regolith.backends.drawings.renderer import render_svg


def _cubesat_contract_graph() -> ContractGraphPayload:
    result = compiler.check(("examples/flagships/cubesat",))
    assert result.is_ok, f"cubesat: check itself failed: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    graph_raw = payload.get("contract_graph")
    assert graph_raw is not None, "cubesat: no contract_graph in payload"
    return ContractGraphPayload.model_validate(graph_raw)


@pytest.fixture(scope="module")
def kestrel_graph() -> ContractGraphPayload:
    return _cubesat_contract_graph()


class TestCubesatContractGraph:
    def test_graph_is_non_trivial(self, kestrel_graph: ContractGraphPayload) -> None:
        # Frame/Antenna/EpsPcb/ObcPcb/AdcsPcb/CommsPcb/PayloadPcb part
        # nodes plus the CardMount/StackMate/AntennaMate/Umbilical
        # interface edges -- a real cross-track machine, not a toy
        # fixture.
        assert len(kestrel_graph.nodes) > 3

    def test_deterministic_across_two_runs(self) -> None:
        g1 = _cubesat_contract_graph()
        g2 = _cubesat_contract_graph()
        m1 = contract_graph("Kestrel", g1)
        m2 = contract_graph("Kestrel", g2)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_svg_is_valid_ascii_xml(self, kestrel_graph: ContractGraphPayload) -> None:
        model = contract_graph("Kestrel", kestrel_graph)
        svg = render_svg(model)
        ET.fromstring(svg)
        svg.decode("ascii")  # ASCII-only, repo-wide rule
