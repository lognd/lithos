"""WO-72 (D183 demo 4, CAM SELF-HOSTING): `examples/flagships/cnc_router_r1
/idler_bearing_plate.hema`'s `plan: extern(...)` clause verified end-to-
end by `std.cam` through the REAL `regolith build --json` pipeline --
the same `machine=`/`tooling=`/`resolution=` seam
`tests/test_cli_build_plan_cam.py` proved for the WO-67 fixture corpus's
throwaway `pillow_block`, here exercised against one of this flagship's
OWN realized plate parts (a genuine machined Z-axis idler bearing plate,
milled from 90x50x20mm bar stock) instead of a single-line fixture --
the machine class comes from `std.machines`, the tool from `std.tooling`
(via `examples/flagships/cnc_router_r1/records/cam.toml`, the WO-69
per-project records convention), and the good plan
(`nc/idler_bearing_plate_op10.nc`, WO-67's own proven fixture G-code,
reused rather than re-invented) discharges Valid across all five
landed `cam.*` models.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_PART = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "flagships"
    / "cnc_router_r1"
    / "idler_bearing_plate.hema"
)

_MODEL_ID_TO_KIND = {
    "cam_parse_gcode_fanuc@1": "cam.parse",
    "cam_envelope_gcode_fanuc@1": "cam.envelope",
    "cam_collision_coarse_gcode_fanuc@1": "cam.collision_coarse",
    "cam_removal_gcode_fanuc@1": "cam.removal",
    "cam_coverage_gcode_fanuc@1": "cam.coverage",
}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "regolith.cli", *args],
        capture_output=True,
        text=True,
    )


def _cam_results(report: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in report["final"]["results"]:
        evidence = r.get("evidence")
        if evidence is None:
            continue
        kind = _MODEL_ID_TO_KIND.get(evidence.get("model_id", ""))
        if kind is not None:
            out[kind] = r
    return out


def test_idler_bearing_plate_discharges_all_five_cam_models_valid() -> None:
    assert _PART.exists(), f"missing corpus source: {_PART}"
    result = _run("build", str(_PART), "--json")
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    report = json.loads(result.stdout)
    cam = _cam_results(report)
    assert set(cam) == {
        "cam.parse",
        "cam.envelope",
        "cam.collision_coarse",
        "cam.removal",
        "cam.coverage",
    }, f"missing cam.* results: {sorted(cam)} in {report['final']['results']}"
    for kind, row in cam.items():
        assert row["evidence"]["status"] == "discharged", (
            f"{kind} did not discharge Valid: {row}"
        )
