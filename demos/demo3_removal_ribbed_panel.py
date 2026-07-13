"""Demo 3 -- removal-vocabulary pins: ribbed_panel (WO-77).

`examples/tracks/hematite/ribbed_panel.hema` declares a `Ribs` op whose
`count` and `thickness` slots are PLANNER-tagged bounds ([4,8] ribs,
[2mm,5mm]) rather than literals. This demo runs the REAL WO-77 chain:

    real .hema + std_removal pack -> compiler.check
    -> emitted FeatureProgram (bounds read off the planner slots, never
       re-invented)
    -> optimize_discrete over integer `count` composed with
       golden-section over the `thickness` interval, EVERY candidate
       realized through the real OCCT interpreter (mass measured)
    -> winner_lock_row (two `cause: optimize(mass, trace=...)` rows)

then emits the physical proof: the STEP solid WITH the pinned ribs, its
part drawing citing the pins, both opt_trace sheets, and the lockfile.
"""

from __future__ import annotations

import json
import re

from regolith import compiler, core_version
from regolith.backends.drawings.producers import mech_part_drawing, opt_trace
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.drawings.renderer_pdf import render_pdf
from regolith.backends.three_d.glb import GlbNode, write_glb
from regolith.backends.three_d.tessellate import tessellate_step
from regolith.backends.three_d.viewer import viewer_html
from regolith.logging_setup import get_logger
from regolith.orchestrator.lockfile import (
    Lockfile,
    LockSection,
)
from regolith.orchestrator.lockfile import (
    render as render_lockfile,
)
from regolith.orchestrator.optimize import (
    ChoicePointDomain,
    EvalOutcome,
    optimize_continuous_golden_section,
    optimize_discrete,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.payload_store import PayloadStore
from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.schema import (
    BlankOp,
    FeatureProgram,
    Point2,
    ResolvedParam,
    RibsOp,
    Sketch,
    Stage,
)

from demos.harness import DemoWriter, artifact_table

_log = get_logger(__name__)

DEMO = "demo3_removal_ribbed_panel"
SURFACE = "removal-vocabulary bounded slots (ribbed_panel, WO-77)"
FIXTURE = "examples/tracks/hematite/ribbed_panel.hema"
PACK = "examples/tracks/hematite/std_removal.hema"

# The fixture panel (see ribbed_panel.hema): 120x80x18mm AL 6061.
_L, _W, _T = 0.120, 0.080, 0.018
_AL_DENSITY_KG_M3 = 2700.0
# The stiffness floor (WO-77 test's stand-in for the FEA stiffness claim):
# count * t_mm^3 >= K puts the per-count optimum thickness interior to
# [2mm,5mm], so the winner is decided by the search, not a bound.
_STIFFNESS_FLOOR = 250.0


def _payload() -> dict:
    out = compiler.check([FIXTURE, PACK])
    if out.is_err:
        raise RuntimeError(f"ribbed_panel: check failed: {out.danger_err}")
    return json.loads(out.danger_ok.payload_json)


def _ribs_params(payload: dict) -> dict:
    program = next(
        p for p in payload["feature_programs"] if p["part_name"] == "RibbedPanel"
    )
    op = next(f for f in program["features"] if f["kind"] == "ribs")
    return op["params"]


def _bounds(payload: dict) -> tuple[list[int], tuple[float, float]]:
    """The search space read off the EMITTED planner slots (declared source)."""
    params = _ribs_params(payload)
    lo, hi = (int(x) for x in re.findall(r"\d+", params["count"]["text"]))
    t_lo, t_hi = (
        float(x) / 1000.0 for x in re.findall(r"[\d.]+", params["thickness"]["text"])
    )
    return list(range(lo, hi + 1)), (t_lo, t_hi)


def _panel_program(count: int, thickness_m: float) -> FeatureProgram:
    sketch = Sketch(
        name="PanelOutline",
        outline=(
            Point2(x=0.0, y=0.0),
            Point2(x=_L, y=0.0),
            Point2(x=_L, y=_W),
            Point2(x=0.0, y=_W),
        ),
    )
    body = BlankOp(name="body", sketch=sketch, thickness=ResolvedParam(value=_T))
    ribs = RibsOp(
        name="lightening",
        count=count,
        pitch=ResolvedParam(value=0.020),
        thickness=ResolvedParam(value=thickness_m),
        height=ResolvedParam(value=0.012),
    )
    return FeatureProgram(
        part_name="RibbedPanel",
        stages=(Stage(name="milled", process="cnc_mill", features=(body, ribs)),),
    )


def _realize(count: int, thickness_m: float):
    result = realize_feature_program(_panel_program(count, thickness_m))
    return result.danger_ok


def run() -> bool:
    """Emit the ribbed_panel proof pack; return True (this surface is live)."""
    writer = DemoWriter(DEMO, SURFACE)
    payload = _payload()
    if payload["diagnostics"]:
        raise RuntimeError(
            f"ribbed_panel did not check clean: {payload['diagnostics']}"
        )
    counts, t_bounds = _bounds(payload)
    store = PayloadStore(str(writer.out_dir))
    inner_traces: dict[str, object] = {}

    def thickness_evaluator_for(count: int):
        def evaluate(assignment: tuple[float, ...]) -> EvalOutcome:
            (thickness_m,) = assignment
            realized = _realize(count, thickness_m)
            mass_kg = realized.geometry.topology.volume_mm3 / 1.0e9 * _AL_DENSITY_KG_M3
            t_mm = thickness_m * 1000.0
            feasible = count * t_mm**3 >= _STIFFNESS_FLOOR
            return EvalOutcome(
                feasible=feasible,
                objective_vector=(mass_kg,),
                verdict_summary=f"count={count} t={t_mm:.3f}mm mass={mass_kg:.6f}kg",
            )

        return evaluate

    def count_evaluator(assignment) -> EvalOutcome:
        count = int(assignment["RibbedPanel.lightening.count"])
        inner = optimize_continuous_golden_section(
            bounds=t_bounds,
            evaluator=thickness_evaluator_for(count),
            budget_evals=16,
            tol=1e-5,
        )
        inner_traces[str(count)] = inner
        if inner.winner is None:
            return EvalOutcome(feasible=False, objective_vector=(float("inf"),))
        best = inner.candidates[inner.winner]
        return EvalOutcome(
            feasible=True,
            objective_vector=tuple(best.objective_vector),
            verdict_summary=best.verdict_summary,
        )

    trace = optimize_discrete(
        domains=[
            ChoicePointDomain(
                subject="RibbedPanel.lightening.count",
                candidates=tuple(str(c) for c in counts),
            )
        ],
        evaluator=count_evaluator,
        objective=("minimize",),
        budget_evals=len(counts),
    )
    winner = trace.candidates[trace.winner]
    winner_count = dict(item.root for item in winner.assignment)[
        "RibbedPanel.lightening.count"
    ]
    inner = inner_traces[winner_count]
    winner_t_m = float(
        dict(item.root for item in inner.candidates[inner.winner].assignment)["x"]
    )
    _log.info(
        "ribbed_panel: winner count=%s thickness=%.4fmm",
        winner_count,
        winner_t_m * 1000,
    )

    # Pin BOTH slots -- the two `cause: optimize(mass, trace=...)` rows.
    count_digest = store_trace(store, trace)
    count_row = winner_lock_row(
        trace, "RibbedPanel.lightening.count", "mass", count_digest
    ).danger_ok
    thickness_digest = store_trace(store, inner)
    thickness_row = winner_lock_row(
        inner, "RibbedPanel.lightening.thickness", "mass", thickness_digest
    ).danger_ok
    lockfile = Lockfile(
        tool_version=core_version(),
        sections=(LockSection(name="", rows=(count_row, thickness_row)),),
    )
    writer.emit("regolith.lock", render_lockfile(lockfile).encode("ascii"))

    # The physical solid WITH the pinned ribs + its part drawing.
    realized = _realize(int(winner_count), winner_t_m)
    writer.emit("ribbed_panel.step", realized.step_bytes)
    mesh = tessellate_step(realized.step_bytes)
    if mesh is not None:
        glb = write_glb((mesh,), (GlbNode(name="RibbedPanel", mesh=0),))
        writer.emit("ribbed_panel.glb", glb)
        writer.emit("ribbed_panel.viewer.html", viewer_html(glb, "RibbedPanel"))
    part_model = mech_part_drawing("RibbedPanel", realized.geometry)
    writer.emit("ribbed_panel_drawing.svg", render_svg(part_model))
    writer.emit("ribbed_panel_drawing.pdf", render_pdf(part_model))

    # The opt_trace sheets: the outer count search + the winner's inner thickness.
    for subject, tr, base in (
        ("RibbedPanel.lightening.count", trace, "opt_trace_count"),
        ("RibbedPanel.lightening.thickness", inner, "opt_trace_thickness"),
    ):
        model = opt_trace(subject, tr)
        writer.emit(f"{base}.svg", render_svg(model))
        writer.emit(f"{base}.pdf", render_pdf(model))

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- optimized quantity: **mass** (realized panel volume x density, "
            "measured by the real OCCT interpreter for EVERY candidate)",
            "- domain: the `Ribs` op's planner-tagged bounded slots, read off the "
            f"emitted FeatureProgram of `{FIXTURE}` --",
            f"  - `RibbedPanel.lightening.count` in [{counts[0]}, {counts[-1]}]",
            "  - `RibbedPanel.lightening.thickness` in [2mm, 5mm]",
            f"- winner: **count = {winner_count} ribs**, "
            f"**thickness = {winner_t_m * 1000:.3f} mm** (fewest ribs at an "
            "interior thickness -- decided by the search over real realized "
            "mass under a stiffness floor, not an authored answer)",
            "- cause rows (verbatim from `regolith.lock`):",
            "",
            "```",
            count_row.value + "    cause: " + count_row.cause,
            thickness_row.value + "    cause: " + thickness_row.cause,
            "```",
            "",
            "## Where a human SEES it",
            "",
            "- `ribbed_panel.step` / `.glb` / `.viewer.html` -- the realized "
            f"solid carrying the pinned {winner_count} ribs; open the viewer "
            "offline to rotate it.",
            "- `ribbed_panel_drawing.svg` / `.pdf` -- the part drawing whose "
            "dimensions carry provenance back to the pinned geometry.",
            f"- `opt_trace_count.svg/.pdf` (trace `{count_digest}`) and "
            f"`opt_trace_thickness.svg/.pdf` (trace `{thickness_digest}`) -- the "
            "outer count search and the winning count's inner thickness search, "
            "each candidate's measured mass and the winner annotation.",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="mass",
        domain="RibbedPanel.lightening.count in [4,8]; thickness in [2mm,5mm]",
        winner=f"count={winner_count}, thickness={winner_t_m * 1000:.3f}mm",
        cause_row=count_row.value + "    cause: " + count_row.cause,
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
