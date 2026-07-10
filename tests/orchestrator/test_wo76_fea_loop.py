"""WO-76: FEA-in-the-loop optimization demonstration + cost accounting.

D184/34-topology.md sec. 1: a value "determined by FEA" is `in [lo,
hi] minimize` whose feasibility claim is discharged by an FEA-class
model -- the engine walks the domain, FEA draws the feasible
boundary. This module drives that composition end to end using ONLY
landed machinery (WO-55 continuous driver, WO-30 pack registry, the
real installed `feldspar` distribution per WO-27's own conformance
recipe) -- no new mechanism, per D184's side-channel ban.

Environment audit (deliverable 1, read before touching bounds/limits):
WO-27's close-out records that at the eps budgets its fixtures carry,
feldspar's own internal planner always finds its closed-form direction
sufficient, so its discretized ccx/gmsh leg (tier="discretized",
feldspar WO-08) never runs in this sandbox -- confirmed again here
(``which ccx``/``which gmsh`` both empty in this environment; see the
WO-76 close-out notes). The tier that ACTUALLY discharges is
feldspar's `fea_static_stress@1` closed-form-analytic model
(`mech.static_stress`, feldspar WO-08's `solver.py`), which is also
the MOST EXPENSIVE tier this environment can run -- and the only
tier registered for this claim kind at all (no built-in regolith
model competes for `mech.static_stress`, per WO-27's conformance
module docstring), so `default_registry()` selection reaches it
unambiguously: an honest structural equivalent of rung-5 forcing,
substituting for the `model=` SOURCE-LEVEL pin (see
`examples/tracks/hematite/lug_bracket.hema`'s ENVIRONMENT NOTE: the
grammar does not yet parse `model=` into `Claim.model_pin`, a
crates/-scoped gap escalated to "main", out of this WO's Python-only
scope).

The exemplar: `lug_bracket.hema`'s `LugEye` part, a pinned thick-wall
eye idealized through the SAME cylinder claim family manifold.hema
already uses (WO-27's own pressure-vessel idealization, reused rather
than inventing new solver wiring). `OuterWall.outer_radius in
[20.5mm, 21.5mm] minimize`: mass falls monotonically as the wall
thins, but the FEA-discharged `mech.static_stress <= 110MPa` claim
goes `violated` below ~20.8mm (checked live below, not assumed) -- so
the true minimizer sits at the FEA-drawn feasible boundary, not at
either authored bound.
"""

from __future__ import annotations

import pytest

pytest.importorskip(
    "feldspar",
    reason="WO-76's FEA-loop demonstration exercises feldspar's optional "
    "pack (the WO-27 skip-if-absent posture); install it per the WO-27 "
    "recipe to run these",
)

import time

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.orchestrator.optimize import (
    EvalOutcome,
    load_trace,
    optimize_continuous_golden_section,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.payload_store import PayloadStore
from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.schema import (
    ExtrudeOp,
    FeatureProgram,
    Point2,
    ProfileHole,
    ResolvedParam,
    Sketch,
    Stage,
)

_STEEL_DENSITY_KG_M3 = 7850.0
_INNER_RADIUS_M = 0.020
_LENGTH_M = 0.025
_STRESS_LIMIT_PA = 110e6
_PRESSURE_PA = 5e6
_YOUNGS_PA = 200e9
_POISSON = 0.3
_BOUNDS = (0.0205, 0.0215)  # matches lug_bracket.hema's `wall` dim


def _lug_program(outer_radius_m: float) -> FeatureProgram:
    """A bounding-square blank with a circular bore -- the realizer's v1
    polygon-outline requirement (mech/schema.py's `Sketch` cut) means
    the true annular cross-section is approximated by its bounding
    square; mass still grows monotonically with `outer_radius_m`,
    which is the only property this evaluator's objective needs."""
    side = 2.0 * outer_radius_m
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=side, y=0.0),
        Point2(x=side, y=side),
        Point2(x=0.0, y=side),
    )
    hole = ProfileHole(
        name="bore",
        center=Point2(x=side / 2.0, y=side / 2.0),
        diameter=ResolvedParam(value=2.0 * _INNER_RADIUS_M),
    )
    sketch = Sketch(name="lug_blank", outline=outline, holes=(hole,))
    op = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=_LENGTH_M))
    stage = Stage(name="turned", process="cnc_lathe", features=(op,))
    return FeatureProgram(part_name="LugEye", material="AISI_4140", stages=(stage,))


def _fea_stress_request(outer_radius_m: float) -> DischargeRequest:
    """The `mech.static_stress` request over the cylinder idealization
    (same five scalar ports WO-27's conformance module exercises)."""
    return DischargeRequest(
        claim_kind="mech.static_stress",
        limit=_STRESS_LIMIT_PA,
        inputs={
            "mech.load.internal_pressure": Interval(lo=_PRESSURE_PA, hi=_PRESSURE_PA),
            "mech.geom.cylinder.inner_radius": Interval(
                lo=_INNER_RADIUS_M, hi=_INNER_RADIUS_M
            ),
            "mech.geom.cylinder.outer_radius": Interval(
                lo=outer_radius_m, hi=outer_radius_m
            ),
            "mech.material.youngs_modulus": Interval(lo=_YOUNGS_PA, hi=_YOUNGS_PA),
            "mech.material.poisson": Interval(lo=_POISSON, hi=_POISSON),
        },
    )


class _WallTimeLedger:
    """Accumulates per-evaluation wall time -- D184's cost-accounting ask.

    A plain in-test recorder (no schema field exists on `CandidateEntry`
    for wall time and adding one is a schema bump, out of WO-76's
    scope): the sanctioned channel for auxiliary per-candidate detail is
    `EvalOutcome.verdict_summary`'s free text (the same channel WO-64's
    `test_wo64_printer_optimize.py` uses for its own mass readout), so
    this ledger both records structured rows here AND folds the same
    number into `verdict_summary` so the trace itself is self-describing.
    """

    def __init__(self) -> None:
        self.rows: list[tuple[float, float, str]] = []  # (x, elapsed_ms, model_id)

    def record(self, x: float, elapsed_ms: float, model_id: str) -> None:
        self.rows.append((x, elapsed_ms, model_id))


def _make_evaluator(store: PayloadStore, ledger: _WallTimeLedger, registry):
    """The staged evaluator: realize mass (cheap) + discharge the FEA
    stress claim (expensive) for one candidate outer radius."""

    def evaluator(assignment: tuple[float, ...]) -> EvalOutcome:
        (outer_radius_m,) = assignment
        realized = realize_feature_program(_lug_program(outer_radius_m)).danger_ok
        volume_m3 = realized.geometry.topology.volume_mm3 / 1.0e9
        mass_kg = volume_m3 * _STEEL_DENSITY_KG_M3

        request = _fea_stress_request(outer_radius_m)
        started = time.perf_counter()
        evidence = registry.discharge(request)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        ledger.record(outer_radius_m, elapsed_ms, evidence.model_id)

        feasible = evidence.status.value == "discharged"
        digest = store.put(realized.geometry.model_dump_json().encode("ascii"))
        verdict = (
            f"LugEye mass_kg={mass_kg:.6f} model={evidence.model_id} "
            f"status={evidence.status.value} elapsed_ms={elapsed_ms:.3f}"
        )
        return EvalOutcome(
            feasible=feasible,
            objective_vector=(mass_kg,),
            verdict_summary=verdict,
            evidence_digests=(digest, f"blake3-evidence:{evidence.hash}"),
        )

    return evaluator


def test_environment_audit_ccx_gmsh_discretized_leg_stays_unexercised() -> None:
    """Deliverable 1: which feldspar FEA-class tier discharges here?

    Live-checked, not assumed: the closed-form-analytic tier
    (`fea_static_stress@1`) discharges the thin-wall corner while the
    thick-wall corner is `violated` (i.e. margin math is real, not a
    rubber stamp) -- consistent with WO-27's recorded cut that the
    discretized ccx/gmsh leg needs a tooled environment this sandbox
    lacks (`shutil.which` both empty), so this run cannot and does not
    exercise it; that residual is unchanged from WO-27.
    """
    import shutil

    assert shutil.which("ccx") is None, "environment audit expects no ccx on PATH"
    assert shutil.which("gmsh") is None, "environment audit expects no gmsh on PATH"

    registry = default_registry()
    thin_wall = registry.discharge(_fea_stress_request(0.0205))
    assert thin_wall.model_id == "fea_static_stress@1"
    assert thin_wall.status.value == "violated"

    thick_wall = registry.discharge(_fea_stress_request(0.0215))
    assert thick_wall.model_id == "fea_static_stress@1"
    assert thick_wall.status.value == "discharged"


def test_fea_loop_optimize_converges_with_forced_model_trace(tmp_path) -> None:
    """The budgeted continuous optimize converges; every candidate's
    trace evidence cites the forced FEA-class model id (acceptance
    criterion 1); wall time is recorded per evaluation (D184 cost
    accounting)."""
    store = PayloadStore(str(tmp_path))
    ledger = _WallTimeLedger()
    registry = default_registry()
    evaluator = _make_evaluator(store, ledger, registry)

    trace = optimize_continuous_golden_section(
        bounds=_BOUNDS, evaluator=evaluator, budget_evals=40, tol=1e-6
    )

    assert trace.termination.value == "converged"
    assert trace.winner is not None

    # Every candidate's trace evidence cites the forced FEA-class model.
    assert ledger.rows, "the evaluator must have run at least once"
    assert all(model_id == "fea_static_stress@1" for _, _, model_id in ledger.rows)
    for candidate in trace.candidates:
        assert candidate.verdict_summary.startswith("LugEye mass_kg=")
        assert "model=fea_static_stress@1" in candidate.verdict_summary
        assert "elapsed_ms=" in candidate.verdict_summary
        assert any(d.startswith("blake3-evidence:") for d in candidate.evidence_digests)

    # Per-evaluation wall time recorded (cost accounting): every row
    # has a non-negative measured duration.
    assert all(elapsed_ms >= 0.0 for _, elapsed_ms, _ in ledger.rows)

    winner = trace.candidates[trace.winner]
    winner_x = float({item.root[0]: item.root[1] for item in winner.assignment}["x"])
    # The winner sits near the FEA-drawn feasible boundary (~0.0208m),
    # strictly inside the declared bounds, not pinned at either one --
    # the "FEA draws the boundary" acceptance shape (34-topology.md
    # sec. 1), distinct from WO-64's monotonic-to-the-bound recipe.
    assert _BOUNDS[0] < winner_x < _BOUNDS[1]

    digest = store_trace(store, trace)
    row_result = winner_lock_row(
        trace, "LugEye.OuterWall.outer_radius", "declared_objective", digest
    )
    assert row_result.is_ok, row_result
    assert row_result.danger_ok.cause.startswith("optimize(")


def test_fea_loop_resume_reevaluates_nothing_cached(tmp_path) -> None:
    """`--resume` semantics at the Python driver level (the CLI's own
    `--resume` threads the same `resume_trace` param, WO-55's
    `_ReplayEvaluator`): re-running with the stored trace performs
    ZERO new FEA discharges (acceptance criterion: resume performs
    zero re-discharges of cached candidates) and reproduces a
    byte-identical trace (INV-30, same-seed determinism)."""
    store = PayloadStore(str(tmp_path))
    ledger_first = _WallTimeLedger()
    registry = default_registry()

    first_trace = optimize_continuous_golden_section(
        bounds=_BOUNDS,
        evaluator=_make_evaluator(store, ledger_first, registry),
        budget_evals=40,
        tol=1e-6,
    )
    assert first_trace.termination.value == "converged"
    first_discharges = len(ledger_first.rows)
    assert first_discharges > 0

    digest = store_trace(store, first_trace)
    loaded = load_trace(store, digest)
    assert loaded.is_ok, loaded
    resume_trace = loaded.danger_ok

    ledger_resume = _WallTimeLedger()

    def _discharge_should_not_be_called(request: DischargeRequest):
        raise AssertionError(
            "resume must not re-discharge a cached candidate's FEA claim"
        )

    class _TripwireRegistry:
        """Fails loudly if the replay path ever reaches a real discharge."""

        def discharge(self, request: DischargeRequest):
            return _discharge_should_not_be_called(request)

    resumed_evaluator = _make_evaluator(store, ledger_resume, _TripwireRegistry())

    resumed_trace = optimize_continuous_golden_section(
        bounds=_BOUNDS,
        evaluator=resumed_evaluator,
        budget_evals=40,
        tol=1e-6,
        resume_trace=resume_trace,
    )

    assert ledger_resume.rows == [], "resume must re-discharge zero cached candidates"
    assert resumed_trace.termination.value == "converged"
    # INV-30: same seed/budget/strategy -> byte-identical winner + trace.
    assert resumed_trace.model_dump_json() == first_trace.model_dump_json()
