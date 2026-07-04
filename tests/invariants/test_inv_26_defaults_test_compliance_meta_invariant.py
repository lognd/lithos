"""INV-26 Defaults-test compliance (meta-invariant) (substrate/13-invariants.md).

Ledger statement:
    **Every default behavior in either language is conservative, local in

Mechanism provided by: WO-15. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-26's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-15) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "The enumerated defaults are not reachable end-to-end. INV-26 is a "
        "meta-invariant requiring, per default (free-variable resolution, "
        "implicit `by spec`, local tolerance allocation, canonical `any`, "
        "eager candidate acceptance, derived workloads), a case where the "
        "default is wrong with a LOUD failure. Each default depends on "
        "resolution/candidate/query machinery not yet wired through the "
        "facade (resolutions=0 over the corpus; no candidate loop in "
        "`check()`; no `any`-orbit or derived-workload lowering), so no "
        "default-wrong case can be constructed. Blocked on WO-04/08/12 "
        "default-resolution wiring."
    ),
    strict=True,
)
def test_inv_26_primary_violation() -> None:
    """Deliberate INV-26 violation must be caught once WO-15 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-26 deliberate-violation fixture + assertion"
    )
