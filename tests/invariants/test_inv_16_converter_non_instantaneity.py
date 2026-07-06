"""INV-16 Converter non-instantaneity (regolith/13-invariants.md).

Ledger statement:
    **No algebraic loop crosses the continuous/discrete boundary.**

Mechanism: `regolith_sem::converter` builds the continuous/discrete
converter graph, applies the ZOH delta-by-type rule, and runs the
within-domain acyclicity check (E0105). WO-05 now types the elec
behavioral bodies (`ports:`/`spec:` blocks, converter/combinational
assignments, and clocked `on <event>:` bodies with `<=` register
updates), and `regolith-lower` (`converter.rs`) feeds those typed nodes
into the graph as a real pass over `.cupr` source.

This module is part of the WO-17 invariant suite: the implementation's
contract with the spec. A spec change that alters INV-16's proof
argument must change this module in the same commit.

End-to-end: a genuine same-domain combinational loop is refused (E0105);
a loop broken by a converter port (comparator sampling the plant, dac
driving it) or a clocked `<=` register is legal -- the delta interrupts
the cycle, so no algebraic loop crosses the boundary. Observed through
the facade payload.

Scope note (honest residual, a tracked cut): the continuous DAE
derivative relations (`x ' = ...`) remain `OpaqueIsland`, so they
contribute no edge. This is sound (the check is under-approximate): a
derivative is an integrator delta, never an algebraic edge, so omitting
it can only miss a would-be cycle, never manufacture a false one.
"""

from __future__ import annotations

import json

from regolith import compiler

# INV-16 diagnostic code (regolith-diag `Family::Parse`).
_COMBINATIONAL_CYCLE = {"family": "parse", "offset": 5}  # E0105


def _codes(payload: dict) -> list[dict]:
    return [d["code"] for d in payload["diagnostics"]]


def _check(src: str, path) -> dict:  # type: ignore[no-untyped-def]
    path.write_text(src, encoding="ascii")
    return json.loads(compiler.check((str(path),)).danger_ok.payload_json)


def test_inv_16_primary_violation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The deliberate INV-16 violation: a genuine algebraic loop entirely
    within one domain (`a = b`, `b = a`, both instantaneous `=`) with no
    converter or register to break it. Must be refused (E0105)."""
    src = "block BadLoop:\n    spec:\n        a = b\n        b = a\n"
    payload = _check(src, tmp_path / "badloop.cupr")
    assert _COMBINATIONAL_CYCLE in _codes(payload), (
        "a same-domain algebraic loop must be refused (INV-16): "
        f"{payload['diagnostics']}"
    )


def test_inv_16_comparator_feeds_own_threshold_is_legal(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The honest legal fixture: the comparator-feeds-own-threshold loop
    (`vout -> cmp -> threshold -> drive -> vout`) closes through two
    converter ports (a comparator sampling the continuous plant, a dac
    driving it), so the loop is broken by a ZOH delta -- combinationally
    acyclic, no diagnostic."""
    src = (
        "block Regulator:\n"
        "    ports:\n"
        "        ctrl_clk: clock(200kHz)\n"
        "    spec:\n"
        "        cmp = comparator(vout, sample=ctrl_clk.rise)\n"
        "        on ctrl_clk.rise:\n"
        "            threshold = cmp\n"
        "        drive = dac(threshold, update=ctrl_clk.rise)\n"
        "        vout = drive\n"
    )
    payload = _check(src, tmp_path / "regulator.cupr")
    assert _COMBINATIONAL_CYCLE not in _codes(payload), payload["diagnostics"]


def test_inv_16_register_broken_loop_is_legal(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A second legal channel: a loop broken by a clocked non-blocking
    `<=` register (`a = b` combinational, `b <= a` register). The register
    commit is a delta, so the combinational subgraph is acyclic."""
    src = (
        "block RegLoop:\n"
        "    ports:\n"
        "        clk: clock(1MHz)\n"
        "    spec:\n"
        "        on clk.rise:\n"
        "            a = b\n"
        "            b <= a\n"
    )
    payload = _check(src, tmp_path / "regloop.cupr")
    assert _COMBINATIONAL_CYCLE not in _codes(payload), payload["diagnostics"]
