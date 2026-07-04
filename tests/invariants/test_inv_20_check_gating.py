"""INV-20 Check gating (substrate/13-invariants.md).

Ledger statement:
    **Nothing expensive runs until everything cheaper has passed for the

Mechanism provided by: WO-15. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-20's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-15) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "Parser granularity blocker LIFTED (WO-05 residual promotion): "
        "in-body malformation now emits `parse:0193` MALFORMED_IN_BODY "
        "ATTRIBUTED to its enclosing declaration subject (a secondary "
        "span into the subject header + a `SubjectError` CST node), so a "
        "per-subject parse-failure signal now exists. REMAINING blocker: "
        "the downstream per-subject gate itself (AD-17) -- rockhead-lower "
        "consuming the subject attribution to exclude exactly that "
        "subject -- plus the WO-15 deliberate-violation fixture, are not "
        "yet implemented (WO-19/WO-15, STUB WO-17 below)."
    ),
    strict=True,
)
def test_inv_20_primary_violation() -> None:
    """Deliberate INV-20 violation must be caught once WO-15 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-20 deliberate-violation fixture + assertion"
    )
