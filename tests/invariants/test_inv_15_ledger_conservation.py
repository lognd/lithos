"""INV-15 Ledger conservation (substrate/13-invariants.md).

Ledger statement:
    **Every conservation ledger (DOF, sketch DOF, driver/load,

Mechanism provided by: WO-12. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-15's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-12) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "INV-15 mechanism landed in Rust (regolith-sem profile: the DOF ledger "
        "is driven from the typed walk CST; conservation is unit-tested in "
        "profile::unit_tests::deliberate_imbalance_is_caught). This CROSS-BOUNDARY "
        "fixture stays xfail until WO-19 lowering feeds populated walks/ledgers "
        "through the FFI end-to-end (regolith-lower contracts still build empty "
        "SystemNodes)."
    ),
    strict=True,
)
def test_inv_15_primary_violation() -> None:
    """Deliberate INV-15 violation must be caught once WO-12 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-15 deliberate-violation fixture + assertion"
    )
