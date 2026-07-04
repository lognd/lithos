"""Harness-side scalar and interval quantities (Phase C model math).

The harness works in plain ``f64`` magnitudes in a single consistent unit
system: unit reconciliation and dimensional checking are the compiler
core's job (``regolith-qty``, AD-1/AD-9), so a model that reaches the
harness is fed numbers whose units the orchestrator has already made
coherent. What the harness DOES own is corner discipline (INV-9): an
input tolerance/environment range is an :class:`Interval`, and a model
evaluates its claim at that interval's own worst corner.
"""

from __future__ import annotations

import struct

from pydantic import BaseModel, ConfigDict, model_validator


def f64_to_bits(value: float) -> int:
    """Pack an ``f64`` into its ``u64`` bit pattern (exact serialization).

    The generated ``Evidence`` schema stores value/eps/margin/coverage as
    bits (AD-5) so a float round-trips byte-exactly through JSON; this is
    the one producer of those bits on the Python side.
    """
    return int(struct.unpack("<Q", struct.pack("<d", value))[0])


def bits_to_f64(bits: int) -> float:
    """Inverse of :func:`f64_to_bits`: recover the ``f64`` from its bits."""
    return float(struct.unpack("<d", struct.pack("<Q", bits))[0])


class Interval(BaseModel):
    """A closed ``[lo, hi]`` range of a scalar quantity's worst-case corner.

    Degenerate (``lo == hi``) for a pinned value; wide for a tolerance,
    environment, or PVT range the model must evaluate conservatively.
    """

    model_config = ConfigDict(frozen=True)

    lo: float
    hi: float

    @model_validator(mode="after")
    def _ordered(self) -> Interval:
        """Reject an inverted range -- a programmer bug, not user data."""
        if self.lo > self.hi:
            raise ValueError(f"inverted interval: lo={self.lo} > hi={self.hi}")
        return self

    @classmethod
    def point(cls, value: float) -> Interval:
        """A degenerate interval pinning a single value."""
        return cls(lo=value, hi=value)

    def corners(self) -> tuple[float, float]:
        """The two endpoints a worst-case sweep must consider."""
        return (self.lo, self.hi)
