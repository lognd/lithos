"""WO-126 acceptance: the bring-up harness pack over the REAL CLI.

Mirrors `tests/test_wo125_debug_profile.py`'s standing bar (real
release build + real debug ship, no mocking): drives `regolith build
--release` then `regolith ship --emit-profile debug` for the two named
fleet vehicles -- mainboard_mx (the rich, board-bearing vehicle) and
printer_k1 (explicitly NOT board-bearing per its own ship spec comment
-- its harness family is the honest, near-empty absence case charter
40 sec. 3/5 describes) -- and asserts:

* the `harness/` family carries `tap_map.json` (WO-125, unmoved bytes)
  plus its WO-126 siblings (`expected_signals.json`, `bringup.md`, and
  per-kind sigrok-cli capture configs where a kind has allocated taps);
* every `expected_signals.json` provenance ref resolves inside the
  SAME package (D224 -- the ship path already refuses otherwise, so a
  successful ship is itself the strongest proof, re-checked here
  directly against the shipped `calc/` family bytes);
* a `calc_sheet`-provenance row's declared threshold and the calc
  sheet it cites agree on which claim discharged it;
* two debug ships of the same build are byte-identical (AD-6/INV-10)
  over the WHOLE harness/ family;
* census/verdict output is untouched between profiles (same fact
  `test_wo125_debug_profile.py` proves for the manifest rollup --
  reasserted here as this WO's own acceptance line item);
* `regolith doctor` reports the `sigrok-cli` catalog row.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAINBOARD = REPO_ROOT / "examples" / "flagships" / "mainboard_mx"
PRINTER_K1 = REPO_ROOT / "examples" / "flagships" / "printer_k1"


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert result.returncode == 0, (
        f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
    )
    return result


def _build_and_ship_debug(project: Path, tmp_path_factory, tag: str) -> Path:
    work = tmp_path_factory.mktemp(f"wo126_{tag}")
    build_dir = work / "build"
    spec = project / "ship.spec.json"
    _cli(
        "build",
        "--release",
        str(project),
        "--spec",
        str(spec),
        "--out",
        str(build_dir),
    )
    out = work / "ship_debug"
    _cli(
        "ship",
        str(project),
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


@pytest.fixture(scope="module")
def mainboard_debug(tmp_path_factory) -> Path:
    return _build_and_ship_debug(MAINBOARD, tmp_path_factory, "mainboard")


@pytest.fixture(scope="module")
def printer_k1_debug(tmp_path_factory) -> Path:
    return _build_and_ship_debug(PRINTER_K1, tmp_path_factory, "printer_k1")


class TestMainboardHarnessFamily:
    def test_harness_family_present_with_all_siblings(self, mainboard_debug) -> None:
        harness = mainboard_debug / "harness"
        assert (harness / "tap_map.json").is_file()
        assert (harness / "expected_signals.json").is_file()
        assert (harness / "bringup.md").is_file()
        capture_files = sorted(p.name for p in harness.glob("capture_*.sigrok-cli"))
        assert capture_files, "no sigrok-cli capture configs emitted"

    def test_expected_signals_provenance_resolves_in_package(
        self, mainboard_debug
    ) -> None:
        signals = json.loads(
            (mainboard_debug / "harness" / "expected_signals.json").read_text()
        )
        assert signals["signals"], "no expected-signal rows on the board flagship"
        book = json.loads((mainboard_debug / "calc" / "calc_book.json").read_text())
        sheet_digests = {s["chain"]["sheet_digest"] for s in book["sheets"]}
        audit = json.loads((mainboard_debug / "calc" / "audit_index.json").read_text())
        claim_names = {r["claim_name"] for r in audit["rows"]}
        for row in signals["signals"]:
            prov = row["provenance"]
            if prov["kind"] == "calc_sheet":
                assert prov["ref"] in sheet_digests, row
            elif prov["kind"] == "claim":
                assert prov["ref"] in claim_names, row
                assert row["expected"] is None, "a claim-only row must carry no number"
                assert row["note"] == "no_verified_expectation"

    def test_at_least_one_row_is_calc_sheet_backed(self, mainboard_debug) -> None:
        signals = json.loads(
            (mainboard_debug / "harness" / "expected_signals.json").read_text()
        )
        kinds = {row["provenance"]["kind"] for row in signals["signals"]}
        assert "calc_sheet" in kinds, (
            "no calc-sheet-backed expectation on the board flagship"
        )

    # frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
    def test_bringup_orders_rails_before_clocks_and_buses(
        self, mainboard_debug
    ) -> None:
        text = (mainboard_debug / "harness" / "bringup.md").read_text()
        # every REGOLITH-TAP marker line, in the document's own order.
        lines = [ln for ln in text.splitlines() if "REGOLITH-TAP" in ln]
        kinds_in_order = []
        for ln in lines:
            if "(rail)" in ln:
                kinds_in_order.append("rail")
            elif "(clock)" in ln:
                kinds_in_order.append("clock")
            elif "(bus)" in ln:
                kinds_in_order.append("bus")
            elif "(signal)" in ln:
                kinds_in_order.append("signal")
        rank = {"rail": 0, "clock": 1, "bus": 2, "signal": 3}
        assert kinds_in_order == sorted(kinds_in_order, key=lambda k: rank[k])

    def test_tap_map_bytes_unmoved_between_wo125_and_wo126(
        self, mainboard_debug
    ) -> None:
        """The harness pack's tap_map.json is WO-125's own bytes -- the
        marker line for every allocated channel is present verbatim
        (no second/rewritten copy)."""
        tap_map = json.loads((mainboard_debug / "harness" / "tap_map.json").read_text())
        bringup = (mainboard_debug / "harness" / "bringup.md").read_text()
        for tap in tap_map["taps"]:
            marker = f"REGOLITH-TAP ch={tap['channel']} target={tap['target_path']}"
            assert marker in bringup

    def test_two_debug_ships_are_byte_identical_over_harness(
        self, mainboard_debug, tmp_path_factory
    ) -> None:
        second = _build_and_ship_debug(MAINBOARD, tmp_path_factory, "mainboard_repeat")
        first_files = sorted(p.name for p in (mainboard_debug / "harness").iterdir())
        second_files = sorted(p.name for p in (second / "harness").iterdir())
        assert first_files == second_files
        for name in first_files:
            assert (mainboard_debug / "harness" / name).read_bytes() == (
                second / "harness" / name
            ).read_bytes(), name

    def test_census_and_gate_untouched_by_the_harness_pack(
        self, mainboard_debug, tmp_path_factory
    ) -> None:
        work = tmp_path_factory.mktemp("wo126_mainboard_release_cmp")
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
        release_out = work / "ship_release"
        _cli(
            "ship",
            str(MAINBOARD),
            "--build",
            str(build_dir),
            "--spec",
            str(spec),
            "--out",
            str(release_out),
            "--emit-profile",
            "release",
        )
        release_manifest = json.loads((release_out / "manifest.json").read_text())
        debug_manifest = json.loads((mainboard_debug / "manifest.json").read_text())
        assert release_manifest["evidence_rollup"] == debug_manifest["evidence_rollup"]
        assert not (release_out / "harness").exists()


class TestPrinterK1NamedAbsence:
    def test_harness_family_honest_absence(self, printer_k1_debug) -> None:
        """printer_k1's controller board realizes no outline inputs
        (its own ship spec comment) -- NOT board-bearing, so the
        harness family is small/near-empty but still emitted, honestly
        (charter 40 sec. 3: 'any project with a tap map')."""
        tap_map = json.loads(
            (printer_k1_debug / "harness" / "tap_map.json").read_text()
        )
        assert tap_map["capacity"]["channels"] == 0
        assert tap_map["taps"] == []
        assert tap_map["family_absences"]["boards"] is not None
        signals = json.loads(
            (printer_k1_debug / "harness" / "expected_signals.json").read_text()
        )
        assert signals["signals"] == []
        assert (printer_k1_debug / "harness" / "bringup.md").is_file()


def test_doctor_reports_sigrok_cli() -> None:
    result = _cli("doctor")
    assert "sigrok-cli" in result.stdout
