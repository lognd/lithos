"""INV-13 No dead uppers (regolith/13-invariants.md).

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
from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.tiers import BuildTier


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


def _conformance_status(impl_bound: str, tmp_path, name: str) -> list[str]:  # type: ignore[no-untyped-def]
    """Build a real `impl Seat for self` fixture and return its statuses.

    Drives the FULL pipeline (compiler -> obligation->DischargeRequest
    bridge -> harness conformance model), so the conformance obligation is
    a REAL lowered obligation, not a hand-built request.
    """
    src = (
        "interface Seat:\n"
        "    q: <= 20\n"
        "part bracket:\n"
        "    impl Seat for self:\n"
        f"        q: {impl_bound}\n"
    )
    path = tmp_path / name
    path.write_text(src, encoding="ascii")
    report = build((str(path),), BuildTier.BUILD).danger_ok
    return [r.evidence.status.value for r in report.results if r.evidence]


def test_inv_13_primary_violation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """INV-13 discharge half: a spec contradicted by its hand-written impl
    must FAIL equivalence, while a conforming impl discharges.

    This now rides a REAL lowered conformance obligation end-to-end through
    the orchestrator bridge (AD-1): the compiler emits the `conforms`
    obligation and threads the upper contract's (`q <= 20`) and lower
    realization's comparator bounds into `given.loads`; the bridge
    (`orchestrator.translate`) lowers those two windows into the harness
    conformance model's :class:`DischargeRequest` (limit = the spec bound,
    input = the impl bound), which checks the impl is a sound REFINEMENT --
    a bound no weaker than the spec's.

    Fixture (an upper-bound spec promise ``q <= 20``):
    - a conforming impl promises the tighter ``q <= 14`` -> discharged;
    - a contradicting impl promises only ``q <= 25`` (a wider window than
      the spec, i.e. LESS than it promised) -> violated, not a silent pass.
    """
    # A conforming realization discharges the conformance obligation.
    assert _conformance_status("<= 14", tmp_path, "refine.hem") == ["discharged"]

    # A realization that contradicts its spec FAILS equivalence (INV-13):
    # a violated evidence value, never a silent pass or indeterminate.
    assert _conformance_status("<= 25", tmp_path, "widen.hem") == ["violated"]
