"""INV-3 Hint droppability (substrate/13-invariants.md).

Ledger statement:
    **For a fixed resolved design, verdicts are invariant under removal of

Mechanism provided by: WO-13. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-3's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-13) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "No end-to-end hint channel to strip. INV-3 needs a resolved design "
        "discharged twice -- once with `@hint`/`policy: prefer` present, once "
        "with them removed -- and the two verdict sets diffed. Neither half is "
        "reachable: the parser does not surface `@hint`/`policy: prefer` into "
        "a resolved design the facade discharges (WO-05 leaves these bodies "
        "opaque), and `compiler.check` does not run candidate enumeration or "
        "discharge (resolutions=0, no candidate loop). Blocked on WO-05 (hint "
        "grammar) + the orchestrator candidate/discharge loop over real "
        "sources."
    ),
    strict=True,
)
def test_inv_03_primary_violation() -> None:
    """Deliberate INV-3 violation must be caught once WO-13 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-3 deliberate-violation fixture + assertion"
    )
