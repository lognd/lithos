"""INV-18 Reference determinism (substrate/13-invariants.md).

Ledger statement:
    **Every resolved reference has exactly one interpretation.**

Mechanism provided by: WO-08. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-18's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-08) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-08 pending: INV-18 mechanism + fixture", strict=True)
def test_inv_18_primary_violation() -> None:
    """Deliberate INV-18 violation must be caught once WO-08 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-18 deliberate-violation fixture + assertion"
    )
