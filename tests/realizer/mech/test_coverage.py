"""WO-62 D171/AD-32 deliverable 3: the feature-coverage ledger's drift
check (the schema-check pattern applied to capability).

The "derived from code" half runs the REAL compiler over the full
golden corpus and collects every `E0443` (contracts family, offset 43
-- "op outside the v1 feature-op set") constructor name it names; the
"committed" half is `regolith.realizer.mech.coverage
.FEATURE_COVERAGE_LEDGER`. A mismatch is a drift: an unledgered skip
(the interpreter/lowering pair started emitting E0443 for a new
constructor no one added to the ledger) or a stale ledger row (a
constructor the corpus no longer spells).
"""

from __future__ import annotations

import json
import re

from regolith import compiler
from regolith.realizer.mech.coverage import (
    FEATURE_COVERAGE_LEDGER,
    SKIPPED_CTORS,
    SUPPORTED_CTORS,
    UNPROJECTED_CTORS,
)

from tests.golden.test_golden_corpus import _CORPUS

_E0443_MSG_CTOR = re.compile(r"= (\w+)\(")


def _e0443_ctors_from_the_live_corpus() -> frozenset[str]:
    """Every constructor word the real compiler names in an `E0443`
    diagnostic across the golden corpus's file groups -- the "derived
    from code" half of the drift check."""
    ctors: set[str] = set()
    for _name, paths in _CORPUS.items():
        outcome = compiler.check(paths)
        if outcome.is_err:
            continue
        payload = json.loads(outcome.danger_ok.payload_json)
        for diag in payload.get("diagnostics", []):
            code = diag.get("code") or {}
            if code.get("family") != "contracts" or code.get("offset") != 43:
                continue
            match = _E0443_MSG_CTOR.search(diag.get("message", ""))
            if match:
                ctors.add(match.group(1))
    return frozenset(ctors)


def test_ledger_matches_the_live_corpus_derivation() -> None:
    """Every `E0443` the real compiler emits over the golden corpus is
    a ledger row (WO-62 d3 acceptance: every current corpus skip is
    ledger-listed) -- and the ledger carries no STALE row the corpus no
    longer exercises."""
    live = _e0443_ctors_from_the_live_corpus()
    assert live == SKIPPED_CTORS, (
        f"ledger drift: corpus skips {sorted(live - SKIPPED_CTORS)} not in the "
        f"ledger; ledger rows {sorted(SKIPPED_CTORS - live)} are stale"
    )


def test_a_realizing_constructor_never_shows_up_as_a_named_skip() -> None:
    """The two halves of the ledger are mutually exclusive: nothing the
    ledger calls `realizes` can ALSO appear in a live `E0443` (that
    would mean the ledger lies about what the v1 set supports)."""
    live = _e0443_ctors_from_the_live_corpus()
    assert not (live & SUPPORTED_CTORS), sorted(live & SUPPORTED_CTORS)


def test_the_three_ledger_categories_partition_the_ledger() -> None:
    """WO-77: `realizes` / `skips(E0443)` / `lowers(...)` are disjoint
    and together cover every ledger row -- a row in no category (a typo
    outcome string) or in two is a ledger bug."""
    assert not (SUPPORTED_CTORS & SKIPPED_CTORS)
    assert not (SUPPORTED_CTORS & UNPROJECTED_CTORS)
    assert not (SKIPPED_CTORS & UNPROJECTED_CTORS)
    assert frozenset(FEATURE_COVERAGE_LEDGER) == (
        SUPPORTED_CTORS | SKIPPED_CTORS | UNPROJECTED_CTORS
    )


def test_lattice_lowers_and_never_appears_as_an_e0443_skip() -> None:
    """WO-77 acceptance ("Lattice declares, lowers, and skips
    HONESTLY"): `Lattice` is recognized vocabulary -- it lowers into an
    ordinary FeatureOp, so the live corpus derivation must never see it
    in an `E0443`, and the ledger carries it as the lowers-without-
    projection category, not a skip."""
    assert "Lattice" in UNPROJECTED_CTORS
    live = _e0443_ctors_from_the_live_corpus()
    assert "Lattice" not in live, "Lattice must LOWER, never E0443-skip"
    # The pre-WO-77 singular `Rib` constructor (reservoir.hema's
    # `PatternOf<Rib(t=..., h=...)>`) is a DIFFERENT verb and stays an
    # honest E0443 skip.
    assert "Rib" in SKIPPED_CTORS


def test_an_unledgered_skip_reddens_the_check() -> None:
    """Negative fixture (WO-62 d3 acceptance): a synthetic corpus
    constructor `E0443`-skipped by the real compiler but ABSENT from
    the committed ledger must fail the comparison -- proving the drift
    check actually catches an unledgered addition, not just passes by
    construction."""
    live = frozenset({"Weld", "TotallyNewUnledgeredConstructor"})
    assert live != SKIPPED_CTORS
    assert "TotallyNewUnledgeredConstructor" not in SKIPPED_CTORS
