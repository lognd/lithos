"""INV-18 Reference determinism (substrate/13-invariants.md).

Ledger statement:
    **Every resolved reference has exactly one interpretation.**

Mechanism provided by: WO-08. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-18's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-08) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "The query engine does not resolve references yet. INV-18 needs "
        "cardinality-typed resolution that fails with E0301 on over/under-"
        "match, broken-orbit `any`, and cross-owner-without-join. "
        "regolith-lower `claims.rs` lowers references structurally 'with no "
        "ambiguity to report yet' -- E0301 is never emitted and "
        "`any`/orbit resolution is not wired -- so no ambiguity fixture can "
        "fail constructively through the facade. Blocked on WO-08 query "
        "resolution + WO-05 query grammar."
    ),
    strict=True,
)
def test_inv_18_primary_violation() -> None:
    """Deliberate INV-18 violation must be caught once WO-08 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-18 deliberate-violation fixture + assertion"
    )
