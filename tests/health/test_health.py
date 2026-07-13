"""WO-106: the repo health gate (`make health`, D219).

Fast, build-free tests over the four health legs' machinery:

* the census golden is enrolled and well-formed;
* the census is SENSITIVE to a new waiver -- acceptance creep cannot
  land silently (the WO-106 acceptance criterion, proven by test);
* the consistency sweeps are green on the real tree;
* the standardized report shape is deterministic.

The heavy end-to-end fleet/demos runs are the ``make health`` legs
themselves (documented runtime), not this suite -- these tests exercise
the derivation + comparison logic that decides green vs red.
"""

from __future__ import annotations

import copy

from tools.health import consistency, fleet
from tools.health.report import HealthReport, LegSummary

# The 15 D210 fleet projects (11 flagships + sdr + dune_buggy +
# reaction_wheel + regen_engine).
_EXPECTED_FLEET = 15


def _base_report() -> dict:
    """A minimal build report: 3 obligations, 1 discharged, 2 accepted."""
    return {
        "final": {
            "release_ok": True,
            "results": [
                {"deferral": None},  # discharged
                {"deferral": {"reason": "conformance_windows_unresolved"}},
                {"deferral": {"reason": "no_model"}},
            ],
            "acceptance": {
                "accepted_hashes": ["h1", "h2"],
                "deviations": [
                    {"kind": "matched"},
                    {"kind": "matched"},
                ],
                "errors": [],
            },
        }
    }


class TestCensusGolden:
    def test_enrolled_and_wellformed(self) -> None:
        golden = fleet.load_census_golden()
        assert golden, "fleet_census.json golden is not enrolled"
        assert len(golden) == _EXPECTED_FLEET
        # Every fleet project is green in the census: zero violated.
        for name, census in golden.items():
            assert census.violated == 0, f"{name}: census shows a violated obligation"
            assert census.obligations >= census.discharged + 0
            assert census.families  # every project ships or names its families

    def test_discovery_matches_golden(self) -> None:
        discovered = {name for name, _root in fleet.discover_fleet()}
        assert discovered == set(fleet.load_census_golden())


class TestAcceptanceCreep:
    """A new waiver MUST move the census -- it can never land silently."""

    def test_base_census(self) -> None:
        census, release_ok, stale = fleet._census_from_report(_base_report())
        assert census.obligations == 3
        assert census.discharged == 1
        assert census.accepted_deviation == 2
        assert census.violated == 0
        assert release_ok is True
        assert stale == 0

    def test_new_backed_waiver_flips_accepted(self) -> None:
        base, _, _ = fleet._census_from_report(_base_report())
        report = _base_report()
        # A new `waive ... by doc(...)` accepts one more obligation.
        report["final"]["acceptance"]["accepted_hashes"].append("h3")
        report["final"]["acceptance"]["deviations"].append({"kind": "matched"})
        moved, _, _ = fleet._census_from_report(report)
        assert moved != base, "a new backed waiver did not move the census"
        assert moved.accepted_deviation == base.accepted_deviation + 1

    def test_new_bare_waiver_is_caught(self) -> None:
        # A BARE waiver (no evidence) harvests stale -- a stale count the
        # fleet leg gates on (release is not clean), never silent.
        report = _base_report()
        report["final"]["acceptance"]["deviations"].append({"kind": "stale"})
        _, _, stale = fleet._census_from_report(report)
        assert stale == 1


class TestDesignHashCrossDirectory:
    """`ship._design_hash` is stable across checkout paths (WO-106 fix)."""

    def test_same_content_two_roots_same_hash(self, tmp_path) -> None:  # noqa: ANN001
        from regolith.backends.ship import _design_hash

        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        for base in ("a", "b"):
            (tmp_path / base / "part.hema").write_text("part X {}\n")
        ha = _design_hash((str(tmp_path / "a" / "part.hema"),), str(tmp_path / "a"))
        hb = _design_hash((str(tmp_path / "b" / "part.hema"),), str(tmp_path / "b"))
        assert ha == hb, "design_hash drifts across checkout paths"

    def test_content_change_moves_hash(self, tmp_path) -> None:  # noqa: ANN001
        from regolith.backends.ship import _design_hash

        src = tmp_path / "part.hema"
        src.write_text("part X {}\n")
        before = _design_hash((str(src),), str(tmp_path))
        src.write_text("part Y {}\n")
        after = _design_hash((str(src),), str(tmp_path))
        assert before != after


class TestConsistencySweeps:
    def test_dnum_uniqueness_clean(self) -> None:
        assert consistency._check_dnums().ok

    def test_extensions_single_sourced(self) -> None:
        assert consistency._check_extensions().ok

    def test_wo_status_no_false_done(self) -> None:
        assert consistency._check_wo_status().ok

    def test_worktrees_is_report_only(self) -> None:
        # Report-only: never gates, whatever worktrees exist.
        assert consistency._check_worktrees().ok


class TestReportShape:
    def test_ok_iff_every_leg_ok(self) -> None:
        legs = (
            LegSummary(leg="check", ok=True),
            LegSummary(leg="fleet", ok=True),
        )
        assert HealthReport(legs=legs).ok
        assert not HealthReport(legs=(*legs, LegSummary(leg="demos", ok=False))).ok

    def test_json_is_deterministic(self) -> None:
        report = HealthReport(
            legs=(LegSummary(leg="check", ok=True, counts={"rc": 0}),)
        )
        assert report.to_json() == report.to_json()
        assert '"leg": "check"' in report.to_json()

    def test_copy_independence(self) -> None:
        r = _base_report()
        _ = copy.deepcopy(r)
        assert fleet._census_from_report(r)[0].obligations == 3
