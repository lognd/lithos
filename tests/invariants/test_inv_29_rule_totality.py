"""INV-29 Rule totality (regolith/13-invariants.md).

Ledger statement:
    **No attached rule is silently skipped or loosened.**

Mechanism provided by: WO-28 (the rule-pack engine --
`regolith-lower/src/rule_engine.rs` evaluation, `rules.rs` E0601/E0602/
E0603 checks, `entities.rs` resolves:/E0604, `claims.rs` rule
obligations). This module is part of the WO-17 invariant suite: a spec
change that alters INV-29's proof argument must change this module in
the same commit.

Four prongs, each a real fixture through ``compiler.check``:

  * HONEST PASS -- a satisfied attached rule reports nothing (no
    diagnostic, no rule obligation): passing is passing.
  * VIOLATION IS LOUD AND WAIVABLE -- the violated twin yields E0601
    with `pack.rule` provenance AND a lowered obligation whose claim
    name is the waive-target spelling.
  * COLLISION, NEVER SHADOWING -- two rules of one qualified name are
    E0602 data, not a priority pick.
  * DEFERRAL IS VISIBLE -- a rule over a domain the static tier cannot
    evaluate becomes an indeterminate obligation naming the blocker,
    never a vacuous pass (the release gate sees it, INV-24).

Loosening-impossible rides INV-2's mechanism: the waive prong asserts
the obligation set is byte-identical with and without the waiver.
"""

from __future__ import annotations

import json
import logging
import os

from regolith import compiler

_log = logging.getLogger(__name__)

_RULE_VIOLATION = {"family": "rule_packs", "offset": 1}
_RULE_COLLISION = {"family": "rule_packs", "offset": 2}

_PACK = """process press_shop:
    capability:
        min_bend_ratio: 1.6
    dfm:
        rule min_bend_radius:
            forall b in bends
            demand: b.radius >= capability.min_bend_ratio * sheet
            why: "press pack minimum inside radius"
"""

_PART_OK = """part bracket:
    stage cut: process=laser_cut(sheet=1.5mm)
    stage formed: process=press_shop, from=cut
        flange = Bend(edge=cut.top, angle=90deg, radius=3mm)
"""

_PART_BAD = _PART_OK.replace("radius=3mm", "radius=1mm")


def _payload(tmp_path, name: str, src: str) -> dict:  # type: ignore[no-untyped-def]
    path = tmp_path / name
    path.write_text(src, encoding="ascii")
    out = compiler.check((os.fspath(path),))
    assert out.is_ok, f"check returned Err: {out}"
    payload = json.loads(out.danger_ok.payload_json)
    _log.info("%s: %d diagnostics", name, len(payload["diagnostics"]))
    return payload


def _rule_obligations(payload: dict) -> list[dict]:
    return [
        ob
        for ob in payload["obligations"]
        if (ob["claim"].get("name") or "").startswith(("dfm(", "drc(", "erc("))
    ]


def test_satisfied_rule_is_a_silent_pass(tmp_path) -> None:  # type: ignore[no-untyped-def]
    payload = _payload(tmp_path, "ok.hema", _PACK + _PART_OK)
    assert payload["diagnostics"] == [], payload["diagnostics"]
    assert _rule_obligations(payload) == []


def test_violation_is_e0601_and_a_waivable_obligation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    payload = _payload(tmp_path, "bad.hema", _PACK + _PART_BAD)
    codes = [d["code"] for d in payload["diagnostics"]]
    assert _RULE_VIOLATION in codes, codes
    (violation,) = [
        d for d in payload["diagnostics"] if d["code"] == _RULE_VIOLATION
    ]
    assert "press_shop.min_bend_radius" in violation["message"]
    assert "press pack minimum inside radius" in violation["message"], (
        "the why: text IS the explanation"
    )
    (obligation,) = _rule_obligations(payload)
    assert obligation["claim"]["name"] == "dfm(press_shop.min_bend_radius)", (
        "the obligation's claim name is the waive-target spelling"
    )


def test_name_collision_is_e0602_not_a_shadowing_pick(tmp_path) -> None:  # type: ignore[no-untyped-def]
    twice = _PACK + "        rule min_bend_radius:\n            demand: true\n"
    payload = _payload(tmp_path, "dup.hema", twice + _PART_OK)
    codes = [d["code"] for d in payload["diagnostics"]]
    assert _RULE_COLLISION in codes, codes


def test_unevaluable_rule_defers_as_a_named_obligation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pack = (
        "process fab2l:\n"
        "    erc:\n"
        "        rule fanout:\n"
        "            forall n in nets\n"
        "            demand: n.load_current <= n.drive_current\n"
    )
    board = "part ctrl:\n    stage bare: process=pcb_fab(fab2l)\n"
    payload = _payload(tmp_path, "defer.cupr", pack + board)
    assert payload["diagnostics"] == [], payload["diagnostics"]
    (obligation,) = _rule_obligations(payload)
    assert obligation["claim"]["name"] == "erc(fab2l.fanout)"
    refs = obligation["given"]["refs"]
    assert any("nets" in detail for _, detail in refs), (
        f"the deferral names its blocked domain: {refs}"
    )


def test_waiving_a_violated_rule_never_alters_the_obligation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    waive = (
        "    waive dfm(press_shop.min_bend_radius) on formed.flange:\n"
        '        basis: "prototype lot, EV-31"\n'
    )
    with_waive = _payload(tmp_path, "waived.hema", _PACK + _PART_BAD + waive)
    without = _payload(tmp_path, "unwaived.hema", _PACK + _PART_BAD)
    assert _rule_obligations(with_waive) == _rule_obligations(without), (
        "a waiver adds an acceptance record; it never rewrites the "
        "obligation (INV-2 carrying INV-29's loosening-impossible half)"
    )
