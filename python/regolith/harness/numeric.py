"""The reduced-tier numeric model contract (WO-26 D105b).

A reduced-tier numeric model is a worst-corner sweep over a scalar
point evaluation (regolith/07 sec. 2's sweep coverage): the subclass
provides ONLY the physics (:meth:`NumericReducedTierModel.evaluate_point`)
plus optional per-input monotonicity declarations and its worst-case
error; the base owns corner enumeration, the grid sweep for
non-monotone axes, the D95 structured coverage axes, and the single
margin rule via the shared :meth:`regolith.harness.model.Model.discharge`
(NO DUPLICATION -- no subclass reimplements corners or the margin).

Conservatism (INV-9): a declared-monotone input contributes exactly its
WORST corner (direction chosen from the declaration and the claim
sense); an undeclared input contributes a k-point grid INCLUDING both
corners -- honest about being a sample, never claimed as a proof, and
recorded per-axis in the evidence's coverage (D95).
"""

from __future__ import annotations

import itertools
from abc import abstractmethod
from collections.abc import Mapping

from typani.result import Ok, Result

from regolith._schema.models import (
    CoverageAxis,
    CoverageDomain1,
    CoverageMethod2,
    CoverageMethod5,
    Grid,
    KItem,
)
from regolith.harness.errors import HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.quantity import Interval
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The monotonicity vocabulary: how the MODEL VALUE moves as this input
# grows. One home for the strings (subclasses import these, never
# respell them).
# frob:doc docs/modules/py-harness.md#numeric
INCREASING = "increasing"
# frob:doc docs/modules/py-harness.md#numeric
DECREASING = "decreasing"

# Grid resolution for an axis with no declared monotonicity. 9 points
# (both corners included) is the conservative default; subclasses
# override `grid_points` when their physics warrants more.
_DEFAULT_GRID_POINTS = 9


def _axis_points(interval: Interval, count: int) -> tuple[float, ...]:
    """``count`` evenly spaced samples of ``interval``, corners included."""
    if interval.lo == interval.hi or count < 2:
        return (interval.lo,)
    step = (interval.hi - interval.lo) / (count - 1)
    return tuple(interval.lo + step * i for i in range(count))


# frob:doc docs/modules/py-harness.md#numeric
class NumericReducedTierModel(Model):
    """A worst-corner numeric sweep over a subclass's point evaluation.

    Subclass obligations: ``signature``/``version``/``cost`` (as for any
    :class:`~regolith.harness.model.Model`), :meth:`evaluate_point`, and
    :attr:`eps`; optionally :attr:`monotonicity` (per-input) and
    :attr:`grid_points`. The base implements :meth:`estimate`.
    """

    @property
    # frob:doc docs/modules/py-harness.md#numeric
    def monotonicity(self) -> Mapping[str, str]:
        """Per-input declared direction of the model value (or absent).

        ``INCREASING``: the value grows with this input; ``DECREASING``:
        it shrinks. An input absent here is swept on a grid instead of
        being reduced to one corner -- the honest default.
        """
        return {}

    @property
    # frob:doc docs/modules/py-harness.md#numeric
    def grid_points(self) -> int:
        """Grid resolution for non-monotone inputs (corners included)."""
        return _DEFAULT_GRID_POINTS

    @property
    @abstractmethod
    # frob:doc docs/modules/py-harness.md#numeric
    def eps(self) -> float:
        """The declared worst-case model error, charged against the margin."""

    @abstractmethod
    # frob:doc docs/modules/py-harness.md#numeric
    def evaluate_point(self, inputs: Mapping[str, float]) -> float:
        """The model value at one fully pinned input point."""

    def _worst_corner(self, name: str, interval: Interval) -> float | None:
        """The single worst corner of a declared-monotone input, or None.

        Worst = the corner that extremizes the value in the claim's
        adverse direction (max for an upper-bound claim, min for a
        lower-bound one), read off the declared monotonicity.
        """
        direction = self.monotonicity.get(name)
        if direction not in (INCREASING, DECREASING):
            return None
        wants_max = self.signature.sense.upper
        value_grows_with_input = direction == INCREASING
        if wants_max == value_grows_with_input:
            return interval.hi
        return interval.lo

    # frob:doc docs/modules/py-harness.md#numeric
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Sweep the input box and report the worst value (INV-9).

        Declared-monotone inputs contribute one corner; the rest a
        ``grid_points`` grid. Every axis is recorded in the D95
        structured coverage (`monotone` vs `grid(k)`), so the evidence
        says exactly how much of the domain was actually visited.
        """
        names = tuple(self.signature.inputs)
        axes: list[tuple[float, ...]] = []
        coverage_axes: list[CoverageAxis] = []
        for name in names:
            interval = request.inputs[name]
            domain = CoverageDomain1(interval=f"[{interval.lo}, {interval.hi}]")
            worst = self._worst_corner(name, interval)
            if worst is not None:
                axes.append((worst,))
                coverage_axes.append(
                    CoverageAxis(
                        axis=name, domain=domain, method=CoverageMethod5.monotone
                    )
                )
            else:
                points = _axis_points(interval, self.grid_points)
                axes.append(points)
                coverage_axes.append(
                    CoverageAxis(
                        axis=name,
                        domain=domain,
                        method=CoverageMethod2(grid=Grid(k=[KItem(len(points))])),
                    )
                )
        wants_max = self.signature.sense.upper
        values = [
            self.evaluate_point(dict(zip(names, point, strict=True)))
            for point in itertools.product(*axes)
        ]
        worst_value = max(values) if wants_max else min(values)
        _log.debug(
            "numeric reduced-tier sweep model=%s points=%d worst=%g",
            self.model_id,
            len(values),
            worst_value,
        )
        return Ok(
            Prediction(
                value=worst_value,
                eps=self.eps,
                coverage=1.0,
                coverage_axes=tuple(coverage_axes),
                in_domain=True,
            )
        )
