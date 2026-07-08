"""INV-4 Symmetry soundness (regolith/13-invariants.md).

Ledger statement:
    **Entity-DB symmetry is under-approximate: a false symmetry is never
    asserted. Orbit-based discharge extension is legal only when the
    obligation's givens are invariant under the orbit's group.**

Mechanism provided by: WO-07 (`SymmetryGroup`/`OrbitTable`) + WO-05
(typed symmetry statements) + WO-19 (`regolith-lower` orbit-contribution
population). This module is part of the WO-17 invariant suite: the
implementation's contract with the spec. A spec change that alters
INV-4's proof argument must change this module in the same commit.

End-to-end: WO-05 now types `pattern`/`break`/`any` statements, and
`regolith-lower` (`ownership.rs`) folds each `pattern` contribution into
an `OrbitTable` (conservative intersection, WO-07) and collapses it on a
`break`. Extending a per-instance result across an orbit (`any`) is legal
only when a declared, non-trivial group licenses it; over a broken or
undeclared orbit the extension is unsound (E0502), observed through the
facade payload.

Scope note (honest residual): the givens-invariance half of the ledger
(a symmetric bolt circle under an ASYMMETRIC LOAD must refuse verify-one)
is the discharging model's check and lives in the Python harness (AD-1),
out of WO-05/19's scope. What is real here is the orbit-soundness gate:
`any` over a collapsed/absent orbit is refused.

Fluid analogue (WO-32 deliverable 6): fluorite's `flow_imbalance(orbit)`
claim form (fluorite/03 sec. 3) states the identical INV-4 requirement
-- a symmetric manifold with asymmetric feed must not license
verify-one -- but fluorite has no `pattern`/`break`/`any` orbit
vocabulary at all, so there is no static hook here to test against;
`examples/negative/44_fluo_asymmetric_feed_verify_one.fluo` documents
the same honest residual as an `EXPECT-TODO: INV-4` corpus fixture
(same shape as `23_asymmetric_givens_verify_one.hema` above) rather
than a passing test, since the check is model/solver (feldspar)
territory for the fluid track too.
"""

from __future__ import annotations

import json

from regolith import compiler

# INV-4 diagnostic code (regolith-diag `Family::Instances`).
_BROKEN_ORBIT_ANY = {"family": "instances", "offset": 2}  # E0502


def _codes(payload: dict) -> list[dict]:
    return [d["code"] for d in payload["diagnostics"]]


def test_inv_04_any_over_a_broken_orbit_is_unsound(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The deliberate INV-4 violation: a `pattern` declares a cyclic
    orbit, a `break` collapses it, and then `any ring` still tries to
    extend a per-instance result across the (now trivial) orbit. This
    must be refused (E0502) -- a false symmetry is never asserted."""
    src = "part p:\n    pattern ring circular 4\n    break ring\n    any ring\n"
    path = tmp_path / "sym.hema"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    assert _BROKEN_ORBIT_ANY in _codes(payload), (
        "extending across a broken orbit must be refused (INV-4): "
        f"{payload['diagnostics']}"
    )


def test_inv_04_any_over_a_live_pattern_orbit_is_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The honest negative control: a declared, non-trivial cyclic orbit
    licenses the orbit extension -- no soundness diagnostic."""
    src = "part p:\n    pattern ring circular 4\n    any ring\n"
    path = tmp_path / "sym_ok.hema"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    assert _BROKEN_ORBIT_ANY not in _codes(payload), payload["diagnostics"]


def test_inv_04_any_with_no_declared_pattern_is_unsound(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A second violation channel: `any` with no pattern declaring an
    orbit has only singletons to extend over -- refused (E0502)."""
    src = "part p:\n    any ring\n"
    path = tmp_path / "sym_none.hema"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    assert _BROKEN_ORBIT_ANY in _codes(payload), payload["diagnostics"]
