"""INV-5 Ownership finality (substrate/13-invariants.md).

Ledger statement:
    **Single ownership and borrow verdicts hold on the realized artifact.**

Mechanism provided by: WO-09. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-5's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-09) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-09 pending: INV-5 mechanism + fixture", strict=True)
def test_inv_05_primary_violation() -> None:
    """Deliberate INV-5 violation must be caught once WO-09 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-5 deliberate-violation fixture + assertion"
    )
