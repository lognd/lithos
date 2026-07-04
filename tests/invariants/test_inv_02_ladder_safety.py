"""INV-2 Ladder safety (substrate/13-invariants.md).

Ledger statement:
    **No override mechanism converts `violated` into `discharged`.**

Mechanism provided by: WO-13. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-2's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-13) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "Blocked on the acceptance-record (ladder rungs 6/7) mechanism, "
        "which does not exist yet. The obligation/evidence status machinery "
        "(WO-13) landed and the orchestrator release gate is total, but "
        "`regolith.orchestrator.orchestrate` records NO waiver/assume/accept "
        "ledger (substrate/12 rungs 6-7): there is no override that attaches "
        "an acceptance record to a violated obligation, so the "
        "'acceptance never modifies status' half of INV-2 cannot be "
        "exercised. The re-keying half (rungs 1/2/4/5 change the obligation "
        "hash) reduces to INV-1, which is covered in "
        "test_inv_01_evidence_binding. Un-xfail when the waiver/assume ledger "
        "(sec. 8) lands."
    ),
    strict=True,
)
def test_inv_02_primary_violation() -> None:
    """Deliberate INV-2 violation must be caught once WO-13 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-2 deliberate-violation fixture + assertion"
    )
