"""graphite: the regolith interaction surface (WO-59, AD-31/D163-D165).

Own distribution over the `regolith` wheel: a textual TUI (config editing,
`check`/`build`/`optimize` driving with VERBATIM diagnostics, build-report
browsing) and a local-web GUI (`graphite serve`: one self-contained,
hand-written ASCII HTML/JS/CSS viewer over a localhost stdlib http server).

Artifact-only channel (AD-24/AD-22 applied to UI): every module here reads
CLI JSON output, disk artifacts (`.regolith/`, `regolith.lock`, ship output
directories), and `regolith.config` -- never `regolith.orchestrator` or
`regolith.harness` internals. See `graphite.artifacts` for the one
disk-scanning module and `tests/test_import_boundary.py` for the
import-graph assertion.
"""

from __future__ import annotations

__version__ = "0.1.0"
