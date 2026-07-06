"""INV-8 Target additivity (regolith/13-invariants.md).

Ledger statement:
    **Contract-level base evidence is always valid under a target;
    realization-level base evidence is reused only when the base
    realization is unchanged.**

Mechanism provided by: WO-12 (contract IR targets + reserves) + WO-19
(`regolith-lower` target/reserve population). This module is part of the
WO-17 invariant suite: the implementation's contract with the spec. A
spec change that alters INV-8's proof argument must change this module in
the same commit.

End-to-end: a `target X of Sys` decl is lowered to a `Target` whose
`draws:` sub-entries quantify how much of each declared `reserves:`
set-aside it consumes. `regolith-lower` sums every target's draws per
reserve against the base's declared reserve; a sum over the reserve is
over-allocation -- `E0432`-family, naming the target (regolith/04
sec. 6, rule 2: "Exceeding a reserve is E0432-family, naming the
target"), observed through the facade payload.

Scope note (honest residual): the realization-level half of INV-8 (a
target whose routing crosses a base region invalidates exactly the
touched subjects via content addressing) is the discharge/region model's
job; what is exercised here is the additive reserve-accounting gate that
INV-8 rule 2 names. Nominal `draws: reserves` with no quantified draw is
left unchecked -- the gate bites only on over-allocation it can prove.
"""

from __future__ import annotations

import json

from regolith import compiler

# INV-8 over-allocation code (regolith-diag `Family::Contracts`, E0432).
_RESERVE_OVER_ALLOCATED = {"family": "contracts", "offset": 32}


def _codes(payload: dict) -> list[dict]:
    return [d["code"] for d in payload["diagnostics"]]


def _check(src: str, tmp_path) -> dict:  # type: ignore[no-untyped-def]
    path = tmp_path / "sys.cupr"
    path.write_text(src, encoding="ascii")
    return json.loads(compiler.check((str(path),)).danger_ok.payload_json)


def test_inv_08_target_over_drawing_a_reserve_fails(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The deliberate INV-8 violation: a debug target draws more GPIO
    than the base reserved -- an over-allocation, E0432 naming it."""
    src = (
        "system Sys:\n"
        "    reserves:\n"
        "        gpio: 4\n"
        "\n"
        "target debug of Sys:\n"
        "    draws:\n"
        "        gpio: 5\n"
    )
    payload = _check(src, tmp_path)
    assert _RESERVE_OVER_ALLOCATED in _codes(payload), (
        "a target drawing beyond a declared reserve must fail (INV-8): "
        f"{payload['diagnostics']}"
    )


def test_inv_08_target_within_reserve_is_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The honest negative control: the target's draws stay within the
    reserve -- additive overlay, no over-allocation."""
    src = (
        "system Sys:\n"
        "    reserves:\n"
        "        gpio: 4\n"
        "\n"
        "target debug of Sys:\n"
        "    draws:\n"
        "        gpio: 3\n"
    )
    payload = _check(src, tmp_path)
    assert _RESERVE_OVER_ALLOCATED not in _codes(payload), payload["diagnostics"]
