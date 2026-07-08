"""INV-18 Reference determinism (regolith/13-invariants.md).

Ledger statement:
    **Every resolved reference has exactly one interpretation.**

Mechanism provided by: WO-08 (`regolith-sem::query` cardinality-typed
resolution) + WO-05 (`feature`/`refer` query grammar) + WO-19
(`regolith-lower::query` resolution against per-scope snapshots). This
module is part of the WO-17 invariant suite: the implementation's
contract with the spec. A spec change that alters INV-18's proof argument
must change this module in the same commit.

End-to-end: `regolith-lower` now resolves each `refer <name>` reference
against its declaration scope's committed entity-DB snapshot via the
WO-08 query engine's `.only` cardinality. The resolver either produces a
unique answer or fails -- there is no tie-break path. Over-match (two
`feature hole` then `refer hole`) and under-match (`refer hole` with no
feature) are both refused with E0301 (`AMBIGUOUS_SELECTION`), observed
through the facade payload.

Scope note (honest residual): the broader cardinality vocabulary
(`.all`/`.any`, `at_intersection` joins, orbit `any`) is implemented in
`regolith-sem::query` and unit-tested there; the WO-19 by-name grammar
exercises the `.only` (bare reference must resolve uniquely) channel of
INV-18. The `any`-over-broken-orbit channel is covered by INV-4.
"""

from __future__ import annotations

import json

from regolith import compiler

# INV-18 diagnostic code (regolith-diag `Family::References`, E0301).
_AMBIGUOUS_SELECTION = {"family": "references", "offset": 1}  # E0301


def _codes(payload: dict) -> list[dict]:
    return [d["code"] for d in payload["diagnostics"]]


def _check(path) -> dict:  # type: ignore[no-untyped-def]
    return json.loads(compiler.check((str(path),)).danger_ok.payload_json)


def test_inv_18_over_match_is_refused(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Deliberate violation: two `feature hole` make `refer hole`
    ambiguous. A reference must have exactly one interpretation, so the
    over-match is refused (E0301), never a heuristic pick."""
    src = "part p:\n    feature hole\n    feature hole\n    refer hole\n"
    path = tmp_path / "over.hema"
    path.write_text(src, encoding="ascii")

    payload = _check(path)
    assert _AMBIGUOUS_SELECTION in _codes(payload), (
        f"an over-matched reference must be refused (INV-18): {payload['diagnostics']}"
    )


def test_inv_18_under_match_is_refused(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A second violation channel: `refer hole` with no `feature hole`
    resolves to nothing -- a bare reference must resolve, so it is
    refused (E0301)."""
    src = "part p:\n    refer hole\n"
    path = tmp_path / "under.hema"
    path.write_text(src, encoding="ascii")

    payload = _check(path)
    assert _AMBIGUOUS_SELECTION in _codes(payload), payload["diagnostics"]


def test_inv_18_unique_reference_is_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The honest negative control: exactly one `feature hole` gives
    `refer hole` a unique interpretation -- no resolution diagnostic."""
    src = "part p:\n    feature hole\n    refer hole\n"
    path = tmp_path / "unique.hema"
    path.write_text(src, encoding="ascii")

    payload = _check(path)
    assert _AMBIGUOUS_SELECTION not in _codes(payload), payload["diagnostics"]
