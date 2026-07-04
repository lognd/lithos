"""INV-11 Monomorphization totality (substrate/13-invariants.md).

Ledger statement:
    **Every static check runs at every instantiation point of every

Mechanism provided by: WO-04. This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-11's proof argument must change this module in
the same commit. The primary deliberate-violation fixture is xfail until
its mechanism (WO-04) lands (STUB WO-17).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason=(
        "WO-19 wired a monomorphization SEAM (regolith-lower checks.rs "
        "enumerates every generic declaration -- typed `GenericParams` "
        "header -- as an expansion point). REMAINING blocker: the "
        "concrete instantiation ARGUMENTS (`PatternOf<TappedHole<M3>>` "
        "at a use site) are still opaque -- WO-05 does not type generic "
        "USE-sites (only decl headers carry a `GenericParams` node), so "
        "a per-point-only failure cannot yet be constructed or expanded, "
        "and the seam's result is not surfaced on the payload. Blocked "
        "on WO-05 typing generic use-sites."
    ),
    strict=True,
)
def test_inv_11_primary_violation() -> None:
    """Deliberate INV-11 violation must be caught once generic use-site
    instantiation arguments are typed (WO-05) and expandable."""
    raise NotImplementedError(
        "STUB WO-17: INV-11 deliberate-violation fixture needs typed "
        "generic use-site instantiation arguments (WO-05 residual)"
    )
