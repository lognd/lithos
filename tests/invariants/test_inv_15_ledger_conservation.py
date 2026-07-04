"""INV-15 Ledger conservation (substrate/13-invariants.md).

Ledger statement:
    **Every conservation ledger (DOF, sketch DOF, driver/load,
    domain-crossing, flow, intent-realization, terminal) is a complete
    accounting: declared items sum against a declared free set, and
    nothing participates outside the ledger.**

Mechanism provided by: WO-11 (regolith-sem profile DOF ledger, the walk
half) + WO-12 (contract IR flow ledger) + WO-19 (`regolith-lower`
system-node population). This module is part of the WO-17 invariant
suite: the implementation's contract with the spec. A spec change that
alters INV-15's proof argument must change this module in the same
commit.

End-to-end: `regolith-lower` builds a `SystemNode` per `system` decl with
its `flows:` edges and the declared flow participants (its `intents:`,
`boundary:`, and `reserves:` names). The system-flow ledger requires
every flow endpoint to be a declared participant -- nothing participates
outside the ledger; a flow to or from an undeclared endpoint is a
conservation leak, `E0420`, observed through the facade payload.

Scope note (honest residual): the DOF/Gruebler half of INV-15 lives in
`regolith-sem` `profile` and is unit-tested there
(`profile::unit_tests::deliberate_imbalance_is_caught`); what is
exercised end-to-end here is the system-flow ledger's completeness gate.
"""

from __future__ import annotations

import json

from regolith import compiler

# INV-15 flow-ledger imbalance code (regolith-diag `Family::Contracts`,
# E0420).
_LEDGER_IMBALANCE = {"family": "contracts", "offset": 20}


def _codes(payload: dict) -> list[dict]:
    return [d["code"] for d in payload["diagnostics"]]


def _check(src: str, tmp_path) -> dict:  # type: ignore[no-untyped-def]
    path = tmp_path / "sys.cupr"
    path.write_text(src, encoding="ascii")
    return json.loads(compiler.check((str(path),)).danger_ok.payload_json)


def test_inv_15_flow_to_undeclared_endpoint_leaks(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The deliberate INV-15 violation: a flow targets `ghost`, which no
    intent/boundary/reserve declares -- participation outside the flow
    ledger, E0420."""
    src = (
        "system Sys:\n"
        "    intents:\n"
        "        sense: sense(x)\n"
        "        decide: compute(y)\n"
        "    flows:\n"
        "        sense -> decide\n"
        "        decide -> ghost\n"
    )
    payload = _check(src, tmp_path)
    assert _LEDGER_IMBALANCE in _codes(payload), (
        "a flow endpoint outside the declared participant set must leak "
        f"(INV-15): {payload['diagnostics']}"
    )


def test_inv_15_flows_between_declared_endpoints_are_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The honest negative control: every flow endpoint is a declared
    intent -- the ledger is complete, no imbalance."""
    src = (
        "system Sys:\n"
        "    intents:\n"
        "        sense: sense(x)\n"
        "        decide: compute(y)\n"
        "    flows:\n"
        "        sense -> decide\n"
    )
    payload = _check(src, tmp_path)
    assert _LEDGER_IMBALANCE not in _codes(payload), payload["diagnostics"]
