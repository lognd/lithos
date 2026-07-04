"""INV-7 Boundary subsumption (substrate/13-invariants.md).

Ledger statement:
    **Evidence transfers into any context whose boundary is contained in
    the proven one.**

Mechanism provided by: WO-12 (contract IR `SystemNode` + boundary
envelopes) + WO-19 (`regolith-lower` system-node population). This module
is part of the WO-17 invariant suite: the implementation's contract with
the spec. A spec change that alters INV-7's proof argument must change
this module in the same commit.

End-to-end: `regolith-lower` builds a `SystemNode` per `system` decl with
its `boundary:` envelope, links each child artifact named in its `parts:`
block to that child's proven boundary, and requires -- for every shared
boundary quantity -- the enclosing envelope to be CONTAINED in the
child's proven one (substrate/04 sec. 6: containment is uniformly the
safe direction; boundary entries are tolerated envelopes). A wider
enclosing envelope means the child would be used outside what it was
proven under: E0407, observed through the facade payload.

Scope note (honest residual): envelopes are interval-compared only when
both endpoints parse to numbers in the SAME unit spelling (the unit table
is a documented WO-05/12 cut). An incomparable pair is left
indeterminate -- INV-7 never assumes a containment it cannot prove.
"""

from __future__ import annotations

import json

from regolith import compiler

# INV-7 diagnostic code (regolith-diag `Family::Contracts`, E0407).
_BOUNDARY_NOT_SUBSUMED = {"family": "contracts", "offset": 7}


def _codes(payload: dict) -> list[dict]:
    return [d["code"] for d in payload["diagnostics"]]


def _check(src: str, tmp_path) -> dict:  # type: ignore[no-untyped-def]
    path = tmp_path / "sys.cupr"
    path.write_text(src, encoding="ascii")
    return json.loads(compiler.check((str(path),)).danger_ok.payload_json)


def test_inv_07_enclosing_envelope_wider_than_child_fails(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The deliberate INV-7 violation: the enclosing system's ambient
    envelope is WIDER than the child artifact's proven envelope, so its
    evidence cannot transfer -- E0407 naming both."""
    src = (
        "system Imu:\n"
        "    boundary:\n"
        "        ambient: [-10degC, 50degC]\n"
        "\n"
        "system Outer:\n"
        "    parts:\n"
        "        imu: Imu\n"
        "    boundary:\n"
        "        ambient: [-40degC, 85degC]\n"
    )
    payload = _check(src, tmp_path)
    assert _BOUNDARY_NOT_SUBSUMED in _codes(payload), (
        "an enclosing boundary wider than a child's proven envelope must "
        f"fail L2 (INV-7): {payload['diagnostics']}"
    )


def test_inv_07_enclosing_envelope_within_child_is_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The honest negative control: the enclosing envelope is contained
    in the child's proven one -- evidence transfers, no diagnostic."""
    src = (
        "system Imu:\n"
        "    boundary:\n"
        "        ambient: [-40degC, 85degC]\n"
        "\n"
        "system Outer:\n"
        "    parts:\n"
        "        imu: Imu\n"
        "    boundary:\n"
        "        ambient: [0degC, 40degC]\n"
    )
    payload = _check(src, tmp_path)
    assert _BOUNDARY_NOT_SUBSUMED not in _codes(payload), payload["diagnostics"]
