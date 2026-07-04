"""Evidence determinism (INV-10) for the harness.

Same inputs -> byte-identical evidence (hash + every bit field). The
`deterministic` flag and the registry version are hash inputs, so a
change in either moves the address.
"""

from __future__ import annotations

from rockhead.harness import DischargeRequest, Interval, ModelRegistry, default_registry
from rockhead.harness.models import register_all
from rockhead.harness.models.buck_ripple import CLAIM_KIND


def _request(deterministic: bool = True) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=0.02,
        deterministic=deterministic,
        inputs={
            "v_in": Interval.point(12.0),
            "v_out": Interval.point(5.0),
            "f_sw": Interval.point(500e3),
            "l": Interval.point(22e-6),
            "c_out": Interval.point(47e-6),
        },
    )


def test_repeat_discharge_is_byte_identical() -> None:
    """Two independent discharges agree on hash and every bit field."""
    first = default_registry().discharge(_request())
    second = default_registry().discharge(_request())
    assert first.model_dump() == second.model_dump()
    assert first.hash == second.hash


def test_deterministic_flag_changes_the_hash() -> None:
    """The declared determinism is folded into the evidence hash (INV-10)."""
    det = default_registry().discharge(_request(deterministic=True))
    nondet = default_registry().discharge(_request(deterministic=False))
    assert det.hash != nondet.hash


def test_registry_version_changes_the_hash() -> None:
    """A registry-version bump invalidates the evidence key (BE-1/INV-1)."""
    bumped = ModelRegistry(version="model-registry@9.9.9")
    register_all(bumped)
    baseline = default_registry().discharge(_request())
    other = bumped.discharge(_request())
    assert baseline.hash != other.hash
