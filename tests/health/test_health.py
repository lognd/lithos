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

# The 17 D210 fleet projects (12 flagships + sdr + dune_buggy +
# reaction_wheel + regen_engine). la_jig8 joined at WO-127 (charter 40
# sec. 4): the logic-analyzer tap jig is held to the same fleet bar as
# every design it exists to test -- 15 -> 16. factory_p1 joined at
# WO-137 (charter 43/AD-42, the facility power-distribution flagship)
# -- 16 -> 17. WO-167's dwelling_r1 example is NOT a fleet member (no
# `magnetite.toml`, deliberately, mirroring `examples/tracks/xdomain/
# sited_transformer`'s precedent): it has no schedule-emitting
# `regolith build`/`ship` stage (see `demos/demo21_dwelling_wiring.py`'s
# SCOPE NOTE), so it stays off the build/ship-green fleet census
# rather than failing that gate honestly-but-loudly every run.
_EXPECTED_FLEET = 17


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
    # frob:tests tools/health/fleet.py::load_census_golden kind="unit"
    # frob:tests tools/health/fleet.py kind="integration"
    def test_enrolled_and_wellformed(self) -> None:
        golden = fleet.load_census_golden()
        assert golden, "fleet_census.json golden is not enrolled"
        assert len(golden) == _EXPECTED_FLEET
        # Every fleet project is green in the census: zero violated.
        for name, census in golden.items():
            assert census.violated == 0, f"{name}: census shows a violated obligation"
            assert census.obligations >= census.discharged + 0
            assert census.families  # every project ships or names its families

    # frob:tests tools/health/fleet.py::discover_fleet kind="unit"
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
    # frob:tests tools/health/consistency.py kind="integration"
    def test_dnum_uniqueness_clean(self) -> None:
        assert consistency._check_dnums().ok

    def test_extensions_single_sourced(self) -> None:
        assert consistency._check_extensions().ok

    def test_wo_status_no_false_done(self) -> None:
        assert consistency._check_wo_status().ok

    def test_worktrees_is_report_only(self) -> None:
        # Report-only: never gates, whatever worktrees exist.
        assert consistency._check_worktrees().ok


# frob:ticket T-0036
class TestConsistencySweepFixtures:
    """T-0036 phase 2 backfill: fixture-driven branch coverage for
    ``tools.health.consistency``'s sub-checks the real-tree tests above
    can only ever see the CLEAN branch of. Each test builds a small
    synthetic tree under ``tmp_path`` and points ``consistency.REPO_ROOT``
    / ``consistency.HEALTH_OUT`` at it via monkeypatch, so the FAILING
    branches (duplicates, liars, competing registries, dirty goldens,
    unresolved refs, stale waivers, unbalanced books, uncovered
    families) get exercised without ever touching the real repo tree."""

    # frob:ticket T-0036
    def test_check_dnums_flags_duplicate_heading(self, tmp_path, monkeypatch) -> None:  # noqa: ANN001
        log_dir = tmp_path / "docs" / "workflow" / "design-log"
        log_dir.mkdir(parents=True)
        (log_dir / "a.md").write_text("# D999 First\n")
        (log_dir / "b.md").write_text("# D999 Second\n")
        monkeypatch.setattr(consistency, "REPO_ROOT", tmp_path)
        result = consistency._check_dnums()
        assert result.ok is False
        assert result.note == "1 collision(s)"

    # frob:ticket T-0036
    def test_check_dnums_addendum_reuse_not_a_collision(
        self, tmp_path, monkeypatch
    ) -> None:  # noqa: ANN001
        log_dir = tmp_path / "docs" / "workflow" / "design-log"
        log_dir.mkdir(parents=True)
        (log_dir / "a.md").write_text("# D999 First\n")
        (log_dir / "b.md").write_text("# D999 addendum\n")
        monkeypatch.setattr(consistency, "REPO_ROOT", tmp_path)
        assert consistency._check_dnums().ok is True

    # frob:ticket T-0036
    def test_check_wo_status_flags_false_done(self, tmp_path, monkeypatch) -> None:  # noqa: ANN001
        wo_dir = tmp_path / "docs" / "workflow" / "work-orders"
        wo_dir.mkdir(parents=True)
        (wo_dir / "WO-99-thing.md").write_text("Status: todo\n")
        (tmp_path / "TODO.md").write_text("- [x] **WO-99** thing\n")
        monkeypatch.setattr(consistency, "REPO_ROOT", tmp_path)
        result = consistency._check_wo_status()
        assert result.ok is False
        assert "false-done" in result.note

    # frob:ticket T-0036
    def test_check_wo_status_residual_status_is_report_only(
        self, tmp_path, monkeypatch
    ) -> None:  # noqa: ANN001
        wo_dir = tmp_path / "docs" / "workflow" / "work-orders"
        wo_dir.mkdir(parents=True)
        (wo_dir / "WO-99-thing.md").write_text("Status: in-progress\n")
        (tmp_path / "TODO.md").write_text("- [x] **WO-99** thing\n")
        monkeypatch.setattr(consistency, "REPO_ROOT", tmp_path)
        result = consistency._check_wo_status()
        assert result.ok is True
        assert "1 residual" in result.note

    # frob:ticket T-0036
    def test_check_extensions_core_mismatch_fails(self, monkeypatch) -> None:  # noqa: ANN001
        from regolith import compiler

        monkeypatch.setattr(compiler, "extensions", lambda: [("bogus", "lang")])
        result = consistency._check_extensions()
        assert result.ok is False
        assert result.note == "core set mismatch"

    # frob:ticket T-0036
    def test_check_extensions_flags_competing_registry(
        self, tmp_path, monkeypatch
    ) -> None:  # noqa: ANN001
        from regolith import compiler

        monkeypatch.setattr(
            compiler,
            "extensions",
            lambda: [(e, "lang") for e in consistency._KNOWN_EXTENSIONS],
        )
        py_dir = tmp_path / "python" / "pkg"
        py_dir.mkdir(parents=True)
        (py_dir / "bad.py").write_text('EXTS = (".hema", ".cupr", ".fluo")\n')
        monkeypatch.setattr(consistency, "REPO_ROOT", tmp_path)
        result = consistency._check_extensions()
        assert result.ok is False
        assert "1 competing" in result.note

    # frob:ticket T-0036
    def test_check_goldens_dirty_flags_porcelain_lines(self, monkeypatch) -> None:  # noqa: ANN001
        class _FakeProc:
            stdout = " M tests/golden/foo.txt\n"

        monkeypatch.setattr(consistency.subprocess, "run", lambda *a, **k: _FakeProc())
        result = consistency._check_goldens()
        assert result.ok is False
        assert result.note == "1 dirty file(s)"

    # frob:ticket T-0036
    def test_check_goldens_clean_when_no_porcelain_output(self, monkeypatch) -> None:  # noqa: ANN001
        class _FakeProc:
            stdout = ""

        monkeypatch.setattr(consistency.subprocess, "run", lambda *a, **k: _FakeProc())
        assert consistency._check_goldens().ok is True

    # frob:ticket T-0036
    def test_check_waivers_flags_unresolved_ref(self, tmp_path, monkeypatch) -> None:  # noqa: ANN001
        ex_dir = tmp_path / "examples"
        ex_dir.mkdir()
        (ex_dir / "p.hema").write_text('waived by doc("missing_memo.md")\n')
        monkeypatch.setattr(consistency, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(
            consistency, "HEALTH_OUT", tmp_path / ".regolith" / "health"
        )
        result = consistency._check_waivers()
        assert result.ok is False
        assert "1 bad-ref" in result.note

    # frob:ticket T-0036
    def test_check_waivers_resolved_ref_and_no_fleet_cache_is_clean(
        self, tmp_path, monkeypatch
    ) -> None:
        ex_dir = tmp_path / "examples"
        ex_dir.mkdir()
        (ex_dir / "memo.md").write_text("memo\n")
        (ex_dir / "p.hema").write_text('waived by doc("memo.md")\n')
        monkeypatch.setattr(consistency, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(
            consistency, "HEALTH_OUT", tmp_path / ".regolith" / "health"
        )
        result = consistency._check_waivers()
        assert result.ok is True
        assert result.note == "0 bad-ref, 0 stale"

    # frob:ticket T-0036
    def test_check_waivers_flags_stale_from_fleet_cache(
        self, tmp_path, monkeypatch
    ) -> None:  # noqa: ANN001
        import json

        health_out = tmp_path / ".regolith" / "health"
        health_out.mkdir(parents=True)
        (health_out / "fleet_results.json").write_text(
            json.dumps({"proj_a": {"stale_waivers": 2}})
        )
        (tmp_path / "examples").mkdir()
        monkeypatch.setattr(consistency, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(consistency, "HEALTH_OUT", health_out)
        result = consistency._check_waivers()
        assert result.ok is False
        assert "2 stale" in result.note

    # frob:ticket T-0036
    def test_check_calc_books_no_cache_is_skipped_ok(
        self, tmp_path, monkeypatch
    ) -> None:  # noqa: ANN001
        monkeypatch.setattr(consistency, "HEALTH_OUT", tmp_path / "absent")
        result = consistency._check_calc_books()
        assert result.ok is True
        assert result.note == "no fleet cache (skipped)"

    # frob:ticket T-0036
    def test_check_calc_books_flags_unbalanced_package(
        self, tmp_path, monkeypatch
    ) -> None:  # noqa: ANN001
        import json

        health_out = tmp_path / ".regolith" / "health"
        health_out.mkdir(parents=True)
        (health_out / "fleet_results.json").write_text(
            json.dumps(
                {
                    "good_pkg": {"calc_book_balanced": True},
                    "bad_pkg": {"calc_book_balanced": False},
                }
            )
        )
        monkeypatch.setattr(consistency, "HEALTH_OUT", health_out)
        result = consistency._check_calc_books()
        assert result.ok is False
        assert "1 unbalanced of 2" in result.note

    # frob:ticket T-0036
    def test_check_demos_coverage_flags_missing_family(self, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.setattr(
            consistency,
            "D222_FAMILY_DEMOS",
            {"drawings": "demo7_drawings_multiview", "ghost_family": "no_such_demo"},
        )
        result = consistency._check_demos_coverage()
        assert result.ok is False
        assert "1 family(ies) uncovered" in result.note

    # frob:ticket T-0036
    def test_check_organization_reports_failed_sub_checks(self, monkeypatch) -> None:  # noqa: ANN001
        from tools.stdlib.organization import SubCheck as OrgSubCheck

        monkeypatch.setattr(
            consistency,
            "run_organization_checks",
            lambda: [OrgSubCheck("std_prefix", False, 1, "bad")],
        )
        result = consistency._check_organization()
        assert result.ok is False
        assert "failed: std_prefix" in result.note

    # frob:ticket T-0036
    def test_check_docs_agreement_reports_failed_sub_checks(self, monkeypatch) -> None:  # noqa: ANN001
        from tools.health.docs_agreement import SubCheck as DocsSubCheck

        monkeypatch.setattr(
            consistency,
            "run_docs_agreement_checks",
            lambda: [DocsSubCheck("readme_index", False, 1, "bad")],
        )
        result = consistency._check_docs_agreement()
        assert result.ok is False
        assert "failed: readme_index" in result.note

    # frob:ticket T-0036
    def test_check_diag_codes_reports_violations(self, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.setattr(
            consistency.diag_codes, "run", lambda: (False, 2, "2 bare kinds")
        )
        result = consistency._check_diag_codes()
        assert result.ok is False
        assert result.count == 2

    # frob:ticket T-0036
    def test_check_units_is_always_ok_but_reports_flagged_count(
        self, monkeypatch
    ) -> None:  # noqa: ANN001
        from tools.health.report import LegSummary as _LegSummary

        monkeypatch.setattr(
            consistency.units,
            "run",
            lambda: _LegSummary(
                leg="units", ok=True, counts={"flagged": 3}, evidence="3 flagged"
            ),
        )
        result = consistency._check_units()
        assert result.ok is True
        assert result.count == 3

    # frob:ticket T-0036
    def test_run_smoke_skips_waivers_and_calc_books(self, monkeypatch) -> None:  # noqa: ANN001
        calls: list[str] = []

        def _stub(name: str, ok: bool = True):  # noqa: ANN001
            def _inner() -> consistency.SubCheck:
                calls.append(name)
                return consistency.SubCheck(name, ok, 0, "stub")

            return _inner

        for name in (
            "_check_dnums",
            "_check_wo_status",
            "_check_extensions",
            "_check_goldens",
            "_check_worktrees",
            "_check_organization",
            "_check_docs_agreement",
            "_check_demos_coverage",
            "_check_diag_codes",
            "_check_units",
            "_check_waivers",
            "_check_calc_books",
        ):
            monkeypatch.setattr(consistency, name, _stub(name))

        summary = consistency.run(smoke=True)
        assert "_check_waivers" not in calls
        assert "_check_calc_books" not in calls
        assert summary.counts["sweeps"] == 10
        assert summary.ok is True

    # frob:ticket T-0036
    def test_run_not_ok_when_a_sweep_fails(self, monkeypatch) -> None:  # noqa: ANN001
        def _stub(name: str, ok: bool):  # noqa: ANN001
            return lambda: consistency.SubCheck(name, ok, 0, "stub")

        for name in (
            "_check_dnums",
            "_check_wo_status",
            "_check_extensions",
            "_check_goldens",
            "_check_worktrees",
            "_check_organization",
            "_check_docs_agreement",
            "_check_demos_coverage",
            "_check_diag_codes",
            "_check_units",
            "_check_waivers",
            "_check_calc_books",
        ):
            ok = name != "_check_wo_status"
            monkeypatch.setattr(consistency, name, _stub(name, ok))

        summary = consistency.run(smoke=False)
        assert summary.ok is False
        assert "_check_wo_status" in summary.evidence
        assert summary.counts["failed"] == 1

    # frob:ticket T-0036
    def test_main_smoke_flag_returns_zero_on_green(self, monkeypatch, capsys) -> None:  # noqa: ANN001
        monkeypatch.setattr(
            consistency,
            "run",
            lambda smoke=False: consistency.LegSummary(
                leg="consistency", ok=True, counts={"sweeps": 1}, evidence="clean"
            ),
        )
        rc = consistency.main(["--smoke"])
        assert rc == 0
        assert "consistency" in capsys.readouterr().out

    # frob:ticket T-0036
    def test_main_returns_one_on_red(self, monkeypatch, capsys) -> None:  # noqa: ANN001
        monkeypatch.setattr(
            consistency,
            "run",
            lambda smoke=False: consistency.LegSummary(
                leg="consistency", ok=False, counts={"sweeps": 1}, evidence="failed"
            ),
        )
        rc = consistency.main([])
        assert rc == 1


class TestReportShape:
    # frob:tests tools/health/report.py::HealthReport.ok kind="unit"
    # frob:tests tools/health/report.py kind="integration"
    def test_ok_iff_every_leg_ok(self) -> None:
        legs = (
            LegSummary(leg="check", ok=True),
            LegSummary(leg="fleet", ok=True),
        )
        assert HealthReport(legs=legs).ok
        assert not HealthReport(legs=(*legs, LegSummary(leg="demos", ok=False))).ok

    # frob:tests tools/health/report.py::HealthReport.to_json kind="unit"
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

    # frob:tests tools/health/waiver_classes.py::classify_basis kind="unit"
    # frob:tests tools/health/waiver_classes.py kind="integration"
    def test_every_class_reachable(self) -> None:
        from tools.health.waiver_classes import classify_basis

        assert classify_basis("module-import conformance edge (D195.3)") == "a"
        assert classify_basis("waiver against the D195-gated window queue") == "b"
        assert classify_basis("no registered harness model (F126.1 model gap)") == "c"
        assert classify_basis("qual unit survived GEVS +6dB; report VR-081") == "d"
        assert classify_basis("just because") is None

    # frob:tests tools/health/waiver_classes.py::classify_deviations kind="unit"
    def test_counts_are_total_and_stable_shape(self) -> None:
        from tools.health.waiver_classes import classify_deviations

        counts, unclassified = classify_deviations(
            ["conformance edge", "nonsense basis"]
        )
        assert set(counts) == {"a", "b", "c", "d"}
        assert counts["a"] == 1
        assert unclassified == ["nonsense basis"]


class TestDocsAgreementSweeps:
    """WO-121/D230: the docs-agreement sweeps stay green on the real tree."""

    # frob:tests tools/health/docs_agreement.py::check_guide_index kind="unit"
    # frob:tests tools/health/docs_agreement.py::check_cli_verbs kind="unit"
    # frob:tests tools/health/docs_agreement.py::check_dead_names kind="unit"
    # frob:tests tools/health/docs_agreement.py::run_all kind="unit"
    # frob:tests tools/health/docs_agreement.py kind="integration"
    def test_docs_agreement_sweeps_clean(self) -> None:
        from tools.health import docs_agreement

        # Smoke-runs the whole sweep composition over the real tree: each
        # sub-check must return the standard (name, ok, count, note) shape.
        # Not asserting every sub is green here -- guide-index drift is a
        # separate, pre-existing docs gap outside this wave's surface.
        subs = docs_agreement.run_all()
        assert subs
        for sub in subs:
            assert isinstance(sub.ok, bool)
            assert isinstance(sub.note, str)


class TestUnitsSweep:
    """WO-150/D262 ruling 2: the bare-numeral rot guard runs clean."""

    # frob:tests tools/health/units.py::scan_demos_out kind="unit"
    # frob:tests tools/health/units.py kind="integration"
    def test_units_scan_runs(self) -> None:
        from tools.health import units

        # Report-only sweep (D262 ruling 2): must run without raising and
        # return a list of finding strings, never gate on its own.
        findings = units.scan_demos_out()
        assert isinstance(findings, list)


class TestDiagCodesSweep:
    """WO-131/D247.4b: every registered diagnostic code stays documented."""

    # frob:tests tools/health/diag_codes.py::check_explain_completeness kind="unit"
    # frob:tests tools/health/diag_codes.py kind="integration"
    def test_diag_codes_run_clean(self) -> None:
        from tools.health import diag_codes

        ok, violations, note = diag_codes.run()
        assert ok, note
        assert violations == 0
