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


@pytest.mark.xfail(
    reason=(
        "Blocked on structured region input, NOT the WO-09 mechanism: the "
        "borrow machinery treats `regions_touched` identically to `modifies` "
        "(the correct rule) and the FE-8 L1 name-resolution pass "
        "(`rockhead_sem::resolve`) landed, but neither makes region "
        "exclusivity reachable end-to-end -- `rockhead-lower` never builds "
        "`EntityKind::Region`/`RegionPolicy` entities or populates "
        "`PredictedDelta.regions_touched` because WO-05 leaves keepout/route/"
        "placement bodies as opaque islands (BE-7). A real green fixture "
        "needs region deltas flowing from parsed source."
    ),
    strict=True,
)
def test_inv_23_primary_violation() -> None:
    """Deliberate INV-23 violation must be caught once WO-09 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-23 deliberate-violation fixture + assertion"
    )
