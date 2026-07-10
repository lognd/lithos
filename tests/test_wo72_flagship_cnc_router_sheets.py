"""WO-72 (D183 demo 5, ship artifacts): part sheets + contract-graph
for `examples/flagships/cnc_router_r1`, mirroring
`tests/test_flagship_printer_sheets.py` / `tests/
test_flagship_printer_contract_graph.py`'s own recipe exactly (same
pre-existing wall those modules record: no `.hema`/`.cupr` source in
this repo reaches T3 RELEASE with a realized-geometry input wired
through the CLI yet -- `regolith.backends.drawings` producers pulled
directly, not a full CLI `ship --release`).

Part sheets: one `FeatureProgram` fixture per realized cnc_router_r1
part, dims mirroring each source file's own declared profile/stage
geometry (`IdlerBearingPlate`'s 90x50x20mm stock; `CarriagePlate`'s
default 150x100x18mm rail-block plate; `SidePlate`'s 240x260x20mm
shoulder; the gantry beam's 80x64mm box section over its 820mm span).
The contract-graph sheet renders the WHOLE cnc_router_r1 project at
L2, pulled off the real `regolith check` build payload, deterministic
across two runs -- audit-clean (no drafting-rule violations) exactly
like the printer's own graph.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest
from regolith import compiler
from regolith._schema.models import ContractGraphPayload
from regolith.backends.drawings.audit import run_drafting_rules
from regolith.backends.drawings.producers import contract_graph, mech_part_drawing
from regolith.backends.drawings.renderer import render_svg
from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.schema import (
    ExtrudeOp,
    FeatureProgram,
    HoleOp,
    Point2,
    ResolvedParam,
    Sketch,
    Stage,
)

_PROJECT = "examples/flagships/cnc_router_r1"


def _plate(part_name: str, w_m: float, d_m: float, t_m: float) -> FeatureProgram:
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=w_m, y=0.0),
        Point2(x=w_m, y=d_m),
        Point2(x=0.0, y=d_m),
    )
    sketch = Sketch(name="blank", outline=outline)
    op = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=t_m))
    stage = Stage(name="cut", process="cnc_mill", features=(op,))
    return FeatureProgram(part_name=part_name, material="AL6082_T6", stages=(stage,))


def _idler_bearing_plate() -> FeatureProgram:
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=0.090, y=0.0),
        Point2(x=0.090, y=0.050),
        Point2(x=0.0, y=0.050),
    )
    sketch = Sketch(name="body", outline=outline)
    extrude = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=0.020))
    pocket = HoleOp(
        name="pocket_a",
        center=Point2(x=0.020, y=0.025),
        diameter=ResolvedParam(value=0.032),
        depth=ResolvedParam(value=0.017),
    )
    bore = HoleOp(
        name="bore_b",
        center=Point2(x=0.070, y=0.025),
        diameter=ResolvedParam(value=0.012),
        depth=ResolvedParam(value=0.017),
    )
    stage = Stage(name="milled", process="cnc_mill", features=(extrude, pocket, bore))
    return FeatureProgram(
        part_name="IdlerBearingPlate", material="AL6082_T6", stages=(stage,)
    )


# One `FeatureProgram` fixture per realized cnc_router_r1 part (dims
# mirror each source file's own declared bounding profile).
_REALIZED_PARTS = {
    "IdlerBearingPlate": _idler_bearing_plate(),
    "CarriagePlate": _plate("CarriagePlate", 0.165, 0.100, 0.018),
    "MotorPlate": _plate("MotorPlate", 0.080, 0.080, 0.010),
    "SidePlate_left": _plate("SidePlate_left", 0.240, 0.260, 0.020),
    "SidePlate_right": _plate("SidePlate_right", 0.240, 0.260, 0.020),
    "GantryBeam": _plate("GantryBeam", 0.080, 0.064, 0.820),
}


def _cnc_router_contract_graph() -> ContractGraphPayload:
    result = compiler.check((_PROJECT,))
    assert result.is_ok, f"cnc_router_r1: check itself failed: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    graph_raw = payload.get("contract_graph")
    assert graph_raw is not None, "cnc_router_r1: no contract_graph in payload"
    return ContractGraphPayload.model_validate(graph_raw)


@pytest.fixture(scope="module")
def router_graph() -> ContractGraphPayload:
    return _cnc_router_contract_graph()


class TestCncRouterPartSheets:
    def test_every_realized_part_gets_a_sheet(self) -> None:
        for part_name, program in _REALIZED_PARTS.items():
            realized = realize_feature_program(program)
            assert realized.is_ok, (part_name, realized.danger_err)
            model = mech_part_drawing(part_name, realized.danger_ok.geometry)
            assert model.sheets, part_name
            svg = render_svg(model)
            ET.fromstring(svg)
            svg.decode("ascii")

    def test_sheets_are_audit_clean(self) -> None:
        for part_name, program in _REALIZED_PARTS.items():
            realized = realize_feature_program(program).danger_ok
            model = mech_part_drawing(part_name, realized.geometry)
            results = run_drafting_rules(model)
            violations = [r for r in results if not r.passed]
            assert violations == [], (part_name, violations)


class TestCncRouterContractGraph:
    def test_graph_is_non_trivial(self, router_graph: ContractGraphPayload) -> None:
        # Every interface (AxisFoot, CarriageDeck, NutSeat, BeamEnd,
        # ShoulderSeat, ClampBore, SpindleBody, BedSeat) plus every
        # artifact node, every mating/connection as an edge -- a real
        # machine (17 source files, weldment + generics + variants +
        # sealed import), not a toy fixture.
        assert len(router_graph.nodes) > 10
        assert len(router_graph.edges) > 3

    def test_deterministic_across_two_runs(self) -> None:
        g1 = _cnc_router_contract_graph()
        g2 = _cnc_router_contract_graph()
        m1 = contract_graph("CncRouterR1", g1)
        m2 = contract_graph("CncRouterR1", g2)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)
