"""WO-97 / D209 coupling: pin a bounded sketch-segment optimize slot from
a REAL per-candidate discharge-margin search.

D209 ruled that a bounded geometric slot's optimizer evaluator IS the
discharge pipeline specialized per candidate -- there is no new evaluator
concept. This module is that specialization for the corpus's bounded
profile-width slots (`<seg>.length = in [lo, hi] minimize`) whose owning
part carries a cantilever-deflection claim:

    per candidate width `b`
      -> section second moment I(b)                       (geometry-at-b)
      -> `mech.beam.cantilever_deflection` DischargeRequest (the model
         channel `beam_bending.py` already registers -- F126.1's gap was
         that a label-named `mech.deflection(...)` claim never REACHED it;
         here the coupling recognizes the claim by its call form and
         drives the model directly, geometry in hand)
      -> feasible iff the deflection margin discharges (>= 0)
      -> objective = the slot value itself (minimize)

The winner is a genuine search result, pinned as a `LockRow.cause =
optimize(...)` (never a guessed literal). A part whose deflection inputs
do NOT resolve from declared data (e.g. `uav_talon` WingSpar, whose gust
reaction is `derived(sf=1.5)` with no declared scalar) stays honestly
`optimizer_evaluator_deferred` -- this module never fabricates a load.

Provenance of the model: Euler-Bernoulli cantilever, end point load,
`delta = F*L**3 / (3*E*I)` (`beam_bending.py`'s cited formula). The
section orientation is DOCUMENTED, not inferred: the optimized width `b`
is the bending depth (the flat plate resists the tip load about the axis
perpendicular to `b`), so `I = t * b**3 / 12` with `t` the plate
thickness -- deflection shrinks as `b` grows, which is exactly what makes
`minimize b` a constrained search rather than a free ride to the lower
bound in the general case.

E2 (the WO-97 result-to-part linkage gap) is resolved by CONSTRUCTION
here: the coupling works from the declared part (its `FeatureProgram`
`part_name` and its named deflection claim), never from an
`ObligationResult.subject_ref` content hash -- so "the part's governing
claim" is selected by name, no new content-hash-to-part channel needed.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.beam_bending import CLAIM_KIND as _CANTILEVER_KIND
from regolith.orchestrator.lockfile import LockRow
from regolith.orchestrator.optimize import (
    EvalOutcome,
    OptimizationTrace,
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
    ResolvedParam,
    Sketch,
    Stage,
)

_log = logging.getLogger(__name__)

# The call form F126.1 routes by: a label-named claim whose resolved LHS
# is a whole `mech.deflection(...)` call is a cantilever-deflection claim
# regardless of the author's label (`sag`/`tip_defl`/`payload_deflection`).
# One home for the string; mirrors `translate._FRAME_FORM_NAMES`' entry.
# frob:doc docs/modules/py-orchestrator.md#optimize_sketch
CANTILEVER_CALL_FORM = "mech.deflection"

# Default search budget: golden-section over one bounded scalar converges
# well inside this (the WO-70 spar-cap proof uses 40).
_DEFAULT_BUDGET = 40


# frob:doc docs/modules/py-orchestrator.md#optimize_sketch
class CantileverSlot(BaseModel):
    """A bounded profile-width slot plus its owning part's resolved
    cantilever-deflection claim -- every input drawn from DECLARED data
    (the profile walk, the `under=<F>` claim clause, the part material
    record), never derived or guessed.

    Lengths are SI metres, force newtons, modulus pascals. `lo_m`/`hi_m`
    are the slot bounds; `length_m` the cantilever span (the pinned
    profile run); `thickness_m` the plate thickness (the extrude
    distance); `limit_m` the deflection bound the claim asserts.
    """

    model_config = ConfigDict(frozen=True)

    part_name: str
    profile: str
    segment: str
    material: str
    lo_m: float
    hi_m: float
    length_m: float
    thickness_m: float
    force_n: float
    e_pa: float
    limit_m: float

    @property
    # frob:doc docs/modules/py-orchestrator.md#optimize_sketch
    # frob:waive TEST001 reason="sketch-opt helper, tested via wo97 optimize tests"
    def slot_id(self) -> str:
        """The lockfile slot spelling `Part.Profile.segment` (INV-21)."""
        return f"{self.part_name}.{self.profile}.{self.segment}"


# frob:doc docs/modules/py-orchestrator.md#optimize_sketch
def section_inertia_m4(thickness_m: float, width_m: float) -> float:
    """Rectangular section second moment about the bending axis, with the
    optimized `width_m` as the bending depth: `I = t * b**3 / 12`
    (documented orientation, see the module docstring)."""
    return thickness_m * width_m**3 / 12.0


def _rect_program(slot: CantileverSlot, width_m: float) -> FeatureProgram:
    """The part's realizer program at candidate `width_m`: the profile
    rectangle (`length_m` run x `width_m`) extruded `thickness_m` deep.

    Same shape as `test_wo70_uav_talon_optimize._spar_cap_program` -- the
    bounded segment substituted as a plain literal, so the realized solid
    is the genuine candidate geometry (STEP-able), not a stand-in.
    """
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=slot.length_m, y=0.0),
        Point2(x=slot.length_m, y=width_m),
        Point2(x=0.0, y=width_m),
    )
    sketch = Sketch(name="blank", outline=outline)
    op = ExtrudeOp(
        name="body", sketch=sketch, distance=ResolvedParam(value=slot.thickness_m)
    )
    stage = Stage(name="mill", process="cnc_mill", features=(op,))
    return FeatureProgram(
        part_name=slot.part_name, material=slot.material, stages=(stage,)
    )


# frob:doc docs/modules/py-orchestrator.md#optimize_sketch
# frob:waive TEST001 reason="sketch-opt helper, tested via wo97 optimize tests"
def make_slot_evaluator(slot: CantileverSlot, store: PayloadStore):
    """A genuine build+discharge evaluator for `slot` (D209): candidate
    width -> realized geometry + a real deflection-margin verdict.

    Feasibility is the harness's own discharge verdict on the cantilever
    claim (margin >= 0), NOT a hand-rolled inequality; the objective is
    the slot width itself (minimize). Every call stores the realized
    geometry so the winner carries STEP-able evidence back to the store.
    """

    def evaluator(assignment: tuple[float, ...]) -> EvalOutcome:
        (width_m,) = assignment
        i_area = section_inertia_m4(slot.thickness_m, width_m)
        request = DischargeRequest(
            claim_kind=_CANTILEVER_KIND,
            limit=slot.limit_m,
            inputs={
                "force": Interval.point(slot.force_n),
                "length": Interval.point(slot.length_m),
                "e_modulus": Interval.point(slot.e_pa),
                "i_area": Interval.point(i_area),
            },
        )
        evidence = default_registry().discharge(request)
        feasible = evidence.status.value == "discharged"

        realized = realize_feature_program(_rect_program(slot, width_m))
        digests: tuple[str, ...] = ()
        if realized.is_ok:
            digest = store.put(realized.danger_ok.geometry.model_dump_json().encode())
            digests = (digest,)

        _log.debug(
            "slot %s candidate b=%.5fm I=%.3ee-8 verdict=%s",
            slot.slot_id,
            width_m,
            i_area * 1e8,
            evidence.status.value,
        )
        return EvalOutcome(
            feasible=feasible,
            objective_vector=(width_m,),
            verdict_summary=(
                f"{slot.slot_id} b={width_m * 1000:.3f}mm {evidence.status.value}"
            ),
            evidence_digests=digests,
        )

    return evaluator


# frob:doc docs/modules/py-orchestrator.md#optimize_sketch
class PinnedSlotArtifact(BaseModel):
    """The shippable outcome of literalizing a bounded slot (WO116R-F2):
    the winning width (`Bounded -> Pinned`), the realizer subject its
    pinned program is keyed under, and the native STEP artifact
    (`step_content_hash` + bytes) now resident in the project's
    `NativeArtifactStore` -- exactly where `preview`/`ship` read native
    part bytes, so the optimizer-pinned geometry is a visible artifact."""

    model_config = ConfigDict(frozen=True)

    subject: str
    width_m: float
    step_content_hash: str
    step_bytes: bytes
    lock_cause: str


# frob:doc docs/modules/py-orchestrator.md#optimize_sketch
def pinned_slot_program(slot: CantileverSlot, width_m: float) -> FeatureProgram:
    """The literalized realizer program: the bounded slot pinned to the
    search winner (`Bounded -> Pinned`), the SAME candidate geometry the
    D209 evaluator scored -- ready for the preview/ship producers."""
    return _rect_program(slot, width_m)


# frob:doc docs/modules/py-orchestrator.md#optimize_sketch
def stage_pinned_slot(
    slot: CantileverSlot,
    paths: tuple[str, ...],
    *,
    subject: str | None = None,
    budget_evals: int = _DEFAULT_BUDGET,
) -> Result[PinnedSlotArtifact, OrchestratorError]:
    """Run the D209 margin search, LITERALIZE the winning width
    (`Bounded -> Pinned`), and route the pinned program through
    `staged_build`'s override channel so its native STEP lands in the
    project's `NativeArtifactStore` -- exactly where `preview`/`ship`
    read native part bytes (WO116R-F2's CLI/preview wiring gap). The
    optimizer-pinned `arm_a6 UpperArm.b` (~24mm) thereby ships a visible
    STEP artifact.

    `Err` (never a fabricated pin/artifact) when the search DEFERS -- no
    candidate width discharges the deflection claim (the honest
    `optimizer_evaluator_deferred` outcome, uav_talon WingSpar's fate).
    """
    # Local imports: `orchestrate` imports the orchestrator surface, so a
    # module-level import here would cycle.
    from regolith.orchestrator.orchestrate import _project_root, staged_build
    from regolith.orchestrator.payload_store import PayloadStore
    from regolith.orchestrator.tiers import BuildTier

    subject = subject or f"{slot.part_name}.body"
    project_root = _project_root(paths)
    store = PayloadStore(project_root)
    trace, row = pin_bounded_slot(slot, store, budget_evals=budget_evals)
    if row.is_err:
        _log.info(
            "stage_pinned_slot %s: search deferred (%s); no artifact shipped",
            slot.slot_id,
            trace.termination.value,
        )
        return Err(row.danger_err)

    # An Ok winner row implies a converged trace with a winner index
    # (`winner_lock_row` returns `Err` otherwise) -- guard for the type
    # checker and against a contract drift, never a silent None-index.
    if trace.winner is None:
        return Err(
            OrchestratorError(
                kind="optimize_no_winner",
                message=f"pinned slot {slot.slot_id}: winner row without a "
                "winner index (contract drift)",
            )
        )
    winner = trace.candidates[trace.winner].objective_vector[0]
    program = pinned_slot_program(slot, winner)

    # Route the LITERALIZED program through the production staged_build
    # override channel so its native STEP is persisted exactly like every
    # other realized part (`orchestrate.staged_build` puts native STEP at
    # realize time into `NativeArtifactStore(project_root)`).
    build_result = staged_build(
        paths, BuildTier.BUILD, feature_programs={subject: program}
    )
    if build_result.is_err:
        return Err(build_result.danger_err)

    realized = realize_feature_program(program)
    if realized.is_err:
        return Err(
            OrchestratorError(
                kind="realize_failed",
                message=f"pinned slot {slot.slot_id} did not realize: "
                f"{realized.danger_err}",
            )
        )
    artifact = realized.danger_ok
    _log.info(
        "stage_pinned_slot %s: pinned b=%.3fmm shipped as %s (step=%s)",
        slot.slot_id,
        winner * 1000.0,
        subject,
        artifact.geometry.step_content_hash,
    )
    return Ok(
        PinnedSlotArtifact(
            subject=subject,
            width_m=winner,
            step_content_hash=artifact.geometry.step_content_hash,
            step_bytes=artifact.step_bytes,
            lock_cause=row.danger_ok.cause,
        )
    )


# frob:doc docs/modules/py-orchestrator.md#optimize_sketch
def pin_bounded_slot(
    slot: CantileverSlot,
    store: PayloadStore,
    *,
    budget_evals: int = _DEFAULT_BUDGET,
) -> tuple[OptimizationTrace, Result[LockRow, OrchestratorError]]:
    """Run the D209 coupling for `slot` and return the search trace plus
    its winner lockfile row (`cause = optimize(...)`).

    The trace's termination is `infeasible` when NO candidate width
    discharges the deflection claim (the honest
    `optimizer_evaluator_deferred` outcome, surfaced as a real search
    result rather than a fabricated pin); otherwise the winner is the
    minimal feasible width.
    """
    trace = optimize_continuous_golden_section(
        bounds=(slot.lo_m, slot.hi_m),
        evaluator=make_slot_evaluator(slot, store),
        budget_evals=budget_evals,
    )
    trace_digest = store_trace(store, trace)
    _log.info(
        "bounded-slot optimize %s: termination=%s winner=%s",
        slot.slot_id,
        trace.termination.value,
        trace.winner,
    )
    row = winner_lock_row(trace, slot.slot_id, "declared_objective", trace_digest)
    return trace, row
