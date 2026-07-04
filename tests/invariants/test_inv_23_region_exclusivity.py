"""INV-23 Region exclusivity (substrate/13-invariants.md).

Ledger statement:
    **Nothing enters an owned exclusion region without a declared overlap

Mechanism provided by: WO-09. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-23's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-09) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-09 pending: INV-23 mechanism + fixture", strict=True)
def test_inv_23_primary_violation() -> None:
    """Deliberate INV-23 violation must be caught once WO-09 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-23 deliberate-violation fixture + assertion"
    )
