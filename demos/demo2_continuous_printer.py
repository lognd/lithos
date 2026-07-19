"""Demo 2 -- continuous staged evaluator: printer_k1 minimize dims (WO-57/WO-64).

The WO body names `duct_vane`, which does NOT exist as a corpus member
(`tests/backends/test_parity.py` records the same substitution, and
WO-64 phase B establishes the recipe): the landed continuous
golden-section evaluator is proven instead over the printer_k1
flagship's TWO real declared minimize dims --

    bed.hema        BedPlateFlat.a       in [220mm, 240mm] minimize
    xy_gantry.hema  CarriagePlateFlat.b  in [ 35mm,  45mm] minimize

each minimizing the REALIZED plate's own mass (volume x density via the
real OCCT interpreter -- mass is measured, never synthesized), so the
true minimizer sits at each dim's lower bound. The demo emits, for the
headline bed dim, the before (upper bound) and after (pinned winner)
STEP + GLB + offline viewer, plus each dim's opt_trace sheet and the
pinned `regolith.lock` with two `cause: optimize(...)` rows.
"""

from __future__ import annotations

from regolith import core_version
from regolith._schema.models import OptimizationTrace
from regolith.backends.drawings.producers import opt_trace
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
    EvalOutcome,
    optimize_continuous_golden_section,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.payload_store import PayloadStore
from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.schema import (
    ExtrudeOp,
    FeatureProgram,
    Point2,
    ResolvedParam,
    Sketch,
    Stage,
)

from demos.harness import DemoWriter, artifact_table

_log = get_logger(__name__)

# frob:doc docs/modules/demos.md#demo-proof-pack-shape
DEMO = "demo2_continuous_printer"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SURFACE = (
    "continuous golden-section over a realized-mass evaluator (printer_k1, WO-57/64)"
)
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
AL_DENSITY_KG_M3 = 2700.0


def _plate_program(
    a_m: float, b_m: float = 0.230, part: str = "HeatedBed"
) -> FeatureProgram:
    """The printer_k1 plate program (verbatim from WO-64's phase-B recipe)."""
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=a_m, y=0.0),
        Point2(x=a_m, y=b_m),
        Point2(x=0.0, y=b_m),
    )
    sketch = Sketch(name="blank", outline=outline)
    op = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=0.004))
    stage = Stage(name="cut", process="laser_cut", features=(op,))
    return FeatureProgram(part_name=part, material="AL5083_H111", stages=(stage,))


def _mass_kg(program: FeatureProgram) -> tuple[float, bytes]:
    """Realize `program` through the real interpreter; return (mass_kg, step_bytes)."""
    realized = realize_feature_program(program).danger_ok
    volume_m3 = realized.geometry.topology.volume_mm3 / 1.0e9
    return volume_m3 * AL_DENSITY_KG_M3, realized.step_bytes


def _search(program_at, bounds, store) -> tuple[OptimizationTrace, float, str]:
    """Golden-section over `bounds`, realizing at each candidate; pin the winner."""

    def evaluator(assignment: tuple[float, ...]) -> EvalOutcome:
        (x,) = assignment
        mass_kg, _ = _mass_kg(program_at(x))
        digest = store.put(program_at(x).model_dump_json().encode("ascii"))
        return EvalOutcome(
            feasible=True,
            objective_vector=(mass_kg,),
            verdict_summary=f"mass_kg={mass_kg:.6f}",
            evidence_digests=(digest,),
        )

    trace = optimize_continuous_golden_section(
        bounds=bounds, evaluator=evaluator, budget_evals=40, tol=1e-5
    )
    assert trace.winner is not None, "golden-section search found no feasible winner"
    winner = trace.candidates[trace.winner]
    winner_x = float({item.root[0]: item.root[1] for item in winner.assignment}["x"])
    digest = store_trace(store, trace)
    return trace, winner_x, digest


def _emit_solid(writer: DemoWriter, name: str, step_bytes: bytes) -> None:
    """Emit STEP + GLB + offline viewer for one realized solid."""
    writer.emit(f"{name}.step", step_bytes)
    mesh = tessellate_step(step_bytes)
    if mesh is None:
        _log.warning("demo2: OCP could not tessellate %s; no GLB emitted", name)
        return
    glb = write_glb((mesh,), (GlbNode(name=name, mesh=0),))
    writer.emit(f"{name}.glb", glb)
    writer.emit(f"{name}.viewer.html", viewer_html(glb, name))


# frob:doc docs/modules/demos.md#demo-proof-pack-shape
def run() -> bool:
    """Emit the continuous proof pack; return True (this surface is live)."""
    writer = DemoWriter(DEMO, SURFACE)
    store = PayloadStore(str(writer.out_dir))

    # Headline dim: the heated bed edge length a in [220mm, 240mm].
    bed_trace, bed_x, bed_digest = _search(
        lambda a: _plate_program(a, part="HeatedBed"), (0.220, 0.240), store
    )
    # Second dim: the XY carriage plate edge length b in [35mm, 45mm].
    car_trace, car_x, car_digest = _search(
        lambda b: _plate_program(0.060, b, part="XCarriage"), (0.035, 0.045), store
    )
    _log.info("demo2: bed a=%.6f m, carriage b=%.6f m", bed_x, car_x)

    # Before/after geometry for the headline dim: upper bound vs winner.
    _, before_step = _mass_kg(_plate_program(0.240, part="HeatedBed"))
    _, after_step = _mass_kg(_plate_program(bed_x, part="HeatedBed"))
    _emit_solid(writer, "bed_before_240mm", before_step)
    _emit_solid(writer, "bed_after_pinned", after_step)

    # Both pinned rows -- the two `cause: optimize(...)` lockfile lines.
    bed_row = winner_lock_row(
        bed_trace, "HeatedBed.BedPlateFlat.a", "mass", bed_digest
    ).danger_ok
    car_row = winner_lock_row(
        car_trace, "XCarriage.CarriagePlateFlat.b", "mass", car_digest
    ).danger_ok
    lockfile = Lockfile(
        tool_version=core_version(),
        sections=(LockSection(name="", rows=(bed_row, car_row)),),
    )
    writer.emit("regolith.lock", render_lockfile(lockfile).encode("ascii"))

    # The opt_trace sheets: candidate table + convergence for each dim.
    for subject, trace, base in (
        ("HeatedBed.BedPlateFlat.a", bed_trace, "opt_trace_bed"),
        ("XCarriage.CarriagePlateFlat.b", car_trace, "opt_trace_carriage"),
    ):
        model = opt_trace(subject, trace)
        writer.emit(f"{base}.svg", render_svg(model))
        writer.emit(f"{base}.pdf", render_pdf(model))

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- optimized quantity: **mass** (realized plate volume x density, "
            "measured by the real OCCT interpreter -- never synthesized)",
            "- domain: two declared continuous minimize dims off the printer_k1 "
            "flagship --",
            "  - `HeatedBed.BedPlateFlat.a` in [220mm, 240mm]",
            "  - `XCarriage.CarriagePlateFlat.b` in [35mm, 45mm]",
            f"- winner: **a = {bed_x * 1000:.3f} mm** (bed) and "
            f"**b = {car_x * 1000:.3f} mm** (carriage) -- each search lands at "
            "its lower bound, where realized mass is minimal",
            "- cause rows (verbatim from `regolith.lock`):",
            "",
            "```",
            bed_row.value + "    cause: " + bed_row.cause,
            car_row.value + "    cause: " + car_row.cause,
            "```",
            "",
            "## Note on the exemplar (honest substitution)",
            "",
            "The WO body names `duct_vane`, which is not a landed corpus member "
            "(`tests/backends/test_parity.py` records the same gap). The LANDED "
            "continuous evaluator machinery (WO-57) is proven here over the "
            "printer_k1 flagship's own real minimize dims, exactly the WO-64 "
            "phase-B recipe.",
            "",
            "## Where a human SEES it",
            "",
            "- `bed_before_240mm.step/.glb/.viewer.html` vs "
            "`bed_after_pinned.step/.glb/.viewer.html` -- the before (upper "
            "bound) and after (pinned winner) heated-bed solid; open either "
            "`.viewer.html` offline to rotate it.",
            f"- `opt_trace_bed.svg/.pdf` (trace `{bed_digest}`) and "
            f"`opt_trace_carriage.svg/.pdf` (trace `{car_digest}`) -- every "
            "realized candidate's measured mass, the convergence polyline, and "
            "the winner annotation.",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="mass",
        domain=(
            "HeatedBed.BedPlateFlat.a in [220,240]mm; "
            "XCarriage.CarriagePlateFlat.b in [35,45]mm"
        ),
        winner=f"a={bed_x * 1000:.3f}mm, b={car_x * 1000:.3f}mm",
        cause_row=bed_row.value + "    cause: " + bed_row.cause,
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
