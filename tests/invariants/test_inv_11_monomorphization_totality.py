"""INV-11 Monomorphization totality (substrate/13-invariants.md).

Ledger statement:
    **Every static check runs at every instantiation point of every

Mechanism provided by: WO-04. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-11's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-04) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-04 pending: INV-11 mechanism + fixture", strict=True)
def test_inv_11_primary_violation() -> None:
    """Deliberate INV-11 violation must be caught once WO-04 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-11 deliberate-violation fixture + assertion"
    )
