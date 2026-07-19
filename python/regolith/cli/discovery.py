"""Manifest-anchored project-root discovery (WO-43 deliverable 1).

Mirrors ``crates/regolith-ls/src/workspace.rs::discover_root`` exactly
(WO-38 deliverable 1) so the CLI and the language server agree on what
"the project" means from a single opened path: walk upward from the
given file/directory looking for ``magnetite.toml``; if none is found
anywhere up to the filesystem root, the opened path itself is the root.
This is a second READER of the same house convention, not a second
implementation of a different one -- the algorithm is deliberately
byte-for-byte the same walk, kept in Python because `regolith.cli` is
Python (AD-14) and the Rust crate is not on the FFI boundary (AD-4).
"""

from __future__ import annotations

from pathlib import Path

_MANIFEST = "magnetite.toml"


# frob:doc docs/modules/py-cli.md#discovery
def discover_project_root(opened: str) -> str:
    """The nearest ``magnetite.toml``'s directory above ``opened``, else
    ``opened`` itself.

    ``opened`` may be a file or a directory, existing or not (a
    not-yet-existing path still resolves by walking its parents).
    """
    path = Path(opened)
    candidate = path if path.is_dir() else path.parent
    while True:
        if (candidate / _MANIFEST).is_file():
            return str(candidate)
        parent = candidate.parent
        if parent == candidate:
            return opened
        candidate = parent
