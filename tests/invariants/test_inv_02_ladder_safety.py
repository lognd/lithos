"""INV-2 Ladder safety (regolith/13-invariants.md).

Ledger statement:
    **No override mechanism converts `violated` into `discharged`.**

Mechanism provided by: WO-13 (the acceptance-record ledger) + WO-19
(the `regolith-lower` waiver pass). This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-2's proof argument must change this module in
the same commit.

Rung 7 (`waive`) now lands end-to-end. The safety property is
realized structurally: a waiver only ever produces a *waived* ledger
record referencing the matched obligations' content hashes; the
waiver pass never touches the obligation or evidence set, and the
record carries NO status field -- so no waiver can convert `violated`
into `discharged`. Two ends are exercised as real fixtures through
`compiler.check`:

  * HONEST PASS -- declaring a waiver leaves the obligation set
    byte-identical to the same source without it (the waiver adds only
    an acceptance record; it changes no verdict).
  * OVERREACH CAUGHT -- an unjustified concession (a `waive` with no
    mandatory `basis:`) is itself a diagnostic (E0702) and is NOT
    recorded as an acceptance.

The re-keying half of INV-2 (a rung 1/2/4/5 override re-keys the
obligation, so stale evidence stops applying) reduces to INV-1 and is
covered in test_inv_01_evidence_binding; here the same mechanism makes
a waiver keyed to a re-keyed claim go stale (INV-12) rather than
silently persist.
"""

from __future__ import annotations

import json
import os

from regolith import compiler

from tests.golden import _util

_MISSING_BASIS = {"family": "evidence", "offset": 2}


def _payload(tmp_path, name: str, src: str) -> dict:  # type: ignore[no-untyped-def]
    path = tmp_path / name
    path.write_text(src, encoding="ascii")
    out = compiler.check((os.fspath(path),))
    assert out.is_ok, f"check returned Err: {out}"
    return json.loads(out.danger_ok.payload_json)


def test_inv_02_a_waiver_never_alters_the_obligation_set(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Honest pass: a waiver adds an acceptance record but changes no
    obligation -- the obligation keys and every evidence status are
    identical with and without the `waive` block, so nothing the waiver
    does can flip a verdict (the load-bearing 'never violated ->
    discharged' guarantee)."""
    body = "part bracket:\n    require Strength:\n        yield: >= 200\n"
    waiver = (
        '    waive Strength.yield on self:\n        basis: "accepted risk, EV-31"\n'
    )

    without = _payload(tmp_path, "without.hema", body)
    with_waiver = _payload(tmp_path, "with.hema", body + waiver)

    # The waiver records an acceptance...
    waived = [e for e in with_waiver["ledger"]["entries"] if "waived" in e]
    assert len(waived) == 1
    assert "status" not in json.dumps(waived[0]), (
        "an acceptance record must carry no verdict field (INV-2)"
    )

    # ...but the obligation set and evidence are untouched by it.
    assert _util.obligation_keys(with_waiver) == _util.obligation_keys(without), (
        "declaring a waiver must not re-key or drop any obligation"
    )
    assert with_waiver["evidence"] == without["evidence"], (
        "a waiver must not alter any evidence status (no violated -> discharged)"
    )


def test_inv_02_an_unjustified_waiver_is_an_overreach_diagnostic(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Overreach caught: a `waive` with no mandatory `basis:` is an
    unjustified concession -- an E0702 diagnostic, never a silent
    acceptance."""
    src = (
        "part bracket:\n"
        "    require Strength:\n"
        "        yield: >= 200\n"
        "    waive Strength.yield on self:\n"
        "        note: 1\n"
    )
    payload = _payload(tmp_path, "overreach.hema", src)

    overreach = [d for d in payload["diagnostics"] if d["code"] == _MISSING_BASIS]
    assert len(overreach) == 1, "a basis-less waiver must be rejected"
    # The overreaching waiver is not accepted onto the ledger.
    waived = [e for e in payload["ledger"]["entries"] if "waived" in e]
    assert not waived, "a rejected waiver is never recorded as an acceptance"
