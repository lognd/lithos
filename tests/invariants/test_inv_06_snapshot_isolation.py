"""INV-6 Snapshot isolation (regolith/13-invariants.md).

Ledger statement:
    **No statement observes a sibling's effects.** Mechanism: sibling
    exports are not name-resolvable within the scope; queries evaluate
    against the scope-entry snapshot by definition.

Mechanism provided by: WO-08 (`regolith-sem::query` resolution) + WO-19
(`regolith-lower::query` per-scope committed snapshots). This module is
part of the WO-17 invariant suite: the implementation's contract with the
spec. A spec change that alters INV-6's proof argument must change this
module in the same commit.

End-to-end: `regolith-lower` builds a committed entity-DB snapshot per
declaration scope from that scope's OWN `feature` statements and resolves
every `refer <name>` reference against it (WO-08 query engine). A
reference naming a SIBLING declaration's feature resolves against a
snapshot that does not contain it, so it under-matches and is refused
(E0301) -- the sibling's committed state is not name-resolvable across the
scope boundary. The query channel of INV-6 is thus enforced by
construction: each scope reads only its own scope-entry snapshot.

Scope note (honest residual): INV-6 lists four reference channels (names,
queries, datums, profile exports). The query/name channel is the one
WO-08/WO-19 own and the one exercised here; datums (immutable captures)
and profile exports (placeless until feature-anchored) are enforced
structurally by their own grammar and carry no cross-scope read path to
violate at this tier.
"""

from __future__ import annotations

import json

from regolith import compiler

# INV-6 diagnostic code (regolith-diag `Family::References`, E0301): an
# unresolved/under-matched reference (the sibling feature is absent).
_AMBIGUOUS_SELECTION = {"family": "references", "offset": 1}  # E0301


def _codes(payload: dict) -> list[dict]:
    return [d["code"] for d in payload["diagnostics"]]


def _check(path) -> dict:  # type: ignore[no-untyped-def]
    return json.loads(compiler.check((str(path),)).danger_ok.payload_json)


def test_inv_06_sibling_reference_is_isolated(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Deliberate violation attempt: `q` refers to `hole`, which is a
    feature of its sibling `p`. `q`'s snapshot does not contain it, so the
    reference under-matches and is refused (E0301) -- no statement observes
    a sibling's effects."""
    src = "part p:\n    feature hole\npart q:\n    refer hole\n"
    path = tmp_path / "sibling.hema"
    path.write_text(src, encoding="ascii")

    payload = _check(path)
    assert _AMBIGUOUS_SELECTION in _codes(payload), (
        "a sibling scope's feature must not be name-resolvable (INV-6): "
        f"{payload['diagnostics']}"
    )


def test_inv_06_own_scope_reference_is_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The honest negative control: `q` refers to its OWN `hole`. The
    sibling `p` also declaring `hole` does not leak in either direction --
    each scope reads only its own scope-entry snapshot, so the reference
    resolves uniquely with no diagnostic."""
    src = "part p:\n    feature hole\npart q:\n    feature hole\n    refer hole\n"
    path = tmp_path / "own.hema"
    path.write_text(src, encoding="ascii")

    payload = _check(path)
    assert _AMBIGUOUS_SELECTION not in _codes(payload), payload["diagnostics"]
