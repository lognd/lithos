"""INV-16 Converter non-instantaneity (substrate/13-invariants.md).

Ledger statement:
    **No algebraic loop crosses the continuous/discrete boundary.**

Mechanism: `regolith_sem::converter` builds the continuous/discrete
converter graph, applies the ZOH delta-by-type rule, and runs the
within-domain acyclicity check (E0105). That sound mechanism now exists
and is unit-tested in Rust (including the comparator-feeds-own-threshold
legal fixture and the combinational-cycle deliberate-violation fixture);
`regolith-lower` wires the acyclicity check as a real pass over the
converter graph.

This module is part of the WO-17 invariant suite: the implementation's
contract with the spec. A spec change that alters INV-16's proof
argument must change this module in the same commit.

The END-TO-END `.cupr` fixture stays xfail: the graph the lowering pass
builds is EMPTY because WO-05 leaves the elec behavioral bodies opaque,
so no honest `.cupr` fixture can populate it yet (see the accurate
blocker in the xfail reason below). Faking a pass would be dishonest;
the Rust unit tests are the real coverage until the grammar lands.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "TRUE BLOCKER: WO-05 body structuring, not the INV-16 mechanism. The "
        "sound converter graph + ZOH delta-by-type rule + within-domain "
        "acyclicity check (E0105) exist and are unit-tested in "
        "regolith_sem::converter (comparator-feeds-own-threshold legal; "
        "combinational-cycle caught), and regolith-lower runs the acyclicity "
        "check as a real pass. But the elec `spec:`/`ports:`/converter/"
        "`on`-event bodies are still `OpaqueIsland` after WO-05 (confirmed "
        "via the buck_converter CST snapshot), so the lowering pass builds an "
        "EMPTY graph over real `.cupr` -- no port kinds, no converter "
        "assignments, no combinational edges are typed. A sound end-to-end "
        "fixture is impossible until WO-05 promotes those behavioral bodies "
        "to typed CST (regolith-syntax, out of this WO's scope); a token-scan "
        "of the opaque islands would be the unsound text-scan heuristic WO-11 "
        "deliberately replaced. Un-xfail once WO-05 types the elec spec body "
        "and regolith-lower feeds it into ConverterGraph."
    ),
    strict=True,
)
def test_inv_16_primary_violation() -> None:
    """Deliberate INV-16 violation, end-to-end, once WO-05 types the body."""
    raise NotImplementedError(
        "Blocked on WO-05 elec spec-body promotion; mechanism unit-tested in "
        "regolith_sem::converter (Rust)."
    )
