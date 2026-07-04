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


@pytest.mark.xfail(reason="WO-15 pending: INV-20 mechanism + fixture", strict=True)
def test_inv_20_primary_violation() -> None:
    """Deliberate INV-20 violation must be caught once WO-15 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-20 deliberate-violation fixture + assertion"
    )
