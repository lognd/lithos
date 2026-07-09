"""Pattern-library machinery (WO-53, AD-28/D144): the two seed packs'
`expect:` fixtures run green, and INV-3 discipline (`advise:` is a
verdict-inert warning, never release-gated, AD-21) holds both when the
recognition rule fires (the `expect: fail` fixture) and when it defers
because the corpus fixture supplies no matching structural entities
(the AD-22-escalated gap named in both fixture files' headers: neither
`pivots` nor `nets` carries populated fields yet, the same status
WO-28's own close-out recorded for jlc_2l's domains).

Drives the typed facade only (`regolith.compiler.rules_test`/`check`,
AD-4), mirroring `tests/golden/test_rules_cli.py`'s shape.
"""

from __future__ import annotations

import logging

from regolith import compiler

_log = logging.getLogger(__name__)

_FOUR_BAR_PACK = "stdlib/std.mech.mechanisms/four_bar.hema"
_LEVEL_SHIFTER_PACK = "stdlib/std.elec.patterns/level_shifter.cupr"
_FOUR_BAR_ADVICE_FIXTURE = "examples/tracks/hematite/four_bar_pattern_advice.hema"
_LEVEL_SHIFTER_ADVICE_FIXTURE = (
    "examples/tracks/cuprite/level_shifter_pattern_advice.cupr"
)


def test_seed_pattern_expect_fixtures_are_green() -> None:
    """`rules test` over both WO-53 seed packs: every case ok, no lints
    (each recognition rule carries both a pass and a fail case)."""
    result = compiler.rules_test((_FOUR_BAR_PACK, _LEVEL_SHIFTER_PACK))
    assert result.is_ok, f"rules_test errored: {result}"
    reports = result.danger_ok
    assert {r.pack for r in reports} == {
        "std.mech.mechanisms",
        "std.elec.patterns",
    }
    for report in reports:
        _log.info("pack %s: %d cases, ok=%s", report.pack, len(report.cases), report.ok)
        assert report.ok, f"{report.pack} fixture failures: {report.cases}"
        assert not report.lints, f"{report.pack} lints: {report.lints}"


def test_seed_pattern_fail_case_is_an_advisory_not_a_release_gate() -> None:
    """The `expect: fail` case (the shape that WOULD recommend the
    pattern) reports `outcome='ok'` -- the engine matched the promised
    verdict -- through the `advise:` severity path, never a `demand:`
    obligation (AD-21: only `demand:` severities release-gate)."""
    result = compiler.rules_test((_FOUR_BAR_PACK, _LEVEL_SHIFTER_PACK))
    assert result.is_ok
    for report in result.danger_ok:
        fail_cases = [c for c in report.cases if c.expected == "fail"]
        assert fail_cases, f"{report.pack}: no fail case to prove verdict-inertness on"
        for case in fail_cases:
            assert case.outcome == "ok", (
                f"{report.pack}/{case.rule}: expected the fail fixture to "
                f"reproduce the promised (advisory) verdict, got {case.outcome}"
            )


def test_advice_pack_attachment_never_blocks_check() -> None:
    """Attaching an `advise:`-only pack (bare `process=` form, the
    `wire_ampacity` precedent) never blocks `check`, whether the rule
    fires or honestly defers for lack of populated structural entities
    (INV-3 discipline, AD-21) -- the corpus proof deliverable 5 asks
    for, alongside the `expect:`-fixture proof above."""
    for fixture in (_FOUR_BAR_ADVICE_FIXTURE, _LEVEL_SHIFTER_ADVICE_FIXTURE):
        result = compiler.check((fixture,))
        assert result.is_ok, f"{fixture}: check errored: {result}"
        outcome = result.danger_ok
        assert outcome.ok, f"{fixture}: check reported not-ok: {outcome.rendered}"
