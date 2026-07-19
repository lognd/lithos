"""WO-87 acceptance: board entity population + rule-eval registry
dereference (D198), over the REAL pipeline.

The five std.board_correctness packs quantify over domains
(`power_pins`/`config_straps`/`exposed_connectors`/`crystals`/
`critical_nets`) that the WO-87 lowering pass now populates from a
`board` decl's declared topology, classified through the
`registry.records` realized-input payload. This suite pins the WO's
acceptance criteria:

1. the hazard board trips >= 1 rule in EVERY family, correctly
   attributed to the offending entity;
2. the fixed twin renders zero diagnostics (its residue is honest
   realized-tier deferral obligations, never firings);
3. std.elec.patterns.decoupling un-blocks through the SAME machinery
   (Net entities + the derived undecoupled count), no special-casing;
4. the mainboard_mx flagship's release surface forms and evaluates
   board-correctness obligations (previously never-formed);
5. the payload kind string matches the Rust reader's constant.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from regolith import compiler
from regolith.magnetite.records_payload import (
    REGISTRY_RECORDS_KIND,
    registry_records_payload,
)

_log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
_PACKS = str(REPO_ROOT / "stdlib" / "std.board_correctness")
_HAZARD = str(REPO_ROOT / "examples" / "negative" / "66_board_correctness_hazard.cupr")
_FIXED = str(
    REPO_ROOT / "examples" / "tracks" / "cuprite" / "board_correctness_fixed.cupr"
)

#: The five wave-1 families (charter 36 sec. 2) by pack name.
_FAMILIES = (
    "pdn_decoupling",
    "bringup_config",
    "interface_protection",
    "clock_discipline",
    "dft_test_points",
)


def _records_input() -> compiler.RealizedInput:
    payload = registry_records_payload((str(REPO_ROOT / "stdlib"),))
    assert payload is not None, "stdlib component records must serialize"
    digest, kind, subject, payload_bytes = payload
    return compiler.RealizedInput(
        digest=digest, kind=kind, subject=subject, payload_bytes=payload_bytes
    )


def _check(*roots: str) -> dict[str, Any]:
    result = compiler.check(tuple(roots), realized_inputs=(_records_input(),))
    assert result.is_ok, f"check returned Err: {result}"
    return json.loads(result.danger_ok.payload_json)


def test_payload_kind_matches_the_rust_reader() -> None:
    """The kind string is spelled in exactly two places -- the Python
    serializer and the Rust reader -- and this test pins both to the
    D198-ratified value (drift would silently drop the payload)."""
    assert REGISTRY_RECORDS_KIND == "registry.records"
    rust_reader = (
        REPO_ROOT / "crates" / "regolith-lower" / "src" / "registry.rs"
    ).read_text(encoding="ascii")
    assert 'REGISTRY_RECORDS_KIND: &str = "registry.records"' in rust_reader


def test_hazard_board_trips_every_family_with_attribution() -> None:
    """WO-87 acceptance 1: >= 1 E0601 violation per family, attributed
    to the entity that carries the hazard."""
    payload = _check(_PACKS, _HAZARD)
    messages = [
        d["message"]
        for d in payload["diagnostics"]
        if "violated" in d["message"] or "advises against" in d["message"]
    ]
    _log.info("hazard firings: %d", len(messages))
    for family in _FAMILIES:
        fired = [m for m in messages if f"`{family}." in m]
        assert fired, f"family {family} fired no rule: {messages}"

    joined = "\n".join(messages)
    # Attribution spot-checks: the offending ENTITY is named.
    assert "`pdn_decoupling.shunt_cap_presence` violated on `u1.dvdd`" in joined
    assert "`bringup_config.strap_not_floating` violated on `qspi_ss`" in joined
    assert "`interface_protection.esd_on_exposed_connector` violated on `j1`" in joined
    # The clock family fires through the rule-eval registry dereference
    # (`x.cl` resolves via the crystal record's cl_pf): 6pF vs 18pF-1pF.
    assert "`clock_discipline.crystal_load_cap_lower` violated on `x1`" in joined
    assert "6pF >= 17pF" in joined
    assert "`dft_test_points.test_point_on_critical_net` violated on `v3v3`" in joined


def test_fixed_twin_renders_zero_diagnostics() -> None:
    """WO-87 acceptance 1 (the other half): the corrected twin fires
    nothing; its only residue is honest realized-tier deferral
    obligations (cap distance, probe clearance, the .where filter)."""
    payload = _check(_PACKS, _FIXED)
    assert payload["diagnostics"] == [], payload["diagnostics"]
    deferred = {
        o["claim"]["name"]
        for o in payload["obligations"]
    }
    assert deferred == {
        "erc(pdn_decoupling.shunt_cap_placement)",
        "erc(interface_protection.vbus_inrush_protection)",
        "erc(dft_test_points.test_point_probe_clearance)",
    }, deferred


def test_decoupling_pattern_unblocks_through_the_same_pass(tmp_path: Path) -> None:
    """WO-87 acceptance: std.elec.patterns.decoupling (the jlc_2l-noted
    gap) evaluates over the SAME pass-populated Net entities -- an
    undecoupled power pin fires the advise, a decoupled one is clean.
    No board-correctness special-casing anywhere in the path."""
    board = tmp_path / "undecoupled.cupr"
    board.write_text(
        "board UndecoupledBoard:\n"
        "    stage review: process=pcb_fab(std.elec.patterns)\n"
        "    then:\n"
        "        u1 = vendor(rp2040)\n"
        "    nets:\n"
        "        v3v3: (u1.iovdd,)\n",
        encoding="ascii",
    )
    pack = str(REPO_ROOT / "stdlib" / "std.elec.patterns" / "decoupling.cupr")
    payload = _check(pack, str(board))
    fired = [
        d["message"]
        for d in payload["diagnostics"]
        if "std.elec.patterns.decoupling_shape" in d["message"]
    ]
    assert fired and "`v3v3`" in fired[0], payload["diagnostics"]

    fixed = tmp_path / "decoupled.cupr"
    fixed.write_text(
        "board DecoupledBoard:\n"
        "    stage review: process=pcb_fab(std.elec.patterns)\n"
        "    then:\n"
        "        u1 = vendor(rp2040)\n"
        "        c1 = vendor(cap_100nf_x7r_0402)\n"
        "    nets:\n"
        "        v3v3: (u1.iovdd, c1.p1)\n",
        encoding="ascii",
    )
    payload = _check(pack, str(fixed))
    assert payload["diagnostics"] == [], payload["diagnostics"]


def test_mainboard_mx_forms_and_evaluates_board_correctness() -> None:
    """WO-87 acceptance 2: the flagship carrier board's obligations
    move from never-formed (0 before this WO) to formed-and-evaluated:
    the two honest realized-tier deferrals form, and no family fires a
    violation (the flagship's declared bring-up hardware is correct)."""
    payload = _check(str(REPO_ROOT / "examples" / "flagships" / "mainboard_mx"), _PACKS)
    names = [o["claim"]["name"] for o in payload["obligations"]]
    bc = [n for n in names if any(f"({f}." in n for f in _FAMILIES)]
    assert bc, f"no board-correctness obligation formed: {names}"
    violations = [
        d["message"]
        for d in payload["diagnostics"]
        if "violated" in d["message"]
    ]
    assert violations == [], violations


def test_board_alone_without_records_stays_honest() -> None:
    """No payload -> record-classified domains stay empty and nothing
    is invented: the hazard board alone (no packs, no records) compiles
    clean, exactly the pre-WO-87 posture for an unattached board."""
    result = compiler.check((_HAZARD,))
    assert result.is_ok
    payload = json.loads(result.danger_ok.payload_json)
    assert payload["diagnostics"] == [], payload["diagnostics"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
