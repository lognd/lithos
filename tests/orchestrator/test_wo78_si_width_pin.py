# ruff: noqa: E501  -- long frob:tests directive symrefs exceed the 88-col house style; the exact path is load-bearing for the frob DSL and cannot wrap
"""WO-78 / charter 35 sec. 3(a): the engine pins trace width against a
50-ohm impedance claim, with the calculation in evidence.

D184's boundary-finding form, composed from landed machinery only (the
WO-76 FEA-loop recipe, model swapped): the trace width is an
`in [lo, hi] minimize` slot whose feasibility claim is the
`elec.impedance(...) within [45, 55] ohm` window discharged by the
feldspar Hammerstad-Jensen model over the JLC04161H-7628 stackup
record. Z0 falls as the trace widens, so `minimize w` drives the
search INTO the window's ceiling: the winner sits at the feasible
boundary (~0.315 mm, where Z0 + eps crosses 55 ohm), strictly inside
the authored bounds -- the pinned width IS the calculated design rule,
cause-attributed via `winner_lock_row` (INV-21).
"""

from __future__ import annotations

import pytest

pytest.importorskip(
    "feldspar",
    reason="WO-78's width-pin demonstration exercises feldspar's optional "
    "pack (the WO-27 skip-if-absent posture)",
)

from pathlib import Path

from regolith._schema.models import Obligation
from regolith.harness import default_registry
from regolith.orchestrator.optimize import (
    EvalOutcome,
    optimize_continuous_golden_section,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.si_stackups import load_si_context
from regolith.orchestrator.translate import translate

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BOUNDS = (0.00025, 0.00040)  # the authored `in [0.25mm, 0.40mm]` slot
_WINDOW = ("45", "55")  # the 50-ohm class window, ohms


def _si_context():
    result = load_si_context(
        str(REPO_ROOT), record_search_paths=(str(REPO_ROOT / "stdlib"),)
    )
    assert result.is_ok, result
    return result.danger_ok


def _half_obligation(suffix: str, op: str, rhs: str, w_m: float) -> Obligation:
    """One window half's obligation, exactly the shape the Rust
    lowering emits (`push_impedance_window_obligations`) with the
    candidate width substituted into the claim's `w=` kwarg."""
    lhs = (
        f"elec.impedance(clk, role=microstrip, stackup=jlc04161h_7628, "
        f"layer=outer, w={w_m})"
    )
    return Obligation.model_validate(
        {
            "claim": {
                "name": f"clk_z0.{suffix}",
                "form": {"form": "comparison", "lhs": lhs, "op": op, "rhs": rhs},
                "forall": [],
                "hints": [],
            },
            "subject_ref": "si-width-pin",
            "given": {"materials": [], "loads": [], "backing": [], "refs": []},
            "hints": [],
        }
    )


def _make_evaluator(registry, si_context, ledger: list[tuple[float, str, bool]]):
    """Feasibility = BOTH window halves discharge through the REAL
    translate() -> registry.discharge() path; objective = the width
    itself (minimize: the narrowest impedance-feasible trace)."""

    def evaluator(assignment: tuple[float, ...]) -> EvalOutcome:
        (w_m,) = assignment
        statuses = []
        model_ids = []
        for suffix, op, rhs in (("lo", ">=", _WINDOW[0]), ("hi", "<=", _WINDOW[1])):
            lowered = translate(
                _half_obligation(suffix, op, rhs, w_m), si_context=si_context
            )
            assert lowered.is_ok, lowered
            evidence = registry.discharge(lowered.danger_ok)
            statuses.append(evidence.status.value)
            model_ids.append(evidence.model_id)
        feasible = all(s == "discharged" for s in statuses)
        verdict = f"w={w_m:.6f} statuses={statuses} models={sorted(set(model_ids))}"
        ledger.append((w_m, verdict, feasible))
        return EvalOutcome(
            feasible=feasible,
            objective_vector=(w_m,),
            verdict_summary=verdict,
        )

    return evaluator


# frob:tests python/regolith/orchestrator/optimize.py::optimize_continuous_golden_section
# frob:tests python/regolith/harness/registry.py::ModelRegistry.model_ids
def test_width_pins_at_the_impedance_boundary(tmp_path) -> None:
    """The winner sits at the feasible boundary, strictly inside the
    authored bounds (never a bound pin); every evaluation's evidence
    cites the Hammerstad-Jensen model; the pin lands with an
    `optimize(...)` cause."""
    registry = default_registry()
    si_context = _si_context()
    ledger: list[tuple[float, str, bool]] = []
    evaluator = _make_evaluator(registry, si_context, ledger)

    trace = optimize_continuous_golden_section(
        bounds=_BOUNDS, evaluator=evaluator, budget_evals=40, tol=1e-7
    )

    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    winner_w = float({i.root[0]: i.root[1] for i in winner.assignment}["x"])

    # The boundary, not a bound: Z0(0.28mm)+eps busts 55 ohm and
    # Z0(0.40mm) is comfortably inside, so minimize-w must stop
    # strictly between the authored bounds, at the ceiling crossing.
    assert _BOUNDS[0] < winner_w < _BOUNDS[1]
    assert 0.00029 < winner_w < 0.00035, winner_w

    # Infeasible evaluations really happened below the boundary (the
    # boundary is DRAWN by the model, not assumed).
    assert any(not feasible for _, _, feasible in ledger), ledger
    assert any(feasible for _, _, feasible in ledger), ledger
    for _, verdict, _ in ledger:
        assert "elec_si_microstrip_z0" in verdict

    # The pinned width is the calculated design rule, cause-attributed.
    store = PayloadStore(str(tmp_path))
    digest = store_trace(store, trace)
    row = winner_lock_row(trace, "SiBoard.clk.width", "minimize_width", digest)
    assert row.is_ok, row
    assert row.danger_ok.cause.startswith("optimize(")
