"""The ``check`` health leg: the existing code gates, unchanged.

This leg does NOT re-implement any gate (D219 refactor rule): it CALLS
``make check`` -- fmt, clippy, ruff, ty, guard-core, schema drift, and
the Rust + Python test suites -- and reports its verdict in the one
standardized shape. It is the cheapest-first leg only relative to the
fleet/demos rebuilds; on its own it is the repo's fast gate.
"""

from __future__ import annotations

import subprocess
import sys

from regolith.logging_setup import get_logger

from tools.health.report import REPO_ROOT, LegSummary

_log = get_logger(__name__)

# frob:waive TEST003 reason="shells to make check; see make health (not in-test)"


# frob:doc docs/modules/tools.md#health-check-leg
def run() -> LegSummary:
    """Run ``make check``; return its standardized summary row."""
    _log.info("check: running `make check`")
    proc = subprocess.run(
        ["make", "check"],
        cwd=REPO_ROOT,
        check=False,
    )
    ok = proc.returncode == 0
    _log.debug("check: make check rc=%d", proc.returncode)
    return LegSummary(
        leg="check",
        ok=ok,
        counts={"rc": proc.returncode},
        evidence="make check (fmt, clippy, ruff, ty, guard-core, schema, tests)",
    )


# frob:doc docs/modules/tools.md#health-check-leg
# frob:waive TEST001 reason="CLI entry pt; see make health (not in-test, recurses)"
def main(argv: list[str] | None = None) -> int:
    """Run the check leg standalone; exit 0 iff green."""
    summary = run()
    print(summary.row())
    return 0 if summary.ok else 1


if __name__ == "__main__":
    sys.exit(main())
