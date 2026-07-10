"""`regolith rules test|try` goldens (WO-28 deliverable 5).

Drives the typed facade only (`regolith.compiler.rules_test` /
`rules_try`, AD-4). Two properties are frozen:

- every REFERENCE pack's `expect:` fixtures run green through
  `rules_test` (the WO-28 acceptance criterion), and a rule missing a
  pass or fail case is a lint WARNING, not a failure;
- `rules_try`'s report over (std.sheet_metal, sheet_bracket) is
  committed as golden data -- matches, verdicts, margins, near-miss
  flags must not drift silently.

Regeneration: never hand-edit the golden file. Run
`REGOLITH_UPDATE_GOLDEN=1 pytest tests/golden/test_rules_cli.py` and
diff-review the change (AD-11).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from regolith import compiler

_log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent / "data"

_SHEET_PACK = "examples/tracks/hematite/std_sheet_metal.hema"
_PCB_PACK = "examples/flagships/espresso_machine/jlc_2l.cupr"
_REMOVAL_PACKS = "examples/tracks/hematite/std_removal.hema"
_BRACKET = "examples/tracks/hematite/sheet_bracket.hema"


def test_reference_pack_expect_fixtures_are_green() -> None:
    """`rules test` over the reference packs (std.sheet_metal, jlc_2l,
    and WO-77's std.removal pair): every case ok, no lints (every rule
    carries both a pass and a fail case, D-H)."""
    result = compiler.rules_test((_SHEET_PACK, _PCB_PACK, _REMOVAL_PACKS))
    assert result.is_ok, f"rules_test errored: {result}"
    reports = result.danger_ok
    assert {r.pack for r in reports} == {
        "std.sheet_metal",
        "jlc_2l",
        "std.removal",
        "std.removal_am",
    }
    for report in reports:
        _log.info("pack %s: %d cases, ok=%s", report.pack, len(report.cases), report.ok)
        assert report.ok, f"{report.pack} fixture failures: {report.cases}"
        assert not report.lints, f"{report.pack} lints: {report.lints}"


def test_missing_expect_case_is_a_lint_warning(tmp_path: Path) -> None:
    """A rule without a fail case draws the untested-law lint but does
    not fail the run."""
    pack = tmp_path / "lint_pack.hema"
    pack.write_text(
        "process lint_pack:\n"
        "    dfm:\n"
        "        rule half_tested:\n"
        "            forall h in holes\n"
        "            demand: h.diameter >= 1mm\n"
        "            expect:\n"
        "                pass: hole(diameter=3mm)\n",
        encoding="ascii",
    )
    result = compiler.rules_test((str(pack),))
    assert result.is_ok, f"rules_test errored: {result}"
    (report,) = result.danger_ok
    assert report.ok, "a lint is a warning, not a failure"
    assert len(report.lints) == 1, report.lints
    assert "fail" in report.lints[0]


def test_rules_try_report_matches_golden() -> None:
    """The try-loop report over the flagship pair is golden data."""
    result = compiler.rules_try(_SHEET_PACK, _BRACKET)
    assert result.is_ok, f"rules_try errored: {result}"
    snapshot = json.loads(result.danger_ok.model_dump_json())

    golden_path = _DATA_DIR / "rules_try_sheet_bracket.json"
    if os.environ.get("REGOLITH_UPDATE_GOLDEN") == "1":
        golden_path.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )
        _log.info("regenerated %s", golden_path)

    assert golden_path.exists(), (
        f"missing golden {golden_path}; regenerate with REGOLITH_UPDATE_GOLDEN=1"
    )
    golden = json.loads(golden_path.read_text(encoding="ascii"))
    assert snapshot == golden, (
        "rules try output drifted; if intentional, regenerate with "
        "REGOLITH_UPDATE_GOLDEN=1 and diff-review"
    )
