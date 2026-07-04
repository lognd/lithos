"""INV-3 Hint droppability (substrate/13-invariants.md).

Ledger statement:
    **For a fixed resolved design, verdicts are invariant under removal of

Mechanism provided by: WO-13. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-3's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-13) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-13 pending: INV-3 mechanism + fixture", strict=True)
def test_inv_03_primary_violation() -> None:
    """Deliberate INV-3 violation must be caught once WO-13 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-3 deliberate-violation fixture + assertion"
    )
