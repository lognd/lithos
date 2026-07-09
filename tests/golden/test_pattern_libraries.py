"""Pattern-library machinery (WO-53, AD-28/D144): the seed packs' and
the Batch A/Batch B content-addendum packs' `expect:` fixtures run
green, and INV-3 discipline (`advise:` is a verdict-inert warning,
never release-gated, AD-21) holds both when a recognition rule fires
(the `expect: fail` fixture) and when it defers because the corpus
fixture supplies no matching structural entities (the AD-22-escalated
gap named in the fixture files' headers: neither `pivots` nor `nets`
carries populated fields yet, the same status WO-28's own close-out
recorded for jlc_2l's domains).

Batch A (std.elec.patterns: decoupling, reverse_polarity, tvs_clamp,
rc_debounce, ldo) and Batch B (std.mech.mechanisms: slider_crank,
lead_screw, belt_drive, gear_train, bearing_arrangement,
helical_spring) are the cycle-28 market research memo's two
v1-blocking pattern-pack content batches (memo sec. 9 rows 1-2),
landed here as a content addendum to WO-53 (which stays CLOSED; see
that WO file's addendum note).

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

# Batch B (mech) content-addendum packs.
_SLIDER_CRANK_PACK = "stdlib/std.mech.mechanisms/slider_crank.hema"
_LEAD_SCREW_PACK = "stdlib/std.mech.mechanisms/lead_screw.hema"
_BELT_DRIVE_PACK = "stdlib/std.mech.mechanisms/belt_drive.hema"
_GEAR_TRAIN_PACK = "stdlib/std.mech.mechanisms/gear_train.hema"
_BEARING_ARRANGEMENT_PACK = "stdlib/std.mech.mechanisms/bearing_arrangement.hema"
_HELICAL_SPRING_PACK = "stdlib/std.mech.mechanisms/helical_spring.hema"

# Batch A (elec) content-addendum packs.
_DECOUPLING_PACK = "stdlib/std.elec.patterns/decoupling.cupr"
_REVERSE_POLARITY_PACK = "stdlib/std.elec.patterns/reverse_polarity.cupr"
_TVS_CLAMP_PACK = "stdlib/std.elec.patterns/tvs_clamp.cupr"
_RC_DEBOUNCE_PACK = "stdlib/std.elec.patterns/rc_debounce.cupr"
_LDO_PACK = "stdlib/std.elec.patterns/ldo.cupr"

_MECH_PACKS = (
    _FOUR_BAR_PACK,
    _SLIDER_CRANK_PACK,
    _LEAD_SCREW_PACK,
    _BELT_DRIVE_PACK,
    _GEAR_TRAIN_PACK,
    _BEARING_ARRANGEMENT_PACK,
    _HELICAL_SPRING_PACK,
)
_ELEC_PACKS = (
    _LEVEL_SHIFTER_PACK,
    _DECOUPLING_PACK,
    _REVERSE_POLARITY_PACK,
    _TVS_CLAMP_PACK,
    _RC_DEBOUNCE_PACK,
    _LDO_PACK,
)
_ALL_PACKS = _MECH_PACKS + _ELEC_PACKS

_BATCH_B_ADVICE_FIXTURE = "examples/tracks/hematite/mech_patterns_batch_b_advice.hema"
_BATCH_A_ADVICE_FIXTURE = "examples/tracks/cuprite/elec_patterns_batch_a_advice.cupr"


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


def test_batch_b_mech_expect_fixtures_are_green() -> None:
    """`rules test` over the Batch B mech content addendum (slider_crank,
    lead_screw, belt_drive, gear_train, bearing_arrangement,
    helical_spring): every case ok, no lints (mirrors the seed test)."""
    result = compiler.rules_test(_MECH_PACKS)
    assert result.is_ok, f"rules_test errored: {result}"
    reports = result.danger_ok
    assert {r.pack for r in reports} == {"std.mech.mechanisms"}
    for report in reports:
        _log.info("pack %s: %d cases, ok=%s", report.pack, len(report.cases), report.ok)
        assert report.ok, f"{report.pack} fixture failures: {report.cases}"
        assert not report.lints, f"{report.pack} lints: {report.lints}"


def test_batch_a_elec_expect_fixtures_are_green() -> None:
    """`rules test` over the Batch A elec content addendum (decoupling,
    reverse_polarity, tvs_clamp, rc_debounce, ldo): every case ok, no
    lints (mirrors the seed test)."""
    result = compiler.rules_test(_ELEC_PACKS)
    assert result.is_ok, f"rules_test errored: {result}"
    reports = result.danger_ok
    assert {r.pack for r in reports} == {"std.elec.patterns"}
    for report in reports:
        _log.info("pack %s: %d cases, ok=%s", report.pack, len(report.cases), report.ok)
        assert report.ok, f"{report.pack} fixture failures: {report.cases}"
        assert not report.lints, f"{report.pack} lints: {report.lints}"


def test_batch_ab_fail_case_is_an_advisory_not_a_release_gate() -> None:
    """Every Batch A/B rule's `expect: fail` case reports `outcome='ok'`
    through the `advise:` severity path, never a `demand:` obligation
    (AD-21), mirroring the seed patterns' verdict-inertness proof."""
    result = compiler.rules_test(_ALL_PACKS)
    assert result.is_ok
    for report in result.danger_ok:
        fail_cases = [c for c in report.cases if c.expected == "fail"]
        assert fail_cases, f"{report.pack}: no fail case to prove verdict-inertness on"
        for case in fail_cases:
            assert case.outcome == "ok", (
                f"{report.pack}/{case.rule}: expected the fail fixture to "
                f"reproduce the promised (advisory) verdict, got {case.outcome}"
            )


def test_batch_ab_advice_pack_attachment_never_blocks_check() -> None:
    """Attaching the Batch A/B packs bare never blocks `check`, whether
    a rule fires or honestly defers for lack of populated structural
    entities (INV-3 discipline, AD-21) -- mirrors the seed proof."""
    for fixture in (_BATCH_B_ADVICE_FIXTURE, _BATCH_A_ADVICE_FIXTURE):
        result = compiler.check((fixture,))
        assert result.is_ok, f"{fixture}: check errored: {result}"
        outcome = result.danger_ok
        assert outcome.ok, f"{fixture}: check reported not-ok: {outcome.rendered}"
