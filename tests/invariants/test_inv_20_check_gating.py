"""INV-20 Check gating (regolith/13-invariants.md).

Ledger statement:
    **Nothing expensive runs until everything cheaper has passed for the

Mechanism provided by: WO-15. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-20's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-15) lands (STUB WO-17).
"""

from __future__ import annotations

import json

from regolith import compiler


def test_inv_20_poisoned_subject_is_gated_but_clean_sibling_is_not(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """INV-20 per-subject gating (AD-17): a subject with a parse error
    produces zero later-pass records (no snapshot, no obligation) while
    a clean sibling checks normally. WO-19 gates on the attributed
    `SubjectError` (`parse:0193`) CST node the parser now emits.

    Fixture: `bad` has an in-body malformation (a stray `)`), `good`
    is clean. The pipeline must exclude exactly `bad` and complete for
    `good` (the WO-19/INV-20 acceptance criterion, observed end-to-end
    through the facade payload)."""
    src = (
        "part bad:\n    )\n    require R:\n        s: >= 1\n"
        "part good:\n    require R:\n        s: >= 1\n"
    )
    path = tmp_path / "gate.hem"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    scopes = {record["scope"] for record in payload["snapshots"]}

    assert "good" in scopes, "a clean sibling must still check"
    assert "bad" not in scopes, (
        "a subject with a parse error must produce zero later-pass "
        "records (INV-20 gating)"
    )
