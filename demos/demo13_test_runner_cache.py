"""Demo 13 -- `regolith test`: a corpus net with cache-proven replay.

WO-115 deliverable 7 (charter toolchain/37, WO-83 slice B). Runs the
REAL `regolith test` CLI over a corpus net of four roots that together
cover all four languages' test declarations:

    examples/flagships/printer_k1        (printer_k1.test.cupr)
    examples/flagships/cubesat           (kestrel.test.cupr +
                                          structure.test.hema)
    examples/tracks/fluorite/aquarium_loop.test.fluo
    examples/tracks/calcite/bus_shelter.test.calx

and proves the content-addressed incremental cache:

    run 1 (COLD -- each project's `.regolith/test-cache.json` removed
           first): every scenario builds through the ordinary door
           (AD-22) and reports `from_cache: false`;
    run 2 (WARM -- nothing changed): every scenario reports
           `from_cache: true` -- an unchanged scenario over an
           unchanged design never rebuilds.

Both machine-readable summaries ship in the pack, plus a diffable
cold-vs-warm table. The cache key is blake3 over scenario + design
content (`regolith.orchestrator.test_runner`), so any source edit
would honestly re-run -- nothing here mutates fleet sources to prove
it (the cold leg already proves the miss path).
"""

from __future__ import annotations

import json
import subprocess
import sys

from regolith.logging_setup import get_logger

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

DEMO = "demo13_test_runner_cache"
SURFACE = "regolith test over a corpus net with cache-proven replay"

_ROOTS = (
    "examples/flagships/printer_k1",
    "examples/flagships/cubesat",
    "examples/tracks/fluorite/aquarium_loop.test.fluo",
    "examples/tracks/calcite/bus_shelter.test.calx",
)
# The projects whose sibling cache files the cold leg clears (single
# .test.<ext> roots cache beside their own parent dir's .regolith/).
_CACHE_FILES = (
    "examples/flagships/printer_k1/.regolith/test-cache.json",
    "examples/flagships/cubesat/.regolith/test-cache.json",
    "examples/tracks/fluorite/.regolith/test-cache.json",
    "examples/tracks/calcite/.regolith/test-cache.json",
    "examples/tracks/.regolith/test-cache.json",
)


def _run_tests() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "regolith.cli",
        "test",
        *_ROOTS,
        "--json",
    ]
    _log.info("demo13: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith test failed (exit {result.returncode}):\n{result.stderr}"
        )
    return json.loads(result.stdout)


def _summary_bytes(payload: dict) -> bytes:
    """Deterministic JSON of the run (sorted keys, trailing newline)."""
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("ascii")


def run() -> bool:
    """Emit the test-runner proof pack; return True (this surface is live)."""
    writer = DemoWriter(DEMO, SURFACE)

    for rel in _CACHE_FILES:
        path = REPO_ROOT / rel
        if path.is_file():
            path.unlink()
            _log.info("demo13: cleared %s for the cold leg", rel)

    cold = _run_tests()
    warm = _run_tests()

    if not cold["ok"] or not warm["ok"]:
        raise RuntimeError("corpus test net not green")
    cold_rows = {t["name"]: t["from_cache"] for t in cold["tests"]}
    warm_rows = {t["name"]: t["from_cache"] for t in warm["tests"]}
    if set(cold_rows) != set(warm_rows) or not cold_rows:
        raise RuntimeError("cold/warm scenario sets differ or are empty")
    if any(cold_rows.values()):
        raise RuntimeError(f"cold leg hit the cache: {cold_rows}")
    if not all(warm_rows.values()):
        raise RuntimeError(f"warm leg missed the cache: {warm_rows}")

    writer.emit("run1_cold.json", _summary_bytes(cold))
    writer.emit("run2_warm.json", _summary_bytes(warm))
    table = ["| scenario | cold from_cache | warm from_cache |", "|---|---|---|"]
    for name in sorted(cold_rows):
        table.append(f"| {name} | {cold_rows[name]} | {warm_rows[name]} |")
    writer.emit("cache_proof.md", ("\n".join(table) + "\n").encode("ascii"))

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- feature proven: `regolith test` discovers and runs every "
            "`test <name>:` declaration under a multi-root corpus net "
            "(cuprite + hematite + fluorite + calcite declarations), "
            "with content-addressed incremental caching.",
            "- pipeline path: the real `regolith test` CLI, each "
            "scenario through the ordinary build door (AD-22) -- no "
            "private pipeline, no fake runner.",
            f"- corpus net: {len(cold_rows)} scenario(s) across "
            f"{len(_ROOTS)} root(s): " + ", ".join(f"`{r}`" for r in _ROOTS) + ".",
            "- cache proof: run 1 (cold, cache files cleared) reports "
            "`from_cache: false` for EVERY scenario; run 2 (unchanged) "
            "reports `from_cache: true` for EVERY scenario -- asserted "
            "programmatically above, tabulated in `cache_proof.md`.",
            "",
            "## Scenarios",
            "",
            *table,
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo13_test_runner_cache",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (test runner, not an optimizer surface)",
        domain="four-language corpus test net (printer_k1, cubesat, fluo, calx)",
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
