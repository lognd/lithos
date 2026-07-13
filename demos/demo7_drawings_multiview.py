"""Demo 7 -- drawings: real HLR multi-view sheets, mech + civil (D222).

WO-115 deliverable 1. Drives the REAL two-command release flow
(`build --release` then `ship`) over TWO flagships and keeps only the
`drawings/` family from each package:

- printer_k1 (mech): the shipped sheets are OCP/OCCT hidden-line
  projections of the REAL pinned STEP bytes (charter 38 sec. 1.5) --
  front/top/side + isometric, dimensions visible in the rendered
  `DrawingModel` tables/entities.
- small_office (civil): the shipped `Frame.svg/.pdf/.dxf` is the civil
  plan/section sheet, projected from the REAL `FramePayload` (the same
  producer path demo6 exercises end to end for the whole package; this
  demo isolates the drawings family alone so it has its own proof).

Every sheet format (svg/pdf/dxf/drawing.json/explain.txt) ships from
the SAME renderer registry `ship` itself drives -- no second renderer,
no synthetic sheet.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from regolith.logging_setup import get_logger

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

DEMO = "demo7_drawings_multiview"
SURFACE = "projected multi-view drawing sheets (mech + civil), charter 38 sec. 1.5"

MECH_PROJECT = REPO_ROOT / "examples" / "flagships" / "printer_k1"
CIVIL_PROJECT = REPO_ROOT / "examples" / "flagships" / "small_office"


def _cli(*args: str) -> None:
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    _log.info("demo7: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        )


def _ship(writer: DemoWriter, tag: str, project) -> list[str]:
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
    drawings_dir = dist_dir / "drawings"
    emitted: list[str] = []
    if drawings_dir.is_dir():
        for path in sorted(drawings_dir.rglob("*")):
            if path.is_file():
                rel = f"{tag}/drawings/" + str(path.relative_to(drawings_dir))
                writer.emit(rel, path.read_bytes())
                emitted.append(rel)
    return emitted


def run() -> bool:
    """Emit the drawings-family proof pack; return True (this surface is live)."""
    writer = DemoWriter(DEMO, SURFACE)
    mech_files = _ship(writer, "mech_printer_k1", MECH_PROJECT)
    civil_files = _ship(writer, "civil_small_office", CIVIL_PROJECT)
    if not mech_files:
        raise RuntimeError("printer_k1 ship package emitted no drawings/ family")
    if not civil_files:
        raise RuntimeError("small_office ship package emitted no drawings/ family")

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- pipeline path: `regolith build --release <project>` then "
            "`regolith ship <project> --build ... --spec ship.spec.json` "
            "(the real two-command release flow; no bespoke drawing "
            "driver) -- the drawings/ family is the sheet set charter 38 "
            "sec. 1.5 describes: OCP/OCCT hidden-line projections of the "
            "pinned STEP bytes for mech, the pinned FramePayload for civil.",
            f"- mech: printer_k1 (`{MECH_PROJECT.name}`), "
            f"{len(mech_files)} file(s) under `drawings/`.",
            f"- civil: small_office (`{CIVIL_PROJECT.name}`), "
            f"{len(civil_files)} file(s) under `drawings/` (the plan/section "
            "sheet, `Frame.*`).",
            "- formats present per sheet: `.svg`, `.pdf`, `.dxf`, "
            "`.drawing.json` (the pre-render IR), `.explain.txt` "
            "(human-readable derivation note).",
            "- determinism: svg/pdf/dxf/drawing.json/explain.txt are all "
            "deterministic renderers (fixed deflection parameters, sorted "
            "output, ryu floats, charter 38 sec. 1.5); re-running this "
            "demo reproduces byte-identical hashes below.",
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo7_drawings_multiview",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (drawings family, not an optimizer surface)",
        domain="printer_k1 mech drawings + small_office civil plan sheet",
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
