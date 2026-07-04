"""Translate a serialized ``Obligation`` into a harness ``DischargeRequest``.

Extracting a numeric discharge request from a serialized obligation is
orchestrator territory (substrate/07 sec. 2 note on ``DischargeRequest``):
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

from rockhead._schema.models import ClaimForm1, Obligation
from rockhead.harness import DischargeRequest, Interval
from rockhead.logging_setup import get_logger

_log = get_logger(__name__)

# Comparators whose claim is an upper bound (value must stay below) vs a
# lower bound (value must stay above). Containment/temporal ops defer.
_UPPER_OPS = frozenset({"<", "<=", "peak<", "peak<="})
_LOWER_OPS = frozenset({">", ">="})

# A leading signed float (optionally followed by a unit we ignore here).
_LEADING_FLOAT = re.compile(r"\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")


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
    if not isinstance(form, ClaimForm1):
        return Err(
            Deferral(
                reason="non_scalar_claim",
                detail=f"claim form {type(form).__name__} is not a scalar comparison",
            )
        )
    # The claim's sense (upper/lower) is the model signature's to declare
    # (substrate/07 sec. 4); here we only reject comparators that do not
    # lower to a one-sided scalar bound the harness can charge eps against.
    if form.op not in _UPPER_OPS and form.op not in _LOWER_OPS:
        return Err(
            Deferral(reason="unsupported_op", detail=f"comparator {form.op!r} defers")
        )
    limit = _parse_float(form.rhs)
    if limit is None:
        return Err(
            Deferral(
                reason="unresolved_limit", detail=f"bound {form.rhs!r} not literal"
            )
        )
    claim_kind = obligation.claim.name or form.lhs
    inputs = _parse_loads(obligation.given.loads)
    _log.debug(
        "translated obligation subject=%s -> claim_kind=%s limit=%g op=%s inputs=%s",
        obligation.subject_ref,
        claim_kind,
        limit,
        form.op,
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
