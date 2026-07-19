"""The ``demos`` health leg: every live WO-108 proof pack still proven.

This leg reuses the WO-108 machinery verbatim -- it never re-implements
the completeness/determinism logic:

* it runs the WO-108 runner (``demos.run_all``) so a broken LIVE surface
  fails loudly (the "run what is proven" bar), and
* it runs the WO-108 completeness+determinism test
  (``tests/test_wo108_demos.py``), which drives each demo twice and
  asserts every manifest row's file exists, hashes as recorded, and is
  byte-identical across runs for deterministic formats.

``smoke`` runs one demo probe only (the cheap ``make check`` seam).
"""

from __future__ import annotations

import subprocess
import sys

from regolith.logging_setup import get_logger

from tools.health.report import REPO_ROOT, LegSummary

_log = get_logger(__name__)

# frob:waive TEST003 reason="WO-108 demo rebuild+determinism; see test_wo108_demos.py"


# frob:doc docs/modules/tools.md#health-demos-leg
def run(*, smoke: bool = False) -> LegSummary:
    """Run the demos leg; return its standardized summary row."""
    from demos.run_all import DEMOS
    from demos.run_all import main as run_all_main

    if smoke:
        # One demo probe: the completeness test parametrized to demo1.
        _log.info("demos: smoke probe (one demo)")
        proc = subprocess.run(
            ["pytest", "-q", "tests/test_wo108_demos.py", "-k", DEMOS[0]],
            cwd=REPO_ROOT,
            check=False,
        )
        ok = proc.returncode == 0
        return LegSummary(
            leg="demos",
            ok=ok,
            counts={"probed": 1},
            evidence=f"tests/test_wo108_demos.py -k {DEMOS[0]}",
        )

    _log.info("demos: running the WO-108 runner + completeness test")
    runner_rc = run_all_main([])
    test_proc = subprocess.run(
        ["pytest", "-q", "tests/test_wo108_demos.py"],
        cwd=REPO_ROOT,
        check=False,
    )
    ok = runner_rc == 0 and test_proc.returncode == 0
    _log.debug("demos: runner rc=%d test rc=%d", runner_rc, test_proc.returncode)
    return LegSummary(
        leg="demos",
        ok=ok,
        counts={"demos": len(DEMOS)},
        evidence="demos/run_all.py + tests/test_wo108_demos.py",
    )


# frob:doc docs/modules/tools.md#health-demos-leg
# frob:waive TEST001 reason="CLI entry pt, WO-108 demo rebuild; see make health"
def main(argv: list[str] | None = None) -> int:
    """Run the demos leg standalone; exit 0 iff green."""
    import argparse

    parser = argparse.ArgumentParser(description="The demos health leg.")
    parser.add_argument("--smoke", action="store_true", help="One demo probe.")
    args = parser.parse_args(argv)
    summary = run(smoke=args.smoke)
    print(summary.row())
    return 0 if summary.ok else 1


if __name__ == "__main__":
    sys.exit(main())
