"""INV-13 No dead uppers (substrate/13-invariants.md).

Ledger statement:
    **When both an upper contract and a lower realization are written, a

Mechanism provided by: WO-12. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-13's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-12) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-12 pending: INV-13 mechanism + fixture", strict=True)
def test_inv_13_primary_violation() -> None:
    """Deliberate INV-13 violation must be caught once WO-12 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-13 deliberate-violation fixture + assertion"
    )
