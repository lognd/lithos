"""Tests for `regolith.harness.quantity` (T-0036 phase 2 stretch): the
`f64_to_bits`/`bits_to_f64` round trip and `Interval`'s ordering
invariant + corner accessor -- the module's line coverage was already
95%+ (only a handful of dedicated statements) but branch coverage was
low because `bits_to_f64`, the inverted-interval rejection, and
`corners()` had never been exercised directly.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from regolith.harness.quantity import Interval, bits_to_f64, f64_to_bits


# frob:ticket T-0036
# frob:tests python/regolith/harness/quantity.py::bits_to_f64 kind="unit"
def test_bits_to_f64_inverts_f64_to_bits() -> None:
    for value in (0.0, 1.0, -1.0, 3.14159, -2.5e10, 1e-300):
        assert bits_to_f64(f64_to_bits(value)) == value


# frob:ticket T-0036
# frob:tests python/regolith/harness/quantity.py::Interval kind="unit"
def test_interval_point_is_degenerate() -> None:
    interval = Interval.point(5.0)
    assert interval.lo == interval.hi == 5.0


# frob:ticket T-0036
# frob:tests python/regolith/harness/quantity.py::Interval.corners kind="unit"
def test_interval_corners_returns_lo_hi_tuple() -> None:
    interval = Interval(lo=1.0, hi=3.0)
    assert interval.corners() == (1.0, 3.0)


# frob:ticket T-0036
# frob:tests python/regolith/harness/quantity.py::Interval kind="unit"
def test_interval_rejects_inverted_range() -> None:
    """`lo > hi` is a programmer bug (an inverted interval), rejected
    at construction -- never silently swapped or clamped."""
    with pytest.raises(ValidationError, match="inverted interval"):
        Interval(lo=5.0, hi=1.0)


# frob:ticket T-0036
# frob:tests python/regolith/harness/quantity.py::Interval kind="unit"
def test_interval_allows_equal_lo_hi() -> None:
    """`lo == hi` is the degenerate (pinned) case, never rejected."""
    interval = Interval(lo=2.0, hi=2.0)
    assert interval.corners() == (2.0, 2.0)
