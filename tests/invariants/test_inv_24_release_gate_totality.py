"""INV-24 Release-gate totality (regolith/13-invariants.md).

Ledger statement:
    **A `--release` build's report contains zero unaccepted violated or
    indeterminate obligations, and every acceptance is listed.**

Mechanism provided by: WO-13 (obligations) + the orchestrator release
gate. The orchestrator routes every obligation through the total harness
path and enforces the gate: any ``violated``/``indeterminate``/deferred
obligation that is not accepted fails ``--release`` (there is no
waiver/assume ledger yet, so nothing is accepted -- strictly conservative).
This is the deliberate-violation fixture the ledger statement requires.
"""

from __future__ import annotations

from regolith.harness.evidence import build_evidence
from regolith.orchestrator import ObligationResult, release_gate
from regolith.orchestrator.translate import Deferral


def _result(*, value: float, limit: float, subject: str) -> ObligationResult:
    """An upper-bound obligation result with honest margin math."""
    evidence = build_evidence(
        model_id="test.model@1",
        claim_kind="stress",
        sense_upper=True,
        value=value,
        eps=0.0,
        limit=limit,
        coverage=1.0,
        cost=1,
        in_domain=True,
        deterministic=True,
        registry_version="test-1",
        inputs_digest="d",
    )
    return ObligationResult(key=f"k:{subject}", subject_ref=subject, evidence=evidence)


def test_inv_24_all_discharged_passes_release() -> None:
    """A report where every obligation discharged clears the gate."""
    results = (_result(value=50.0, limit=100.0, subject="a"),)
    assert results[0].is_resolved
    assert release_gate(results).is_ok


def test_inv_24_unaccepted_violation_fails_release() -> None:
    """A single unaccepted violated obligation refuses the release build."""
    results = (
        _result(value=50.0, limit=100.0, subject="ok"),
        _result(value=150.0, limit=100.0, subject="bad"),  # violated
    )
    assert results[1].is_violated
    gate = release_gate(results)
    assert gate.is_err
    assert gate.danger_err.kind == "release_gate_failed"


def test_inv_24_deferred_obligation_fails_release() -> None:
    """A deferral (no verdict formed) is not proven, so it gates release."""
    deferred = ObligationResult(
        key="k:deferred",
        subject_ref="deferred",
        deferral=Deferral(reason="no_model", detail="no harness model"),
    )
    assert deferred.is_indeterminate
    assert release_gate((deferred,)).is_err
