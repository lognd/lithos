"""INV-12 Waiver honesty (substrate/13-invariants.md).

Ledger statement:
    **A waiver never alters evidence status; its match set is
    lockfile-recorded; a waiver matching nothing is an error.**

Mechanism provided by: WO-13 (the ledger schema) + WO-19 (the
`regolith-lower` waiver pass that matches declared `waive` blocks
against the emitted obligations). This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-12's proof argument must change this module in
the same commit.

The waiver ladder now lands end-to-end: `regolith-lower::waivers`
parses every in-source `waive ...:` block, matches it against the
obligation set, and records it on the ledger surfaced in
`payload.ledger`. Two ends of the honesty guarantee are exercised
here as real fixtures through `compiler.check`:

  * HONEST PASS -- a waiver that matches a real claim obligation
    appears on the ledger as waived-with-reason (its `basis` and the
    accepted obligation hash), never as a silent clean pass.
  * DELIBERATE VIOLATION -- a waiver whose target matches nothing the
    pipeline emits is a stale-waiver error (E0701) naming it, so a
    waiver can never quietly exist without a live target.

The match-set-GROWTH half of INV-12 (an unscoped waiver silently
absorbing a *new* failure, surfaced in the lockfile diff) needs the
lockfile materialization that is orchestrator/WO-14 territory; it is
recorded as the remaining INV-12 surface in TODO.md sec. 5 and is not
constructible from the static core alone.
"""

from __future__ import annotations

import json
import os

from regolith import compiler

_STALE_WAIVER = {"family": "evidence", "offset": 1}


def _payload(tmp_path, src: str) -> dict:  # type: ignore[no-untyped-def]
    path = tmp_path / "a.hem"
    path.write_text(src, encoding="ascii")
    out = compiler.check((os.fspath(path),))
    assert out.is_ok, f"check returned Err: {out}"
    return json.loads(out.danger_ok.payload_json)


def test_inv_12_a_matched_waiver_is_recorded_with_its_reason(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Honest pass: a waiver over a live claim appears on the ledger as
    waived-with-reason with its accepted obligation, not as a clean
    pass, and raises no diagnostic."""
    src = (
        "part bracket:\n"
        "    require Strength:\n"
        "        yield: >= 200\n"
        "    waive Strength.yield on self:\n"
        '        basis: "prototype lot only, EV-31"\n'
    )
    payload = _payload(tmp_path, src)

    waived = [e["waived"] for e in payload["ledger"]["entries"] if "waived" in e]
    assert len(waived) == 1, "the waiver must be recorded on the ledger"
    record = waived[0]
    assert record["kind"] == "matched"
    assert record["waiver"]["basis"] == "prototype lot only, EV-31"
    assert record["matched"], "the accepted obligation hash is recorded"
    # The waiver surfaces its reason; it never silences the diagnostics.
    assert not payload["diagnostics"], "a matching waiver is clean but audited"


def test_inv_12_a_waiver_matching_nothing_is_an_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Deliberate violation: a waiver whose claim target matches no
    emitted obligation is a stale-waiver error (E0701) naming it -- a
    waiver cannot quietly exist without a live target."""
    src = (
        "part bracket:\n"
        "    require Strength:\n"
        "        yield: >= 200\n"
        "    waive Strength.ghost on self:\n"
        '        basis: "targets a claim that does not exist"\n'
    )
    payload = _payload(tmp_path, src)

    stale = [d for d in payload["diagnostics"] if d["code"] == _STALE_WAIVER]
    assert len(stale) == 1, "a stale waiver must be a diagnostic"
    assert "Strength.ghost" in stale[0]["message"], "the diagnostic names the target"
