"""Request/evidence capture for the D226 QA harness (WO-117).

``Model.discharge`` (``regolith/harness/model.py``) is the ONE shared,
non-abstract choke point every claim discharge flows through -- it
calls the subclass's own ``estimate`` override, then folds the result
through the single margin rule into an ``Evidence``. Wrapping THIS
method (never the per-subclass ``estimate`` overrides, which are
separate function objects a base-class patch cannot see) captures, for
every real discharge in a ``staged_build`` run, the exact resolved
``DischargeRequest`` (claim kind, interval-boxed inputs, limit, payload
bytes) paired with the ``Evidence`` it produced (model id, value, eps,
margin, verdict) -- in dispatch order.

This module captures DATA IN TRANSIT ONLY: it never imports, calls, or
re-implements any model's formula code, so an oracle fed from a
``CapturedCall`` is an independent recomputation of the same physical
quantity from the same resolved inputs the real discharge consumed.

WO117-F2 (named scope note): the calc sheet's own ``inputs`` tuple
(``regolith.backends.calc.inputs_from_given``) reflects only a claim's
``given:`` provenance pins (materials/loads/refs) and is EMPTY for any
obligation whose numeric inputs resolve via frame/section/record
extraction (the beam/DFM/bearing families are exactly this shape) --
so a literal "read the committed calc-book JSON and recompute" cannot
reach most discharged families today. This capture is the honest
substitute: it reads the SAME resolved scalar inputs the real
discharge consumed, at the one boundary where they exist as numbers
before the calc book's provenance-string projection. Reopen: thread
the resolved numerics onto the calc sheet itself (a WO-114-lineage
increment), then point the oracles at the sheet bytes directly.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from regolith.harness.model import DischargeRequest, Model
from regolith.orchestrator.payload_store import PayloadResolver


@dataclass(frozen=True)
class CapturedCall:
    """One real discharge: the resolved request paired with its evidence.

    ``inputs`` are the request's interval endpoints per port;
    ``payloads`` are the request's RAW payload bytes per port (resolved
    through the same resolver handle the model received -- data, not
    model code). Evidence fields are ``None`` when the discharge
    returned ``Err`` (the indeterminate path).
    """

    model_id: str
    claim_kind: str
    sense_upper: bool
    inputs: dict[str, tuple[float, float]]
    limit: float
    payloads: dict[str, bytes]
    value: float | None
    eps: float | None
    margin: float | None
    status: str | None


@dataclass
class Capture:
    """Every discharge call seen while the capture context was active."""

    calls: list[CapturedCall] = field(default_factory=list)

    # frob:waive TEST005 reason="test-file fixture/helper with environment-gated branches (tool-absent paths unreachable in a kicad-less env); TEST005 measuring test code is a tool quirk (TEST001 skips test files, TEST005 does not) -- FROBLEMS 2026-07-19"
    def by_model(self, model_id_prefix: str) -> list[CapturedCall]:
        """Captured calls whose ``model_id`` starts with the prefix."""
        return [c for c in self.calls if c.model_id.startswith(model_id_prefix)]

    # frob:waive TEST005 reason="test-file fixture/helper with environment-gated branches (tool-absent paths unreachable in a kicad-less env); TEST005 measuring test code is a tool quirk (TEST001 skips test files, TEST005 does not) -- FROBLEMS 2026-07-19"
    def model_ids(self) -> set[str]:
        """Every distinct model id captured."""
        return {c.model_id for c in self.calls}


def _bits_to_f64(bits: int) -> float:
    """Decode an f64 bit pattern (the evidence wire encoding).

    Local ``struct`` decode -- this module deliberately imports nothing
    from ``regolith.harness`` beyond the two types it wraps.
    """
    return struct.unpack("<d", struct.pack("<Q", bits))[0]


def _resolve_payloads(
    request: DischargeRequest, resolver: PayloadResolver | None
) -> dict[str, bytes]:
    """Fetch every payload port's raw bytes via the call's own resolver.

    Data only: the resolver is the orchestrator's content-addressed
    byte store; no record model is constructed here.
    """
    if resolver is None or not request.payloads:
        return {}
    out: dict[str, bytes] = {}
    for port, ref in request.payloads.items():
        resolved = resolver(ref.digest)
        if resolved.is_ok:
            out[port] = resolved.danger_ok
    return out


@contextmanager
def capture_discharge_calls() -> Iterator[Capture]:
    """Record every ``Model.discharge`` call's request + evidence.

    Patches the shared base-class method for the duration of the
    ``with`` block only; restores the original unconditionally.
    """
    cap = Capture()
    original = Model.discharge

    def wrapped(
        self: Model,
        request: DischargeRequest,
        *,
        registry_version: str,
        pack_name: str = "regolith",
        pack_version: str | None = None,
        resolver: PayloadResolver | None = None,
    ):
        result = original(
            self,
            request,
            registry_version=registry_version,
            pack_name=pack_name,
            pack_version=pack_version,
            resolver=resolver,
        )
        value = eps = margin = None
        status = None
        if result.is_ok:
            evidence = result.danger_ok
            value = _bits_to_f64(evidence.value_bits)
            eps = _bits_to_f64(evidence.eps_bits)
            margin = _bits_to_f64(evidence.margin_bits)
            raw_status = evidence.status
            status = getattr(raw_status, "value", str(raw_status))
        cap.calls.append(
            CapturedCall(
                model_id=self.model_id,
                claim_kind=request.claim_kind,
                sense_upper=self.signature.sense.upper,
                inputs={k: (iv.lo, iv.hi) for k, iv in request.inputs.items()},
                limit=request.limit,
                payloads=_resolve_payloads(request, resolver),
                value=value,
                eps=eps,
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
