"""The embedded-post depth adequacy model pack (WO-85/D194).

Covers: the discharge verdict (declared clears the bound), the
violated verdict (declared short of the bound), the lower-bound sense
(the conservative corner is the SHALLOWEST declared depth), the
domain guards, registry pickup, and determinism (INV-10).
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.post_embedment import CLAIM_KIND, PostEmbedmentModel


def _request(
    declared: float | tuple[float, float] = 1.4,
    required: float = 0.0,
    limit: float = 1.2,
) -> DischargeRequest:
    lo, hi = declared if isinstance(declared, tuple) else (declared, declared)
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "declared_depth": Interval(lo=lo, hi=hi),
            "required_depth": Interval.point(required),
        },
    )


def test_declared_depth_is_the_predicted_value() -> None:
    """The claimed quantity IS the declared depth (a datum, eps 0)."""
    prediction = PostEmbedmentModel().estimate(_request(declared=1.4))
    assert prediction.is_ok, prediction
    pred = prediction.danger_ok
    assert pred.value == 1.4
    assert pred.eps == 0.0
    assert pred.in_domain


def test_lower_bound_sense_takes_the_shallowest_corner() -> None:
    """An interval-valued declared depth predicts its MIN corner (the
    conservative direction for a `>= bound` claim, INV-9)."""
    prediction = PostEmbedmentModel().estimate(_request(declared=(1.3, 1.6)))
    assert prediction.is_ok
    assert prediction.danger_ok.value == 1.3


def test_signature_is_a_lower_bound_over_both_depths() -> None:
    """The sense is `lower` (deeper is safer) over declared+required."""
    sig = PostEmbedmentModel().signature
    assert not sig.sense.upper
    assert set(sig.inputs) == {"declared_depth", "required_depth"}
    assert sig.claim_kind == CLAIM_KIND


def test_domain_guards_reject_nonpositive_declared_depth() -> None:
    """A zero/negative declared depth is a domain error (a post with no
    embedment is not this model's subject), as is a negative required
    depth."""
    model = PostEmbedmentModel()
    assert model.estimate(_request(declared=0.0)).is_err
    assert model.estimate(_request(declared=-0.5)).is_err
    assert model.estimate(_request(required=-0.1)).is_err


def test_registry_discharges_and_violates_end_to_end() -> None:
    """The default registry routes `civil.embedment` here: 1.4m declared
    vs a 1.2m frost bound discharges; a 1.0m declared depth violates."""
    registry = default_registry()
    ok = registry.discharge(_request(declared=1.4, limit=1.2))
    assert ok.status.value == "discharged", ok
    short = registry.discharge(_request(declared=1.0, limit=1.2))
    assert short.status.value == "violated", short


def test_determinism_same_inputs_same_prediction() -> None:
    """Two identical requests predict identically (INV-10)."""
    a = PostEmbedmentModel().estimate(_request()).danger_ok
    b = PostEmbedmentModel().estimate(_request()).danger_ok
    assert (a.value, a.eps, a.coverage) == (b.value, b.eps, b.coverage)
