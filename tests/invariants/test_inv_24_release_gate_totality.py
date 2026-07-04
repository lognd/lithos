"""INV-24 Release-gate totality (substrate/13-invariants.md).

Ledger statement:
    **A `--release` build's report contains zero unaccepted violated or

Mechanism provided by: WO-13. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-24's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-13) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-13 pending: INV-24 mechanism + fixture", strict=True)
def test_inv_24_primary_violation() -> None:
    """Deliberate INV-24 violation must be caught once WO-13 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-24 deliberate-violation fixture + assertion"
    )
