"""INV-16 Converter non-instantaneity (substrate/13-invariants.md).

Ledger statement:
    **No algebraic loop crosses the continuous/discrete boundary.**

Mechanism provided by: WO-11. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-16's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-11) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "No clocked-body/converter graph over real sources. INV-16 needs the "
        "elec profile to build the continuous/discrete converter graph from "
        "parsed `.cupr`, apply the ZOH delta-by-type rule, and run the "
        "within-domain acyclicity check -- then the comparator-feeds-own-"
        "threshold fixture (legal, loop-free) and a combinational-cycle "
        "fixture (must fail statically). regolith-lower/regolith-sem does not "
        "construct these graphs; WO-05 leaves clocked/converter bodies "
        "opaque. Blocked on WO-11 (profiles) + WO-05 body structuring."
    ),
    strict=True,
)
def test_inv_16_primary_violation() -> None:
    """Deliberate INV-16 violation must be caught once WO-11 lands."""
    raise NotImplementedError(
        "STUB WO-17: INV-16 deliberate-violation fixture + assertion"
    )
