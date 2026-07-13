"""Compose the four health legs cheapest-first (`python -m tools.health`).

Runs ``check`` -> ``consistency`` -> ``demos`` -> ``fleet`` (the
consistency sweeps are cheap and read the fleet leg's cache when present,
so the composed order additionally runs a fleet pass FIRST when a full
run is requested, then the sweeps over its cache). Each leg emits its one
standardized row; the composed :class:`HealthReport` is written to
``health_report.json`` and the loud verdict is printed to stdout.

``--smoke`` runs the cheap probes only (the ``make check`` health-smoke:
one project, one demo, the build-free consistency sweeps) and skips the
existing ``make check`` re-run (the caller IS ``make check``).
"""

from __future__ import annotations

import argparse
import os
import sys

from regolith.logging_setup import get_logger, log_verdict

from tools.health import check, consistency, demos, fleet
from tools.health.report import HealthReport, LegSummary

_log = get_logger(__name__)


def run_all(*, smoke: bool = False) -> HealthReport:
    """Run every leg and return the composed report.

    Full run order is cheapest-first for feedback, but the fleet leg runs
    before the consistency sweep so the waiver-ledger sub-check can read
    the fleet cache. Smoke skips the ``check`` leg (the caller is it).
    """
    update_golden = os.environ.get("REGOLITH_UPDATE_GOLDEN") == "1"
    legs: list[LegSummary] = []

    if not smoke:
        legs.append(check.run())

    # Fleet before consistency so the waiver sub-check reads its cache.
    legs.append(fleet.run(smoke=smoke, update_golden=update_golden))
    legs.append(demos.run(smoke=smoke))
    legs.append(consistency.run(smoke=smoke))

    # Present cheapest-first in the report regardless of run order.
    order = {"check": 0, "consistency": 1, "demos": 2, "fleet": 3}
    legs.sort(key=lambda leg: order.get(leg.leg, 99))
    return HealthReport(legs=tuple(legs))


def main(argv: list[str] | None = None) -> int:
    """Run ``make health`` (or the smoke subset); exit 0 iff green."""
    parser = argparse.ArgumentParser(description="The repo health gate (D219).")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Cheap probes only (the `make check` health-smoke).",
    )
    args = parser.parse_args(argv)

    report = run_all(smoke=args.smoke)
    path = report.write()
    _log.info("health: wrote %s", path)
    print(report.verdict_block())
    log_verdict(
        _log,
        report.ok,
        "health: all legs green" if report.ok else "health: a leg failed",
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
