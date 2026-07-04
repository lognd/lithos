"""INV-7 Boundary subsumption (substrate/13-invariants.md).

Ledger statement:
    **Evidence transfers into any context whose boundary is contained in

Mechanism provided by: WO-12. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-7's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-12) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "No L2 boundary-subset check over real sources. INV-7 needs the "
        "contract-IR L2 check that requires an import's boundary to be an "
        "enclosing subset of the proven envelope, then a fixture widening an "
        "ambient past an import's to force an L2 failure. regolith-lower "
        "builds empty SystemNodes (no contract IR / boundary envelopes), so "
        "no containment is computed at the facade. Blocked on WO-12 contract "
        "IR + boundary-import checking over parsed sources."
    ),
    strict=True,
)
def test_inv_07_primary_violation() -> None:
    """Deliberate INV-7 violation must be caught once WO-12 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-7 deliberate-violation fixture + assertion"
    )
