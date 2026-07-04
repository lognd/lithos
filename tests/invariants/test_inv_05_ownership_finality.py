"""INV-5 Ownership finality (substrate/13-invariants.md).

Ledger statement:
    **Single ownership and borrow verdicts hold on the realized artifact.**

Mechanism provided by: WO-09 (`BorrowTable`) + WO-05 (typed ownership
statements) + WO-19 (`regolith-lower` predicted-delta population). This
module is part of the WO-17 invariant suite: the implementation's
contract with the spec. A spec change that alters INV-5's proof argument
must change this module in the same commit.

End-to-end: WO-05 now types `bind`/`modify` statements, and
`regolith-lower` (`ownership.rs`) constructs a per-scope `BorrowTable`
and `PredictedDelta.modifies` from that parsed source. A role binding is
a permanent borrow; a later feature modifying the borrowed entity is a
borrow conflict, reported bidirectionally (E0302, SEAM-1), observed here
through the facade payload.
"""

from __future__ import annotations

import json

from regolith import compiler

# INV-5 diagnostic code (regolith-diag `Family::References`).
_BORROW_CONFLICT = {"family": "references", "offset": 2}  # E0302


def _codes(payload: dict) -> list[dict]:
    return [d["code"] for d in payload["diagnostics"]]


def test_inv_05_modify_of_a_bound_entity_is_a_conflict(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The deliberate INV-5 violation: a role binding holds a permanent
    borrow on `seat`; a later `modify seat` transfers ownership out from
    under the borrow. This must fail as a borrow conflict, reported at
    BOTH ends (the modifier and the borrower)."""
    src = "part p:\n    bind seat\n    modify seat\n"
    path = tmp_path / "own.hem"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    conflicts = [c for c in _codes(payload) if c == _BORROW_CONFLICT]
    assert len(conflicts) == 2, (
        "a modify of a borrowed entity must be caught bidirectionally "
        f"(INV-5): {payload['diagnostics']}"
    )


def test_inv_05_modify_of_an_unbound_entity_is_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The honest negative control: modifying an entity nobody borrowed
    is legal -- no borrow conflict."""
    src = "part p:\n    bind seat\n    modify hub\n"
    path = tmp_path / "own_ok.hem"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    assert _BORROW_CONFLICT not in _codes(payload), payload["diagnostics"]
