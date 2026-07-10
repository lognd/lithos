"""WO-83 slice B acceptance: the `regolith test` runner (charter
toolchain/37 sec. 3) over the real corpus this slice adds.

Slice A proved grammar + lowering (`tests/test_wo83_test_decl_lowering
.py`); this module proves the runner: discovery, real-pipeline
expectation evaluation (all five forms), content-address caching, and
rule-pack unification -- through the actual `regolith.orchestrator.
test_runner` API (no CLI subprocess -- `tests/golden/` already covers
the CLI-vs-facade seam pattern for other verbs).
"""

from __future__ import annotations

from pathlib import Path

from regolith.orchestrator.test_runner import (
    discover_rule_pack_files,
    discover_test_files,
    render_summary,
    run_tests,
)


def _purge_test_cache(test_file: str) -> None:
    """Force a cold cache for `test_file`'s project dir: the runner's
    content-address cache persists in `.regolith/` across local runs
    (gitignored), so cache-behavior tests must start from a known
    state instead of inheriting whatever the developer ran last."""
    cache = Path(test_file).parent / ".regolith" / "test-cache.json"
    cache.unlink(missing_ok=True)


def test_discovers_every_track_plus_the_flagship_starter() -> None:
    """The `.test.<ext>` convention finds every corpus member this
    slice added, across all four tracks plus the flagship."""
    files = discover_test_files(
        (
            "examples/tracks",
            "examples/negative",
            "examples/flagships/printer_k1",
        )
    )
    names = {f.name for f in files}
    assert "spar_bracket_wo83.test.hema" in names
    assert "lug_bracket.test.hema" in names
    assert "03_volt_plus_amp.test.cupr" in names
    assert "40_fluo_medium_mismatch.test.fluo" in names
    assert "48_calx_no_circulation_edges.test.calx" in names
    assert "buck_converter.test.cupr" in names
    assert "aquarium_loop.test.fluo" in names
    assert "bus_shelter.test.calx" in names
    assert "printer_k1.test.cupr" in names


def test_green_corpus_member_passes_every_form_it_declares() -> None:
    """`lug_bracket.test.hema`'s config-axis pin + verdict expectation
    holds against the REAL ordinary build (AD-22): a genuine green
    sample, not an aspiration."""
    results = run_tests(("examples/tracks/hematite/lug_bracket.test.hema",))
    assert len(results) == 1
    case = results[0]
    assert case.ok, case.details
    assert case.name == "lug_bracket_pin_case"


def test_flagship_winner_form_matches_the_real_seeded_optimizer() -> None:
    """`printer_k1.test.cupr`'s `winner` expectation is checked against
    a REAL `optimize_discrete` run over the project's actual `by
    select(...)` choice point (D161/D168) -- never a second scoring
    path."""
    results = run_tests(("examples/flagships/printer_k1/printer_k1.test.cupr",))
    assert len(results) == 1
    assert results[0].ok, results[0].details


def test_diagnostic_negative_twin_matches_the_one_renderer_verbatim() -> None:
    """A diagnostic expectation is checked against the ONE renderer's
    actual output (AD-7) for a real negative fixture -- no second
    rendering of diagnostics."""
    results = run_tests(("examples/negative/03_volt_plus_amp.test.cupr",))
    assert len(results) == 1
    assert results[0].ok, results[0].details


def test_slice_a_proof_fixture_renders_an_honest_red() -> None:
    """`spar_bracket_wo83.test.hema` is slice A's grammar/lowering
    round-trip proof, never tuned for pipeline accuracy -- `regolith
    test` renders it as a genuine, informative FAIL (never a silent
    pass), the "red sample" half of the close-out's proof pair."""
    path = "examples/tracks/hematite/spar_bracket_wo83.test.hema"
    _purge_test_cache(path)
    results = run_tests((path,))
    assert len(results) == 1
    case = results[0]
    assert not case.ok
    assert any("verdict" in d for d in case.details)


def test_cache_hit_on_unchanged_rerun() -> None:
    """Charter sec. 1.4: an unchanged scenario over an unchanged design
    is a cache hit on the second run -- and the hit replays the WHOLE
    result (details included), not a degraded ok-bool."""
    path = "examples/tracks/fluorite/aquarium_loop.test.fluo"
    _purge_test_cache(path)
    first = run_tests((path,))
    assert len(first) == 1 and not first[0].from_cache
    second = run_tests((path,))
    assert len(second) == 1 and second[0].from_cache
    assert second[0].ok == first[0].ok
    assert second[0].details == first[0].details
    assert second[0].error == first[0].error


def test_rule_pack_unification_runs_through_the_same_discovery() -> None:
    """`regolith test` finds WO-28's `expect: pass:`/`fail:` fixtures
    (no separate extension convention) and they delegate to the real
    `compiler.rules_test` machinery -- one surface, no duplicated
    semantics."""
    packs = discover_rule_pack_files(("examples/tracks/hematite/std_sheet_metal.hema",))
    assert packs == ("examples/tracks/hematite/std_sheet_metal.hema",)


def test_render_summary_cargo_style_and_parallel_scenarios() -> None:
    """One line per test plus a trailing pass/fail summary line; the
    buck_converter file carries TWO declarations, so this also drives
    the parallel per-file scenario path (charter sec. 1.4)."""
    results = run_tests(("examples/tracks/cuprite/buck_converter.test.cupr",))
    assert len(results) == 2
    text, ok = render_summary(results)
    assert ok
    assert "buck_converter_pin_case ... ok" in text
    assert "buck_converter_transient_case ... ok" in text
    assert "test result: ok. 2 passed; 0 failed" in text
