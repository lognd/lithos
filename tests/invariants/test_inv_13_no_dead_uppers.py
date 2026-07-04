"""INV-13 No dead uppers (substrate/13-invariants.md).

Ledger statement:
    **When both an upper contract and a lower realization are written, a

Mechanism provided by: WO-12. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-13's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-12) lands (STUB WO-17).
"""

from __future__ import annotations

import json

import pytest
from rockhead import compiler


def test_inv_13_impl_binding_emits_a_conformance_obligation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """INV-13 mechanism (compiler side): when an upper contract and a
    lower realization are both written (`impl Seat for self`), a
    conformance obligation is emitted by construction. WO-19 BE-6 wires
    the impl/extern/import edges into obligations; this exercises it
    end-to-end through the facade.

    The complementary "must FAIL equivalence" half (a spec contradicted
    by its hand-written impl) is discharge -- harness/Python territory
    per AD-1 -- and is out of the compiler-lowering scope this test
    covers; here we assert the obligation EXISTS (INV-13's "a
    conformance obligation exists between them")."""
    src = (
        "interface Seat:\n    x: 1\n"
        "part bracket:\n    impl Seat for self:\n        y: 1\n"
    )
    path = tmp_path / "conform.hem"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    forms = [ob["claim"]["form"] for ob in payload["obligations"]]
    assert any(f.get("op") == "conforms" and f.get("lhs") == "Seat" for f in forms), (
        f"expected a conformance obligation for `impl Seat`, got {forms}"
    )


@pytest.mark.xfail(
    reason=(
        "INV-13 discharge half (a spec contradicted by its hand-written "
        "impl must FAIL equivalence) needs the Python harness equivalence "
        "model (AD-1), not yet wired. The compiler-side mechanism (a "
        "conformance obligation is EMITTED by construction) is now green "
        "-- see test_inv_13_impl_binding_emits_a_conformance_obligation."
    ),
    strict=True,
)
def test_inv_13_primary_violation() -> None:
    """Deliberate INV-13 violation must FAIL equivalence once the harness
    equivalence model lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-13 deliberate-violation discharge needs the "
        "Python harness equivalence model"
    )
