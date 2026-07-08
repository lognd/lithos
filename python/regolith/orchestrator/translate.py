"""Translate a serialized ``Obligation`` into a harness ``DischargeRequest``.

Extracting a numeric discharge request from a serialized obligation is
orchestrator territory (regolith/07 sec. 2 note on ``DischargeRequest``):
the obligation's quantity expressions are text until resolution pins them,
and the harness consumes only the resolved form. This module does that
lowering for the scalar-comparison claim form and reports an explicit
:class:`Deferral` for anything it cannot resolve numerically -- never a
silent drop (INV-24 totality feeds on honest deferrals).

The numeric parsing here is deliberately conservative: it reads a leading
float off a bound/load expression (unit suffixes are the resolver's job,
not re-implemented here) and defers when a value is not yet a literal.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import ClaimForm1, Obligation
from regolith.harness import DischargeRequest, Interval
from regolith.harness.models.conformance import CLAIM_KIND_LOWER, CLAIM_KIND_UPPER
from regolith.harness.models.workload_realization import CLAIM_KIND as _REALIZATION_KIND
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# Comparators whose claim is an upper bound (value must stay below) vs a
# lower bound (value must stay above). Containment/temporal ops defer.
_UPPER_OPS = frozenset({"<", "<=", "peak<", "peak<="})
_LOWER_OPS = frozenset({">", ">="})

# A leading signed float (optionally followed by a unit we ignore here).
_LEADING_FLOAT = re.compile(r"\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")

# The conformance refinement sense (carried in `given.loads` by the core
# when both windows resolve) -> the harness conformance model's claim kind.
_CONFORMANCE_CLAIM_KIND = {"upper": CLAIM_KIND_UPPER, "lower": CLAIM_KIND_LOWER}

# The rule-3 derived-workload cause tag the core emits in `given.loads`
# for a realization edge it auto-allocated (`realization_obligation`,
# `regolith-lower/src/claims.rs`). Prefix match: the tag's tail is the
# realized intent's name, which this module does not need to parse.
_DERIVED_CAUSE_PREFIX = "derived(intent "

# The arbitrary matching constant the derived-workload identity model
# discharges against (see `regolith.harness.models.workload_realization`
# -- there is no physical quantity here, only a structural identity).
_REALIZATION_IDENTITY_LIMIT = 1.0

# Comparator tokens the predicate `rhs` may lead with, longest first so
# `<=`/`>=` win over `<`/`>`. The core lowers a `subject: predicate`
# claim line with a fixed `op="require"` (the comparator is inside the
# predicate text, `07` sec. 4), so the orchestrator splits it back out
# here to recover the claim's SENSE (upper/lower bound).
_COMPARATORS: tuple[str, ...] = ("peak<=", "peak<", "<=", ">=", "<", ">")


def _split_comparator(op: str, rhs: str) -> tuple[str, str] | None:
    """Recover ``(comparator, bound_text)`` from a claim's ``op``/``rhs``.

    A claim whose ``op`` is already a comparator keeps it (the bound is the
    whole ``rhs``). The lowering's placeholder ``op="require"`` instead
    carries the comparator at the head of ``rhs`` (``">= 6 dB"``); split it
    off. Returns ``None`` when no one-sided comparator is present (the
    caller defers -- a containment/equality/temporal predicate never lowers
    to a scalar bound here).
    """
    if op in _UPPER_OPS or op in _LOWER_OPS:
        return op, rhs
    if op == "require":
        head = rhs.lstrip()
        for comp in _COMPARATORS:
            if head.startswith(comp):
                return comp, head[len(comp) :]
    return None


class Deferral(BaseModel):
    """An obligation the orchestrator could not lower to a numeric request.

    Honest, greppable, and release-gated: a deferral is neither a pass nor
    a violation -- it says "no numeric obligation was formed here" and the
    release gate (INV-24) treats it as unresolved.
    """

    model_config = ConfigDict(frozen=True)

    reason: str
    detail: str


class GivenResolutionError(BaseModel):
    """D97 (sec. 8.4): a named given could not be resolved to a scalar.

    Never a guess: property-record evaluation over the environment box
    (worst corner via declared monotonicity, else the full-domain hull)
    and interface-envelope load extraction either produce a resolved
    value or this error, naming the exact given that failed -- carried
    into an INDETERMINATE discharge (never a silent drop).
    """

    model_config = ConfigDict(frozen=True)

    given: str
    detail: str

    def as_deferral(self) -> Deferral:
        """The existing :class:`Deferral` surface this error rides on."""
        return Deferral(
            reason="given_unresolved",
            detail=f"given {self.given!r} did not resolve: {self.detail}",
        )


# D97 item 4: regime tags LOWERING asserts from claim-kind construction
# (the "start with the WO-13 claim-kind table's guarantees" instruction).
# Every shipped `mech.*` closed-form claim kind is a static, linear-
# elastic model (regolith/07's WO-13 built-in models never model
# plasticity or dynamics); extend only where a kind's construction
# genuinely guarantees the tag.
_MECH_STATIC_REGIMES: tuple[str, ...] = ("linear_elastic", "static")


def _regimes_for(claim_kind: str) -> tuple[str, ...]:
    """The regime tags LOWERING asserts for ``claim_kind`` (D97 item 4)."""
    if claim_kind.startswith("mech."):
        return _MECH_STATIC_REGIMES
    return ()


def resolve_givens(
    loads: list[str],
) -> Result[dict[str, Interval], GivenResolutionError]:
    """D97 items (a)/(b): resolve ``given.loads`` lines to scalar intervals.

    Each ``name: value`` line either parses as a numeric interval (the
    worst-corner/full-domain-hull evaluation already performed upstream
    by the property-record/load-envelope extraction this orchestrator
    seam consumes) or is an honest, named resolution failure -- never a
    guess. Lines this module does not attempt to split on `:` (no colon
    present) are ignored, matching the existing `given.loads` shape.
    """
    resolved: dict[str, Interval] = {}
    for line in loads:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        name = name.strip()
        interval = _parse_interval(value)
        if interval is None:
            return Err(
                GivenResolutionError(
                    given=name,
                    detail=(
                        f"value {value.strip()!r} is not a resolved numeric interval"
                    ),
                )
            )
        resolved[name] = interval
    return Ok(resolved)


def _parse_float(text: str) -> float | None:
    """Read a leading float off ``text`` (unit suffix ignored), or ``None``."""
    match = _LEADING_FLOAT.match(text)
    if match is None:
        return None
    return float(match.group(1))


def _parse_interval(text: str) -> Interval | None:
    """Parse ``[lo, hi]`` or a bare point value into an :class:`Interval`."""
    stripped = text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        parts = stripped[1:-1].split(",")
        if len(parts) != 2:
            return None
        lo, hi = _parse_float(parts[0]), _parse_float(parts[1])
        if lo is None or hi is None:
            return None
        return Interval(lo=lo, hi=hi)
    point = _parse_float(stripped)
    if point is None:
        return None
    return Interval(lo=point, hi=point)


def _load_fields(loads: list[str]) -> dict[str, str]:
    """Split ``given.loads`` (``name: value`` text) into a raw string map.

    Unlike :func:`resolve_givens` this keeps non-numeric values (the
    conformance sense marker), leaving numeric parsing to the caller.
    """
    fields: dict[str, str] = {}
    for line in loads:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        fields[name.strip()] = value.strip()
    return fields


def _translate_conformance(
    obligation: Obligation,
) -> Result[DischargeRequest, Deferral]:
    """Lower a ``conforms`` obligation to a conformance-model request.

    INV-13/26 (the implicit-``by spec`` default): the compiler emits one
    conformance obligation per ``impl``/extern/import binding. When both the
    upper contract and the lower realization carried a resolved comparator
    bound, the core threads the two refinement windows into ``given.loads``
    (``conformance_sense``/``spec_bound``/``impl_bound``); this lowers them
    into the harness conformance model's request (limit = the spec bound,
    the single ``impl_bound`` input = the realization's bound). Absent those
    windows the obligation defers HONESTLY, naming the exact missing fields
    -- the compiler never invents a window the source did not state.
    """
    fields = _load_fields(obligation.given.loads)
    sense = fields.get("conformance_sense")
    spec_text = fields.get("spec_bound")
    impl_text = fields.get("impl_bound")
    if sense is None or spec_text is None or impl_text is None:
        return Err(
            Deferral(
                reason="conformance_windows_unresolved",
                detail=(
                    "conforms obligation carries no resolved "
                    "conformance_sense/spec_bound/impl_bound windows "
                    "(refinement-bound extraction is a WO-12 cut)"
                ),
            )
        )
    claim_kind = _CONFORMANCE_CLAIM_KIND.get(sense)
    spec_bound = _parse_float(spec_text)
    impl_bound = _parse_float(impl_text)
    if claim_kind is None or spec_bound is None or impl_bound is None:
        return Err(
            Deferral(
                reason="conformance_windows_unresolved",
                detail=f"conforms windows not numeric (sense={sense!r})",
            )
        )
    _log.debug(
        "translated conforms obligation subject=%s -> %s limit=%g impl_bound=%g",
        obligation.subject_ref,
        claim_kind,
        spec_bound,
        impl_bound,
    )
    return Ok(
        DischargeRequest(
            claim_kind=claim_kind,
            limit=spec_bound,
            inputs={"impl_bound": Interval(lo=impl_bound, hi=impl_bound)},
            deterministic=True,
            regimes=_regimes_for(claim_kind),
        )
    )


def _translate_realization(
    obligation: Obligation,
) -> Result[DischargeRequest, Deferral]:
    """Lower an `implies`-form realization obligation (EOPEN-15 rules 2/3).

    Only a rule-3 DERIVED edge lowers: its `cause: derived(intent ...)`
    tag (`given.loads`) marks a workload whose demand vector was copied
    VERBATIM from the intent it realizes (cuprite/05 sec. 1 rule 3), so
    "workload implies intent" is a structural identity -- always sound,
    zero model error -- and the harness's identity model
    (`regolith.harness.models.workload_realization`) discharges it.

    A DECLARED (non-derived) edge's implication is a genuine claim over
    the intent's own rate/state/latency demands (rule 2), and those
    quantities are not threaded through the obligation today (`intents:`
    bodies are opaque islands, WO-05 cut; `docs/audit/TRIAGE.md`). Rather
    than invent a window, this defers HONESTLY: the orchestrator forms no
    numeric request, so the release gate sees an indeterminate obligation
    -- loud, never a silent pass (INV-24/26).
    """
    fields = _load_fields(obligation.given.loads)
    cause = fields.get("cause", "")
    if not cause.startswith(_DERIVED_CAUSE_PREFIX):
        return Err(
            Deferral(
                reason="realization_not_derived_unverifiable",
                detail=(
                    "a declared realization edge's demand implication "
                    "needs the intent's own rate/state/latency quantities, "
                    "which are not threaded through the obligation (WO-05 "
                    "cut); only rule-3 derived (verbatim-copy) edges "
                    "discharge today"
                ),
            )
        )
    _log.debug(
        "translated derived-realization obligation subject=%s -> %s",
        obligation.subject_ref,
        _REALIZATION_KIND,
    )
    return Ok(
        DischargeRequest(
            claim_kind=_REALIZATION_KIND,
            limit=_REALIZATION_IDENTITY_LIMIT,
            inputs={},
            deterministic=True,
            regimes=_regimes_for(_REALIZATION_KIND),
        )
    )


def translate(obligation: Obligation) -> Result[DischargeRequest, Deferral]:
    """Lower ``obligation`` to a :class:`DischargeRequest`, or a deferral.

    Only the scalar-comparison claim form (``lhs op rhs``) lowers; the
    claim kind is the claim name if present, else the ``lhs`` text. A
    non-scalar form, an unknown comparator, or a non-literal bound each
    yields an explicit :class:`Deferral` the caller surfaces (never a
    silent pass).
    """
    form = obligation.claim.form
    if isinstance(form, ClaimForm1) and form.op == "conforms":
        return _translate_conformance(obligation)
    if isinstance(form, ClaimForm1) and form.op == "implies":
        return _translate_realization(obligation)
    if not isinstance(form, ClaimForm1):
        return Err(
            Deferral(
                reason="non_scalar_claim",
                detail=f"claim form {type(form).__name__} is not a scalar comparison",
            )
        )
    # The claim's sense (upper/lower) is the model signature's to declare
    # (regolith/07 sec. 4); here we only reject comparators that do not
    # lower to a one-sided scalar bound the harness can charge eps against.
    # The comparator may sit in `op` OR at the head of `rhs` (the core's
    # `op="require"` placeholder form) -- recover it either way.
    split = _split_comparator(form.op, form.rhs)
    if split is None:
        return Err(
            Deferral(reason="unsupported_op", detail=f"comparator {form.op!r} defers")
        )
    comparator, bound_text = split
    limit = _parse_float(bound_text)
    if limit is None:
        return Err(
            Deferral(
                reason="unresolved_limit", detail=f"bound {bound_text!r} not literal"
            )
        )
    claim_kind = obligation.claim.name or form.lhs
    # D97 (sec. 8.4): resolve every named given honestly -- a load line
    # that never became a numeric interval defers naming the given,
    # never a silent drop.
    resolved = resolve_givens(obligation.given.loads)
    if resolved.is_err:
        given_error = resolved.danger_err
        _log.info(
            "obligation %s: given %r unresolved (%s)",
            obligation.subject_ref,
            given_error.given,
            given_error.detail,
        )
        return Err(given_error.as_deferral())
    inputs = resolved.danger_ok
    regimes = _regimes_for(claim_kind)
    _log.debug(
        "translated obligation subject=%s -> claim_kind=%s limit=%g op=%s "
        "inputs=%s regimes=%s",
        obligation.subject_ref,
        claim_kind,
        limit,
        comparator,
        sorted(inputs),
        regimes,
    )
    return Ok(
        DischargeRequest(
            claim_kind=claim_kind,
            limit=limit,
            inputs=inputs,
            deterministic=True,
            regimes=regimes,
        )
    )
