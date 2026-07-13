"""Demo 6 -- fleet showcase: a full `regolith ship` package (small_office).

The other five demos each isolate ONE optimizer surface. This demo shows
the whole thing in situ: the real two-command release flow

    regolith build --release <project> --out build/
    regolith ship  <project> --build build/ --spec ship.spec.json --out dist/

run via the REAL CLI (`python -m regolith.cli`, the console entry) over a
green fleet project, producing the complete `dist/` package -- index,
gate/parity/acceptance ledgers, drawings, 3D, BOM. small_office is chosen
because its `build --release` ITSELF runs the WO-65 free-section search
over its declared `std.civil.w_shape` members, so the shipped package's
own `regolith.lock` carries real `cause: optimize(mass_per_length, ...)`
rows -- the complete fleet package and a live optimizer pin in one tree.

The full dist tree's bytes are gitignored; this demo's manifest records
every file with its content hash, and PROOF.md points at the human-
readable index + the optimize rows.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from regolith.logging_setup import get_logger

from demos.harness import DemoWriter, REPO_ROOT, artifact_table

_log = get_logger(__name__)

DEMO = "demo6_fleet_showcase"
SURFACE = "full regolith ship package with a live optimize pin (small_office)"
PROJECT = REPO_ROOT / "examples" / "flagships" / "small_office"
SHIP_SPEC = PROJECT / "ship.spec.json"


def _cli(*args: str) -> None:
    """Invoke the REAL regolith CLI (the console entry) as a subprocess."""
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    _log.info("demo6: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        )


def run() -> bool:
    """Emit the fleet-showcase proof pack; return True (this surface is live)."""
    writer = DemoWriter(DEMO, SURFACE)
    build_dir = writer.out_dir / "build"
    dist_dir = writer.out_dir / "dist"
    for stale in (build_dir, dist_dir):
        if stale.exists():
            shutil.rmtree(stale)

    _cli("build", "--release", str(PROJECT), "--out", str(build_dir))
    _cli(
        "ship",
        str(PROJECT),
        "--build",
        str(build_dir),
        "--spec",
        str(SHIP_SPEC),
        "--out",
        str(dist_dir),
    )

    # Record every file of the real dist package, hashed.
    for path in sorted(dist_dir.rglob("*")):
        if path.is_file():
            rel = "dist/" + str(path.relative_to(dist_dir))
            writer.emit(rel, path.read_bytes())

    # Pull the live optimize row from the shipped package's own lockfile.
    lock_path = build_dir / "regolith.lock"
    optimize_rows = [
        line.strip()
        for line in lock_path.read_text().splitlines()
        if "cause: optimize(" in line
    ]
    if not optimize_rows:
        raise RuntimeError("small_office package carried no cause: optimize(...) row")
    _log.info("demo6: %d optimize row(s) in the shipped lockfile", len(optimize_rows))
    winner = optimize_rows[0].split("cause:")[0].strip()

    index_hash = next(r.sha256 for r in writer.rows if r.path == "dist/index.md")
    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- optimized quantity: **mass_per_length** -- small_office's steel "
            "members declared `section: in registry(std.civil.w_shape)`, sized "
            "by the WO-65 free-section search during `build --release`, here "
            "inside a FULL release package",
            "- domain: the flagship's free-section `std.civil.w_shape` members",
            "- winner + cause rows (verbatim from the shipped `build/regolith.lock`):",
            "",
            "```",
            *optimize_rows,
            "```",
            "",
            "## The full package a human opens",
            "",
            "This is the complete `regolith ship` dist tree, produced by the "
            "real two-command flow (`build --release` then `ship`):",
            "",
            f"- `dist/index.md` (sha256 `{index_hash}`) -- the release-gate stamp "
            "and the content-hashed listing of every artifact family.",
            "- `dist/drawings/` -- per-part SVG + PDF + DXF drawings.",
            "- `dist/3d/` -- per-part GLB + offline viewer.",
            "- `dist/bom/` -- the massed BOM (csv/json/md/pdf).",
            "- `dist/gate_summary.json`, `dist/parity_ledger.json`, "
            "`dist/acceptance_ledger.json`, `dist/manifest.json` -- the signed "
            "release ledgers.",
            "",
            "Every file above is content-addressed in this demo's `manifest.json` "
            "and re-verifiable with `regolith ship --verify`.",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="mass_per_length (free-section search)",
        domain="small_office full ship package + its std.civil.w_shape section pins",
        winner=winner,
        cause_row=optimize_rows[0],
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
