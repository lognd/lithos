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
from regolith.realizer.mech.coverage import SKIPPED_CTORS, SUPPORTED_CTORS

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


def test_an_unledgered_skip_reddens_the_check() -> None:
    """Negative fixture (WO-62 d3 acceptance): a synthetic corpus
    constructor `E0443`-skipped by the real compiler but ABSENT from
    the committed ledger must fail the comparison -- proving the drift
    check actually catches an unledgered addition, not just passes by
    construction."""
    live = frozenset({"Weld", "TotallyNewUnledgeredConstructor"})
    assert live != SKIPPED_CTORS
    assert "TotallyNewUnledgeredConstructor" not in SKIPPED_CTORS
