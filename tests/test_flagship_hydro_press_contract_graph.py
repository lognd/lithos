"""WO-73 acceptance: hydro_press_h30's contract-graph sheet renders
the machine's L2 surface (WO-61's `diagram.contract_graph` producer),
mirroring `test_flagship_printer_contract_graph.py`'s own real-check
recipe (not a synthetic fixture) for the second flagship-wave machine
that carries a mech contract graph.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest
from regolith import compiler
from regolith._schema.models import ContractGraphPayload
from regolith.backends.drawings.producers import contract_graph
from regolith.backends.drawings.renderer import render_svg


def _hydro_press_contract_graph() -> ContractGraphPayload:
    result = compiler.check(("examples/flagships/hydro_press_h30",))
    assert result.is_ok, f"hydro_press_h30: check itself failed: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    graph_raw = payload.get("contract_graph")
    assert graph_raw is not None, "hydro_press_h30: no contract_graph in payload"
    return ContractGraphPayload.model_validate(graph_raw)


@pytest.fixture(scope="module")
def press_graph() -> ContractGraphPayload:
    return _hydro_press_contract_graph()


class TestHydroPressContractGraph:
    def test_graph_is_non_trivial(self, press_graph: ContractGraphPayload) -> None:
        # CylinderMount/PlatenGuide interfaces plus the ram/platen/
        # head-plate/gusset part nodes, plus the GuidePost mating
        # edges -- a real machine surface, not a toy fixture.
        assert len(press_graph.nodes) > 3

    def test_deterministic_across_two_runs(self) -> None:
        g1 = _hydro_press_contract_graph()
        g2 = _hydro_press_contract_graph()
        m1 = contract_graph("HydroPressH30", g1)
        m2 = contract_graph("HydroPressH30", g2)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_svg_is_valid_ascii_xml(self, press_graph: ContractGraphPayload) -> None:
        model = contract_graph("HydroPressH30", press_graph)
        svg = render_svg(model)
        ET.fromstring(svg)
        svg.decode("ascii")  # ASCII-only, repo-wide rule
