"""graphite imports no `regolith.orchestrator`/`regolith.harness` internals
(WO-59 acceptance criterion, artifact-only channel per AD-24/AD-22): the
GUI/TUI consume CLI JSON + schema-versioned disk artifacts, never Python
internals of the compiler/orchestrator side.
"""

from __future__ import annotations

import re
from pathlib import Path

_FORBIDDEN_RE = re.compile(
    r"^\s*(from\s+regolith\.(orchestrator|harness)(\.|import)|"
    r"import\s+regolith\.(orchestrator|harness)\b)",
    re.MULTILINE,
)


def test_no_orchestrator_or_harness_imports_anywhere_in_graphite():
    graphite_dir = Path(__file__).resolve().parents[1] / "graphite"
    offenders = []
    for path in graphite_dir.rglob("*.py"):
        if _FORBIDDEN_RE.search(path.read_text()):
            offenders.append(str(path))
    assert offenders == [], (
        f"graphite must stay on the artifact-only channel (AD-24/AD-22): {offenders}"
    )
