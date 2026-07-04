"""INV-19 Promises, not actuals (substrate/13-invariants.md).

Ledger statement:
    **No system-level verdict depends on an artifact's internals except

Mechanism provided by: WO-12. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-19's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-12) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "Contract IR now builds real SystemNodes (WO-12/WO-19: boundary, "
        "reserves, flows, targets), and the L2 system checks (INV-7/8/15) "
        "read only that promise-level contract surface -- promises/boundary/ "
        "reserves, never an artifact internal. INV-19 holds BY CONSTRUCTION of "
        "that input set: the surface grammar has no way to express a "
        "system-level claim reaching an artifact internal, and the escalation "
        "opt-ins (`model=`, `measured`, `spice_extracted`) that WOULD reach one "
        "are not yet lowered. So there is no surface-expressible deliberate "
        "violation to catch here; the spec's test (edit an artifact internal "
        "without a contract change; assert zero system-obligation re-runs) is a "
        "MULTI-BUILD content-addressing check (INV-1/INV-10 territory) that "
        "needs escalation-edge lowering + a two-build harness, not just "
        "SystemNode population. Stays xfail with that accurate reason; NOT "
        "faked."
    ),
    strict=True,
)
def test_inv_19_primary_violation() -> None:
    """Deliberate INV-19 violation must be caught once WO-12 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-19 deliberate-violation fixture + assertion"
    )
