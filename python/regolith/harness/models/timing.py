"""`std.timing`: WO-156 (D264) -- grounding `budget kind=timing` closure.

Charter: `docs/spec/cuprite/04-structural-layer.md` sec. 5/5a (the
`budget <name> kind=timing:` container; the contribution-sum-vs-limit
math shape shared with a tolerance chain; `E0432`/`BUDGET_CANNOT_CLOSE`
naming the worst contributor when a budget cannot close). The Rust IR
side (`crates/regolith-ir/src/budget.rs::close_budget`) already sums
interval contributions against a literal limit and already emits
`E0432` when they cannot close -- this module's job (per the WO's own
scope) is GROUNDING: producing the contribution VALUES from real
provenance (a datasheet citation or an extracted route length + cited
stackup `Dk`) instead of a hand-typed literal, and applying the exact
same sum-vs-limit-at-the-worst-corner arithmetic at the harness layer
so a `elec.timing_budget` claim can discharge through the ONE model/
evidence path every other harness model uses (`regolith.harness.model
.Model.discharge`) -- never a second closure mechanism.

D266 (2026-07-16) withdrew the `stdlib/ti.mcu` datasheet corpus this
WO's own body cites as its first data source, pending counsel review
of the sourcing/licensing posture -- content only, not code. This
module carries NO reference to any withdrawn record; every citation a
caller supplies is theirs to provide (real, once a corpus lands, or
synthetic-for-tests today, exactly the WO-138/WO-139 conversion
precedent D266 recorded). `Cited`/`CitedInterval`/`MeasCondition`
(`regolith.magnetite.citation`) are the ONE structured-citation carrier
(D257) this module builds on, unmodified.

Conservative-choice ruling (recorded here, not escalated): the
Dk-to-propagation-velocity formula charter 35 does not spell out a
closed form beyond the shared TEM assumption its own rule 6 already
names for every Dk-derived quantity in this stackup family. This
module uses the standard TEM-in-a-uniform-dielectric relation
`v_p = c / sqrt(Dk)` (c = speed of light in vacuum) -- textbook
physics, not a new design decision, and consistent with charter 35's
stated TEM validity domain. Escalate (per the WO's own instruction) if
a real fixture ever needs a non-TEM stackup this formula cannot cover.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, model_validator
from typani.result import Err, Ok, Result

from regolith._codes import BUDGET_CANNOT_CLOSE
from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature
from regolith.logging_setup import get_logger
from regolith.magnetite.citation import Cited, CitedInterval

if TYPE_CHECKING:
    from regolith.orchestrator.payload_store import PayloadResolver

_log = get_logger(__name__)

# frob:doc docs/modules/py-harness.md#models-timing
CLAIM_KIND = "elec.timing_budget"

# frob:doc docs/modules/py-harness.md#models-timing
CONTRIBUTIONS_PORT = "timing_contributions"
# frob:doc docs/modules/py-harness.md#models-timing
CONTRIBUTIONS_KIND = "timing_contribution_table"

# Speed of light in vacuum, mm/ns (exact SI conversion: 299792458 m/s).
# frob:doc docs/modules/py-harness.md#models-timing
LIGHT_SPEED_MM_PER_NS = 299.792458


# frob:doc docs/modules/py-harness.md#models-timing
def stackup_v_p_mm_per_ns(dk: float) -> float:
    """Propagation velocity from a stackup's dielectric constant.

    `v_p = c / sqrt(Dk)`, the standard TEM-in-a-uniform-dielectric
    relation (charter 35 rule 6's own TEM validity domain) -- see this
    module's docstring for the conservative-choice ruling that picked
    this closed form.
    """
    if dk <= 0.0:
        raise ValueError(f"stackup Dk must be positive, got {dk!r}")
    return LIGHT_SPEED_MM_PER_NS / math.sqrt(dk)


# frob:doc docs/modules/py-harness.md#models-timing
def route_delay_ns(length_mm: float, dk: float) -> float:
    """A route's propagation delay: extracted length over Dk-derived `v_p`.

    Charter 35 rule 2's pre-layout-allocated / post-layout-re-discharged
    pattern (established for impedance) applies unmodified: pre-layout
    ``length_mm`` is the budget-allocated share, post-layout it is the
    `RealizedLayout`-extracted length (`bus_length_match`,
    `04-structural-layer.md:193-196`) -- this function does not care
    which stage supplied it, only that it is a length in mm.
    """
    return length_mm / stackup_v_p_mm_per_ns(dk)


# frob:doc docs/modules/py-harness.md#models-timing
class TimingContribution(BaseModel):
    """One grounded contribution to a `kind=timing` budget's closure sum.

    Exactly one grounding source is representable per contribution
    (enforced at construction, D257's "uncited value unrepresentable"
    bar applied at this consumer, WO-156 acceptance criterion 2):
    either a datasheet-cited interval (`cited`, e.g. a silicon
    promise's `t_pd`/`t_su`/`t_h`/`t_co`) or a route delay
    (`route_length_mm` + `route_dk`, a `Cited[float]` stackup `Dk`).
    There is no third field that accepts a bare literal.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    cited: CitedInterval | None = None
    route_length_mm: float | None = None
    route_dk: Cited[float] | None = None

    @model_validator(mode="after")
    def _exactly_one_grounding_source(self) -> TimingContribution:
        """Refuse a contribution with zero or two grounding sources."""
        has_cited = self.cited is not None
        has_route = self.route_length_mm is not None or self.route_dk is not None
        if has_cited and has_route:
            raise ValueError(
                f"contribution {self.name!r}: carries BOTH a cited interval "
                "and route fields -- exactly one grounding source is allowed"
            )
        if not has_cited and not has_route:
            raise ValueError(
                f"contribution {self.name!r}: no grounding source -- a bare "
                "literal contribution is not representable (D257 bar, "
                "applied at this consumer)"
            )
        if has_route and (self.route_length_mm is None or self.route_dk is None):
            raise ValueError(
                f"contribution {self.name!r}: a route contribution needs "
                "BOTH route_length_mm and route_dk"
            )
        return self

    # frob:doc docs/modules/py-harness.md#models-timing
    # frob:tests tests/harness/test_std_timing.py::test_route_contribution_pessimal_ns_matches_hand_computed_delay
    def pessimal_ns(self) -> float:
        """This contribution's worst-corner (pessimal) delay, in ns.

        A cited interval takes its `hi` end (WO-156's v1 single-corner
        posture, `04-structural-layer.md` sec. 5a); a symbolic `hi` (a
        `str` bound, D257's `CitedInterval.hi` carve-out) is not yet
        representable as a v1 pessimal number and raises -- the same
        "no silent narrowing" posture the rest of this pass takes,
        never a guessed float.
        """
        if self.cited is not None:
            hi = self.cited.hi
            if not isinstance(hi, (int, float)):
                raise ValueError(
                    f"contribution {self.name!r}: symbolic cited.hi "
                    f"({hi!r}) has no v1 numeric pessimal-corner reading"
                )
            return float(hi)
        assert self.route_length_mm is not None and self.route_dk is not None
        return route_delay_ns(self.route_length_mm, self.route_dk.value)

    # frob:doc docs/modules/py-harness.md#models-timing
    def citation_summary(self) -> str:
        """A human-readable citation string for calc-book rendering.

        Renders through the EXISTING generic calc-sheet input path
        (`regolith.backends.calc.inputs_from_given`, AD-7 -- one
        renderer) as a `declared_literal` load's `source` text; no new
        renderer code is added for this claim kind.
        """
        if self.cited is not None:
            c = self.cited.citation
            return (
                f"{c.manufacturer} {c.document} rev.{c.revision} "
                f"p.{c.page} table {c.table}"
            )
        assert self.route_dk is not None
        c = self.route_dk.citation
        return (
            f"route length={self.route_length_mm:g}mm "
            f"Dk={self.route_dk.value:g} "
            f"({c.manufacturer} {c.document} rev.{c.revision} "
            f"p.{c.page} table {c.table})"
        )


# frob:doc docs/modules/py-harness.md#models-timing
class TimingContributionTable(BaseModel):
    """The `timing_contribution_table` payload (WO-156): the named
    grounded contributions a `budget kind=timing` closure sums, keyed
    to a budget name for the calc-book's own labeling."""

    model_config = ConfigDict(frozen=True)

    budget_name: str
    contributions: tuple[TimingContribution, ...]

    @model_validator(mode="after")
    def _at_least_one_contribution(self) -> TimingContributionTable:
        if not self.contributions:
            raise ValueError(
                f"timing budget {self.budget_name!r}: at least one "
                "contribution is required"
            )
        return self


# frob:doc docs/modules/py-harness.md#models-timing
class TimingBudgetClosure(BaseModel):
    """The result of closing a `kind=timing` budget: every contribution's
    pessimal value + citation, the sum, the limit, the slack, and the
    verdict -- the calc-book timing-closure table's own row shape
    (WO-156 deliverable 5)."""

    model_config = ConfigDict(frozen=True)

    budget_name: str
    limit_ns: float
    contribution_names: tuple[str, ...]
    contribution_ns: tuple[float, ...]
    contribution_citations: tuple[str, ...]
    sum_ns: float
    slack_ns: float
    verdict: str
    worst_contributor: str
    diagnostic_code: str | None = None


# frob:doc docs/modules/py-harness.md#models-timing
# frob:tests tests/harness/test_std_timing.py::test_e0432_negative_fixture_names_the_right_worst_contributor
def close_timing_budget(
    budget_name: str, limit_ns: float, contributions: Sequence[TimingContribution]
) -> Result[TimingBudgetClosure, DomainError]:
    """Close a `kind=timing` budget: sum every contribution's pessimal
    (worst-corner) delay and compare it to `limit_ns` (the declared
    clock period or interface window) -- the same closed-form
    arithmetic `close_budget` (`regolith-ir/src/budget.rs`) applies to
    literal declared contributions, source-ordered, now fed by grounded
    values (WO-156 deliverable 2). A budget that cannot close is named
    with `E0432`/`BUDGET_CANNOT_CLOSE` (reused verbatim, no new
    diagnostic family, D264 ruling "nothing-new-here") and its worst
    (largest) contributor.

    Returns `Err(DomainError)` only for a MALFORMED contribution (a
    symbolic pessimal reading, `TimingContribution.pessimal_ns`'s own
    guard) -- a budget that closes over valid numbers but exceeds its
    limit is a legitimate `violated` verdict, not an error (the same
    "violated is data, not an exception" posture every other model
    takes).
    """
    if not contributions:
        return Err(
            DomainError(
                model_id="std.timing.timing_budget",
                message=f"timing budget {budget_name!r}: no contributions to close",
            )
        )
    names: list[str] = []
    values: list[float] = []
    citations: list[str] = []
    for c in contributions:
        try:
            ns = c.pessimal_ns()
        except ValueError as exc:
            _log.error(
                "close_timing_budget: budget=%s contributor=%s malformed: %s",
                budget_name,
                c.name,
                exc,
            )
            return Err(
                DomainError(model_id="std.timing.timing_budget", message=str(exc))
            )
        names.append(c.name)
        values.append(ns)
        citations.append(c.citation_summary())

    total = sum(values)
    slack = limit_ns - total
    worst_index = max(range(len(values)), key=lambda i: values[i])
    worst_name = names[worst_index]
    closes = slack >= 0.0
    verdict = "closed" if closes else "violated"
    diag_code = None if closes else BUDGET_CANNOT_CLOSE
    if not closes:
        _log.warning(
            "close_timing_budget: %s budget=%s worst_contributor=%s sum_ns=%.6g "
            "limit_ns=%.6g slack_ns=%.6g",
            BUDGET_CANNOT_CLOSE,
            budget_name,
            worst_name,
            total,
            limit_ns,
            slack,
        )
    else:
        _log.debug(
            "close_timing_budget: budget=%s closed sum_ns=%.6g limit_ns=%.6g "
            "slack_ns=%.6g",
            budget_name,
            total,
            limit_ns,
            slack,
        )
    return Ok(
        TimingBudgetClosure(
            budget_name=budget_name,
            limit_ns=limit_ns,
            contribution_names=tuple(names),
            contribution_ns=tuple(values),
            contribution_citations=tuple(citations),
            sum_ns=total,
            slack_ns=slack,
            verdict=verdict,
            worst_contributor=worst_name,
            diagnostic_code=diag_code,
        )
    )


def _resolve_contributions(
    request: DischargeRequest, resolver: PayloadResolver | None
) -> Result[TimingContributionTable, HarnessError]:
    """Resolve + parse the request's `timing_contributions` payload."""
    ref = request.payloads.get(CONTRIBUTIONS_PORT)
    if ref is None:  # pragma: no cover -- signature match guarantees it
        return Err(
            DomainError(
                model_id="std.timing.timing_budget",
                message=f"no {CONTRIBUTIONS_PORT} payload",
            )
        )
    if resolver is None:
        return Err(
            DomainError(
                model_id="std.timing.timing_budget",
                message="no payload store resolver configured",
            )
        )
    resolved = resolver(ref.digest)
    if resolved.is_err:
        return Err(
            DomainError(
                model_id="std.timing.timing_budget",
                message=(
                    f"payload {ref.digest} did not resolve: "
                    f"{resolved.danger_err.message}"
                ),
            )
        )
    try:
        table = TimingContributionTable.model_validate_json(resolved.danger_ok)
    except Exception as exc:  # noqa: BLE001 -- malformed payload is data, not a bug
        return Err(
            DomainError(
                model_id="std.timing.timing_budget",
                message=f"malformed timing_contribution_table payload: {exc}",
            )
        )
    return Ok(table)


# frob:doc docs/modules/py-harness.md#models-timing
class TimingBudgetModel(Model):
    """`elec.timing_budget` (WO-156, D264): source-generic closure over a
    request-carried `timing_contribution_table` payload (mirrors the
    `signal_table` payload-carried-structured-data pattern,
    `harness/models/hdl/signal_table.py`) -- one model instance serves
    every timing budget, since every request carries its own grounded
    contributions rather than a fixture-pinned set."""

    @property
    # frob:doc docs/modules/py-harness.md#models-timing
    def version(self) -> str:
        """Pure closed-form arithmetic; version bumps only on a formula change."""
        return "1"

    @property
    # frob:doc docs/modules/py-harness.md#models-timing
    def cost(self) -> int:
        """Cheapest tier: pure arithmetic over already-resolved citations."""
        return 1

    @property
    # frob:doc docs/modules/py-harness.md#models-timing
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="timing_budget",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            domain=("elec", "timing"),
            payload_kinds={CONTRIBUTIONS_PORT: CONTRIBUTIONS_KIND},
            required_regimes=(),
        )

    @property
    # frob:doc docs/modules/py-harness.md#models-timing
    def citation(self) -> str | None:
        """The model's own method is the tolerance-chain sum-vs-limit shape
        `04-structural-layer.md` sec. 5 documents; every per-value citation
        is the CONTRIBUTION's own, rendered separately (calc-book inputs)."""
        return "cuprite/04-structural-layer.md sec. 5 (contribution-sum budget closure)"

    @property
    # frob:doc docs/modules/py-harness.md#models-timing
    def output_unit(self) -> str | None:
        """Timing closure sums/limits are always nanoseconds (v1 posture)."""
        return "ns"

    # frob:doc docs/modules/py-harness.md#models-timing
    # frob:tests tests/harness/test_std_timing.py::test_timing_budget_model_estimate_matches_close_timing_budget
    def estimate(
        self,
        request: DischargeRequest,
        *,
        resolver: PayloadResolver | None = None,
    ) -> Result[Prediction, HarnessError]:
        """The claim's quantity is the closure sum in ns; `eps=0.0` (the
        arithmetic is exact given the contributions' own pessimal
        readings, no additional model error is introduced by summing)."""
        resolved = _resolve_contributions(request, resolver)
        if resolved.is_err:
            return Err(resolved.danger_err)
        table = resolved.danger_ok
        closed = close_timing_budget(
            table.budget_name, request.limit, table.contributions
        )
        if closed.is_err:
            return Err(closed.danger_err)
        closure = closed.danger_ok
        return Ok(Prediction(value=closure.sum_ns, eps=0.0, in_domain=True))


# frob:doc docs/modules/py-harness.md#models-timing
def timing_closure_given_loads(closure: TimingBudgetClosure) -> tuple[str, ...]:
    """Render a closed/violated `TimingBudgetClosure` as `Given.loads`
    entries carrying each contribution's citation inline -- the exact
    shape `regolith.backends.calc.inputs_from_given` already renders
    generically (`name: value unit`, `declared_literal` provenance), so
    a timing calc sheet's citations are visible through the ONE
    existing renderer with NO new rendering code (WO-156 deliverable 5/
    acceptance criterion 3)."""
    rows = []
    for name, ns, cite in zip(
        closure.contribution_names,
        closure.contribution_ns,
        closure.contribution_citations,
        strict=True,
    ):
        rows.append(f"{name}: {ns:g} ns  # {cite}")
    return tuple(rows)


__all__ = [
    "CLAIM_KIND",
    "CONTRIBUTIONS_KIND",
    "CONTRIBUTIONS_PORT",
    "LIGHT_SPEED_MM_PER_NS",
    "TimingBudgetClosure",
    "TimingBudgetModel",
    "TimingContribution",
    "TimingContributionTable",
    "close_timing_budget",
    "route_delay_ns",
    "stackup_v_p_mm_per_ns",
    "timing_closure_given_loads",
]
