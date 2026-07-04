"""INV-1 Evidence binding (substrate/13-invariants.md).

Ledger statement:
    **Every evidence item is bound to the exact obligation it discharged.**
    Mechanism: obligations are content-addressed over (claim, subject
    snapshot, givens, registry record hashes, model-registry version);
    evidence is keyed by obligation hash.

Mechanism provided by: WO-13 (obligation content-addressing) + WO-19
(the `regolith-lower` pipeline that actually produces obligations over
real sources). This module is part of the WO-17 invariant suite: the
implementation's contract with the spec. A spec change that alters
INV-1's proof argument must change this module in the same commit.

Ledger test: "mutate each key component; assert cache miss."

STATUS (checked live during WO-19 wiring, cycle 12): the full fixture
needs two things not present yet --
  1. `Obligation::content_hash` (the real content-addressed key) is
     not exposed on the JSON payload surface (WO-19 STATUS: schema
     surface refresh did not carry it out to `_schema`/facade). This
     suite uses a stable sha256-of-canonical-JSON proxy instead
     (`tests/golden/_util.obligation_keys`) -- good enough to assert
     *stability*, not to reproduce the real hash function.
  2. A live "mutate one key component, expect a different key"
     probe was attempted against `examples/cubesat` (perturbing a
     boundary literal referenced by an obligation's `given`) and
     produced NO obligation-key change: WO-19's value-source
     lowering is recorded PARTIAL (`resolutions=0` over the whole
     corpus), so boundary/claim values are not yet threaded into the
     obligation `given`/`claim` records the pipeline emits. The
     mutation-sensitivity half of INV-1 is therefore not yet
     constructible from a real fixture; it needs WO-19's residual
     grammar (value-source lowering) or a WO-13-level unit fixture
     that exercises `Obligation::content_hash` directly (out of
     scope here -- Rust logic, not test wiring).

What IS asserted below: obligation keys are present, non-empty, and
stable across independent builds of the same source (the identity
half of the guarantee -- no source edit is even required to observe
whether the key wobbles).
"""

from __future__ import annotations

import json

from regolith import compiler

from tests.golden import _util


def test_inv_01_obligation_keys_present_and_stable() -> None:
    """Obligation keys exist and do not wobble across independent
    builds of identical input (the identity/stability half of INV-1;
    see module docstring for the mutation-sensitivity half that is
    not yet constructible from a real fixture)."""
    first = compiler.check(("examples/cubesat",)).danger_ok
    second = compiler.check(("examples/cubesat",)).danger_ok

    first_keys = _util.obligation_keys(json.loads(first.payload_json))
    second_keys = _util.obligation_keys(json.loads(second.payload_json))

    assert first_keys, "expected at least one obligation over examples/cubesat"
    assert first_keys == second_keys


def test_inv_01_mutating_a_key_component_changes_the_key(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Ledger test: mutate a key component (the governing material, part
    of the obligation's `given:`) and assert a different obligation key
    -- a cache miss. WO-19 BE-2 threads structured materials/loads into
    `given`, so two otherwise-identical claims governed by different
    materials now hash differently (end-to-end through the facade)."""
    template = (
        "part bracket:\n    material: {mat}\n"
        "    require Strength:\n        yield: >= 200\n"
    )
    a = tmp_path / "a.hem"
    a.write_text(template.format(mat="AL7075_T6"), encoding="ascii")
    b = tmp_path / "b.hem"
    b.write_text(template.format(mat="TI64"), encoding="ascii")

    keys_a = _util.obligation_keys(
        json.loads(compiler.check((str(a),)).danger_ok.payload_json)
    )
    keys_b = _util.obligation_keys(
        json.loads(compiler.check((str(b),)).danger_ok.payload_json)
    )

    assert keys_a, "expected at least one obligation"
    assert keys_a != keys_b, (
        "mutating the governing material must change the obligation key "
        "(INV-1 mutation-sensitivity via given:)"
    )
