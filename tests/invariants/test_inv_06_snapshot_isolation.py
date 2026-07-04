"""INV-6 Snapshot isolation (substrate/13-invariants.md).

Ledger statement:
    **No statement observes a sibling's effects.** Mechanism: sibling

Mechanism provided by: WO-07. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-6's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-07) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "No end-to-end scope/query channel to violate. INV-6 needs each "
        "reference channel (names, queries, datums, profile exports) to be "
        "attempted against a sibling and statically refused. regolith-lower "
        "leaves scope/query bodies opaque (WO-05 BE-7) and no query resolves "
        "against a scope-entry snapshot through the facade, so a "
        "sibling-observation attempt cannot be constructed. Blocked on WO-05 "
        "structuring scope/query bodies + WO-08 query resolution + WO-10 "
        "scope snapshots."
    ),
    strict=True,
)
def test_inv_06_primary_violation() -> None:
    """Deliberate INV-6 violation must be caught once WO-07 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-6 deliberate-violation fixture + assertion"
    )
