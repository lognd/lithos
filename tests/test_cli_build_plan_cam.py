"""WO-69 end-to-end proof: a `plan:` clause on a real corpus part reaches
`std.cam` (WO-67) through the REAL `regolith build --json` pipeline --
source -> Rust lowering (`push_plan_obligations`) -> orchestrator staging
(`plan_staging`/`_translate_cam`) -> the five landed `cam.*` models, not a
pack-level unit test. The good plan discharges Valid x5; the out-of-
travel variant surfaces `cam.envelope` violated by name, via the same
subprocess console entry point `tests/test_cli_build.py` uses (AD-10:
a real process boundary, not `CliRunner`).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_MANIFEST = '[package]\nname = "wo69-plan-cam"\n'

_SOURCE = (
    "part pillow_block:\n"
    '    plan: extern("plan.nc", gcode_fanuc) machine=fixture_mill_3axis, '
    "tooling=fixture_tool_1, resolution=0.05mm\n"
)

# The exact pillow_block geometry WO-67's `tests/harness/test_cam_models.py`
# fixture corpus already proved Valid/violated against (ONE fixture shape,
# reused rather than re-invented -- NO DUPLICATION).
_GOOD_PLAN = (
    Path(__file__).resolve().parent / "fixtures" / "cam" / "good.nc"
).read_text()
_OUT_OF_TRAVEL_PLAN = (
    Path(__file__).resolve().parent / "fixtures" / "cam" / "out_of_travel.nc"
).read_text()

_RECORDS_TOML = """
[[machine]]
key = "fixture_mill_3axis"
name = "fixture_mill_3axis"
kind = "mill_3axis"
travel = { x_min = 0.0, x_max = 300.0, y_min = 0.0, y_max = 200.0, \
z_min = -50.0, z_max = 50.0 }
max_feed_mm_min = 3000.0
source = "WO-69 e2e fixture"

[[tool]]
key = "fixture_tool_1"
tool_id = 1
diameter_mm = 6.0
flutes = 4
stickout_mm = 30.0
source = "WO-69 e2e fixture"

[[stock_target]]
key = "fixture_target"
geometry_digest = "fixture:pillow_block:v1"
stock = { x_min = 0.0, x_max = 90.0, y_min = 0.0, y_max = 50.0, \
z_min = -20.0, z_max = 0.0 }
finished = { x_min = 0.0, x_max = 90.0, y_min = 0.0, y_max = 50.0, \
z_min = -18.0, z_max = -0.1 }
margin_mm = 0.5
features = [
  { name = "pocket_a", kind = "pocket", touch_zone = \
{ x_min = 9.0, x_max = 41.0, y_min = 9.0, y_max = 41.0, z_min = -18.0, \
z_max = -1.0 } },
  { name = "bore_b", kind = "bore", touch_zone = \
{ x_min = 69.0, x_max = 81.0, y_min = 29.0, y_max = 41.0, z_min = -18.0, \
z_max = -1.0 } },
]
"""


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "regolith.cli", *args],
        capture_output=True,
        text=True,
    )


def _project(tmp_path: Path, plan_text: str) -> Path:
    (tmp_path / "magnetite.toml").write_text(_MANIFEST)
    (tmp_path / "records").mkdir(parents=True, exist_ok=True)
    (tmp_path / "records" / "cam.toml").write_text(_RECORDS_TOML)
    (tmp_path / "plan.nc").write_text(plan_text)
    source = tmp_path / "pillow_block.hema"
    source.write_text(_SOURCE)
    return source


_MODEL_ID_TO_KIND = {
    "cam_parse_gcode_fanuc@1": "cam.parse",
    "cam_envelope_gcode_fanuc@1": "cam.envelope",
    "cam_collision_coarse_gcode_fanuc@1": "cam.collision_coarse",
    "cam_removal_gcode_fanuc@1": "cam.removal",
    "cam_coverage_gcode_fanuc@1": "cam.coverage",
}


def _cam_results(report: dict) -> dict[str, dict]:
    """claim_kind -> its ObligationResult dict, for the five cam.* claims
    (keyed by the discharging model id, WO-67's landed registration --
    `Evidence` carries `model_id`, not a `claim_kind` field)."""
    out: dict[str, dict] = {}
    for r in report["final"]["results"]:
        evidence = r.get("evidence")
        if evidence is None:
            continue
        kind = _MODEL_ID_TO_KIND.get(evidence.get("model_id", ""))
        if kind is not None:
            out[kind] = r
    return out


def test_a_good_plan_discharges_all_five_cam_models_valid(tmp_path: Path) -> None:
    source = _project(tmp_path, _GOOD_PLAN)
    result = _run("build", str(source), "--json")
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
    # cam.removal's margin-arithmetic gap (WO-69's ledger finding, fixed
    # by folding `target.margin_mm` into `cam.removal`'s claim `limit`
    # in `orchestrator/translate.py`'s `_translate_cam`, instead of
    # claiming the declared resolution `eps` against an exact-zero
    # limit) is now fixed -- all five cam.* obligations discharge Valid
    # for a good plan.
    for kind, row in cam.items():
        assert row["evidence"]["status"] == "discharged", (
            f"{kind} did not discharge Valid: {row}"
        )


def test_out_of_travel_plan_surfaces_cam_envelope_violated(tmp_path: Path) -> None:
    source = _project(tmp_path, _OUT_OF_TRAVEL_PLAN)
    result = _run("build", str(source), "--json")
    report = json.loads(result.stdout)
    cam = _cam_results(report)
    assert "cam.envelope" in cam, f"cam.envelope missing: {sorted(cam)}"
    assert cam["cam.envelope"]["evidence"]["status"] == "violated", cam["cam.envelope"]


def test_removing_the_plan_field_removes_the_cam_obligations(tmp_path: Path) -> None:
    (tmp_path / "magnetite.toml").write_text(_MANIFEST)
    source = tmp_path / "plain.hema"
    source.write_text("part p:\n    a: 1mm\n")
    result = _run("build", str(source), "--json")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert not _cam_results(report), "no plan: field -> no cam.* obligations"
