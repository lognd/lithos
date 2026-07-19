"""The ONE standardized shape every health leg reports in (D219).

Every leg -- however heavy or cheap its internals -- returns exactly one
:class:`LegSummary` (leg name, ok, integer counts, a human-followable
evidence pointer). The composed :class:`HealthReport` is what
``health_report.json`` serializes and what ``make health``'s verdict
reads: green iff every leg is ok.

Serialized deterministically (sorted keys, no timestamps) so a health
report is diffable and a re-run over an unchanged tree is byte-stable.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

# tools/ lives at the repo root; REPO_ROOT is its parent.
# frob:doc docs/modules/tools.md#health-report-shape
REPO_ROOT = Path(__file__).resolve().parents[2]

# Where the composed report and each leg's cached artifacts land. Kept
# under a gitignored scratch dir so a health run never dirties the tree.
# frob:doc docs/modules/tools.md#health-report-shape
HEALTH_OUT = REPO_ROOT / ".regolith" / "health"
# frob:doc docs/modules/tools.md#health-report-shape
REPORT_NAME = "health_report.json"


# frob:doc docs/modules/tools.md#health-report-shape
class LegSummary(BaseModel):
    """One health leg's standardized summary row.

    ``leg`` names the leg; ``ok`` is its verdict; ``counts`` is a small
    map of integer tallies the leg chose to surface (e.g.
    ``{"projects": 15, "green": 15}``); ``evidence`` points a human at
    where to look (a path, a command, or a one-line pointer).
    """

    model_config = ConfigDict(frozen=True)

    leg: str
    ok: bool
    counts: dict[str, int] = {}
    evidence: str = ""

    # frob:doc docs/modules/tools.md#health-report-shape
    def row(self) -> str:
        """A single fixed-width text row for the loud verdict block."""
        mark = "PASS" if self.ok else "FAIL"
        counts = " ".join(f"{k}={v}" for k, v in sorted(self.counts.items()))
        return f"  [{mark}] {self.leg:12} {counts:40} {self.evidence}"


# frob:doc docs/modules/tools.md#health-report-shape
class HealthReport(BaseModel):
    """The composed four-leg report; green iff every leg is ok."""

    model_config = ConfigDict(frozen=True)

    legs: tuple[LegSummary, ...] = ()

    # frob:doc docs/modules/tools.md#health-report-shape
    @property
    def ok(self) -> bool:
        """True iff every leg passed."""
        return all(leg.ok for leg in self.legs)

    # frob:doc docs/modules/tools.md#health-report-shape
    def to_json(self) -> str:
        """Deterministic JSON (sorted keys, trailing newline)."""
        payload = self.model_dump(mode="json")
        return json.dumps(payload, sort_keys=True, indent=2) + "\n"

    # frob:doc docs/modules/tools.md#health-report-shape
    def write(self, path: Path | None = None) -> Path:
        """Persist the report; return the path written."""
        target = path if path is not None else HEALTH_OUT / REPORT_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json())
        return target

    # frob:doc docs/modules/tools.md#health-report-shape
    # frob:waive TEST001 reason="thin wrapper over LegSummary.row; verified each run"
    def verdict_block(self) -> str:
        """The loud human verdict every ``make health`` run prints."""
        head = "HEALTH: PASS" if self.ok else "HEALTH: FAIL"
        rows = "\n".join(leg.row() for leg in self.legs)
        return f"{rows}\n{head}"
