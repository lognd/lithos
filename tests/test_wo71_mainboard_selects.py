"""WO-71 D183 demonstration 2: `by select` on >= 2 regulator stages
in `examples/flagships/mainboard_mx/power_tree.cupr` (`Rail5V`,
`Rail3V3`), pinned via a real `regolith optimize` run with a declared
cost objective (cause + trace in the lockfile row). Template:
`tests/test_wo56_ebi_decode.py` (WO-56 D161's `by select` shape) --
same D168 chain: real `.cupr` source -> `regolith.compiler.check` ->
`BuildPayload.choice_points` -> `domains_from_choice_points` ->
`optimize_discrete` -> `winner_lock_row` (INV-21 `cause:
optimize(...)` pin). Proves both stages are genuinely policy-driven
via the same policy-flip discipline WO-56 established.
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
MAINBOARD_SOURCE = REPO_ROOT / "examples" / "flagships" / "mainboard_mx"

# Declared, closed-form per-candidate cost tables (regolith/12 sec. 4's
# `policy: minimize` surface does not yet parse a numeric cost
# expression -- see `domains_from_choice_points`'s docstring; same
# documented closed-form-only discipline the WO-56 test uses). Ledger
# refs (WO-71 dispatch prompt): Rail5V candidates are a discrete buck
# (tps54331, 2-part class), an integrated buck module (mp2315, single
# part), and a higher-current discrete buck (ltc3891, more BOM);
# Rail3V3 candidates are a buck (tps62130), an LDO (tps7a47, cheapest
# part count but worse efficiency -- still the declared cost winner
# under the "cheap" table to prove the flip is real), and a second
# buck variant (mp2315b).
_COST_5V_BUCK_MODULE_CHEAP = {
    "Rail5V.Rail5V": {
        "buck_tps54331": 1.85,
        "buck_mp2315": 0.95,
        "buck_ltc3891": 3.20,
    }
}
_COST_5V_DISCRETE_CHEAP = {
    "Rail5V.Rail5V": {
        "buck_tps54331": 0.60,
        "buck_mp2315": 1.40,
        "buck_ltc3891": 3.20,
    }
}
_COST_3V3_LDO_CHEAP = {
    "Rail3V3.Rail3V3": {
        "buck_tps62130": 1.10,
        "ldo_tps7a47": 0.35,
        "buck_mp2315b": 1.25,
    }
}
_COST_3V3_BUCK_CHEAP = {
    "Rail3V3.Rail3V3": {
        "buck_tps62130": 0.40,
        "ldo_tps7a47": 1.30,
        "buck_mp2315b": 1.25,
    }
}


def _compiled_choice_points() -> dict[str, dict[str, object]]:
    result = compiler.check((str(MAINBOARD_SOURCE),))
    assert result.is_ok, result
    outcome = result.danger_ok
    assert outcome.ok, "mainboard_mx must check clean"
    payload = json.loads(outcome.payload_json)
    choice_points = payload["choice_points"]
    assert choice_points, "mainboard_mx must lower real ChoicePoints"
    return choice_points


def test_mainboard_has_two_regulator_choice_points() -> None:
    """The compiled artifact's `BuildPayload.choice_points` carries
    both declared regulator-stage select subjects (D183 demonstration
    2: >= 2 stages), each with its exact declared candidate set."""
    choice_points = _compiled_choice_points()
    assert {"Rail5V.Rail5V", "Rail3V3.Rail3V3"} <= set(choice_points)
    assert choice_points["Rail5V.Rail5V"]["candidate_refs"] == [
        "buck_tps54331",
        "buck_mp2315",
        "buck_ltc3891",
    ]
    assert choice_points["Rail3V3.Rail3V3"]["candidate_refs"] == [
        "buck_tps62130",
        "ldo_tps7a47",
        "buck_mp2315b",
    ]


def _run(subject: str, cost_table: dict[str, dict[str, float]], tmp_path: Path):
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
    store = PayloadStore(tmp_path)
    digest = store_trace(store, trace)
    row_result = winner_lock_row(trace, subject, "cost", digest)
    assert row_result.is_ok, row_result
    return trace, row_result.danger_ok


def test_rail5v_picks_the_policy_best_candidate(tmp_path: Path) -> None:
    """`buck_mp2315` (cost 0.95, cheapest) wins the declared-cost
    objective; the winning pin's `cause` names the real trace digest
    (INV-21)."""
    trace, row = _run("Rail5V.Rail5V", _COST_5V_BUCK_MODULE_CHEAP, tmp_path)
    assert trace.termination.value == "converged"
    winner = trace.candidates[trace.winner]
    assert (
        dict(item.root for item in winner.assignment)["Rail5V.Rail5V"] == "buck_mp2315"
    )
    assert row.cause.startswith("optimize(cost, trace=")
    assert "buck_mp2315" in row.value


def test_rail5v_flipping_cost_order_flips_the_winner(tmp_path: Path) -> None:
    """Policy-flip test: reversing the declared cost preference flips
    which candidate the SAME real ChoicePoint's search picks."""
    _, row_module = _run("Rail5V.Rail5V", _COST_5V_BUCK_MODULE_CHEAP, tmp_path)
    _, row_discrete = _run("Rail5V.Rail5V", _COST_5V_DISCRETE_CHEAP, tmp_path)
    assert "buck_mp2315" in row_module.value
    assert "buck_tps54331" in row_discrete.value
    assert row_module.value != row_discrete.value


def test_rail3v3_picks_the_policy_best_candidate(tmp_path: Path) -> None:
    trace, row = _run("Rail3V3.Rail3V3", _COST_3V3_LDO_CHEAP, tmp_path)
    assert trace.termination.value == "converged"
    winner = trace.candidates[trace.winner]
    assert (
        dict(item.root for item in winner.assignment)["Rail3V3.Rail3V3"]
        == "ldo_tps7a47"
    )
    assert row.cause.startswith("optimize(cost, trace=")
    assert "ldo_tps7a47" in row.value


def test_rail3v3_flipping_cost_order_flips_the_winner(tmp_path: Path) -> None:
    _, row_ldo = _run("Rail3V3.Rail3V3", _COST_3V3_LDO_CHEAP, tmp_path)
    _, row_buck = _run("Rail3V3.Rail3V3", _COST_3V3_BUCK_CHEAP, tmp_path)
    assert "ldo_tps7a47" in row_ldo.value
    assert "buck_tps62130" in row_buck.value
    assert row_ldo.value != row_buck.value
