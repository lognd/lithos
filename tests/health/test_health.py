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

# The 16 D210 fleet projects (12 flagships + sdr + dune_buggy +
# reaction_wheel + regen_engine). la_jig8 joined at WO-127 (charter 40
# sec. 4): the logic-analyzer tap jig is held to the same fleet bar as
# every design it exists to test -- 15 -> 16.
_EXPECTED_FLEET = 16


def _base_report() -> dict:
    """A minimal build report: 3 obligations, 1 discharged, 2 accepted.

    Census v2 (D220.3): the discharged row carries model-backed
    resolved evidence; every deviation carries a D220.2-classifiable
    ``basis`` (one class-a edge, one class-c machinery exclusion).
    """
    return {
        "final": {
            "release_ok": True,
            "results": [
                {"deferral": None, "evidence": {"status": "discharged"}},
                {"deferral": {"reason": "conformance_windows_unresolved"}},
                {"deferral": {"reason": "no_model"}},
            ],
            "acceptance": {
                "accepted_hashes": ["h1", "h2"],
                "deviations": [
                    {
                        "kind": "matched",
                        "basis": (
                            "module-import conformance edge: no scalar window "
                            "exists on a bare import (D195.3)"
                        ),
                    },
                    {
                        "kind": "matched",
                        "basis": (
                            "no registered harness model for label kind 'x' "
                            "(F126.1 model gap)"
                        ),
                    },
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
        census, release_ok, stale, unclassified = fleet._census_from_report(
            _base_report()
        )
        assert census.obligations == 3
        assert census.discharged == 1
        assert census.accepted_deviation == 2
        assert census.violated == 0
        assert census.deferred == 2
        assert census.waived_by_class == {"a": 1, "b": 0, "c": 1, "d": 0}
        assert unclassified == ()
        assert release_ok is True
        assert stale == 0

    def test_new_backed_waiver_flips_accepted(self) -> None:
        base, _, _, _ = fleet._census_from_report(_base_report())
        report = _base_report()
        # A new `waive ... by doc(...)` accepts one more obligation.
        report["final"]["acceptance"]["accepted_hashes"].append("h3")
        report["final"]["acceptance"]["deviations"].append(
            {"kind": "matched", "basis": "interface conformance edge (D195.3)"}
        )
        moved, _, _, _ = fleet._census_from_report(report)
        assert moved != base, "a new backed waiver did not move the census"
        assert moved.accepted_deviation == base.accepted_deviation + 1
        assert moved.waived_by_class["a"] == base.waived_by_class["a"] + 1

    def test_new_bare_waiver_is_caught(self) -> None:
        # A BARE waiver (no evidence) harvests stale -- a stale count the
        # fleet leg gates on (release is not clean), never silent.
        report = _base_report()
        report["final"]["acceptance"]["deviations"].append(
            {"kind": "stale", "basis": "conformance edge"}
        )
        _, _, stale, _ = fleet._census_from_report(report)
        assert stale == 1

    def test_out_of_class_waiver_is_a_named_failure(self) -> None:
        # D220.3: a waiver whose basis sits outside the D220.2 closed
        # classes surfaces as `unclassified` -- the fleet leg fails on
        # it regardless of the golden (never launderable by regen).
        report = _base_report()
        report["final"]["acceptance"]["deviations"].append(
            {"kind": "matched", "basis": "because I said so"}
        )
        _, _, _, unclassified = fleet._census_from_report(report)
        assert unclassified == ("because I said so",)

    def test_pin_unmatched_indeterminate_is_not_discharged(self) -> None:
        # WO117-F1: a deferral-free INDETERMINATE (the pin-unmatched
        # marker) must never count as discharged -- it is waived mass,
        # not model-backed resolved.
        report = _base_report()
        report["final"]["results"].append(
            {
                "deferral": None,
                "evidence": {
                    "status": "indeterminate",
                    "model_id": "harness.model_pin_unmatched",
                },
            }
        )
        census, _, _, _ = fleet._census_from_report(report)
        assert census.obligations == 4
        assert census.discharged == 1, "an indeterminate counted as discharged"
        assert census.deferred == 3


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


class TestWaiverClasses:
    """The D220.2 classifier: the one-home census vocabulary."""

    def test_every_class_reachable(self) -> None:
        from tools.health.waiver_classes import classify_basis

        assert classify_basis("module-import conformance edge (D195.3)") == "a"
        assert classify_basis("waiver against the D195-gated window queue") == "b"
        assert classify_basis("no registered harness model (F126.1 model gap)") == "c"
        assert classify_basis("qual unit survived GEVS +6dB; report VR-081") == "d"
        assert classify_basis("just because") is None

    def test_counts_are_total_and_stable_shape(self) -> None:
        from tools.health.waiver_classes import classify_deviations

        counts, unclassified = classify_deviations(
            ["conformance edge", "nonsense basis"]
        )
        assert set(counts) == {"a", "b", "c", "d"}
        assert counts["a"] == 1
        assert unclassified == ["nonsense basis"]
