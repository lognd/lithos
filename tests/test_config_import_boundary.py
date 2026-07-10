"""Config never reaches the margin math (WO-59 D164, charter sec. 1.1):
`regolith.harness` and `regolith.compiler`'s discharge path must never
import `regolith.config`, or a config knob could silently flip a verdict.
"""

from __future__ import annotations

import re
from pathlib import Path

_IMPORT_RE = re.compile(
    r"^\s*(from\s+regolith\.config\s+import|from\s+regolith\s+import\s+config"
    r"|import\s+regolith\.config)\b",
    re.MULTILINE,
)

_FORBIDDEN_DIRS = ("harness", "orchestrator/nogood_cache.py")


def test_harness_never_imports_config():
    root = Path(__file__).resolve().parents[1] / "python" / "regolith"
    harness_dir = root / "harness"
    assert harness_dir.is_dir()
    offenders = []
    for path in harness_dir.rglob("*.py"):
        if _IMPORT_RE.search(path.read_text()):
            offenders.append(str(path))
    assert offenders == [], (
        f"regolith.harness must never import regolith.config: {offenders}"
    )


def test_discharge_module_never_imports_config():
    root = Path(__file__).resolve().parents[1] / "python" / "regolith"
    for path in root.rglob("*discharge*.py"):
        assert not _IMPORT_RE.search(path.read_text()), (
            f"discharge path must never import regolith.config: {path}"
        )
