"""INV-16 Converter non-instantaneity (substrate/13-invariants.md).

Ledger statement:
    **No algebraic loop crosses the continuous/discrete boundary.**

Mechanism provided by: WO-11. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-16's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-11) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-11 pending: INV-16 mechanism + fixture", strict=True)
def test_inv_16_primary_violation() -> None:
    """Deliberate INV-16 violation must be caught once WO-11 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-16 deliberate-violation fixture + assertion"
    )
