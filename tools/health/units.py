"""The ``units`` consistency sub-check: a bare-numeral rot guard over
the emitted artifact corpus (WO-150, D262 ruling 2, the SWEEP half).

The structural half (`regolith.backends.quantity.DimensionedValue`,
`regolith.backends.hdl.HdlTierRow`, `regolith.backends.instructions.
FastenerCallout`) makes a bare float unreachable at the TYPE level for
the interfaces it changed. This sweep is the second, weaker line of
defense D262 ruling 2 calls for: a regression tripwire over surfaces
the type system cannot reach at all -- prose/markdown table cells in
the committed demo proof packs (`demos/out/*/PROOF.md`), which are
free-form text a renderer assembles with plain f-strings, not a typed
model.

The heuristic is DELIBERATELY coarse (a bare numeral markdown-table
cell, no adjacent unit token) and WILL flag legitimate non-quantity
cells (a row index, a channel count, a BOM quantity) as false
positives -- this is fine and expected for a report-only sweep: per
the F154 lesson applied in reverse (D262 ruling 2), a gate promoted
before it is satisfiable gets waived, so this sweep does not gate
`make check`/`make health` at first landing. Promotion to a hard
error (and, with it, tightening the heuristic to drop known-honest
non-quantity columns) is a LATER, separate reviewed decision once the
corpus is observed clean under it -- NOT taken by this change.
"""

from __future__ import annotations

import re
from pathlib import Path

from regolith.logging_setup import get_logger

from tools.health.report import REPO_ROOT, LegSummary

_log = get_logger(__name__)

# frob:doc docs/modules/tools.md#health-units-sweep
DEMOS_OUT = REPO_ROOT / "demos" / "out"

# A markdown table cell holding nothing but a numeral: optional sign,
# digits, optional decimal/exponent -- no adjacent unit letters, no
# "_(no verified expectation)_"/"-"/hash-ref honest-gap marker. A cell
# that DOES carry a unit ("45 ohm") or an honest marker never matches.
_BARE_CELL_RE = re.compile(r"^[+-]?[0-9][0-9.eE+_]*$")


def _bare_numerals_in_markdown(path: Path) -> list[str]:
    """Every bare-numeral table-cell finding in one markdown file, as
    ``"<path>:<line>: bare numeral '<cell>' in table cell"`` strings."""
    findings: list[str] = []
    relative = path.relative_to(REPO_ROOT)
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        # Only pipe-table rows; skip the header separator row (`---`).
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        if (
            set(stripped.replace("|", "").replace("-", "").replace(":", "").strip())
            == set()
        ):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        for cell in cells:
            if _BARE_CELL_RE.match(cell):
                findings.append(
                    f"{relative}:{lineno}: bare numeral {cell!r} in table cell"
                )
    return findings


# frob:doc docs/modules/tools.md#health-units-sweep
# frob:waive TEST001 reason="scan helper, see test_units_scan_runs_clean"
def scan_demos_out() -> list[str]:
    """Report-only scan of the committed demo proof corpus
    (`demos/out/*/PROOF.md`) for dimensioned-looking bare numerals the
    type system cannot reach (WO-150 sweep half)."""
    if not DEMOS_OUT.is_dir():
        return []
    findings: list[str] = []
    for path in sorted(DEMOS_OUT.rglob("PROOF.md")):
        findings.extend(_bare_numerals_in_markdown(path))
    return findings


# frob:doc docs/modules/tools.md#health-units-sweep
# frob:waive TEST005 reason="measured 16.7% branch on 2026-07-19; backfill T-0036"
def run() -> LegSummary:
    """Run the sweep; ALWAYS ``ok=True`` (report-only per D262 ruling 2
    -- see module docstring for why this must not gate at first
    landing)."""
    findings = scan_demos_out()
    for finding in findings:
        _log.warning(
            "units: bare dimensioned-looking numeral (report-only): %s", finding
        )
    note = "clean" if not findings else f"{len(findings)} flagged (report-only)"
    return LegSummary(
        leg="units",
        ok=True,
        counts={"flagged": len(findings)},
        evidence=note,
    )


# frob:doc docs/modules/tools.md#health-units-sweep
# frob:waive TEST001 reason="CLI entry point; exercised via make health integration"
# frob:waive TEST005 reason="measured 9.1% branch on 2026-07-19; backfill T-0036"
def main(argv: list[str] | None = None) -> int:
    """Run the sweep standalone; always exits 0 (report-only)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="WO-150 bare-numeral sweep (report-only, D262 ruling 2)."
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print every finding, not just the summary row.",
    )
    args = parser.parse_args(argv)
    summary = run()
    print(summary.row())
    if args.report:
        for finding in scan_demos_out():
            print(finding)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
