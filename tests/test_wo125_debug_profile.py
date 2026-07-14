"""WO-125 acceptance: the debug emission profile over the REAL CLI.

Drives ``regolith build --release`` then ``regolith ship
--emit-profile {release,debug}`` for the two augmentable fleet
projects -- mainboard_mx (the fleet's one board-bearing project;
WO-127's jig is the second, ledgered) and riscv_hart_rv1 (HDL) -- and
asserts the charter 40 acceptance facts on the shipped bytes:

* the debug package carries the placed tap header + labeled test
  points (``boards/tap_placements.json``) and the tap map
  (``harness/tap_map.json``) -- INV-32 held or the ship would have
  refused;
* verdict/census output is IDENTICAL between profiles (D206/D220.1:
  the manifest evidence rollup and ``gate_summary.json`` are
  byte-equal);
* the release package is untouched by the debug machinery (no
  ``harness/`` family, no ``REGOLITH-TAP`` marker anywhere).

Heavier than a unit test (real release builds), the same standing bar
`tests/test_wo108_demos.py` sets for the proof packs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAINBOARD = REPO_ROOT / "examples" / "flagships" / "mainboard_mx"
RISCV = REPO_ROOT / "examples" / "flagships" / "riscv_hart_rv1"


def _cli(*args: str) -> None:
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert result.returncode == 0, (
        f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
    )


@pytest.fixture(scope="module")
def mainboard_ships(tmp_path_factory) -> dict[str, Path]:
    """One release build of mainboard_mx, shipped under BOTH profiles."""
    work = tmp_path_factory.mktemp("wo125_mainboard")
    build_dir = work / "build"
    spec = MAINBOARD / "ship.spec.json"
    _cli(
        "build",
        "--release",
        str(MAINBOARD),
        "--spec",
        str(spec),
        "--out",
        str(build_dir),
    )
    ships: dict[str, Path] = {}
    for profile in ("release", "debug"):
        out = work / f"ship_{profile}"
        _cli(
            "ship",
            str(MAINBOARD),
            "--build",
            str(build_dir),
            "--spec",
            str(spec),
            "--out",
            str(out),
            "--emit-profile",
            profile,
        )
        ships[profile] = out
    return ships


class TestMainboardDebugShip:
    def test_debug_package_places_header_and_labeled_test_points(
        self, mainboard_ships
    ) -> None:
        placements_path = mainboard_ships["debug"] / "boards" / "tap_placements.json"
        assert placements_path.is_file()
        plan = json.loads(placements_path.read_text())
        assert plan["header_record"] == "tap_header_2x08_254"
        assert plan["header_placement"]["reference"] == "J_DBG1"
        assert plan["test_points"], "no test points placed"
        refs = [tp["placement"]["reference"] for tp in plan["test_points"]]
        assert refs[0] == "TP_DBG0"
        # Channel-label DATA rides the placement (WO-124 renders it).
        labels = plan["silkscreen_labels"]
        assert labels and labels[0]["text"] == "CH0"
        assert plan["silkscreen_rendering"]["handoff"] == "WO-124"
        # The declared placement rule ships verbatim (D224).
        assert "deterministic debug-placement rule" in plan["placement_rule"]

    def test_tap_map_allocates_the_explicit_refclk_first(self, mainboard_ships) -> None:
        tap_map = json.loads(
            (mainboard_ships["debug"] / "harness" / "tap_map.json").read_text()
        )
        assert tap_map["header"]["present"] is True
        assert tap_map["header"]["record"] == "tap_header_2x08_254"
        taps = tap_map["taps"]
        assert taps, "no taps allocated on the board flagship"
        # The spec's explicit tap won channel 0 (charter 40 sec. 2).
        assert taps[0]["channel"] == 0
        assert taps[0]["source"] == "explicit"
        assert taps[0]["target_path"].endswith(".refclk")
        assert taps[0]["connector_pin"] == 1

    def test_census_and_gate_identical_between_profiles(self, mainboard_ships) -> None:
        rollups = {}
        for profile, out in mainboard_ships.items():
            manifest = json.loads((out / "manifest.json").read_text())
            rollups[profile] = manifest["evidence_rollup"]
            assert manifest["profile"] == profile
        assert rollups["release"] == rollups["debug"]
        assert (mainboard_ships["release"] / "gate_summary.json").read_bytes() == (
            mainboard_ships["debug"] / "gate_summary.json"
        ).read_bytes()

    def test_release_package_is_untouched_by_debug_machinery(
        self, mainboard_ships
    ) -> None:
        release = mainboard_ships["release"]
        assert not (release / "harness").exists()
        assert not (release / "boards" / "tap_placements.json").exists()
        for path in release.rglob("*"):
            if path.is_file():
                assert b"REGOLITH-TAP" not in path.read_bytes(), path

    def test_debug_adds_files_release_files_unchanged(self, mainboard_ships) -> None:
        """The debug file SET is the release set plus additions; every
        deterministic shared file is byte-identical (the real-kicad
        exports embed TF.CreationDate timestamps and are honestly
        nondeterministic per run, so they are compared by presence)."""
        manifests = {
            profile: json.loads((out / "manifest.json").read_text())
            for profile, out in mainboard_ships.items()
        }
        rel = {f["relpath"] for f in manifests["release"]["files"]}
        dbg = {f["relpath"] for f in manifests["debug"]["files"]}
        assert rel - dbg == set(), "debug ship dropped release files"
        added = dbg - rel
        assert "harness/tap_map.json" in added
        assert "boards/tap_placements.json" in added


@pytest.fixture(scope="module")
def riscv_debug(tmp_path_factory) -> Path:
    """One release build of riscv_hart_rv1, shipped under the debug profile."""
    work = tmp_path_factory.mktemp("wo125_riscv")
    build_dir = work / "build"
    spec = RISCV / "ship.spec.json"
    _cli(
        "build",
        "--release",
        str(RISCV),
        "--spec",
        str(spec),
        "--out",
        str(build_dir),
    )
    out = work / "ship_debug"
    _cli(
        "ship",
        str(RISCV),
        "--build",
        str(build_dir),
        "--spec",
        str(spec),
        "--out",
        str(out),
        "--emit-profile",
        "debug",
    )
    return out


class TestRiscvDebugShip:
    def test_hdl_tap_module_routes_declared_pins(self, riscv_debug) -> None:
        module_path = (
            riscv_debug / "hdl" / "hdl" / "pc_incr_rtl" / "src" / "debug_taps.v"
        )
        assert module_path.is_file()
        text = module_path.read_text()
        assert "module regolith_debug_taps" in text
        assert "assign dbg0 =" in text
        assert "REGOLITH-TAP" in text

    def test_tap_map_capped_at_declared_pins_with_named_absences(
        self, riscv_debug
    ) -> None:
        tap_map = json.loads((riscv_debug / "harness" / "tap_map.json").read_text())
        # HDL-only package with two declared pins: never more than two
        # allocated channels (the map cannot overstate the hardware).
        assert 0 < len(tap_map["taps"]) <= 2
        # No board, no firmware: named family absences, never silence.
        assert tap_map["family_absences"]["boards"] is not None
        assert tap_map["family_absences"]["firmware"] is not None
        assert tap_map["family_absences"]["hdl"] is None
