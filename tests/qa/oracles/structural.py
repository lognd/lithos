"""Independent structural/identity oracles + the ONE margin rule (D226).

Covers the families whose discharge is a structural comparison rather
than continuous physics -- and the margin arithmetic every family's
recomputation closes over:

* margin rule -- regolith/07's single verdict arithmetic, written
  fresh: ``margin = limit - (value + eps)`` for an upper-bound claim,
  ``margin = (value - eps) - limit`` for a lower-bound one. Every
  sampled sheet's recorded margin must equal this from its own
  value/eps/limit.
* workload identity -- a rule-3 derived workload copies the intent's
  demand vector verbatim (cuprite/05 sec. 1), so the discharge is the
  matched constant 1.0 with zero model error, exactly.
* conformance refinement (upper) -- the impl's promised ceiling at its
  worst (highest) corner; the spec's ceiling arrives as the limit.
* hdl build -- a discharged ``hdl.build`` means the toolchain reported
  ZERO errors (value 0.0 exactly); re-running the compiler is not a
  closed form, so the recomputation is the exact-zero identity plus
  the margin rule (named cut: the build itself is re-proven by the
  demos leg's firmware/HDL pack, not by this oracle).
"""

from __future__ import annotations

from collections.abc import Mapping


def margin(value: float, eps: float, limit: float, *, upper: bool) -> float:
    """The single margin rule, written fresh from regolith/07."""
    if upper:
        return limit - (value + eps)
    return (value - eps) - limit


def workload_identity(_inputs: Mapping[str, tuple[float, float]]) -> float:
    """The derived-edge identity discharge's exact matched constant."""
    return 1.0


def conformance_upper(inputs: Mapping[str, tuple[float, float]]) -> float:
    """Worst (highest) corner of the impl's promised upper bound."""
    return max(inputs["impl_bound"])


def hdl_build_errors(_inputs: Mapping[str, tuple[float, float]]) -> float:
    """A discharged HDL build reported exactly zero errors."""
    return 0.0


def hdl_sim_mismatches(_inputs: Mapping[str, tuple[float, float]]) -> float:
    """A discharged sim assert reported exactly zero vector mismatches."""
    return 0.0
