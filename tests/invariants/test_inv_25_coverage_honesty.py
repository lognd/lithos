"""INV-25 Coverage honesty (regolith/13-invariants.md).

Ledger statement:
    **Evidence states the coverage it achieved, and partial coverage never
    reads as full.** Mechanism: swept obligations carry their domain;
    evidence carries ``coverage:``; the discharge rule compares claimed
    coverage against the obligation's domain, and a gap yields
    ``indeterminate`` by the margin rule's domain check.

Mechanism provided by: the harness discharge rule
(:mod:`regolith.harness.evidence`, the single home of the margin/status
rule) -- ``coverage < 1.0`` short-circuits to ``indeterminate`` BEFORE
the margin sign is consulted, so a partial sweep can never surface as
``discharged`` even when its worst sample clears the limit with room to
spare. This module is part of the WO-17 invariant suite: a spec change
that alters INV-25's proof argument must change this module in the same
commit.

Ledger test: "a sweep discharged at corners by a model without declared
monotonicity must come back indeterminate." The fixture drives a real
:class:`~regolith.harness.model.Model` through the shared
:meth:`Model.discharge` path (NOT a hand-built ``Evidence``): the same
model, same healthy margin, differs ONLY in whether it claims full
coverage -- honest full coverage discharges; a corner-only sweep of a
non-monotone model comes back indeterminate.
"""

from __future__ import annotations

from regolith.harness import MODEL_REGISTRY_VERSION
from regolith.harness.errors import HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.quantity import Interval
from regolith.harness.signature import ClaimSense, ModelSignature
from typani.result import Ok, Result

_CLAIM = "test.coverage_honesty"


class _SweepModel(Model):
    """A stress-style upper-bound model whose declared coverage is a knob.

    Stands in for "a model that sweeps at corners without declared
    monotonicity": its worst sample clears the limit with healthy
    margin, but it only claims ``coverage`` of the obligation's domain.
    """

    def __init__(self, coverage: float) -> None:
        self._coverage = coverage

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name=_CLAIM,
            claim_kind=_CLAIM,
            sense=ClaimSense.upper_bound(),
            inputs=("load",),
        )

    @property
    def version(self) -> str:
        return "1"

    @property
    def cost(self) -> int:
        return 1

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        # Worst-corner value well under the limit -> a healthy margin, so
        # the ONLY thing that can hold this back from `discharged` is the
        # coverage gap (that is the property under test).
        return Ok(Prediction(value=50.0, eps=0.0, coverage=self._coverage))


def _request() -> DischargeRequest:
    return DischargeRequest(
        claim_kind=_CLAIM, limit=100.0, inputs={"load": Interval.point(1.0)}
    )


def test_inv_25_full_coverage_with_healthy_margin_discharges() -> None:
    """The honest-pass baseline: full domain coverage + margin -> discharged."""
    evidence = _SweepModel(coverage=1.0).discharge(
        _request(), registry_version=MODEL_REGISTRY_VERSION
    )
    assert evidence.is_ok
    assert evidence.danger_ok.status.value == "discharged"


def test_inv_25_partial_coverage_never_reads_as_discharged() -> None:
    """Same healthy margin, but a corner-only (0.5) sweep must come back
    ``indeterminate`` -- partial coverage never reads as full (INV-25)."""
    evidence = _SweepModel(coverage=0.5).discharge(
        _request(), registry_version=MODEL_REGISTRY_VERSION
    )
    assert evidence.is_ok
    status = evidence.danger_ok.status.value
    assert status == "indeterminate", (
        f"partial coverage must be indeterminate, not {status!r} "
        "(INV-25: partial coverage never reads as full)"
    )
    assert status != "discharged"
