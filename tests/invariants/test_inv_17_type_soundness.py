"""INV-17 Type soundness (substrate/13-invariants.md).

Ledger statement:
    **No dimensionally inconsistent expression, no `==` on a continuous
    quantity, and no interval/range confusion survives L1.**

Mechanism provided by: WO-02 (`regolith-syntax` parse-time dimensional
analysis). This module is part of the WO-17 invariant suite: the
implementation's contract with the spec. A spec change that alters
INV-17's proof argument must change this module in the same commit.

All FOUR INV-17 violation classes are now testable end-to-end through
the real facade (`regolith.compiler.check`): `E0101` (incompatible
quantities), `E0102` (`==` on a continuous quantity), `E0103`
(interval/range confusion), and `E0104` (two-reference log sum, e.g.
`dBm + dBm`). Each fixture below crafts a single-file source and asserts
the parse diagnostic fires at L1, before any later pass.
"""

from __future__ import annotations

import json
from pathlib import Path

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


def test_inv_17_interval_range_confusion_dies_at_l1(tmp_path: Path) -> None:
    """`[1, 2 .. 3]` mixes the `[a, b]` interval and `[i .. j]` range
    separators in one bracket -- must die at L1 with `E0103`."""
    source = tmp_path / "bad_range.hem"
    source.write_text("part p:\n    x: [1, 2 .. 3]\n")

    result = compiler.check((str(tmp_path),))
    assert result.is_ok
    outcome = result.danger_ok
    assert outcome.ok is False

    payload = json.loads(outcome.payload_json)
    codes = {(d["code"]["family"], d["code"]["offset"]) for d in payload["diagnostics"]}
    assert ("parse", 3) in codes, payload["diagnostics"]


def test_inv_17_two_reference_log_sum_dies_at_l1(tmp_path: Path) -> None:
    """`3dBm + 3dBm` is the two-reference log-sum violation (substrate/02
    sec. 5a): a sum of log terms is legal iff at most one referenced term
    remains -- must die at L1 with `E0104`."""
    source = tmp_path / "bad_logsum.hem"
    source.write_text("part W:\n    material: AL6061_T6\n    p: 3dBm + 3dBm\n")

    result = compiler.check((str(tmp_path),))
    assert result.is_ok
    outcome = result.danger_ok
    assert outcome.ok is False

    payload = json.loads(outcome.payload_json)
    codes = {(d["code"]["family"], d["code"]["offset"]) for d in payload["diagnostics"]}
    assert ("parse", 4) in codes, payload["diagnostics"]
