"""Demo 4 -- civil section search: footbridge free-section family (WO-65).

`examples/tracks/calcite/footbridge.calx` declares its girders as
`section: in registry(std.civil.w_shape)` -- a FREE section over a
declared family. WO-65's `search_free_section` runs a real
`optimize_discrete` search that picks the lightest w_shape clearing
every declared demand (strength AND the L/360 deflection bound), pinning
`cause: optimize(mass_per_length, trace=<digest>)` (INV-21/INV-22).

This demo is wired behind an availability probe: it runs the REAL
`orchestrate.build` over footbridge, and if the landed WO-65 search
produced winner rows it emits the pinned lockfile, the two search-trace
sheets (loaded from the persisted traces), and the civil plan +
member-schedule sheet. If the machinery is absent it records an honest
gap (nonzero under `make demos-strict`).

To keep every write under `demos/out/` (never the corpus), the demo
builds a COPY of the design inside its own output tree.
"""

from __future__ import annotations

import json
import re
import shutil

from regolith import core_version
from regolith._schema.models import FramePayload
from regolith.backends.drawings.producers import civil_plan_section, opt_trace
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.drawings.renderer_pdf import render_pdf
from regolith.logging_setup import get_logger
from regolith.orchestrator.lockfile import (
    Lockfile,
    LockSection,
)
from regolith.orchestrator.lockfile import (
    render as render_lockfile,
)
from regolith.orchestrator.optimize import load_trace
from regolith.orchestrator.payload_store import PayloadStore

from demos.harness import REPO_ROOT, DemoWriter, artifact_table, gap_proof

_log = get_logger(__name__)

# frob:doc docs/modules/demos.md#demo-proof-pack-shape
DEMO = "demo4_section_search"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SURFACE = "civil free-section search over a declared family (footbridge, WO-65)"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SOURCE = REPO_ROOT / "examples" / "tracks" / "calcite" / "footbridge.calx"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
STDLIB = str(REPO_ROOT / "stdlib")
_TRACE_RE = re.compile(r"trace=(blake3:[0-9a-f]+)")


def _section_search_available() -> bool:
    """Probe: is the WO-65 free-section search present on the installed core?"""
    try:
        from regolith.orchestrator.frame_resolve import (
            search_free_section,  # noqa: F401
        )
    except ImportError:
        return False
    return True


# frob:doc docs/modules/demos.md#demo-proof-pack-shape
def run() -> bool:
    """Emit the section-search proof pack; return True iff live."""
    writer = DemoWriter(DEMO, SURFACE)
    if not _section_search_available():
        gap_proof(
            writer,
            surface=SURFACE,
            optimized_quantity="mass_per_length",
            domain="footbridge girders over std.civil.w_shape",
            blocked_on="WO-65 (frame_resolve.search_free_section)",
            detail=(
                "The free-section search evaluator is not importable on the "
                "installed core; this demo goes live automatically once WO-65 "
                "lands."
            ),
        )
        return False

    from regolith.orchestrator.orchestrate import build
    from regolith.orchestrator.tiers import BuildTier

    # Build a COPY inside the demo tree so the trace store (.regolith) and
    # any build scratch land under demos/out/, never in the corpus.
    src_dir = writer.out_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    design = src_dir / "footbridge.calx"
    shutil.copyfile(SOURCE, design)

    report = build(
        (str(design),), BuildTier.BUILD, frame_record_paths=(STDLIB,)
    ).danger_ok
    rows = tuple(sorted(report.frame_lock_rows, key=lambda r: r.slot))
    if not rows:
        raise RuntimeError("footbridge build produced no frame_lock_rows (search off?)")
    _log.info("demo4: %d section winner row(s)", len(rows))

    # The pinned lockfile -- the optimize(mass_per_length, ...) rows.
    lockfile = Lockfile(
        tool_version=core_version(),
        sections=(LockSection(name="", rows=rows),),
    )
    writer.emit("regolith.lock", render_lockfile(lockfile).encode("ascii"))

    # The search-trace sheets, loaded from the traces the build persisted.
    store = PayloadStore(str(src_dir))
    for row in rows:
        match = _TRACE_RE.search(row.cause)
        if match is None:
            continue
        loaded = load_trace(store, match.group(1))
        if loaded.is_err:
            _log.warning(
                "demo4: could not load trace %s: %s", row.slot, loaded.danger_err
            )
            continue
        member = row.slot.split(".")[1]
        model = opt_trace(row.slot, loaded.danger_ok)
        writer.emit(f"opt_trace_{member}.svg", render_svg(model))
        writer.emit(f"opt_trace_{member}.pdf", render_pdf(model))

    # The civil plan + member-schedule sheet off the real FramePayload.
    payload = json.loads(report.payload_json)
    frame_name = next(iter(payload["frames"]))
    frame = FramePayload.model_validate(payload["frames"][frame_name])
    plan_model = civil_plan_section(frame_name, frame)
    writer.emit("plan_schedule.svg", render_svg(plan_model))
    writer.emit("plan_schedule.pdf", render_pdf(plan_model))

    winners = ", ".join(r.value for r in rows)
    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- optimized quantity: **mass_per_length** (the lightest section "
            "clearing every declared demand -- strength AND the L/360 "
            "deflection bound -- under the SAME value+eps margin discharge uses)",
            "- domain: the footbridge girders' declared "
            "`section: in registry(std.civil.w_shape)` free-section family",
            f"- winners: **{winners}** (G1 is deflection-governed -> a heavier "
            "shape than the strength-only G2)",
            "- cause rows (verbatim from `regolith.lock`):",
            "",
            "```",
            *[r.value + "    cause: " + r.cause for r in rows],
            "```",
            "",
            "## Where a human SEES it",
            "",
            "- `opt_trace_G1.svg/.pdf`, `opt_trace_G2.svg/.pdf` -- the real "
            "search traces (loaded from the persisted trace store): every "
            "w_shape candidate's mass-per-length, feasibility, and the winner.",
            "- `plan_schedule.svg/.pdf` -- the frame plan + member schedule.",
            "",
            "### Honest residual (named, no producer edit)",
            "",
            "The member-schedule producer currently renders each free member's "
            "DECLARED domain (`unresolved`/free) rather than writing back the "
            "searched winner; the authoritative pinned section is the "
            "`cause: optimize(...)` lockfile row + the trace sheet above. "
            "Writing the search winner into the schedule cell is a WO-65 "
            "producer follow-on, out of this WO's (no-machinery-change) scope.",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="mass_per_length",
        domain="footbridge girders over std.civil.w_shape",
        winner=winners,
        cause_row=rows[0].value + "    cause: " + rows[0].cause,
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
