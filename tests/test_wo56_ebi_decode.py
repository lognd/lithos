"""WO-56 deliverable 6: the `ebi_decode` elec demo, end to end.

`examples/tracks/cuprite/ebi_decode.cupr` declares
`impl AddressDecodeGlue by select(nor_glue, cpld, mcu_chip_selects)`
(D161, the sixth impl strategy). This test proves the FULL D168 chain
for real, not a synthetic spec:

    real `.cupr` source
    -> `regolith.compiler.check` (the real compiler)
    -> `BuildPayload.choice_points` (D168's first-class field,
       `regolith-lower::contracts::select_choice_point`)
    -> `regolith.orchestrator.optimize.domains_from_choice_points`
    -> `optimize_discrete` (the real discrete driver)
    -> `winner_lock_row` (INV-21 `cause: optimize(...)` pin)

and that the winner is genuinely policy-driven: flipping the declared
per-candidate cost table's preference flips which candidate wins (the
WO-56 "policy-flip" test named in the WO's close-out).
"""

from __future__ import annotations

import json
from pathlib import Path

from regolith import compiler
from regolith.orchestrator.nogood_cache import NogoodCache
from regolith.orchestrator.optimize import (
    domains_from_choice_points,
    optimize_discrete,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.payload_store import PayloadStore

REPO_ROOT = Path(__file__).resolve().parent.parent
EBI_DECODE_SOURCE = REPO_ROOT / "examples" / "tracks" / "cuprite" / "ebi_decode.cupr"

# The declared, closed-form per-candidate cost table for this demo
# (regolith/12 sec. 4's `policy: minimize` surface does not yet parse a
# numeric cost expression -- see `domains_from_choice_points`'s
# docstring; this is the same documented closed-form-only discipline
# `discrete_domains_from_spec`'s own `costs` table already uses).
# Ledger refs (WO-56 dispatch prompt): nor_glue = ti.logic.sn74hc138 +
# ti.logic.sn74hc02 (two discrete parts, higher part-count cost); cpld
# = microchip.cpld.atf1502asl_7 (one part, mid cost); mcu_chip_selects
# = st.mcu.stm32f4_fsmc_bank1 (no added part -- the MCU already has the
# FSMC controller, lowest cost).
_COST_NOR_GLUE_HIGH = {
    "decoder_board.AddressDecodeGlue": {
        "nor_glue": 2.40,  # two 74HC parts
        "cpld": 1.10,  # one CPLD
        "mcu_chip_selects": 0.0,  # no added part
    }
}

# The SAME domain, with the cost order flipped end to end (nor_glue
# now cheapest): the policy-flip test proves the winner is genuinely
# read from the declared objective, not hardcoded.
_COST_NOR_GLUE_CHEAP = {
    "decoder_board.AddressDecodeGlue": {
        "nor_glue": 0.0,
        "cpld": 1.10,
        "mcu_chip_selects": 2.40,
    }
}


def _compiled_choice_points() -> dict[str, dict[str, object]]:
    result = compiler.check((str(EBI_DECODE_SOURCE),))
    assert result.is_ok, result
    outcome = result.danger_ok
    assert outcome.ok, "ebi_decode.cupr must check clean"
    payload = json.loads(outcome.payload_json)
    choice_points = payload["choice_points"]
    assert choice_points, "ebi_decode.cupr must lower a real ChoicePoint"
    return choice_points


# frob:tests python/regolith/orchestrator/optimize.py::discrete_domains_from_spec
def test_ebi_decode_choice_point_is_real_and_subject_keyed() -> None:
    """The compiled artifact's `BuildPayload.choice_points` carries the
    exact declared subject/candidates -- not an invented placeholder."""
    choice_points = _compiled_choice_points()
    assert set(choice_points) == {"decoder_board.AddressDecodeGlue"}
    cp = choice_points["decoder_board.AddressDecodeGlue"]
    assert cp["candidate_refs"] == ["nor_glue", "cpld", "mcu_chip_selects"]


def _run(cost_table: dict[str, dict[str, float]], tmp_path: Path):
    choice_points = _compiled_choice_points()
    domains, evaluator, screen, objective = domains_from_choice_points(
        choice_points, cost_table
    )
    trace = optimize_discrete(
        domains,
        evaluator,
        objective,
        seed=0,
        budget_evals=100,
        screen=screen,
        nogood_cache=NogoodCache(),
    )
    store = PayloadStore(str(tmp_path))
    digest = store_trace(store, trace)
    row_result = winner_lock_row(
        trace, "decoder_board.AddressDecodeGlue", "cost", digest
    )
    assert row_result.is_ok, row_result
    return trace, row_result.danger_ok


def test_ebi_decode_picks_the_policy_best_candidate(tmp_path: Path) -> None:
    """`mcu_chip_selects` (cost 0.0) wins the declared-cost objective;
    the winning pin's `cause` names the real trace digest (INV-21)."""
    trace, row = _run(_COST_NOR_GLUE_HIGH, tmp_path)
    assert trace.termination.value == "converged"
    winner = trace.candidates[trace.winner]
    assert dict(item.root for item in winner.assignment) == {
        "decoder_board.AddressDecodeGlue": "mcu_chip_selects"
    }
    assert row.cause.startswith("optimize(cost, trace=")
    assert "mcu_chip_selects" in row.value


def test_flipping_the_cost_order_flips_the_winner(tmp_path: Path) -> None:
    """The policy-flip test: reversing the declared cost preference
    (nor_glue cheapest instead of mcu_chip_selects) flips which
    candidate the SAME real ChoicePoint's search picks."""
    _, row_high = _run(_COST_NOR_GLUE_HIGH, tmp_path)
    _, row_cheap = _run(_COST_NOR_GLUE_CHEAP, tmp_path)
    assert "mcu_chip_selects" in row_high.value
    assert "nor_glue" in row_cheap.value
    assert row_high.value != row_cheap.value
