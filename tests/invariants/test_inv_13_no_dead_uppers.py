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

from regolith import compiler
from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.conformance import CLAIM_KIND_UPPER


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


def test_inv_13_primary_violation() -> None:
    """INV-13 discharge half: a spec contradicted by its hand-written impl
    must FAIL equivalence, while a conforming impl discharges.

    This exercises the Python harness equivalence model (AD-1,
    ``harness.models.conformance``): given an UPPER contract (the spec's
    demanded bound, carried as the request ``limit``) and a LOWER
    realization (the impl's declared bound), it checks the impl is a sound
    REFINEMENT -- a bound no weaker than the spec's. The end-to-end
    obligation->request bridge (resolving the ``conforms`` claim form's
    two windows into a :class:`DischargeRequest`) is orchestrator
    territory and stays a tracked gap; the compiler-side emission is
    covered by test_inv_13_impl_binding_emits_a_conformance_obligation.
    Here we drive the harness discharge pipeline directly on both a
    conforming and a contradicting realization.

    Fixture (an upper-bound spec promise, e.g. mass/ripple/stress
    ``Q <= 20``):
    - a conforming impl promises the tighter ``Q <= 14`` -> discharged;
    - a contradicting impl promises only ``Q <= 25`` (a wider window than
      the spec, i.e. LESS than it promised) -> violated, not a silent pass.
    """
    registry = default_registry()

    def _conformance(impl_bound: float, spec_bound: float) -> str:
        request = DischargeRequest(
            claim_kind=CLAIM_KIND_UPPER,
            limit=spec_bound,
            inputs={"impl_bound": Interval.point(impl_bound)},
        )
        return registry.discharge(request).status.value

    # A conforming realization discharges the conformance obligation.
    assert _conformance(impl_bound=14.0, spec_bound=20.0) == "discharged"

    # A realization that contradicts its spec FAILS equivalence (INV-13):
    # a violated evidence value, never a silent pass or indeterminate.
    assert _conformance(impl_bound=25.0, spec_bound=20.0) == "violated"
