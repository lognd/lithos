"""INV-17 Type soundness (substrate/13-invariants.md).

Ledger statement:
    **No dimensionally inconsistent expression, no `==` on a continuous
    quantity, and no interval/range confusion survives L1.**

Mechanism provided by: WO-02 (`regolith-syntax` parse-time dimensional
analysis). This module is part of the WO-17 invariant suite: the
implementation's contract with the spec. A spec change that alters
INV-17's proof argument must change this module in the same commit.

Verified live during WO-19 wiring (cycle 12): `regolith_syntax::parse`
already emits `E0101` (incompatible quantities) and `E0102` (`==` on a
continuous quantity) for crafted single-file sources driven through
the real facade (`regolith.compiler.check`) -- these two violation
classes are genuinely testable end-to-end today, so their xfail is
lifted. `E0103` (interval/range confusion) was not probed live and is
left `xfail` rather than guessed at.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from regolith import compiler


def test_inv_17_incompatible_quantities_dies_at_l1(tmp_path: Path) -> None:
    """`5mm + 3kg` is dimensionally inconsistent -- must die at L1 with
    `E0101`, never reach a later pass."""
    source = tmp_path / "bad_units.hem"
    source.write_text("part Widget:\n    material: AL6061_T6\n    bad: 5mm + 3kg\n")

    result = compiler.check((str(tmp_path),))
    assert result.is_ok
    outcome = result.danger_ok
    assert outcome.ok is False

    payload = json.loads(outcome.payload_json)
    codes = {(d["code"]["family"], d["code"]["offset"]) for d in payload["diagnostics"]}
    assert ("parse", 1) in codes, payload["diagnostics"]


def test_inv_17_equality_on_continuous_dies_at_l1(tmp_path: Path) -> None:
    """`==` on a continuous quantity is the equality-ban violation --
    must die at L1 with `E0102`."""
    source = tmp_path / "bad_equality.hem"
    source.write_text("part Widget:\n    material: AL6061_T6\n    ok: 5mm == 3mm\n")

    result = compiler.check((str(tmp_path),))
    assert result.is_ok
    outcome = result.danger_ok
    assert outcome.ok is False

    payload = json.loads(outcome.payload_json)
    codes = {(d["code"]["family"], d["code"]["offset"]) for d in payload["diagnostics"]}
    assert ("parse", 2) in codes, payload["diagnostics"]


@pytest.mark.xfail(
    reason=(
        "WO-02 fixture pending: interval `[a, b]` vs half-open range "
        "`[i .. j]` confusion (E0103) was not exercised live while "
        "wiring WO-19 -- the other two INV-17 violation classes "
        "(E0101/E0102) are now covered above via the real facade."
    ),
    strict=True,
)
def test_inv_17_interval_range_confusion_dies_at_l1() -> None:
    """Ledger test: interval/range confusion must die at L1 with E0103."""
    raise NotImplementedError(
        "STUB WO-17: craft an interval-vs-range-confusion fixture "
        "and drive it through regolith.compiler.check"
    )
