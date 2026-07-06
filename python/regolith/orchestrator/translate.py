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

    Unlike :func:`_parse_loads` this keeps non-numeric values (the
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
        )
    )


def _parse_loads(loads: list[str]) -> dict[str, Interval]:
    """Parse ``given.loads`` lines (``name: value``) into input intervals."""
    inputs: dict[str, Interval] = {}
    for line in loads:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        interval = _parse_interval(value)
        if interval is not None:
            inputs[name.strip()] = interval
    return inputs


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
    inputs = _parse_loads(obligation.given.loads)
    _log.debug(
        "translated obligation subject=%s -> claim_kind=%s limit=%g op=%s inputs=%s",
        obligation.subject_ref,
        claim_kind,
        limit,
        comparator,
        sorted(inputs),
    )
    return Ok(
        DischargeRequest(
            claim_kind=claim_kind,
            limit=limit,
            inputs=inputs,
            deterministic=True,
        )
    )
