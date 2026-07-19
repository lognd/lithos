"""WO-78 / charter 35 sec. 3(c): the `by select` stackup choice flips
with the cost policy, with impedance feasibility as the screen.

`examples/tracks/cuprite/si_board.cupr` declares
`impl SiStackup by select(jlc04161h_7628, jlc06161h_7628,
jlc04161h_1080)` (D161's sixth impl strategy, lowered to a real
`BuildPayload.choice_points` entry). This test drives the D168 chain
over it with the charter's OWN feasibility rule: a candidate is
feasible iff the board's 50-ohm impedance window is achievable on it
(discharged by the feldspar model over the candidate's record
geometry at the board's w=0.36mm). jlc04161h_1080 is the CHEAPEST
candidate in both cost tables and NEVER wins: its thin outer prepreg
puts Z0 at 26.9 ohm, outside every window -- "impedance-feasible +
cost-best", honestly, never "cheapest regardless".

Costs are the declared closed-form per-candidate table (the WO-56
`test_wo56_ebi_decode.py` convention: `policy: minimize` does not yet
parse numeric cost expressions): the 4-layer JLC04161H-7628 vs its
6-layer sibling JLC06161H-7628 -- identical published outer geometry,
identical impedance verdicts, different layer counts. Under
4L-cheapest the 4-layer wins; flipping the cost order flips the
winner to the 6-layer: the LAYER COUNT is genuinely the policy's
decision, not hardcoded.
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip(
    "feldspar",
    reason="WO-78's stackup-select feasibility screen discharges the "
    "feldspar impedance model (the WO-27 skip-if-absent posture)",
)

import json
from collections.abc import Mapping
from pathlib import Path

from regolith import compiler
from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.orchestrator.nogood_cache import NogoodCache
from regolith.orchestrator.optimize import (
    ChoicePointDomain,
    EvalOutcome,
    optimize_discrete,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.si_stackups import load_si_context

REPO_ROOT = Path(__file__).resolve().parent.parent
_SI_BOARD = REPO_ROOT / "examples" / "tracks" / "cuprite" / "si_board.cupr"
_SUBJECT = "SiBoard.SiStackup"
_W_M = 0.00036  # the board's declared trace width
_WINDOW = (45.0, 55.0)  # the board's 50-ohm class window

# Declared per-candidate cost tables (arbitrary units; the flip is the
# point). jlc04161h_1080 is cheapest in BOTH -- and screened out by
# impedance infeasibility in both.
_COST_4L_CHEAP = {"jlc04161h_7628": 2.0, "jlc06161h_7628": 5.0, "jlc04161h_1080": 1.0}
_COST_6L_CHEAP = {"jlc04161h_7628": 5.0, "jlc06161h_7628": 2.0, "jlc04161h_1080": 1.0}


def _compiled_choice_point() -> dict[str, Any]:
    result = compiler.check((str(_SI_BOARD),))
    assert result.is_ok, result
    payload = json.loads(result.danger_ok.payload_json)
    cp = payload["choice_points"][_SUBJECT]
    assert cp["candidate_refs"] == [
        "jlc04161h_7628",
        "jlc06161h_7628",
        "jlc04161h_1080",
    ]
    return cp


def _si_context():
    result = load_si_context(
        str(REPO_ROOT), record_search_paths=(str(REPO_ROOT / "stdlib"),)
    )
    assert result.is_ok, result
    return result.danger_ok


def _impedance_feasible(registry, record) -> tuple[bool, float]:
    """Both window halves discharged on this candidate's published
    geometry -- charter sec. 1.4's feasibility rule, verbatim."""
    h_m, er, t_m = (
        record.microstrip_h_m(),
        record.microstrip_er(),
        record.microstrip_t_m(),
    )
    assert h_m is not None and er is not None
    inputs = {
        "elec.si.microstrip.w": Interval(lo=_W_M, hi=_W_M),
        "elec.si.microstrip.h": Interval(lo=h_m, hi=h_m),
        "elec.si.microstrip.t": Interval(lo=t_m, hi=t_m),
        "elec.si.microstrip.er": Interval(lo=er, hi=er),
    }
    statuses = []
    for kind, limit in (
        ("elec.si.microstrip_z0.lo", _WINDOW[0]),
        ("elec.si.microstrip_z0.hi", _WINDOW[1]),
    ):
        evidence = registry.discharge(
            DischargeRequest(claim_kind=kind, limit=limit, inputs=inputs)
        )
        statuses.append(evidence.status.value)
    return all(s == "discharged" for s in statuses), h_m


def _run(cost_table: Mapping[str, float], tmp_path: Path):
    cp = _compiled_choice_point()
    registry = default_registry()
    si_context = _si_context()
    domain = ChoicePointDomain(subject=_SUBJECT, candidates=tuple(cp["candidate_refs"]))

    def evaluator(assignment: Mapping[str, str]) -> EvalOutcome:
        candidate = assignment[_SUBJECT]
        record = si_context.stackups[candidate]
        feasible, _ = _impedance_feasible(registry, record)
        return EvalOutcome(
            feasible=feasible,
            objective_vector=(cost_table[candidate],),
            verdict_summary=(
                f"{candidate}: layers={record.layer_count} "
                f"impedance_feasible={feasible} cost={cost_table[candidate]}"
            ),
        )

    trace = optimize_discrete(
        (domain,),
        evaluator,
        ["minimize"],
        seed=0,
        budget_evals=10,
        nogood_cache=NogoodCache(),
    )
    assert trace.termination.value == "converged"
    store = PayloadStore(str(tmp_path))
    digest = store_trace(store, trace)
    row = winner_lock_row(trace, _SUBJECT, "cost", digest)
    assert row.is_ok, row
    return trace, row.danger_ok


# frob:tests python/regolith/orchestrator/si_stackups.py::StackupRecord.microstrip_h_m
# frob:tests python/regolith/orchestrator/si_stackups.py::StackupRecord.microstrip_er
# frob:tests python/regolith/orchestrator/si_stackups.py::StackupRecord.microstrip_t_m
def test_infeasible_cheapest_candidate_never_wins(tmp_path: Path) -> None:
    """jlc04161h_1080 (cost 1.0, Z0 = 26.9 ohm) is evaluated, found
    impedance-infeasible, and loses to a costlier feasible candidate --
    the screen is real, and it is IN the trace, auditable."""
    trace, row = _run(_COST_4L_CHEAP, tmp_path)
    assert "jlc04161h_1080" not in row.value
    infeasible = [
        c for c in trace.candidates if "impedance_feasible=False" in c.verdict_summary
    ]
    assert infeasible, [c.verdict_summary for c in trace.candidates]
    assert all("jlc04161h_1080" in c.verdict_summary for c in infeasible)


def test_cost_policy_flip_flips_the_layer_count(tmp_path: Path) -> None:
    """Charter sec. 3(c): the same board, the same claims, the same
    screen -- flipping the declared cost order flips the chosen
    stackup between the 4-layer and 6-layer siblings, each pin
    carrying its `optimize(cost, trace=...)` cause (INV-21)."""
    _, row_4l = _run(_COST_4L_CHEAP, tmp_path)
    _, row_6l = _run(_COST_6L_CHEAP, tmp_path)
    assert "jlc04161h_7628" in row_4l.value
    assert "jlc06161h_7628" in row_6l.value
    assert row_4l.value != row_6l.value
    for row in (row_4l, row_6l):
        assert row.cause.startswith("optimize(cost, trace=")
