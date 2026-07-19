"""Demo 8 -- BOM v2 + cost + member schedule (D222, charter 38 sec. 1.7/1.8).

Three real fleet surfaces, one proof pack:

1. Derived BOM with REAL masses (cnc_router_r1): `build --release` +
   `ship` emit the `bom/` family -- rows derived from the design graph,
   mass = std.materials density x OCP volume with material + geometry
   pins, four deterministic formats (csv/json/md/pdf). Nothing is
   invented: unsourced fittings say so, and every cost cell without an
   estimate carries its reason.
2. Member schedule (timber_pavilion): the shipped civil sheet carries
   the Member Schedule table (id/role/length/section/material per
   member, sections + materials record-pinned) in PDF/SVG/DXF plus the
   machine-readable `.drawing.json` rows.
3. Cost sheet (timber_pavilion): the build persists a REAL
   `ItemizedEstimate` (`all/construction`, the D147 costing evidence);
   this demo resolves it through the SAME `ship.resolve_cost_estimates`
   channel `ship` itself uses and renders the WO-101 deliverable-5
   `cost_summary_sheet` producer to PDF + SVG. The ship-side `cost/`
   dist family is WO-101's still-open residual (Status: in-progress) --
   see WO115-F1 in PROOF.md; the producer + the evidence are real, the
   dist wiring is the named gap.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from regolith.backends.cost_schedule import cost_summary_sheet
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.drawings.renderer_pdf import render_pdf
from regolith.backends.ship import resolve_cost_estimates
from regolith.logging_setup import get_logger
from regolith.orchestrator.orchestrate import StagedBuildReport

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

# frob:doc docs/modules/demos.md#demo-proof-pack-shape
DEMO = "demo8_bom_cost_schedule"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SURFACE = "derived BOM v2 (real masses) + cost sheet + member schedule"

# frob:doc docs/modules/demos.md#demo-proof-pack-shape
BOM_PROJECT = REPO_ROOT / "examples" / "flagships" / "cnc_router_r1"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
CIVIL_PROJECT = REPO_ROOT / "examples" / "flagships" / "timber_pavilion"


def _cli(*args: str) -> None:
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    _log.info("demo8: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        )


def _build_and_ship(writer: DemoWriter, tag: str, project: Path) -> Path:
    """Run the real two-command flow; return the build dir (report source)."""
    build_dir = writer.out_dir / f"build_{tag}"
    dist_dir = writer.out_dir / f"dist_{tag}"
    for stale in (build_dir, dist_dir):
        if stale.exists():
            shutil.rmtree(stale)
    _cli("build", "--release", str(project), "--out", str(build_dir))
    _cli(
        "ship",
        str(project),
        "--build",
        str(build_dir),
        "--spec",
        str(project / "ship.spec.json"),
        "--out",
        str(dist_dir),
    )
    return build_dir


def _emit_family(writer: DemoWriter, tag: str, family_dir: Path, prefix: str) -> int:
    count = 0
    for path in sorted(family_dir.rglob("*")):
        if path.is_file():
            writer.emit(
                f"{tag}/{prefix}/" + str(path.relative_to(family_dir)),
                path.read_bytes(),
            )
            count += 1
    return count


# frob:doc docs/modules/demos.md#demo-proof-pack-shape
# frob:waive TEST005 reason="demo run() orchestration: env-gated branches (tool presence, fleet subsets) make branch coverage jitter across stamps; measured 2026-07-19; backfill T-0036"
def run() -> bool:
    """Emit the BOM/cost/schedule proof pack; return True (live)."""
    writer = DemoWriter(DEMO, SURFACE)

    # -- 1. Derived BOM v2 with real masses (cnc_router_r1) ------------
    cnc_build = _build_and_ship(writer, "cnc_router_r1", BOM_PROJECT)
    cnc_bom = _emit_family(
        writer, "cnc_router_r1", writer.out_dir / "dist_cnc_router_r1" / "bom", "bom"
    )
    if cnc_bom == 0:
        raise RuntimeError("cnc_router_r1 shipped no bom/ family")
    bom_csv = (writer.out_dir / "dist_cnc_router_r1" / "bom" / "bom.csv").read_text()
    massed_rows = [
        line
        for line in bom_csv.splitlines()[1:]
        if line.split(",")[7].strip() not in ("", '""') and "TOTAL" not in line
    ]
    if not massed_rows:
        raise RuntimeError("cnc_router_r1 BOM carries no real mass rows")
    total_row = next(line for line in bom_csv.splitlines() if line.startswith("TOTAL"))

    # -- 2. Member schedule (timber_pavilion civil sheet) ---------------
    timber_build = _build_and_ship(writer, "timber_pavilion", CIVIL_PROJECT)
    timber_drawings = writer.out_dir / "dist_timber_pavilion" / "drawings"
    schedule_files = 0
    for path in sorted(timber_drawings.rglob("PavilionFrame.*")):
        writer.emit("timber_pavilion/schedule/" + path.name, path.read_bytes())
        schedule_files += 1
    if schedule_files == 0:
        raise RuntimeError("timber_pavilion shipped no PavilionFrame sheet")
    sheet_json = next(timber_drawings.rglob("PavilionFrame.drawing.json")).read_text()
    if "Member Schedule" not in sheet_json:
        raise RuntimeError("PavilionFrame sheet carries no Member Schedule table")

    # -- 3. Cost sheet from the REAL persisted estimate -----------------
    # The build's own report names its persisted ItemizedEstimate
    # (`all/construction`); resolve it through the SAME channel `ship`
    # uses (`resolve_cost_estimates`), then render the WO-101
    # deliverable-5 producer. Real evidence, real producer -- the dist
    # `cost/` wiring is WO115-F1 (see PROOF.md).
    report = StagedBuildReport.model_validate_json(
        (timber_build / "build_report.json").read_text()
    )
    estimates = resolve_cost_estimates(report, str(CIVIL_PROJECT))
    if not estimates:
        raise RuntimeError(
            "timber_pavilion build persisted no resolvable cost estimate"
        )
    model = cost_summary_sheet("timber_pavilion", estimates)
    writer.emit("timber_pavilion/cost/cost_summary.pdf", render_pdf(model))
    writer.emit("timber_pavilion/cost/cost_summary.svg", render_svg(model))
    total = next(iter(estimates.values())).total
    cost_total = f"{total.lo:.2f}..{total.hi:.2f} {total.unit}"

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "## 1. Derived BOM v2 with real masses (cnc_router_r1)",
            "",
            "- pipeline path: `regolith build --release` + `regolith ship "
            "--spec ship.spec.json` -- the `bom/` family (csv/json/md/pdf) "
            "derives rows from the design graph (charter 38 sec. 1.7): "
            f"{len(massed_rows)} row(s) carry a REAL mass (std.materials "
            "density x OCP volume over the pinned STEP bytes) with "
            "`material_pin` + `geometry_pin` provenance columns.",
            f"- totals row (verbatim): `{total_row}`",
            "- honesty: fittings with no record ship `UNSOURCED`; every "
            "empty mass/cost cell carries its reason column, never a "
            "fabricated number.",
            "",
            "## 2. Member schedule (timber_pavilion)",
            "",
            "- the shipped civil sheet `PavilionFrame.*` carries the "
            "`Member Schedule` table -- one row per frame member "
            "(id/role/length/section/material, sections + materials "
            "record-pinned) -- in PDF/SVG/DXF plus the machine-readable "
            "`.drawing.json` rows.",
            "",
            "## 3. Cost sheet from real costing evidence (timber_pavilion)",
            "",
            "- the release build persists a REAL `ItemizedEstimate` "
            "(`all/construction`, D147 costing evidence) into the "
            "discharge-time payload store; this demo resolves it via "
            "`regolith.backends.ship.resolve_cost_estimates` (the SAME "
            "channel `ship` threads into the BOM cost join) and renders "
            "the WO-101 deliverable-5 `cost_summary_sheet` producer to "
            "PDF + SVG.",
            f"- estimate grand total: {cost_total}.",
            "- WO115-F1 (named gap, not papered over): no fleet ship "
            "package today emits the `cost/` dist family (`index.md` says "
            "`cost/: absent` everywhere) -- `cost_summary_sheet` has no "
            "ship-side caller (WO-101 Status: in-progress), and the BOM "
            "cost JOIN columns stay honestly empty fleet-wide because no "
            "persisted estimate subject matches a BOM row subject "
            "(timber's estimate subject is `all`; cnc has none). The "
            "producer and the evidence above are both real; the dist "
            "wiring is the WO-101 residual.",
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo8_bom_cost_schedule",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (BOM/cost/schedule family, not an optimizer surface)",
        domain="cnc_router_r1 BOM + timber_pavilion schedule/cost evidence",
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    _log.info("demo8: cnc build report at %s (BOM source)", cnc_build)
    return True


if __name__ == "__main__":
    run()
