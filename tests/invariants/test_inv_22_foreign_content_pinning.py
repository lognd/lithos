"""INV-22 Foreign-content pinning (substrate/13-invariants.md).

Ledger statement:
    **All foreign content -- imports, externs, registry records, format

Mechanism provided by: WO-16. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-22's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-16) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-16 pending: INV-22 mechanism + fixture", strict=True)
def test_inv_22_primary_violation() -> None:
    """Deliberate INV-22 violation must be caught once WO-16 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-22 deliberate-violation fixture + assertion"
    )
