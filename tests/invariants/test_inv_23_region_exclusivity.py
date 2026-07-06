"""INV-23 Region exclusivity (regolith/13-invariants.md).

Ledger statement:
    **Nothing enters an owned exclusion region without a declared overlap
    join.**

Mechanism provided by: WO-09 (region conflict = the borrow machinery) +
WO-05 (typed region statements) + WO-19 (`regolith-lower` region-entity
population). This module is part of the WO-17 invariant suite: the
implementation's contract with the spec. A spec change that alters
INV-23's proof argument must change this module in the same commit.

End-to-end: WO-05 now types `region`/`keepout`/`route` statements, and
`regolith-lower` (`ownership.rs`) builds `EntityKind::Region` entities
with a `RegionPolicy` and populates `PredictedDelta.regions_touched` from
that parsed source. Routing into an owned exclusion region is the SAME
borrow conflict as modifying a borrowed face (E0302), caught by the
ownership checker -- not a post-hoc rule pass. A declared `join` is the
explicit overlap that exempts it.
"""

from __future__ import annotations

import json

from regolith import compiler

# INV-23 diagnostic code: a region conflict is a borrow conflict.
_BORROW_CONFLICT = {"family": "references", "offset": 2}  # E0302


def _codes(payload: dict) -> list[dict]:
    return [d["code"] for d in payload["diagnostics"]]


def test_inv_23_route_into_a_keepout_is_a_conflict(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The deliberate INV-23 violation: `route trace into solar` enters
    an owned exclusion region (`keepout solar`) with no declared join.
    This must fail as a borrow conflict, not slip through."""
    src = "part p:\n    keepout solar\n    route trace into solar\n"
    path = tmp_path / "region.hem"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    assert _BORROW_CONFLICT in _codes(payload), (
        "routing into an owned exclusion region must be a borrow conflict "
        f"(INV-23): {payload['diagnostics']}"
    )


def test_inv_23_declared_join_is_exempt(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The honest negative control: a declared `join` is the explicit
    overlap declaration that legalizes entering the region."""
    src = "part p:\n    keepout solar\n    route trace join solar\n"
    path = tmp_path / "region_ok.hem"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    assert _BORROW_CONFLICT not in _codes(payload), payload["diagnostics"]


def test_inv_23_arbitration_region_is_shared(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A second honest control: an arbitration-policy region is shared,
    so routing into it is not a conflict."""
    src = "part p:\n    region shared arbitration\n    route trace into shared\n"
    path = tmp_path / "region_arb.hem"
    path.write_text(src, encoding="ascii")

    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    assert _BORROW_CONFLICT not in _codes(payload), payload["diagnostics"]
