"""WO-125 continuation tests: deliverables 3-7 (tap header record,
board/firmware/HDL augmentation, tap map, INV-32).

The ship-path integration tests monkeypatch `staged_build` exactly the
way `tests/backends/test_ship.py` does (the ship() contract is what is
under test, not the orchestrator); the record loader and candidate
extraction are tested against the REAL stdlib record and synthetic
payloads. The heavier real-CLI acceptance runs live in
`tests/test_wo125_debug_profile.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import regolith.backends.ship as ship_mod
from regolith._codes import TAP_MAP_DISAGREEMENT
from regolith._schema.models import (
    Claim,
    ClaimForm1,
    ClaimForm5,
    Form,
    Form4,
    Given,
    Obligation,
)
from regolith.backends.debug_taps import (
    ExplicitTap,
    Tap,
    TapSet,
    check_tap_agreement,
    load_tap_header_record,
    resolve_explicit_taps,
    tap_candidates_from_payload,
    tap_marker,
)
from regolith.backends.firmware import (
    FirmwareArtifact,
    FirmwareBackend,
    debug_taps_header,
)
from regolith.backends.framework import OutputFile
from regolith.backends.hdl import (
    HdlBackend,
    HdlBuildProducts,
    HdlSourceFile,
    debug_tap_module,
)
from regolith.orchestrator.lockfile import Lockfile
from regolith.orchestrator.orchestrate import BuildReport, StagedBuildReport
from regolith.orchestrator.tiers import BuildTier
from regolith.realizer.elec.debug_placement import derive_tap_placements
from regolith.realizer.elec.pinmux import PinAssignment, PinmuxResult
from regolith.realizer.firmware.contract import ClockDecl, FirmwareDesign
from regolith.realizer.firmware.realize import realize_firmware
from typani.result import Ok

REPO_ROOT = Path(__file__).resolve().parents[2]
STDLIB_ROOT = REPO_ROOT / "stdlib"


def _si_claim(name: str, net: str) -> Claim:
    return Claim(
        forall=[],
        form=ClaimForm1(
            form=Form.comparison,
            lhs=f"elec.impedance({net}, role=microstrip, stackup=s, "
            "layer=outer, w=0.36mm)",
            op="within",
            rhs="[45ohm, 55ohm]",
        ),
        hints=[],
        name=name,
    )


def _rms_claim(name: str, signal: str) -> Claim:
    return Claim(
        forall=[],
        form=ClaimForm5(
            band="[100kHz, 10MHz]",
            form=Form4.rms,
            op="<",
            rhs="30mV",
            signal=signal,
        ),
        hints=[],
        name=name,
    )


def _obligation(claim: Claim, subject_ref: str) -> dict:
    return Obligation(
        claim=claim,
        given=Given(materials=[], loads=[], backing=[], refs=[]),
        hints=[],
        subject_ref=subject_ref,
    ).model_dump(mode="json")


def _payload() -> dict:
    """A payload naming one clock net (SI), one bus net (SI), and one
    rail signal (rms over `v(out)`), across two scopes."""
    return {
        "snapshots": [
            {"hash": "h1", "scope": "CarrierSi"},
            {"hash": "h2", "scope": "Rail5V"},
        ],
        "obligations": [
            _obligation(_si_claim("refclk_z0", "refclk"), "h1"),
            _obligation(_si_claim("usb_z0", "usb_dp_dm"), "h1"),
            _obligation(_rms_claim("ripple", "v(out)"), "h2"),
        ],
    }


class TestTapHeaderRecord:
    # frob:tests python/regolith/backends/debug_taps.py::TapHeaderRecord.connector_pin kind="unit"
    # frob:tests python/regolith/backends/debug_taps.py::load_tap_header_record kind="unit"
    def test_loads_the_one_stdlib_record(self) -> None:
        result = load_tap_header_record(str(REPO_ROOT), (str(STDLIB_ROOT),))
        assert result.is_ok
        header = result.danger_ok
        assert header is not None
        assert header.key == "tap_header_2x08_254"
        assert header.channels == 8
        assert header.positions == 16
        # Signal-on-odd ordering: channel N rides pin 2N+1.
        assert header.connector_pin(0) == 1
        assert header.connector_pin(7) == 15
        assert header.reference  # cited like any std record (AD-37)

    def test_absence_is_ok_none(self, tmp_path) -> None:
        result = load_tap_header_record(str(tmp_path), ())
        assert result.is_ok
        assert result.danger_ok is None

    def test_two_records_is_a_loud_single_home_error(self, tmp_path) -> None:
        for name in ("a", "b"):
            pkg = tmp_path / f"pkg_{name}"
            (pkg / "records").mkdir(parents=True)
            (pkg / "magnetite.toml").write_text('[package]\nname = "x"\n')
            (pkg / "records" / "hdr.toml").write_text(
                f'[[component]]\nkey = "hdr_{name}"\nclass = "tap_header"\n'
                "channels = 4\npositions = 8\npitch_mm = 2.54\n"
                'connector = "c"\nordering = "o"\nground = "g"\nkeying = "k"\n'
            )
        result = load_tap_header_record(str(tmp_path), ())
        assert result.is_err
        assert result.danger_err.kind == "tap_header_record_duplicate"


class TestTapCandidates:
    # frob:tests python/regolith/backends/debug_taps.py::tap_candidates_from_payload kind="unit"
    def test_extracts_scoped_kinds_deterministically(self) -> None:
        candidates = tap_candidates_from_payload(_payload())
        paths = [(c.target_path, c.kind) for c in candidates]
        # rails < clocks < buses (charter 40 sec. 2), then target_path.
        assert paths == [
            ("Rail5V.out", "rail"),
            ("CarrierSi.refclk", "clock"),
            ("CarrierSi.usb_dp_dm", "bus"),
        ]

    def test_empty_payload_yields_no_candidates(self) -> None:
        assert tap_candidates_from_payload({}) == ()


class TestExplicitResolution:
    # frob:tests python/regolith/backends/debug_taps.py::resolve_explicit_taps kind="unit"
    def test_unique_suffix_resolves(self) -> None:
        candidates = tap_candidates_from_payload(_payload())
        resolved = resolve_explicit_taps(
            (ExplicitTap(target_path="refclk"),), candidates
        )
        assert resolved.is_ok
        assert resolved.danger_ok[0].target_path == "CarrierSi.refclk"

    def test_unknown_is_a_diagnostic(self) -> None:
        candidates = tap_candidates_from_payload(_payload())
        resolved = resolve_explicit_taps(
            (ExplicitTap(target_path="no_such_net"),), candidates
        )
        assert resolved.is_err
        assert resolved.danger_err.kind == "unknown_explicit_tap"

    def test_ambiguous_suffix_is_a_diagnostic(self) -> None:
        payload = _payload()
        payload["snapshots"].append({"hash": "h3", "scope": "OtherBoard"})
        payload["obligations"].append(
            _obligation(_si_claim("refclk2_z0", "refclk"), "h3")
        )
        candidates = tap_candidates_from_payload(payload)
        resolved = resolve_explicit_taps(
            (ExplicitTap(target_path="refclk"),), candidates
        )
        assert resolved.is_err
        assert resolved.danger_err.kind == "ambiguous_explicit_tap"


def _tap_set() -> TapSet:
    return TapSet(
        taps=(
            Tap(
                channel=0,
                kind="clock",
                target_path="CarrierSi.refclk",
                why="claim refclk_z0",
                source="explicit",
            ),
            Tap(
                channel=1,
                kind="rail",
                target_path="Rail5V.out",
                why="claim ripple",
                source="derived",
            ),
        )
    )


def _header():
    result = load_tap_header_record(str(REPO_ROOT), (str(STDLIB_ROOT),))
    header = result.danger_ok
    assert header is not None
    return header


class TestPlacements:
    # frob:tests python/regolith/realizer/elec/debug_placement.py::derive_tap_placements kind="unit"
    def test_places_header_and_labeled_test_points(self) -> None:
        plan = derive_tap_placements("MainboardMcu", _tap_set(), _header())
        assert plan.header_placement.reference == "J_DBG1"
        assert plan.header_record == "tap_header_2x08_254"
        assert [tp.placement.reference for tp in plan.test_points] == [
            "TP_DBG0",
            "TP_DBG1",
        ]
        # One silkscreen channel label per test point (WO-124 handoff DATA).
        assert [lbl.text for lbl in plan.silkscreen_labels] == ["CH0", "CH1"]
        assert all(lbl.layer == "F.Silkscreen" for lbl in plan.silkscreen_labels)
        # The declared placement rule ships verbatim (D224: a decision,
        # named as one).
        assert "deterministic debug-placement rule" in plan.placement_rule

    def test_deterministic(self) -> None:
        a = derive_tap_placements("s", _tap_set(), _header())
        b = derive_tap_placements("s", _tap_set(), _header())
        assert a.model_dump_json() == b.model_dump_json()


class TestFirmwareHeader:
    # frob:tests python/regolith/backends/debug_taps.py::tap_marker kind="unit"
    # frob:tests python/regolith/backends/firmware.py::debug_taps_header kind="unit"
    def test_table_rows_and_release_noop(self) -> None:
        text = debug_taps_header(_tap_set())
        assert "#ifdef REGOLITH_DEBUG_TAPS" in text
        assert tap_marker(0, "CarrierSi.refclk") in text
        assert tap_marker(1, "Rail5V.out") in text
        assert "#define REGOLITH_TAP_COUNT 2" in text
        # Release half: hooks compile to nothing.
        assert "#define REGOLITH_TRACE(ch, value) ((void)0)" in text
        assert text.isascii()


class TestHdlTapModule:
    # frob:tests python/regolith/backends/hdl.py::debug_tap_module kind="unit"
    def test_routes_declared_pins_in_channel_order(self) -> None:
        text = debug_tap_module(_tap_set(), ("dbg0", "dbg1"))
        assert tap_marker(0, "CarrierSi.refclk") in text
        assert "assign dbg0 = tap_ch0_CarrierSi_refclk;" in text
        assert "assign dbg1 = tap_ch1_Rail5V_out;" in text
        assert "NAMED ABSENCES" not in text

    def test_overflow_is_a_named_absence_never_silent(self) -> None:
        text = debug_tap_module(_tap_set(), ("dbg0",))
        assert "assign dbg0 = tap_ch0_CarrierSi_refclk;" in text
        assert "NAMED ABSENCES" in text
        assert "ch=1 target=Rail5V.out reason=no_spare_debug_pin" in text
        # The absence line is NOT an INV-32 marker (it must not claim
        # the tap exists in this artifact).
        assert tap_marker(1, "Rail5V.out") not in text


class TestInv32Check:
    def _map_bytes(self) -> bytes:
        return json.dumps(
            {
                "taps": [
                    {"channel": 0, "target_path": "CarrierSi.refclk"},
                    {"channel": 1, "target_path": "Rail5V.out"},
                ]
            }
        ).encode("ascii")

    # frob:tests python/regolith/backends/debug_taps.py::check_tap_agreement kind="unit"
    def test_agreement_holds(self) -> None:
        files = (
            OutputFile.of(
                "firmware/x/generated/debug_taps.h",
                debug_taps_header(_tap_set()).encode("ascii"),
            ),
        )
        assert check_tap_agreement(self._map_bytes(), files).is_ok

    def test_map_row_without_artifact_fails(self) -> None:
        files = (
            OutputFile.of(
                "hdl/x/src/debug_taps.v",
                debug_tap_module(_tap_set(), ("dbg0",)).encode("ascii"),
            ),
        )
        # channel 1 overflowed the single pin: it exists in the map but
        # in no artifact -> INV-32 must refuse.
        result = check_tap_agreement(self._map_bytes(), files)
        assert result.is_err
        assert result.danger_err.kind == TAP_MAP_DISAGREEMENT
        assert "Rail5V.out" in result.danger_err.message

    def test_forged_artifact_tap_fails(self) -> None:
        files = (
            OutputFile.of(
                "firmware/x/generated/debug_taps.h",
                debug_taps_header(_tap_set()).encode("ascii"),
            ),
            OutputFile.of(
                "hdl/x/src/rogue.v",
                f"// {tap_marker(9, 'Nowhere.net')}\n".encode("ascii"),
            ),
        )
        result = check_tap_agreement(self._map_bytes(), files)
        assert result.is_err
        assert "Nowhere.net" in result.danger_err.message

    def test_binary_artifacts_are_skipped(self) -> None:
        files = (
            OutputFile.of(
                "firmware/x/generated/debug_taps.h",
                debug_taps_header(_tap_set()).encode("ascii"),
            ),
            OutputFile.of("3d/blob.glb", b"\x00\xff\xfe binary"),
        )
        assert check_tap_agreement(self._map_bytes(), files).is_ok


def _clean_report(payload: dict | None = None) -> StagedBuildReport:
    final = BuildReport(
        tier=BuildTier.RELEASE,
        ok=True,
        release_ok=True,
        payload_json=json.dumps(payload) if payload is not None else "",
    )
    return StagedBuildReport(final=final, iterations=1, realized_inputs=())


def _firmware_artifact() -> FirmwareArtifact:
    design = FirmwareDesign(
        name="fw",
        family="stm32g0",
        pinmux=PinmuxResult(
            assignments=(
                PinAssignment.caused(
                    flow="u_mcu.uart2.tx", instance="uart2.tx", pin="PA9"
                ),
            )
        ),
        events=(),
        clocks=(
            ClockDecl(name="sysclk", freq_hz=48_000_000, cause="planner(clock sysclk)"),
        ),
        partitions=(),
    )
    tree = realize_firmware(design).danger_ok
    return FirmwareArtifact(tree=tree)


class TestShipDebugProfile:
    def _ship(self, tmp_path, out_name, **kwargs):
        return ship_mod.ship(
            (str(tmp_path),),
            kwargs.pop("backends"),
            str(tmp_path / out_name),
            lockfile=Lockfile(tool_version="0.1.0"),
            **kwargs,
        )

    @staticmethod
    def _patch_stdlib(monkeypatch) -> None:
        """Point the debug preparation's record walk at the repo stdlib
        (a tmp_path project has no magnetite.toml, so the ordinary
        resolver honestly finds nothing)."""
        monkeypatch.setattr(
            ship_mod,
            "resolve_record_search_paths",
            lambda root: (str(STDLIB_ROOT),),
        )

    def test_debug_ship_emits_tap_map_and_firmware_table(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report(_payload()))
        )
        self._patch_stdlib(monkeypatch)
        result = self._ship(
            tmp_path,
            "out",
            backends={"firmware": FirmwareBackend()},
            firmware={"fw": _firmware_artifact()},
            profile="debug",
            debug_spec={"taps": ["refclk"]},
        )
        assert result.is_ok
        manifest = result.danger_ok
        assert manifest.profile == "debug"
        relpaths = {f.relpath for f in manifest.files}
        assert "harness/tap_map.json" in relpaths
        assert "firmware/firmware/fw/generated/debug_taps.h" in relpaths
        tap_map = json.loads(
            (tmp_path / "out" / "harness" / "tap_map.json").read_text()
        )
        assert tap_map["header"]["record"] == "tap_header_2x08_254"
        # The explicit tap won channel 0.
        assert tap_map["taps"][0]["target_path"] == "CarrierSi.refclk"
        assert tap_map["taps"][0]["source"] == "explicit"
        assert tap_map["taps"][0]["connector_pin"] == 1
        # Named family absences for what this package does not carry.
        assert tap_map["family_absences"]["boards"] is not None
        assert tap_map["family_absences"]["firmware"] is None
        index = (tmp_path / "out" / "index.md").read_text()
        assert "harness/: present" in index

    def test_release_ship_is_untouched_and_debug_only_adds(
        self, tmp_path, monkeypatch
    ) -> None:
        """Release byte-identity: the debug profile only ADDS files;
        every release-profile file is byte-identical in both packages
        except the index/manifest/ledgers that enumerate the additions."""
        monkeypatch.setattr(
            ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report(_payload()))
        )
        self._patch_stdlib(monkeypatch)
        release = self._ship(
            tmp_path,
            "rel",
            backends={"firmware": FirmwareBackend()},
            firmware={"fw": _firmware_artifact()},
        )
        debug = self._ship(
            tmp_path,
            "dbg",
            backends={"firmware": FirmwareBackend()},
            firmware={"fw": _firmware_artifact()},
            profile="debug",
        )
        assert release.is_ok and debug.is_ok
        rel_files = {f.relpath: f.sha256 for f in release.danger_ok.files}
        dbg_files = {f.relpath: f.sha256 for f in debug.danger_ok.files}
        added = set(dbg_files) - set(rel_files)
        # WO-126: the debug ship's `harness/` family now carries the
        # WO-125 tap map plus its expected-signal/bring-up siblings
        # (this fixture's synthetic report yields zero results, so the
        # calc book -- and every provenance ref -- is honestly skipped,
        # logged by `_build_calc_book`; every tap-kind group it
        # allocates still gets its own capture config).
        assert added == {
            "harness/tap_map.json",
            "harness/expected_signals.json",
            "harness/bringup.md",
            "harness/capture_rails.sigrok-cli",
            "harness/capture_clocks.sigrok-cli",
            "harness/capture_buses.sigrok-cli",
            "firmware/firmware/fw/generated/debug_taps.h",
        }
        # WO-130: `artifact_index.json` enumerates the SAME emitted set
        # `index.md` does (one row per file, including the debug-only
        # rows `added` above names) -- it legitimately differs between
        # the two profiles for the same reason `index.md` already does.
        enumerating = {"index.md", "artifact_index.json"}
        for relpath, digest in rel_files.items():
            if relpath in enumerating:
                continue
            assert dbg_files[relpath] == digest, relpath
        # Verdict/census math untouched (D206/D220.1): the rollup and
        # gate summary are byte-equal between the two profiles.
        assert release.danger_ok.evidence_rollup == debug.danger_ok.evidence_rollup
        assert (tmp_path / "rel" / "gate_summary.json").read_bytes() == (
            tmp_path / "dbg" / "gate_summary.json"
        ).read_bytes()
        # No marker/map leaks into the release package.
        assert "harness/tap_map.json" not in rel_files
        for path in (tmp_path / "rel").rglob("*"):
            if path.is_file():
                assert b"REGOLITH-TAP" not in path.read_bytes(), path

    def test_debug_ship_is_deterministic_per_profile(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report(_payload()))
        )
        self._patch_stdlib(monkeypatch)
        runs = []
        for name in ("d1", "d2"):
            result = self._ship(
                tmp_path,
                name,
                backends={"firmware": FirmwareBackend()},
                firmware={"fw": _firmware_artifact()},
                profile="debug",
                debug_spec={"taps": ["refclk"]},
            )
            assert result.is_ok
            runs.append({f.relpath: f.sha256 for f in result.danger_ok.files})
        assert runs[0] == runs[1]

    def test_hdl_only_capacity_is_capped_at_declared_pins(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report(_payload()))
        )
        self._patch_stdlib(monkeypatch)
        products = HdlBuildProducts(
            sources=(HdlSourceFile(filename="top.v", content=b"module top;"),)
        )
        result = self._ship(
            tmp_path,
            "out",
            backends={"hdl": HdlBackend()},
            hdl={"rtl": products},
            profile="debug",
            debug_spec={"hdl_debug_pins": {"rtl": ["dbg0", "dbg1"]}},
        )
        assert result.is_ok
        tap_map = json.loads(
            (tmp_path / "out" / "harness" / "tap_map.json").read_text()
        )
        # 3 candidates but only 2 declared pins: capacity capped so the
        # map never overstates the hardware (charter 40 sec. 5), the
        # third candidate is a named unallocated row, and INV-32 holds.
        assert len(tap_map["taps"]) == 2
        assert len(tap_map["unallocated"]) == 1
        relpaths = {f.relpath for f in result.danger_ok.files}
        assert "hdl/hdl/rtl/src/debug_taps.v" in relpaths

    def test_no_augmentable_family_allocates_zero_honestly(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report(_payload()))
        )
        self._patch_stdlib(monkeypatch)
        result = self._ship(tmp_path, "out", backends={}, profile="debug")
        assert result.is_ok
        tap_map = json.loads(
            (tmp_path / "out" / "harness" / "tap_map.json").read_text()
        )
        assert tap_map["taps"] == []
        assert len(tap_map["unallocated"]) == 3
        assert "no augmentable artifact family" in tap_map["capacity"]["why"]

    def test_unknown_explicit_tap_refuses_the_ship(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report(_payload()))
        )
        self._patch_stdlib(monkeypatch)
        result = self._ship(
            tmp_path,
            "out",
            backends={"firmware": FirmwareBackend()},
            firmware={"fw": _firmware_artifact()},
            profile="debug",
            debug_spec={"taps": ["not_a_net"]},
        )
        assert result.is_err
        assert result.danger_err.kind == "unknown_explicit_tap"
        assert not (tmp_path / "out" / "manifest.json").exists()

    def test_release_ship_ignores_debug_spec(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            ship_mod, "staged_build", lambda *a, **k: Ok(_clean_report(_payload()))
        )
        self._patch_stdlib(monkeypatch)
        result = self._ship(
            tmp_path,
            "out",
            backends={"firmware": FirmwareBackend()},
            firmware={"fw": _firmware_artifact()},
            debug_spec={"taps": ["not_a_net"]},  # would refuse a debug ship
        )
        assert result.is_ok
        relpaths = {f.relpath for f in result.danger_ok.files}
        assert "harness/tap_map.json" not in relpaths
