"""INV-27 File-layout invariance (regolith/13-invariants.md).

Ledger statement:
    **For a fixed set of top-level declarations and pinned dependencies,
    verdicts, resolutions, and evidence identities are invariant under how
    the declarations are distributed across source files.** Mechanism: all
    cross-declaration references are by name through imports; resolution
    binds to declaration identity, never file identity; obligation keys
    (INV-1) contain claims, subject snapshots, givens, and record hashes
    -- no source paths.

Mechanism provided by: the WO-19 lowering pipeline over a multi-file
package (sorted file order, snapshot hashing per AD-18) plus the
content-derived obligation keying (INV-1). This module is part of the
WO-17 invariant suite: a spec change that alters INV-27's proof argument
must change this module in the same commit.

Ledger test: "split a golden example into two files; assert identical
verdicts, lockfile rows, and evidence keys." Here: the same top-level
declarations are checked once as a single file and once split across two
files in a package directory; the obligation keys and entity-snapshot
hashes (the content-addressed identities INV-1/INV-27 name) must be
byte-identical, because no downstream key can observe which file holds a
declaration.
"""

from __future__ import annotations

from regolith import compiler

from tests.golden import _util

# A fixed set of independent top-level declarations: a conformance
# binding (emits a conformance obligation) plus a required claim. Neither
# references the other, so the split is a pure layout change.
_DECL_A = (
    "interface Seat:\n    x: 1\npart bracket:\n    impl Seat for self:\n        y: 1\n"
)
_DECL_B = "part gizmo:\n    require R:\n        s: >= 1\n"


def _payload(paths):  # type: ignore[no-untyped-def]
    return _util.stable_snapshot(compiler.check(tuple(paths)).danger_ok.payload_json)


def test_inv_27_split_across_files_preserves_identities(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The same declarations in one file vs split across two files in a
    package produce identical obligation keys and snapshot hashes -- file
    organization is invisible to every downstream identity (INV-27)."""
    whole_dir = tmp_path / "whole"
    whole_dir.mkdir()
    (whole_dir / "all.hema").write_text(_DECL_A + _DECL_B, encoding="ascii")

    split_dir = tmp_path / "split"
    split_dir.mkdir()
    (split_dir / "a.hema").write_text(_DECL_A, encoding="ascii")
    (split_dir / "b.hema").write_text(_DECL_B, encoding="ascii")

    whole = _payload([str(whole_dir)])
    split = _payload([str(split_dir)])

    assert whole["obligation_keys"], "expected at least one obligation"
    # Obligation identities (INV-1 keys) are layout-invariant.
    assert whole["obligation_keys"] == split["obligation_keys"]
    # Entity-snapshot content hashes are layout-invariant.
    assert whole["snapshot_hashes"] == split["snapshot_hashes"]
    # The verdict-bearing counts agree too.
    assert whole["obligation_count"] == split["obligation_count"]
    assert whole["snapshot_count"] == split["snapshot_count"]
