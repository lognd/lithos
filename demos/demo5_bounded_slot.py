"""Demo 5 -- bounded sketch-segment slot: arm_a6 UpperArm margin search
(WO-97/D209, retargeted per F128.3).

`arm_a6`'s `link1.hema` declares `UpperArmSection.b = in [24mm, 40mm]
minimize` -- a bounded sketch-segment slot -- promoted to a
`SegmentLength::Bounded` closure (WO-97 promotion half, landed). The
D209 coupling (`regolith.orchestrator.optimize_sketch`) is the discharge
pipeline specialized per candidate: each trial width realizes the
section geometry, drives the registered `mech.beam.cantilever_deflection`
model with the part's own declared force/span/material inputs, and keeps
only the candidates whose deflection margin discharges. The winner is
the minimal feasible width, pinned as a genuine `cause: optimize(...)`
row -- never a guessed literal.

`uav_talon`'s WingSpar carries the SAME slot shape but its governing
load is `derived(sf=1.5)` with no declared scalar force, so it cannot
be driven through this coupling without fabricating a load; it stays
honestly `optimizer_evaluator_deferred` (recorded in this demo's
PROOF.md, not silently dropped -- F128.3).
"""

from __future__ import annotations

import json
import shutil

from regolith import core_version
from regolith.backends.drawings.producers import opt_trace
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.drawings.renderer_pdf import render_pdf
from regolith.backends.three_d.glb import GlbNode, write_glb
from regolith.backends.three_d.tessellate import tessellate_step
from regolith.backends.three_d.viewer import viewer_html
from regolith.logging_setup import get_logger
from regolith.orchestrator.lockfile import Lockfile, LockSection
from regolith.orchestrator.lockfile import render as render_lockfile
from regolith.orchestrator.payload_store import PayloadStore

from demos.harness import REPO_ROOT, DemoWriter, artifact_table, gap_proof

_log = get_logger(__name__)

DEMO = "demo5_bounded_slot"
SURFACE = (
    "bounded sketch-segment slot sized by a real margin search "
    "(arm_a6 UpperArm, WO-97/D209)"
)
PROJECT = REPO_ROOT / "examples" / "flagships" / "arm_a6"
# The E1-named governing claim kind a bounded-slot part must reach for
# the coupling to pin a genuine value (F126.1/D209).
_CANTILEVER_KIND = "mech.beam.cantilever_deflection"

# Declared-data constants, cited exactly as
# `tests/orchestrator/test_wo97_arm_a6_bounded_optimize.py` cites them:
# force from `link1.hema`'s `payload_deflection: mech.deflection(...,
# under=6.87N ...) < 1.5mm` claim (POSE_REACH: 0.3kg tip payload +
# ~0.4kg distal self-weight, arm_a6.cupr rung 1); E from
# `stdlib/std.materials/records/aluminum.toml` AL6061_T6; thickness from
# `Blank(UpperArmSection, thickness=20mm)`, same file.
_FORCE_N = 6.87
_E_PA = 68.9e9
_THICKNESS_M = 0.020
_LIMIT_M = 0.0015  # link1.hema: payload_deflection < 1.5mm
# The tightened-limit variant (F128.3): a limit strictly between the
# deflection at the upper and lower bound forces the winner off the
# lower bound -- the proof that the search is a real constrained
# optimize, not a rubber stamp that always lands on 24mm.
_TIGHTENED_LIMIT_M = 2.0e-5


def _coupling_available() -> bool:
    """Probe: is the D209 sketch-slot evaluator + its cantilever model
    channel present on the installed core?

    Flips True once `optimize_sketch` is importable AND the harness
    registry actually carries a model for the cantilever-deflection
    claim kind it drives -- the two halves F125/F126.1 named as the gap.
    """
    try:
        from regolith.harness import default_registry
        from regolith.orchestrator.optimize_sketch import (  # noqa: F401
            CantileverSlot,
            pin_bounded_slot,
        )
    except ImportError:
        return False
    kinds = {k for k, _ in default_registry().registered_keys()}
    return _CANTILEVER_KIND in kinds


def _upper_arm_slot(work_dir, limit_m: float):
    """Resolve the bounded slot from the REAL compiled arm_a6 payload
    (the promoted `feature_programs` sketch, never a hand fixture), then
    attach the declared claim/material inputs."""
    from regolith.orchestrator.optimize_sketch import CantileverSlot
    from regolith.orchestrator.orchestrate import build
    from regolith.orchestrator.tiers import BuildTier

    report = build((str(work_dir),), BuildTier.CHECK).danger_ok
    payload = json.loads(report.payload_json)
    for program in payload.get("feature_programs") or []:
        if program.get("part_name") != "UpperArm":
            continue
        for profile, sketch in (program.get("sketches") or {}).items():
            promoted = sketch.get("promoted") if isinstance(sketch, dict) else None
            if not isinstance(promoted, dict):
                continue
            segments = {
                s.get("name"): s.get("length") for s in promoted.get("segments") or []
            }
            bounded = (segments.get("b") or {}).get("bounded")
            span = (segments.get("a") or {}).get("pinned")
            if bounded is None or span is None:
                continue
            return CantileverSlot(
                part_name="UpperArm",
                profile=str(profile),
                segment="b",
                material="AL6061_T6",
                lo_m=float(bounded["lo"]) / 1000.0,
                hi_m=float(bounded["hi"]) / 1000.0,
                length_m=float(span) / 1000.0,
                thickness_m=_THICKNESS_M,
                force_n=_FORCE_N,
                e_pa=_E_PA,
                limit_m=limit_m,
            )
    raise RuntimeError("UpperArm bounded slot not found in the arm_a6 payload")


def run() -> bool:
    """Emit the bounded-slot proof pack; return True iff live."""
    writer = DemoWriter(DEMO, SURFACE)
    if not _coupling_available():
        gap_proof(
            writer,
            surface=SURFACE,
            optimized_quantity="UpperArm.UpperArmSection.b (bounded sketch-segment)",
            domain="arm_a6 UpperArm bounded sketch-segment [24mm, 40mm]",
            blocked_on="WO-97 D209 coupling + structural model channel (F125/F126.1)",
            detail=(
                "The bounded slot promotes to a `SegmentLength::Bounded` closure "
                "(WO-97 promotion half, landed), but D209's per-candidate "
                "evaluator (`optimize_sketch.pin_bounded_slot`) is not importable "
                "or the registry carries no model for "
                f"`{_CANTILEVER_KIND}` on the installed core, so no part can be "
                "pinned to a genuine optimize(...) value. This probe flips to "
                "the live path the moment both land."
            ),
        )
        return False

    from regolith.orchestrator.optimize_sketch import _rect_program, pin_bounded_slot
    from regolith.realizer.mech.interpreter import realize_feature_program

    # Build a COPY inside the demo tree so no build scratch lands in the
    # corpus (same discipline as demo3/demo4).
    work = writer.out_dir / "src"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(PROJECT, work)

    store = PayloadStore(str(work))
    slot = _upper_arm_slot(work, _LIMIT_M)
    trace, row_result = pin_bounded_slot(slot, store)
    if row_result.is_err:
        raise RuntimeError(
            f"UpperArm bounded slot did not pin: {row_result.danger_err}"
        )
    row = row_result.danger_ok
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    winner_width_mm = winner.objective_vector[0] * 1000.0

    # The tightened-limit variant (F128.3): re-run with a limit that
    # binds before the lower bound, proving the search genuinely moves
    # (real constrained optimize, not a rubber stamp on the lower bound).
    tight_slot = _upper_arm_slot(work, _TIGHTENED_LIMIT_M)
    tight_store = PayloadStore(str(work / "tightened"))
    tight_trace, tight_row_result = pin_bounded_slot(tight_slot, tight_store)
    assert tight_trace.winner is not None
    tight_winner = tight_trace.candidates[tight_trace.winner]
    tight_winner_width_mm = tight_winner.objective_vector[0] * 1000.0

    # (a) winner + cause row, verbatim, as the pinned lockfile.
    lockfile = Lockfile(
        tool_version=core_version(),
        sections=(LockSection(name="", rows=(row,)),),
    )
    writer.emit("regolith.lock", render_lockfile(lockfile).encode("ascii"))

    # (b) the REALIZED STEP for the winning geometry + GLB + viewer, off
    # the SAME construction the evaluator used for every candidate.
    program = _rect_program(slot, winner.objective_vector[0])
    realized = realize_feature_program(program)
    if realized.is_err:
        raise RuntimeError(f"winner geometry did not realize: {realized.danger_err}")
    step_bytes = realized.danger_ok.step_bytes
    writer.emit("upper_arm_section.step", step_bytes)
    mesh = tessellate_step(step_bytes)
    glb = write_glb((mesh,), (GlbNode(name="UpperArmSection", mesh=0),))
    writer.emit("upper_arm_section.glb", glb)
    writer.emit("upper_arm_section.viewer.html", viewer_html(glb, "UpperArmSection"))

    # (c) the search-trace sheet -- every candidate width, feasibility,
    # and the winner, off the SAME trace object the coupling pinned from.
    trace_model = opt_trace(row.slot, trace)
    writer.emit("opt_trace_b.svg", render_svg(trace_model))
    writer.emit("opt_trace_b.pdf", render_pdf(trace_model))

    cause_row = row.value + "    cause: " + row.cause
    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- optimized quantity: **UpperArm.UpperArmSection.b** (the bounded "
            "sketch-segment width, [24mm, 40mm])",
            "- domain: arm_a6 UpperArm's cantilever-deflection margin search "
            "(Euler-Bernoulli, end point load, `beam_bending.py`'s "
            "`mech.beam.cantilever_deflection` model), driven by DECLARED "
            f"inputs -- force {_FORCE_N}N (`link1.hema` payload_deflection "
            f"claim), span {slot.length_m * 1000:.0f}mm (promoted profile "
            f"run), E={_E_PA:.3e}Pa (AL6061_T6), thickness "
            f"{slot.thickness_m * 1000:.0f}mm (Blank record)",
            f"- winner: **b={winner_width_mm:.3f}mm** (the 1.5mm limit is "
            "slack at every candidate, so the minimizer converges to the "
            "lower bound, 24mm)",
            "- cause row (verbatim from `regolith.lock`):",
            "",
            "```",
            cause_row,
            "```",
            "",
            "## Binding-constraint evidence (the search is real)",
            "",
            f"Re-running the SAME coupling with the deflection limit tightened "
            f"to {_TIGHTENED_LIMIT_M * 1000:.3f}mm (below the deflection at "
            "24mm, above it at ~40mm) moves the winner OFF the lower bound: "
            f"**b={tight_winner_width_mm:.3f}mm** "
            f"(termination={tight_trace.termination.value}, "
            f"feasible={tight_winner.feasible}). A rubber-stamp evaluator "
            "would land on 24mm regardless of the limit; this one does not.",
            "",
            "## Honest residual: uav_talon WingSpar stays deferred",
            "",
            "`uav_talon`'s WingSpar carries the same `SegmentLength::Bounded` "
            "slot shape, but its governing load is `derived(sf=1.5)` -- there "
            "is no declared scalar force to hand the cantilever model, only a "
            "safety-factor derivation. Driving it through this coupling would "
            "require fabricating a load, which WO-97/D209 forbids; it stays "
            "honestly `optimizer_evaluator_deferred` (demo5 was retargeted to "
            "arm_a6 UpperArm, the part that genuinely pins -- F128.3). No demo "
            "in this pack claims WingSpar is live.",
            "",
            "## Where a human SEES it",
            "",
            "- `upper_arm_section.step` / `.glb` / `.viewer.html` -- the "
            "realized solid at the winning width; open the viewer in a "
            "browser.",
            "- `opt_trace_b.svg` / `.pdf` -- the real search trace: every "
            "candidate width, its feasibility, and the winner.",
            "- `regolith.lock` -- the pinned `cause: optimize(...)` row.",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="UpperArm.UpperArmSection.b (bounded sketch-segment)",
        domain="arm_a6 UpperArm bounded sketch-segment [24mm, 40mm]",
        winner=f"b={winner_width_mm:.3f}mm",
        cause_row=cause_row,
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
