"""INV-27 File-layout invariance (substrate/13-invariants.md).

Ledger statement:
    **For a fixed set of top-level declarations and pinned dependencies,

Mechanism provided by: WO-10. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-27's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-10) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="WO-10 pending: INV-27 mechanism + fixture", strict=True)
def test_inv_27_primary_violation() -> None:
    """Deliberate INV-27 violation must be caught once WO-10 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-27 deliberate-violation fixture + assertion"
    )
