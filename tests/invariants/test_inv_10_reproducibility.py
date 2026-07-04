"""INV-10 Reproducibility (substrate/13-invariants.md).

Ledger statement:
    **Given (source, lockfile, tool versions): all decisions and evidence

Mechanism provided by: WO-14. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-10's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-14) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-14 pending: INV-10 mechanism + fixture", strict=True)
def test_inv_10_primary_violation() -> None:
    """Deliberate INV-10 violation must be caught once WO-14 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-10 deliberate-violation fixture + assertion"
    )
