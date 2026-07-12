"""WO-14 lockfile: render/parse round-trip determinism and malformed input."""

from __future__ import annotations

from regolith.orchestrator.lockfile import Lockfile, LockRow, LockSection, parse, render


def _sample() -> Lockfile:
    return Lockfile(
        tool_version="0.1.0",
        sections=(
            LockSection(
                name="",
                rows=(
                    LockRow(
                        slot="flange.radius",
                        value="2.4mm",
                        cause="dfm(sheet.min_bend_radius)",
                    ),
                    LockRow(
                        slot="seat.runout",
                        value="+-0.015",
                        cause="budget(mesh_alignment)",
                        policy_note="prefer(low_cost)",
                    ),
                ),
                record_pins=(("jlc.pcb@2.3.0", "sha256:aa10f3"),),
            ),
            LockSection(
                name="flight",
                rows=(
                    LockRow(
                        slot="net.vdd.width",
                        value="0.3mm",
                        cause="drc(jlc_2l.current_capacity)",
                    ),
                ),
            ),
        ),
    )


def test_render_is_ascii_and_sorted() -> None:
    text = render(_sample())
    assert text.isascii()
    # base section ("") sorts before "flight"
    assert text.index('[section ""]') < text.index('[section "flight"]')
    # rows within a section are sorted by slot
    assert text.index("flange.radius") < text.index("seat.runout")


def test_render_cause_shape() -> None:
    text = render(_sample())
    assert "flange.radius = 2.4mm" in text
    assert "cause: dfm(sheet.min_bend_radius)" in text
    assert "policy: prefer(low_cost)" in text


def test_round_trip_identity() -> None:
    original = _sample()
    text1 = render(original)
    parsed = parse(text1).danger_ok
    text2 = render(parsed)
    assert text1 == text2
    assert parsed == original


def test_render_is_deterministic_across_calls() -> None:
    assert render(_sample()) == render(_sample())


def test_empty_lockfile_round_trips() -> None:
    empty = Lockfile(tool_version="0.1.0")
    text = render(empty)
    parsed = parse(text).danger_ok
    assert parsed == empty


def test_parse_rejects_missing_header() -> None:
    result = parse("not a lockfile\n")
    assert result.is_err
    assert result.danger_err.kind == "malformed_header"


def test_parse_rejects_row_before_section() -> None:
    result = parse("# regolith.lock tool_version=0.1.0\nfoo = bar cause: x\n")
    assert result.is_err
    assert result.danger_err.kind == "row_before_section"


def test_parse_rejects_malformed_row() -> None:
    text = '# regolith.lock tool_version=0.1.0\n[section ""]\nno equals sign here\n'
    result = parse(text)
    assert result.is_err
    assert result.danger_err.kind == "malformed_row"


def test_parse_rejects_pin_before_section() -> None:
    text = "# regolith.lock tool_version=0.1.0\npin foo@1.0 = sha256:abc\n"
    result = parse(text)
    assert result.is_err
    assert result.danger_err.kind == "pin_before_section"


# --- F124.2: accepted waiver match-set persistence + cross-build diff ---


def test_waiver_section_round_trips() -> None:
    """A waiver section persists each target's accepted hashes and parses
    back byte-stably (targets + hashes sorted)."""
    from regolith.orchestrator.lockfile import waiver_match_sets, waiver_section

    match_sets = {
        "Strength.fatigue_life": frozenset({"h2", "h1"}),
        "Manufacture.makeable": frozenset({"hx"}),
    }
    section = waiver_section(match_sets)
    assert section is not None
    lockfile = Lockfile(tool_version="0.1.0", sections=(section,))
    text = render(lockfile)
    parsed = parse(text)
    assert parsed.is_ok, parsed
    assert waiver_match_sets(parsed.danger_ok) == {
        "Strength.fatigue_life": frozenset({"h1", "h2"}),
        "Manufacture.makeable": frozenset({"hx"}),
    }


def test_waiver_section_empty_is_none() -> None:
    """No accepted hashes -> no section (a clean build adds nothing)."""
    from regolith.orchestrator.lockfile import waiver_section

    assert waiver_section({}) is None
    assert waiver_section({"T": frozenset()}) is None


def test_waiver_match_sets_absent_section() -> None:
    """An older lockfile with no waivers section yields an empty prior map."""
    from regolith.orchestrator.lockfile import waiver_match_sets

    assert waiver_match_sets(Lockfile(tool_version="0.1.0")) == {}


def test_accepted_match_sets_feed_growth_diff() -> None:
    """The persisted map is exactly what the next build diffs to warn on an
    unscoped waiver's cross-build match-set growth (INV-12 rule 5)."""
    from regolith.orchestrator.acceptance import (
        AcceptanceOutcome,
        Deviation,
        accepted_match_sets_by_target,
        match_set_growth_warnings,
    )

    prior = AcceptanceOutcome(
        accepted_hashes=("h1",),
        deviations=(
            Deviation(
                target="Manufacture.makeable",
                scope=None,
                basis="b",
                evidence="test(fai)",
                kind="matched",
                accepted=("h1",),
                match_set=("h1",),
                expires=None,
            ),
        ),
    )
    prior_map = accepted_match_sets_by_target(prior)
    # Next build accepts h1 AND a new h2 under the same unscoped target.
    now = AcceptanceOutcome(
        accepted_hashes=("h1", "h2"),
        deviations=(
            Deviation(
                target="Manufacture.makeable",
                scope=None,
                basis="b",
                evidence="test(fai)",
                kind="matched",
                accepted=("h1", "h2"),
                match_set=("h1",),
                expires=None,
            ),
        ),
    )
    warnings = match_set_growth_warnings(now, prior_map)
    assert len(warnings) == 1
    assert "h2" in warnings[0]
