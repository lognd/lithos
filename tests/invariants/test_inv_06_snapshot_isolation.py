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
        "No end-to-end scope/query RESOLUTION channel to violate -- the true "
        "residual blocker, distinct from the INV-04/05/23 grammar gap that "
        "WO-05/WO-19 closed this cycle. INV-6 needs each reference channel "
        "(names, queries, datums, profile exports) to be RESOLVED against a "
        "scope-entry snapshot and a sibling reference statically refused. "
        "regolith-lower now populates ownership/region/symmetry deltas from "
        "typed source, but it still runs no query engine (WO-08) against "
        "per-scope-entry snapshots (WO-10): `run_checks` never resolves a "
        "name/query against a sibling's committed snapshot, so a "
        "sibling-observation attempt has nothing to be refused by. Blocked on "
        "WO-08 query resolution + WO-10 scope-entry snapshots wired into the "
        "lowering pipeline, not on the parser."
    ),
    strict=True,
)
def test_inv_06_primary_violation() -> None:
    """Deliberate INV-6 violation must be caught once WO-07 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-6 deliberate-violation fixture + assertion"
    )
