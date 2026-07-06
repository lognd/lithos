"""INV-9 Corner conservatism (regolith/13-invariants.md).

Ledger statement:
    **Every check is evaluated at its own worst-case corner.** Mechanism:
    corner maps are part of each model's contract; interval arithmetic in
    budgets/ledgers is outward-rounding. Argument: this reduces to a
    per-model obligation -- the WO-17 model test family sweeps corners
    against the model's selection.

Mechanism provided by: the harness discharge path (a model estimates a
claim at its interval inputs' own worst corner, regolith/07 sec. 4;
INV-9). This is the per-model obligation the ledger names: the fixture
below is the harness-side corner sweep the WO-17 suite owns.

This module is part of the WO-17 invariant suite: a spec change that
alters INV-9's proof argument must change this module in the same commit.

The deliberate-violation shape: a demand between the nominal (point)
value and the box's worst corner. A nominal-only evaluation would report
``discharged``; the worst-corner discipline reports ``violated``. The
gap between them IS the guarantee -- worst-corner evaluation catches a
violation a naive nominal check would miss. Driven through the real
``default_registry().discharge`` path, not a hand-built evidence value.

(The compiler-side end-to-end wiring of corner MAPS into obligations is
not exercised here -- ``check()`` produces obligations but discharge is
the harness's job per AD-1; the model-side corner obligation the ledger
reduces INV-9 to is what this suite is responsible for.)
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.buck_ripple import CLAIM_KIND, BuckRippleModel

# The datasheet operating point (examples/elec/buck_converter.cupr).
_POINT = {
    "v_in": Interval.point(12.0),
    "v_out": Interval.point(5.0),
    "f_sw": Interval.point(500e3),
    "l": Interval.point(22e-6),
    "c_out": Interval.point(47e-6),
}
# The same design with tolerance/environment boxes on every input. The
# worst ripple corner is max v_in, min f_sw, min L, min C_out.
_BOX = {
    "v_in": Interval(lo=12.0, hi=24.0),
    "v_out": Interval.point(5.0),
    "f_sw": Interval(lo=300e3, hi=500e3),
    "l": Interval(lo=10e-6, hi=22e-6),
    "c_out": Interval(lo=22e-6, hi=47e-6),
}


def _value(inputs: dict[str, Interval]) -> float:
    request = DischargeRequest(claim_kind=CLAIM_KIND, limit=0.02, inputs=inputs)
    return BuckRippleModel().estimate(request).danger_ok.value


def _discharge(inputs: dict[str, Interval], *, limit: float) -> str:
    request = DischargeRequest(claim_kind=CLAIM_KIND, limit=limit, inputs=inputs)
    return default_registry().discharge(request).status.value


def test_inv_09_worst_corner_catches_a_violation_nominal_would_miss() -> None:
    """A demand set strictly between the nominal value and the box's worst
    corner: the worst-corner discipline reports ``violated`` where a
    nominal-only evaluation would report ``discharged`` (INV-9)."""
    nominal = _value(_POINT)
    worst = _value(_BOX)
    assert worst > nominal, "widening inputs must never lower the worst corner"

    # A limit the nominal design clears but the worst corner does not.
    limit = (nominal + worst) / 2.0

    assert _discharge(_POINT, limit=limit) == "discharged"
    assert _discharge(_BOX, limit=limit) == "violated", (
        "worst-corner evaluation must catch the corner violation that a "
        "nominal-only check misses (INV-9 corner conservatism)"
    )
