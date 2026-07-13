"""Demo 14 -- spec-less `regolith preview` vs `ship`: byte-parity where designed.

WO-115 deliverable 8 (D197). Over cnc_router_r1, the demo runs BOTH
review doors:

    regolith preview <project> --out prev/     (NO --spec: auto-derived
        sheet set -- one per subject in the build's realized maps --
        plus the 3D family and gate_summary.json)
    regolith build --release + regolith ship   (the release package)

and proves the two designed relationships on the real bytes:

1. BYTE-PARITY where designed: the 3D family (GLB + viewer.html) is
   never stamped (binary geometry is not a sheet the honesty banner
   rides -- `run_preview`'s own rule), so every preview 3D file must be
   byte-identical to the shipped package's counterpart. Asserted
   file-by-file below.
2. STAMPED DIVERGENCE where designed: preview sheets carry the D197
   honesty stamp as a model-level annotation; ship sheets never do.
   For every shipped drawing subject the demo strips exactly that one
   stamp annotation from the preview `.drawing.json` and asserts the
   remainder equals ship's model -- the ONLY difference is the stamp.

The preview stamp itself is honest state: cnc_router_r1 is
RELEASE-CLEAN with accepted deviations, and `gate_summary.json` ships
in this pack verbatim.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from regolith.logging_setup import get_logger

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

DEMO = "demo14_preview_parity"
SURFACE = "spec-less preview artifact set vs ship byte-parity (D197)"
PROJECT = REPO_ROOT / "examples" / "flagships" / "cnc_router_r1"


def _cli(*args: str) -> None:
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    _log.info("demo14: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        )


def _strip_stamp(model: dict, stamp_text: str) -> dict:
    """Remove the one D197 stamp annotation from every sheet (verifying
    it is present and FIRST, the documented prepend position)."""
    for sheet in model["sheets"]:
        annotations = sheet["annotations"]
        if not annotations or annotations[0]["text"] != stamp_text:
            raise RuntimeError(
                "preview sheet does not lead with the D197 stamp annotation"
            )
        sheet["annotations"] = annotations[1:]
    return model


def run() -> bool:
    """Emit the preview-parity proof pack; return True (live)."""
    writer = DemoWriter(DEMO, SURFACE)
    prev_dir = writer.out_dir / "preview"
    build_dir = writer.out_dir / "build"
    dist_dir = writer.out_dir / "dist"
    for stale in (prev_dir, build_dir, dist_dir):
        if stale.exists():
            shutil.rmtree(stale)

    _cli("preview", str(PROJECT), "--out", str(prev_dir))
    _cli("build", "--release", str(PROJECT), "--out", str(build_dir))
    _cli(
        "ship",
        str(PROJECT),
        "--build",
        str(build_dir),
        "--spec",
        str(PROJECT / "ship.spec.json"),
        "--out",
        str(dist_dir),
    )

    from regolith.orchestrator.orchestrate import GateSummary

    gate = GateSummary.model_validate_json(
        (prev_dir / "gate_summary.json").read_text()
    )
    stamp_text = gate.stamp_text
    writer.emit(
        "preview/gate_summary.json", (prev_dir / "gate_summary.json").read_bytes()
    )

    # 1. Byte-parity: every preview 3D file == the shipped counterpart.
    ship_3d = {p.name: p for p in (dist_dir / "3d").rglob("*") if p.is_file()}
    parity_rows: list[str] = []
    for path in sorted((prev_dir / "3d").iterdir()):
        counterpart = ship_3d.get(path.name)
        if counterpart is None:
            raise RuntimeError(f"preview 3D file {path.name} missing from ship")
        if path.read_bytes() != counterpart.read_bytes():
            raise RuntimeError(f"3D byte-parity broken for {path.name}")
        parity_rows.append(path.name)
        writer.emit("preview/3d/" + path.name, path.read_bytes())
    if not parity_rows:
        raise RuntimeError("preview emitted no 3D family")

    # 2. Stamped divergence: preview sheet minus the stamp == ship sheet.
    ship_drawings = {
        p.name: p
        for p in (dist_dir / "drawings").rglob("*.drawing.json")
        if p.is_file()
    }
    stamped_subjects: list[str] = []
    for name, ship_path in sorted(ship_drawings.items()):
        prev_path = prev_dir / "drawings" / name
        if not prev_path.is_file():
            raise RuntimeError(f"spec-less preview missed shipped sheet {name}")
        stripped = _strip_stamp(json.loads(prev_path.read_text()), stamp_text)
        if stripped != json.loads(ship_path.read_text()):
            raise RuntimeError(
                f"{name}: preview and ship sheets differ beyond the stamp"
            )
        stamped_subjects.append(name)
        writer.emit("preview/drawings/" + name, prev_path.read_bytes())
    if not stamped_subjects:
        raise RuntimeError("no shipped drawing subjects to compare")

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- pipeline path: `regolith preview <project> --out` with NO "
            "--spec (the auto-derived sheet set) beside the real "
            "`build --release` + `ship` package, both over "
            "cnc_router_r1.",
            f"- preview gate stamp (honest state): `{stamp_text}`.",
            f"- BYTE-PARITY (designed): all {len(parity_rows)} preview 3D "
            "file(s) (GLB + viewer.html) are byte-identical to the "
            "shipped package's -- the 3D family is never stamped, so "
            "review bytes ARE release bytes. Asserted file-by-file.",
            f"- STAMPED DIVERGENCE (designed): all {len(stamped_subjects)} "
            "shipped drawing subject(s) appear in the spec-less preview "
            "set, and stripping exactly the one leading D197 stamp "
            "annotation from each preview `.drawing.json` reproduces "
            "ship's model EXACTLY -- the stamp is the only difference, "
            "asserted structurally per sheet.",
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo14_preview_parity",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (preview family, not an optimizer surface)",
        domain="cnc_router_r1 spec-less preview vs release package",
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
