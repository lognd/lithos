"""The buck output-voltage-ripple model pack (reference closed-form).

Covers: a known-answer numeric check against the hand-derived formula,
the discharge verdict, corner conservatism (INV-9), and the domain guard.
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.buck_ripple import CLAIM_KIND, BuckRippleModel
from regolith.harness.quantity import bits_to_f64

# The datasheet-style operating point from examples/elec/buck_converter.cupr
# (l1=22uH, c_out=47uF land in that file's lockfile comment).
_VIN, _VOUT, _FSW, _L, _COUT = 12.0, 5.0, 500e3, 22e-6, 47e-6
_LIMIT = 0.02  # 20 mV ripple limit (require Regulation: ripple)


def _point_request(limit: float = _LIMIT) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "v_in": Interval.point(_VIN),
            "v_out": Interval.point(_VOUT),
            "f_sw": Interval.point(_FSW),
            "l": Interval.point(_L),
            "c_out": Interval.point(_COUT),
        },
    )


def _hand_ripple(vin: float, vout: float, fsw: float, ind: float, cout: float) -> float:
    """The textbook CCM buck ripple, recomputed independently of the model."""
    delta_i_l = vout * (vin - vout) / (vin * fsw * ind)
    return delta_i_l / (8.0 * fsw * cout)


def test_known_answer_value() -> None:
    """Model value matches the hand-derived closed form to f64 precision."""
    prediction = BuckRippleModel().estimate(_point_request())
    assert prediction.is_ok
    expected = _hand_ripple(_VIN, _VOUT, _FSW, _L, _COUT)
    # ~1.4103804 mV for this operating point.
    assert abs(prediction.danger_ok.value - expected) < 1e-15
    assert abs(expected - 0.0014103803997421018) < 1e-15


def test_discharged_with_healthy_margin() -> None:
    """1.4 mV worst-case ripple + 5% eps is well under the 20 mV limit."""
    evidence = default_registry().discharge(_point_request())
    assert evidence.status.value == "discharged"
    assert bits_to_f64(evidence.margin_bits) > 0.0
    assert evidence.model_id == "buck_output_ripple_ccm@1"


def test_violated_when_limit_below_ripple() -> None:
    """A tighter-than-ripple limit is a violation, distinct from indeterminate."""
    evidence = default_registry().discharge(_point_request(limit=0.001))
    assert evidence.status.value == "violated"


def test_corner_conservatism_takes_worst_corner() -> None:
    """Widening inputs to a box never lowers the reported ripple (INV-9)."""
    point = BuckRippleModel().estimate(_point_request()).danger_ok.value
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=_LIMIT,
        inputs={
            # Worst ripple is at max v_in, min f_sw, min L, min C_out.
            "v_in": Interval(lo=_VIN, hi=24.0),
            "v_out": Interval.point(_VOUT),
            "f_sw": Interval(lo=300e3, hi=_FSW),
            "l": Interval(lo=10e-6, hi=_L),
            "c_out": Interval(lo=22e-6, hi=_COUT),
        },
    )
    worst = BuckRippleModel().estimate(boxed).danger_ok.value
    assert worst >= point
    # Independently: the worst corner is the widened extreme.
    expected_worst = _hand_ripple(24.0, _VOUT, 300e3, 10e-6, 22e-6)
    assert abs(worst - expected_worst) < 1e-15


def test_out_of_domain_is_not_a_buck() -> None:
    """v_out above v_in is not a buck operating point -> domain error."""
    req = _point_request().model_copy(
        update={
            "inputs": {
                "v_in": Interval.point(5.0),
                "v_out": Interval.point(12.0),
                "f_sw": Interval.point(_FSW),
                "l": Interval.point(_L),
                "c_out": Interval.point(_COUT),
            }
        }
    )
    prediction = BuckRippleModel().estimate(req)
    assert prediction.is_err
    # And the registry surfaces it as indeterminate, not a silent pass.
    evidence = default_registry().discharge(req)
    assert evidence.status.value == "indeterminate"
