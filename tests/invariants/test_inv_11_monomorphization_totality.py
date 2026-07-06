"""INV-11 Monomorphization totality (regolith/13-invariants.md).

Ledger statement:
    **Every static check runs at every instantiation point of every
    discrete domain (integers, enums, variants).**

Mechanism provided by: WO-05 (typed generic use-site instantiations) +
WO-19 (`regolith-lower` monomorphization). This module is part of the
WO-17 invariant suite: the implementation's contract with the spec. A
spec change that alters INV-11's proof argument must change this module
in the same commit.

End-to-end: WO-05 now types generic USE-sites (`Pair<M3>` ->
`InstExpr`/`GenericArgs`, disambiguated from claim comparisons `a < b`),
and `regolith-lower` expands each generic declaration over its distinct
instantiations. Two totality guards fall out of the proof argument and
are observed here through the facade payload:

  * an instantiation whose arity does not match its declaration is an
    un-expandable point -- a per-point-only failure that must fail the
    build (E0504); and
  * a generic declared and referenced nowhere is a dead generic with an
    empty monomorphization point-set (E0503).
"""

from __future__ import annotations

import json

from regolith import compiler

# INV-11 diagnostic codes (regolith-diag `Family::Instances`).
_GENERIC_ARITY_MISMATCH = {"family": "instances", "offset": 4}  # E0504
_DEAD_GENERIC = {"family": "instances", "offset": 3}  # E0503


def _codes(payload: dict) -> list[dict]:
    return [d["code"] for d in payload["diagnostics"]]


def test_inv_11_arity_mismatch_is_a_per_point_failure(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A generic instantiated at the wrong arity is an un-expandable
    monomorphization point: the build must fail at that point (E0504),
    the deliberate INV-11 per-point-only violation."""
    src = "interface Pair<a, b>:\n    x: 1\npart plain:\n    p = Pair<M3>()\n"
    path = tmp_path / "mono.hem"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    assert _GENERIC_ARITY_MISMATCH in _codes(payload), (
        "an arity-mismatched instantiation must fail the build (INV-11): "
        f"{payload['diagnostics']}"
    )


def test_inv_11_dead_generic_has_empty_point_set(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A generic declared but never instantiated has no monomorphization
    point and is reported as a dead generic (E0503)."""
    src = "interface Dead<z>:\n    y: 1\npart plain:\n    q: 2\n"
    path = tmp_path / "dead.hem"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    assert _DEAD_GENERIC in _codes(payload), (
        f"a never-instantiated generic must be flagged dead: {payload['diagnostics']}"
    )


def test_inv_11_matching_arity_instantiation_is_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The negative control: an instantiation whose arity matches its
    declaration expands cleanly -- no monomorphization diagnostic."""
    src = (
        "interface One<a>:\n    x: 1\n"
        "part plain:\n    p = One<M3>()\n    r = One<M3>()\n"
    )
    path = tmp_path / "ok.hem"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    codes = _codes(payload)
    assert _GENERIC_ARITY_MISMATCH not in codes, codes
    assert _DEAD_GENERIC not in codes, codes
