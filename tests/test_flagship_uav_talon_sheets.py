"""WO-70 (D183 required surface): ship artifacts for `uav_talon`'s
realized parts (`WingSpar`, `BoomClamp`) and the avionics harness
block diagram, mirroring `tests/test_flagship_printer_sheets.py`'s
own direct-producer recipe (`regolith.backends.drawings` producers,
not a full CLI `ship --release` -- that module's own docstring
records no `.hema`/`.cupr` source in this repo reaches T3 RELEASE
with a realized-geometry input wired through the CLI yet, unchanged
by this dispatch).
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from regolith import compiler
from regolith._schema.models import HarnessPayload
from regolith.backends.drawings.audit import run_drafting_rules
from regolith.backends.drawings.producers import elec_blocks, mech_part_drawing
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


def _plate(
    part_name: str, material: str, w_m: float, d_m: float, t_m: float
) -> FeatureProgram:
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=w_m, y=0.0),
        Point2(x=w_m, y=d_m),
        Point2(x=0.0, y=d_m),
    )
    sketch = Sketch(name="body", outline=outline)
    op = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=t_m))
    stage = Stage(name="cut", process="laser_cut", features=(op,))
    return FeatureProgram(part_name=part_name, material=material, stages=(stage,))


def _boom_clamp() -> FeatureProgram:
    # Mirrors `airframe.hema`'s `BoomClampFlat` (40mm x 30mm, 4mm sheet)
    # and its two M5 clamp-bolt holes.
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=0.040, y=0.0),
        Point2(x=0.040, y=0.030),
        Point2(x=0.0, y=0.030),
    )
    sketch = Sketch(name="body", outline=outline)
    extrude = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=0.004))
    bolt_a = HoleOp(
        name="bolt_a",
        center=Point2(x=0.008, y=0.008),
        diameter=ResolvedParam(value=0.005),
        depth=ResolvedParam(value=0.004),
    )
    bolt_b = HoleOp(
        name="bolt_b",
        center=Point2(x=0.032, y=0.008),
        diameter=ResolvedParam(value=0.005),
        depth=ResolvedParam(value=0.004),
    )
    stage = Stage(name="cut", process="laser_cut", features=(extrude, bolt_a, bolt_b))
    return FeatureProgram(part_name="BoomClamp", material="AL6061_T6", stages=(stage,))


# One `FeatureProgram` fixture per realized part in `uav_talon`
# (`airframe.hema`'s `WingSpar` cap and `BoomClamp`).
_REALIZED_PARTS = {
    "WingSpar": _plate("WingSpar", "AL7075_T6", 0.900, 0.003, 0.060),
    "BoomClamp": _boom_clamp(),
}


def _uav_talon_harness() -> HarnessPayload:
    result = compiler.check(("examples/flagships/uav_talon",))
    assert result.is_ok, f"uav_talon: check itself failed: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    harnesses = payload.get("harnesses") or {}
    assert harnesses, "uav_talon: no harness in payload"
    first_name = sorted(harnesses)[0]
    return HarnessPayload.model_validate(harnesses[first_name])


class TestUavTalonPartSheets:
    def test_every_realized_part_gets_a_sheet(self) -> None:
        for part_name, program in _REALIZED_PARTS.items():
            realized = realize_feature_program(program)
            assert realized.is_ok, (part_name, realized.danger_err)
            model = mech_part_drawing(part_name, realized.danger_ok.geometry)
            assert model.sheets, part_name
            svg = render_svg(model)
            ET.fromstring(svg)
            svg.decode("ascii")

    def test_sheets_are_deterministic(self) -> None:
        for part_name, program in _REALIZED_PARTS.items():
            realized = realize_feature_program(program).danger_ok
            m1 = mech_part_drawing(part_name, realized.geometry)
            m2 = mech_part_drawing(part_name, realized.geometry)
            assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(
                by_alias=True
            )
            assert render_svg(m1) == render_svg(m2)

    def test_sheets_pass_the_drafting_audit(self) -> None:
        for part_name, program in _REALIZED_PARTS.items():
            realized = realize_feature_program(program).danger_ok
            model = mech_part_drawing(part_name, realized.geometry)
            results = list(run_drafting_rules(model))
            failed = [r for r in results if not r.passed]
            assert not failed, (part_name, failed)


class TestUavTalonHarnessBlockDiagram:
    def test_renders_and_is_deterministic(self) -> None:
        harness = _uav_talon_harness()
        m1 = elec_blocks("UavTalon", harness)
        m2 = elec_blocks("UavTalon", harness)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        svg1 = render_svg(m1)
        assert svg1 == render_svg(m2)
        ET.fromstring(svg1)
        svg1.decode("ascii")
