"""INV-17 Type soundness (substrate/13-invariants.md).

Ledger statement:
    **No dimensionally inconsistent expression, no `==` on a continuous

Mechanism provided by: WO-02. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-17's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-02) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-02 pending: INV-17 mechanism + fixture", strict=True)
def test_inv_17_primary_violation() -> None:
    """Deliberate INV-17 violation must be caught once WO-02 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-17 deliberate-violation fixture + assertion"
    )
