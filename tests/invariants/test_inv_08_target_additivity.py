"""INV-8 Target additivity (substrate/13-invariants.md).

Ledger statement:
    **Contract-level base evidence is always valid under a target;

Mechanism provided by: WO-12. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-8's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-12) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "No target/reserve model over real sources. INV-8 needs target and "
        "reserved-region constructs plus the base-contract-immutability check "
        "(a target whose routing crosses a base region is rejected; a "
        "base-perturbing target invalidates exactly the touched subjects). "
        "regolith-lower has no target/reserve lowering and builds empty "
        "SystemNodes, so neither the syntactic rejection nor the "
        "content-addressed reuse/invalidation is exercisable. Blocked on "
        "WO-12 contract IR (targets + reserves)."
    ),
    strict=True,
)
def test_inv_08_primary_violation() -> None:
    """Deliberate INV-8 violation must be caught once WO-12 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-8 deliberate-violation fixture + assertion"
    )
