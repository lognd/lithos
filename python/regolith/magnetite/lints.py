"""``magnetite.toml [lints]`` resolution (WO-40 deliverable 4).

Spec: `docs/spec/toolchain/24-developer-tooling.md` sec. 5. A manifest's
``[lints]`` table (already flattened into ``Manifest.lints`` by
``regolith.magnetite.manifest.load_manifest``) is the code -> action
table `regolith.compiler.check`/``compile`` forward straight to the
Rust core, which is the ONE place (`regolith_diag::apply_lint_config`)
that promotes a `deny`'d code's severity to `Error`. No-manifest
projects resolve to the empty table -- pure defaults (every lint stays
at `Warning`).
"""

from __future__ import annotations

from regolith.logging_setup import get_logger
from regolith.magnetite.manifest import Manifest

_log = get_logger(__name__)


def resolve_lint_config(manifest: Manifest | None) -> tuple[tuple[str, str], ...]:
    """Return the ``(code, action)`` pairs to pass to
    :func:`regolith.compiler.check`/:func:`regolith.compiler.compile`.

    ``manifest is None`` (no ``magnetite.toml`` found) is the documented
    no-manifest default: pure defaults, every lint at ``Warning``.
    """
    if manifest is None:
        _log.debug("no manifest: every lint code stays at its Warning default")
        return ()
    _log.debug(
        "resolved %d [lints] entries from %s", len(manifest.lints), manifest.name
    )
    return manifest.lints
