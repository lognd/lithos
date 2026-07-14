"""Request/evidence capture for the D226 QA harness (WO-117).

``Model.discharge`` (``regolith/harness/model.py``) is the ONE shared,
non-abstract choke point every concrete model's claim discharge flows
through -- it calls the subclass's own ``estimate`` override, then
folds the result through the single margin rule into an ``Evidence``.
Wrapping THIS method (never the per-subclass ``estimate`` overrides,
which are separate function objects a base-class patch cannot see)
captures, for every real claim discharge in a ``staged_build`` run, the
exact resolved ``DischargeRequest`` (claim kind, worst-corner-boxed
inputs, limit) paired with the ``Evidence`` it produced (model id,
value, margin, verdict) -- in dispatch order, keyed by model id.

This module captures DATA IN TRANSIT ONLY: it never imports, calls, or
re-implements any model's own formula code, so an oracle built from a
``CapturedCall`` is still an independent computation of the same
physical quantity from the same resolved inputs a real discharge used.

WO117-F1 (named cut, D226 scope note): the calc sheet's own ``inputs``
tuple (``regolith.backends.calc.inputs_from_given``) reflects only a
claim's ``given:`` block provenance (materials/loads/refs) and is
EMPTY for any obligation whose numeric inputs are resolved via frame/
section extraction rather than a declared ``given:`` (the beam/DFM/
bearing families sampled here are exactly this shape) -- so a literal
"read the committed calc-book JSON's inputs and recompute" is not
possible for most of the fleet's discharged families today. This
capture module is the honest substitute: it reads the SAME resolved
scalar inputs the real discharge consumed (captured at the harness
boundary, the one place they exist as numbers before the calc book's
provenance-string projection), which is the actual quantity D226 asks
to be independently re-verified. Reopen: give ``inputs_from_given`` a
frame/section-resolution reader so the calc book itself carries these
numbers (a WO-114-lineage follow-up, not this WO's scope).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from regolith.harness.model import DischargeRequest, Model


@dataclass(frozen=True)
class CapturedCall:
    """One real discharge: the resolved request paired with its evidence."""

    model_id: str
    claim_kind: str
    inputs: dict[str, tuple[float, float]]
    limit: float
    value: float | None
    margin: float | None
    status: str | None


@dataclass
class Capture:
    """Every discharge call seen while the capture context was active."""

    calls: list[CapturedCall] = field(default_factory=list)

    def by_model(self, model_id_prefix: str) -> list[CapturedCall]:
        """Every captured call whose ``model_id`` starts with the prefix."""
        return [c for c in self.calls if c.model_id.startswith(model_id_prefix)]


def _bits_to_f64(bits: int) -> float:
    """Local bit-pattern decode (mirrors ``harness.quantity.bits_to_f64``,
    reimplemented here so this capture module needs no harness import
    beyond the ``Model``/``DischargeRequest`` types it wraps)."""
    import struct

    return struct.unpack("<d", struct.pack("<Q", bits))[0]


@contextmanager
def capture_discharge_calls() -> Iterator[Capture]:
    """Record every ``Model.discharge`` call's request + evidence.

    Patches the shared base-class method for the duration of the
    ``with`` block only; restores the original unconditionally.
    """
    cap = Capture()
    original = Model.discharge

    def wrapped(self: Model, request: DischargeRequest, **kwargs: object):
        result = original(self, request, **kwargs)
        value = margin = None
        status = None
        if result.is_ok:
            evidence = result.danger_ok
            value = _bits_to_f64(evidence.value_bits)
            margin = _bits_to_f64(evidence.margin_bits)
            status = evidence.status.value if hasattr(evidence.status, "value") else str(evidence.status)
        cap.calls.append(
            CapturedCall(
                model_id=self.model_id,
                claim_kind=request.claim_kind,
                inputs={k: (iv.lo, iv.hi) for k, iv in request.inputs.items()},
                limit=request.limit,
                value=value,
                margin=margin,
                status=status,
            )
        )
        return result

    Model.discharge = wrapped  # type: ignore[method-assign]
    try:
        yield cap
    finally:
        Model.discharge = original  # type: ignore[method-assign]
