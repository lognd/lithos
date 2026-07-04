"""The conformance-refinement model pack (INV-13 discharge half).

Covers: a conforming impl (a bound no weaker than the spec's) discharges;
a contradicting impl (a wider window than the spec promises) is caught as
``violated``, not indeterminate; the worst-corner rule (INV-9) over an
impl bound with tolerance; a non-comparable (non-finite) bound is honestly
``indeterminate``, never a false pass; and determinism (INV-10).
"""

from __future__ import annotations

import math

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.conformance import (
    CLAIM_KIND_LOWER,
    CLAIM_KIND_UPPER,
    ConformanceRefinementModel,
)


def _upper_request(impl_bound: Interval, spec_bound: float) -> DischargeRequest:
    """An upper-sense conformance request: impl ceiling vs the spec ceiling."""
    return DischargeRequest(
        claim_kind=CLAIM_KIND_UPPER,
        limit=spec_bound,
        inputs={"impl_bound": impl_bound},
    )


def _lower_request(impl_bound: Interval, spec_bound: float) -> DischargeRequest:
    """A lower-sense conformance request: impl floor vs the spec floor."""
    return DischargeRequest(
        claim_kind=CLAIM_KIND_LOWER,
        limit=spec_bound,
        inputs={"impl_bound": impl_bound},
    )


def test_upper_conforming_impl_discharges() -> None:
    """An impl ceiling tighter than the spec's refines it -> discharged."""
    # Spec promises Q <= 20; impl promises the tighter Q <= 14 -> conforms.
    evidence = default_registry().discharge(_upper_request(Interval.point(14.0), 20.0))
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "conformance_refinement_upper@1"


def test_upper_contradicting_impl_is_violated() -> None:
    """An impl ceiling WIDER than the spec's contradicts it -> violated."""
    # Spec promises Q <= 20; impl only promises Q <= 25 -- weaker, a wider
    # window than the spec -> equivalence FAILS (INV-13), not indeterminate.
    evidence = default_registry().discharge(_upper_request(Interval.point(25.0), 20.0))
    assert evidence.status.value == "violated"


def test_lower_conforming_impl_discharges() -> None:
    """An impl floor tighter (higher) than the spec's refines it."""
    # Spec promises Q >= 6; impl promises the tighter Q >= 9 -> conforms.
    evidence = default_registry().discharge(_lower_request(Interval.point(9.0), 6.0))
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "conformance_refinement_lower@1"


def test_lower_contradicting_impl_is_violated() -> None:
    """An impl floor LOWER than the spec's contradicts it -> violated."""
    # Spec promises Q >= 6; impl only promises Q >= 3 -- weaker -> fails.
    evidence = default_registry().discharge(_lower_request(Interval.point(3.0), 6.0))
    assert evidence.status.value == "violated"


def test_upper_worst_corner_uses_the_widest_impl_bound() -> None:
    """An impl bound with tolerance is judged at its weakest (max) corner."""
    # Impl bound ranges [14, 22]; its worst (highest) corner 22 exceeds the
    # spec's 20, so a conservative refinement check must FAIL (INV-9).
    prediction = ConformanceRefinementModel(upper=True).estimate(
        _upper_request(Interval(lo=14.0, hi=22.0), 20.0)
    )
    assert prediction.is_ok
    assert prediction.danger_ok.value == 22.0
    evidence = default_registry().discharge(
        _upper_request(Interval(lo=14.0, hi=22.0), 20.0)
    )
    assert evidence.status.value == "violated"


def test_non_finite_bound_is_indeterminate_not_a_pass() -> None:
    """A non-comparable (infinite) impl bound is honest indeterminate."""
    evidence = default_registry().discharge(
        _upper_request(Interval(lo=0.0, hi=math.inf), 20.0)
    )
    assert evidence.status.value == "indeterminate"


def test_determinism_same_inputs_same_hash() -> None:
    """Identical conformance requests give a byte-identical hash (INV-10)."""
    first = default_registry().discharge(_upper_request(Interval.point(14.0), 20.0))
    second = default_registry().discharge(_upper_request(Interval.point(14.0), 20.0))
    assert first.hash == second.hash
