"""WO-64 phase C: ship outputs for `examples/flagships/printer_k1/` --
part sheets for every realized mech part (charter `31-flagships.md`
sec. 2 phase C: "ship --release emits drawings...") and the harness
block diagram, via the WO-50 `regolith.backends.drawings` producers
directly (the same direct-producer path `tests/
test_flagship_printer_contract_graph.py` (WO-64 phase A deliverable 4)
already uses for the contract-graph sheet, not a full CLI `ship
--release` -- `tests/backends/test_ship.py`'s own module docstring
records that no `.hema`/`.cupr` source in this repo reaches T3
RELEASE with a realized-geometry input wired through the CLI yet, a
pre-existing wall this dispatch does not attempt to close).

Mech part geometry: `realize_feature_program` over hand-built
`FeatureProgram` fixtures mirroring each source part's own declared
profile/stage geometry -- the exact idiom `tests/orchestrator/
test_wo64_phase_c_bed_carriage.py` and `test_wo64_xy_gantry_assembly
.py` already established for this project (no `.hema` -> realizer
FeatureProgram producer exists end to end; the compiler's own
`feature_programs` build payload is a DIFFERENT, op-graph-shaped
diagnostic surface, not the realizer's input schema -- confirmed by
inspection this dispatch, not assumed).

The harness block diagram uses the REAL `HarnessPayload` off `compiler
.check(("examples/flagships/printer_k1",))`'s own build payload
(`harnesses[0]`), exactly like the contract-graph test's `printer_
graph` fixture -- a legitimate direct-producer pull, no synthetic
harness.
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


def _plate(part_name: str, w_m: float, d_m: float, t_m: float) -> FeatureProgram:
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=w_m, y=0.0),
        Point2(x=w_m, y=d_m),
        Point2(x=0.0, y=d_m),
    )
    sketch = Sketch(name="blank", outline=outline)
    op = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=t_m))
    stage = Stage(name="cut", process="laser_cut", features=(op,))
    return FeatureProgram(part_name=part_name, material="AL6061_T6", stages=(stage,))


def _bed_carriage() -> FeatureProgram:
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=0.230, y=0.0),
        Point2(x=0.230, y=0.230),
        Point2(x=0.0, y=0.230),
    )
    sketch = Sketch(name="body", outline=outline)
    extrude = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=0.012))
    bore = HoleOp(
        name="z_nut_bore",
        center=Point2(x=0.115, y=0.115),
        diameter=ResolvedParam(value=0.008),
        depth=ResolvedParam(value=0.012),
    )
    stage = Stage(name="milled", process="cnc_mill", features=(extrude, bore))
    return FeatureProgram(
        part_name="BedCarriage", material="AL6061_T6", stages=(stage,)
    )


# One `FeatureProgram` fixture per realized part in `printer_k1`
# (`bed.hema`'s `HeatedBed`; `xy_gantry.hema`'s four sheet parts;
# `z_motion.hema`'s `BedCarriage`) -- dims mirror each source file's
# own declared profile.
_REALIZED_PARTS = {
    "HeatedBed": _plate("HeatedBed", 0.230, 0.230, 0.004),
    "XCarriage": _plate("XCarriage", 0.060, 0.040, 0.003),
    "XRailBracketLeft": _plate("XRailBracketLeft", 0.040, 0.020, 0.002),
    "XRailBracketRight": _plate("XRailBracketRight", 0.040, 0.020, 0.002),
    "YCarriage": _plate("YCarriage", 0.060, 0.040, 0.003),
    "BedCarriage": _bed_carriage(),
}


def _printer_harness() -> HarnessPayload:
    result = compiler.check(("examples/flagships/printer_k1",))
    assert result.is_ok, f"printer_k1: check itself failed: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    harnesses = payload.get("harnesses") or {}
    assert harnesses, "printer_k1: no harness in payload"
    first_name = sorted(harnesses)[0]
    return HarnessPayload.model_validate(harnesses[first_name])


class TestPrinterPartSheets:
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


class TestPrinterHarnessBlockDiagram:
    def test_renders_and_is_deterministic(self) -> None:
        harness = _printer_harness()
        m1 = elec_blocks("PrinterK1", harness)
        m2 = elec_blocks("PrinterK1", harness)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        svg1 = render_svg(m1)
        assert svg1 == render_svg(m2)
        ET.fromstring(svg1)
        svg1.decode("ascii")
