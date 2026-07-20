# ruff: noqa: E501  -- long frob:tests directive symrefs exceed the 88-col house style; the exact path is load-bearing for the frob DSL and cannot wrap
"""The reduced-tier numeric base + its shipped customers (WO-26 D105a/b).

Covers: the base's monotone worst-corner selection vs grid sweep (D95
coverage axes recorded per method), the lumped-thermal reference pack's
known answer and discharge verdicts, and the buck efficiency/transient
packs (the WO-26 tracked-pack list, unblocked by D105a/D102).
"""

from __future__ import annotations

from collections.abc import Mapping

from regolith._schema.models import CoverageMethod2, CoverageMethod5
from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.buck_efficiency import (
    CLAIM_KIND as EFFICIENCY_KIND,
)
from regolith.harness.models.buck_efficiency import (
    BuckEfficiencyModel,
)
from regolith.harness.models.buck_transient import (
    CLAIM_KIND as TRANSIENT_KIND,
)
from regolith.harness.models.buck_transient import (
    BuckTransientModel,
)
from regolith.harness.models.lumped_thermal import (
    CLAIM_KIND as THERMAL_KIND,
)
from regolith.harness.models.lumped_thermal import (
    LumpedThermalModel,
)
from regolith.harness.numeric import INCREASING, NumericReducedTierModel
from regolith.harness.signature import ClaimSense, ModelSignature


class _ProbeModel(NumericReducedTierModel):
    """A tiny upper-bound model recording every evaluated point."""

    def __init__(self) -> None:
        self.points: list[dict[str, float]] = []

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="probe",
            claim_kind="test.probe",
            sense=ClaimSense.upper_bound(),
            inputs=("mono", "wild"),
        )

    @property
    def version(self) -> str:
        return "1"

    @property
    def cost(self) -> int:
        return 1

    @property
    def monotonicity(self) -> Mapping[str, str]:
        return {"mono": INCREASING}

    @property
    def grid_points(self) -> int:
        return 5

    @property
    def eps(self) -> float:
        return 0.0

    def evaluate_point(self, inputs: Mapping[str, float]) -> float:
        self.points.append(dict(inputs))
        # Non-monotone in `wild`: peaks mid-interval.
        return inputs["mono"] - (inputs["wild"] - 0.5) ** 2


def _probe_request() -> DischargeRequest:
    return DischargeRequest(
        claim_kind="test.probe",
        limit=10.0,
        inputs={"mono": Interval(lo=1.0, hi=3.0), "wild": Interval(lo=0.0, hi=1.0)},
    )


# frob:tests python/regolith/harness/numeric.py::NumericReducedTierModel.grid_points
# frob:tests python/regolith/harness/numeric.py::NumericReducedTierModel.evaluate_point
# frob:tests python/regolith/harness/models/lumped_thermal.py::LumpedThermalModel.evaluate_point
# frob:tests python/regolith/harness/models/buck_efficiency.py::BuckEfficiencyModel.evaluate_point
# frob:tests python/regolith/harness/models/buck_transient.py::BuckTransientModel.evaluate_point
def test_declared_monotone_input_contributes_one_worst_corner() -> None:
    """`mono` (increasing, upper-bound claim) is pinned at its HI corner
    for every evaluated point; `wild` is grid-swept."""
    model = _ProbeModel()
    prediction = model.estimate(_probe_request()).danger_ok
    assert model.points, "the sweep must evaluate at least one point"
    assert all(p["mono"] == 3.0 for p in model.points)
    assert len({p["wild"] for p in model.points}) == 5, "5-point grid on wild"
    # Worst (max) value: mono=3 at wild=0.5 (the interior grid midpoint).
    assert abs(prediction.value - 3.0) < 1e-12


def test_coverage_axes_record_monotone_vs_grid() -> None:
    """Each axis's coverage method says how it was actually covered."""
    prediction = _ProbeModel().estimate(_probe_request()).danger_ok
    methods = {axis.axis: axis.method for axis in prediction.coverage_axes}
    assert methods["mono"] == CoverageMethod5.monotone
    assert isinstance(methods["wild"], CoverageMethod2), "grid(k) on the wild axis"


def test_lumped_thermal_known_answer_discharges() -> None:
    """T_j = 300 + 2 * 10 = 320 K; +5 K eps clears a 350 K ceiling."""
    request = DischargeRequest(
        claim_kind=THERMAL_KIND,
        limit=350.0,
        inputs={
            "ambient": Interval(lo=290.0, hi=300.0),
            "power": Interval(lo=1.0, hi=2.0),
            "r_theta": Interval(lo=8.0, hi=10.0),
        },
    )
    prediction = LumpedThermalModel().estimate(request).danger_ok
    assert abs(prediction.value - 320.0) < 1e-12, "all-increasing -> all-hi corner"
    evidence = default_registry().discharge(request)
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "thermo_lumped_steady@1"


def test_lumped_thermal_violated_when_ceiling_is_below_worst_corner() -> None:
    request = DischargeRequest(
        claim_kind=THERMAL_KIND,
        limit=310.0,
        inputs={
            "ambient": Interval.point(300.0),
            "power": Interval.point(2.0),
            "r_theta": Interval.point(10.0),
        },
    )
    evidence = default_registry().discharge(request)
    assert evidence.status.value == "violated"


def test_buck_efficiency_worst_point_is_interior_capable() -> None:
    """The load sweep (D105a's `forall i(out)` domain) is grid-swept:
    the minimum efficiency lands at a corner of the load range here
    (light load, fixed losses dominating), found by the grid."""
    request = DischargeRequest(
        claim_kind=EFFICIENCY_KIND,
        limit=0.85,
        inputs={
            "v_out": Interval.point(5.0),
            "i_out": Interval(lo=0.2, hi=3.0),
            "r_series": Interval.point(0.05),
            "p_fixed": Interval.point(0.05),
        },
    )
    model = BuckEfficiencyModel()
    prediction = model.estimate(request).danger_ok
    # eta at i=0.2: 1.0/(1.0 + 0.05*0.04 + 0.05) = 0.95057...; the model
    # must not report anything better than the true worst grid point.
    eta_light = 1.0 / (1.0 + 0.05 * 0.2**2 + 0.05)
    assert prediction.value <= eta_light + 1e-12
    evidence = default_registry().discharge(request)
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "buck_efficiency_loss_budget@1"


# frob:ticket T-0036
# frob:tests python/regolith/harness/models/buck_efficiency.py::BuckEfficiencyModel.evaluate_point kind="unit"
def test_buck_efficiency_evaluate_point_zero_total_power_is_zero_eta() -> None:
    """T-0036 branch backfill: an all-zero operating point (`v_out=0`,
    `i_out=0`, `p_fixed=0`) drives `total <= 0.0`, the model's own
    div-by-zero guard -- efficiency reads honestly as 0.0, never a
    ZeroDivisionError or a NaN."""
    model = BuckEfficiencyModel()
    eta = model.evaluate_point(
        {"v_out": 0.0, "i_out": 0.0, "r_series": 0.05, "p_fixed": 0.0}
    )
    assert eta == 0.0


def test_buck_transient_discharges_a_fast_loop() -> None:
    """f_c = 50 kHz, tol = 2%: t_s = ln(50)/(2 pi 5e4) = 12.5 us; even
    +50% eps clears a 500 us window."""
    request = DischargeRequest(
        claim_kind=TRANSIENT_KIND,
        limit=500e-6,
        inputs={"f_c": Interval(lo=5e4, hi=1e5), "tol": Interval.point(0.02)},
    )
    evidence = default_registry().discharge(request)
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "converter_settling_dominant_pole@1"


def test_buck_transient_zero_crossover_is_a_domain_error_not_a_pass() -> None:
    """A non-positive crossover corner has unbounded settling time: an
    explicit indeterminate (DomainError), never a non-finite value in
    evidence and never a silent pass."""
    request = DischargeRequest(
        claim_kind=TRANSIENT_KIND,
        limit=500e-6,
        inputs={"f_c": Interval(lo=0.0, hi=1e5), "tol": Interval.point(0.02)},
    )
    result = BuckTransientModel().estimate(request)
    assert result.is_err
    evidence = default_registry().discharge(request)
    assert evidence.status.value == "indeterminate"


def test_numeric_sweep_is_deterministic() -> None:
    """Same request, byte-identical evidence hash (INV-10)."""
    request = DischargeRequest(
        claim_kind=THERMAL_KIND,
        limit=350.0,
        inputs={
            "ambient": Interval(lo=290.0, hi=300.0),
            "power": Interval(lo=1.0, hi=2.0),
            "r_theta": Interval(lo=8.0, hi=10.0),
        },
    )
    first = default_registry().discharge(request)
    second = default_registry().discharge(request)
    assert first.hash == second.hash
