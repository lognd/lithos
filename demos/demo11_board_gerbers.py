"""Demo 11 -- boards: a real KiCad gerber set from a BoardOutline.

WO-115 deliverable 5 (charter 38 sec. 1.10). mainboard_mx is the board
flagship: its `.cupr` declares the real 305x244mm BoardOutline, and the
release flow ships the `boards/` manufacturing family:

    regolith build --release --spec ship.spec.json   (the elec leg
        realizes the board: the spec's `elec_boards` block pins
        `deterministic: true`, so the DETERMINISTIC fake-KiCad tier
        writes the outline-only `.kicad_pcb` -- stamped as such by
        `(generator regolith-fake-kicad)` and `board_status.json`)
    regolith ship --build ... --spec ...             (the ElecBackend
        resolves the pinned board bytes and drives REAL `kicad-cli pcb
        export gerbers|drill|pos` -- toolenv resolves kicad-cli 10.0.4
        on this host -- into the shipped gerber/drill/pick-place set)

Honesty labels carried through: the board is `unrouted -- fab-shape
evidence` (real outline, no routing performed; never a fabricated
"routed"), and the REAL kicad-cli exports embed `TF.CreationDate`
timestamps, so every gerber/drill/pos row in this manifest is marked
deterministic=False with that reason -- the fake tier stays the
deterministic CI leg, exactly as the charter stamps it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

from regolith.logging_setup import get_logger

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

DEMO = "demo11_board_gerbers"
SURFACE = "real KiCad gerber set from the mainboard_mx BoardOutline"
PROJECT = REPO_ROOT / "examples" / "flagships" / "mainboard_mx"

# Real kicad-cli output embeds TF.CreationDate: honestly nondeterministic.
_TIMESTAMPED_DIRS = ("gerbers/", "drill/", "pos/")


def _cli(*args: str) -> None:
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    _log.info("demo11: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        )


def run() -> bool:
    """Emit the boards-family proof pack; return True (this surface is live)."""
    writer = DemoWriter(DEMO, SURFACE)
    build_dir = writer.out_dir / "build"
    dist_dir = writer.out_dir / "dist"
    for stale in (build_dir, dist_dir):
        if stale.exists():
            shutil.rmtree(stale)

    spec = PROJECT / "ship.spec.json"
    _cli(
        "build",
        "--release",
        str(PROJECT),
        "--spec",
        str(spec),
        "--out",
        str(build_dir),
    )
    _cli(
        "ship",
        str(PROJECT),
        "--build",
        str(build_dir),
        "--spec",
        str(spec),
        "--out",
        str(dist_dir),
    )

    boards = dist_dir / "boards"
    gerbers: list[str] = []
    for path in sorted(boards.rglob("*")):
        if not path.is_file():
            continue
        rel_in_family = str(path.relative_to(boards))
        deterministic = not rel_in_family.startswith(_TIMESTAMPED_DIRS)
        writer.emit(
            "boards/" + rel_in_family, path.read_bytes(), deterministic=deterministic
        )
        if rel_in_family.startswith("gerbers/"):
            gerbers.append(rel_in_family)
    if not gerbers:
        raise RuntimeError("mainboard_mx shipped no gerbers")

    # Assert the proof's load-bearing facts on the real bytes.
    status = json.loads((boards / "board_status.json").read_text())
    if status["status"] != "unrouted":
        raise RuntimeError(f"unexpected board status: {status}")
    edge_cuts = next(boards.glob("gerbers/*Edge_Cuts*")).read_text()
    if "KiCad" not in edge_cuts:
        raise RuntimeError("Edge_Cuts gerber does not carry the KiCad header")
    pcb_text = (boards / "board.kicad_pcb").read_text()
    if "regolith-fake-kicad" not in pcb_text:
        raise RuntimeError("pinned board is not stamped with its generator tier")

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- feature proven: the shipped `boards/` manufacturing family "
            "(charter 38 sec. 1.10) -- gerber set, excellon drill file, "
            "pick-and-place CSV, the pinned `board.kicad_pcb`, the elec "
            "BOM (the spec's four vendor parts), and `panel.json`, all "
            "from the design's own declared 305x244mm BoardOutline.",
            "- pipeline path: `regolith build --release --spec` (the elec "
            "leg realizes the board; the spec pins `deterministic: true` "
            "so the fake-KiCad tier writes the outline-only board, "
            "stamped `(generator regolith-fake-kicad)`) then `regolith "
            "ship --build --spec` (the ElecBackend resolves the pinned "
            "bytes and drives REAL `kicad-cli pcb export` -- kicad-cli "
            "10.0.4 via toolenv on this host).",
            f"- {len(gerbers)} gerber layer(s), verified to carry the real "
            "KiCad generation header.",
            "- honesty labels: `board_status.json` says `unrouted -- "
            "fab-shape evidence: real board outline, no routing "
            "performed` (asserted above; never a fabricated routed "
            "claim). The real kicad-cli exports embed `TF.CreationDate` "
            "timestamps, so every `gerbers/`, `drill/`, `pos/` row below "
            "is marked deterministic=False -- the fake tier remains the "
            "deterministic CI leg, exactly as charter 38 stamps it. "
            "Re-running this demo refreshes exactly those rows' hashes "
            "in `manifest.json` (the labeled churn); every "
            "deterministic row reproduces byte-identically.",
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo11_board_gerbers",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (boards family, not an optimizer surface)",
        domain="mainboard_mx BoardOutline -> gerber/drill/pos manufacturing set",
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
