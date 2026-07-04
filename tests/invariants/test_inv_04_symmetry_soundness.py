"""INV-4 Symmetry soundness (substrate/13-invariants.md).

Ledger statement:
    **Entity-DB symmetry is under-approximate: a false symmetry is never

Mechanism provided by: WO-07. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-4's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-07) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-07 pending: INV-4 mechanism + fixture", strict=True)
def test_inv_04_primary_violation() -> None:
    """Deliberate INV-4 violation must be caught once WO-07 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-4 deliberate-violation fixture + assertion"
    )
