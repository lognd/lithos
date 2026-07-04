"""INV-25 Coverage honesty (substrate/13-invariants.md).

Ledger statement:
    **Evidence states the coverage it achieved, and partial coverage never

Mechanism provided by: WO-13. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-25's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-13) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-13 pending: INV-25 mechanism + fixture", strict=True)
def test_inv_25_primary_violation() -> None:
    """Deliberate INV-25 violation must be caught once WO-13 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-25 deliberate-violation fixture + assertion"
    )
