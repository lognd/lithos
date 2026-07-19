"""Orchestrator: tiers, evidence cache, discharge routing, loop, release gate.

Exercises the AD-1 orchestrator seam with synthetic obligations and a test
harness model (no compiler pass needed): build-tier progression, cache
hit/miss + registry-version invalidation (INV-1/BE-1), the lazy loop, and
release-gate totality (INV-24).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from regolith._schema.models import (
    Claim,
    ClaimForm1,
    ClaimForm7,
    Form,
    Given,
    Obligation,
)
from regolith.harness import (
    ClaimSense,
    DischargeRequest,
    ModelRegistry,
    ModelSignature,
    Prediction,
)
from regolith.harness.attest import Valid
from regolith.harness.errors import HarnessError
from regolith.harness.model import Model
from regolith.magnetite import (
    KeyDesignation,
    TrustKeySet,
    TrustTier,
    generate_signing_key,
)
from regolith.orchestrator import (
    BuildTier,
    EvidenceStore,
    LockRow,
    ObligationResult,
    discharge_all,
    discharge_one,
    lazy_loop,
    obligation_cache_key,
    release_gate,
)
from regolith.orchestrator.orchestrate import (
    _pending_geom_extract_subjects,
    build,
    put_realized_geometry,
    realized_lock_rows,
    staged_build,
)
from regolith.orchestrator.payload_store import PayloadStore
from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.schema import (
    ExtrudeOp,
    FeatureProgram,
    FlowPath,
    FlowSegment,
    Point2,
    ResolvedParam,
    Sketch,
    Stage,
)
from typani.result import Ok, Result

from tests.realizer.mech.fixtures import coolant_bracket_program

_PLATE_OUTLINE = (
    Point2(x=0.0, y=0.0),
    Point2(x=0.02, y=0.0),
    Point2(x=0.02, y=0.02),
    Point2(x=0.0, y=0.02),
)


def _line_run_program(
    part_name: str, selector: str, *, flow_area_m2: float = 1.0e-4
) -> FeatureProgram:
    """A bare-plate `FeatureProgram` declaring one un-bore-backed flow
    path at ``selector`` (WO-42 deliverable 5 test fixture): mirrors
    ``coolant_bracket_program`` but with a caller-chosen selector so it
    can be made to match an arbitrary `.fluo` `from=<ref>` subject
    (`RealizedFlownetInputs::geometry`'s exact-string subject match).
    ``bore=None`` on the segment means D130's bore-consistency
    cross-check is skipped (existence-only validation, still exercised
    honestly -- this fixture is not gaming the validator, it simply has
    no bore feature to reference). ``flow_area_m2`` is overridable so a
    test can produce a second geometry variant (G42 anti-staleness).
    """
    sketch = Sketch(name="plate", outline=_PLATE_OUTLINE)
    extrude = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=0.001))
    stage = Stage(name="cut", process="laser_cut", features=(extrude,))
    segment = FlowSegment(
        role="run",
        flow_area=ResolvedParam(value=flow_area_m2),
        length=ResolvedParam(value=2.0),
        elevation_change=ResolvedParam(value=0.3),
        roughness_class="drawn_tube",
    )
    flow_path = FlowPath(selector=selector, segments=(segment,))
    return FeatureProgram(
        part_name=part_name,
        material="AISI_304",
        stages=(stage,),
        flow_paths=(flow_path,),
    )


# --- fixtures -------------------------------------------------------------


class _StressModel(Model):
    """A trivial upper-bound model: predicts the sum of its input corners."""

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="test.stress",
            claim_kind="stress",
            sense=ClaimSense.upper_bound(),
            inputs=("load",),
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def cost(self) -> int:
        return 1

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        load = request.inputs["load"]
        return Ok(Prediction(value=load.hi, eps=0.0, coverage=1.0, in_domain=True))


def _registry() -> ModelRegistry:
    reg = ModelRegistry(version="model-registry@test-1")
    reg.register(_StressModel())
    return reg


def _obligation(lhs: str, op: str, rhs: str, load: str) -> Obligation:
    return Obligation(
        claim=Claim(
            name=lhs,
            form=ClaimForm1(form=Form.comparison, lhs=lhs, op=op, rhs=rhs),
            forall=[],
            hints=[],
        ),
        subject_ref=f"blake3:{lhs}",
        given=Given(materials=[], loads=[f"load: {load}"], backing=[]),
        hints=[],
    )


# --- WO-32 D4b: flownet payload emission -----------------------------------


# frob:tests python/regolith/backends/drawings/renderer.py::content_digest
def test_build_puts_flownet_payloads_under_the_obligations_own_digest(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    """WO-32 D4b: `orchestrate.build` is the FIRST orchestrator
    `PayloadStore` producer. A `.fluo` source with a `fluids.*` claim
    lowers (D4a) to an obligation carrying a `kind: flownet` `PayloadRef`
    whose digest is the Rust-computed `FlownetPayload.content_digest()`
    (AD-18 canonical encoder); `build()` must store the payload bytes
    under EXACTLY that digest so a later `PayloadStore.resolve(digest)`
    (the D96 sec. 8.3 discharge-time handle) is a hit, not a miss.
    """
    src = (
        "medium Water: liquid\n"
        "    props: registry(potable_water_nist)\n"
        "flownet Loop(medium=Water):\n"
        "    reference: ambient(101kPa, 293K)\n"
        "    nodes: a, b\n"
        "    edges:\n"
        "        supply: Pipe(from=line.run) (a -> b)\n"
        "require Margin:\n"
        "    dp: fluids.dp(a -> b) <= 40kPa\n"
    )
    path = tmp_path / "loop.fluo"
    path.write_text(src, encoding="ascii")

    report = build((str(path),), BuildTier.BUILD).danger_ok
    assert report.ok, "a clean fluid source must lower without diagnostics"

    payload = json.loads(_check_payload_json(path))
    obligations = payload["obligations"]
    flownet_refs = [
        ref
        for ob in obligations
        for ref in ob.get("payloads") or []
        if ref["kind"] == "flownet"
    ]
    assert flownet_refs, "the fluid claim must lower to a flownet payload ref"

    store = PayloadStore(str(tmp_path))
    for ref in flownet_refs:
        resolved = store.resolve(ref["digest"])
        assert resolved.is_ok, (
            f"payload digest {ref['digest']!r} (origin={ref['origin']!r}) "
            "was not found in the store after build() -- the producer "
            "either stored under the wrong key or never ran"
        )
        stored = json.loads(resolved.danger_ok)
        assert stored["nodes"] == ["a", "b"]


def test_put_realized_geometry_stores_and_resolves(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """WO-42 deliverable 4's mech emission seam: a realized geometry's
    JSON bytes are stored under a fresh blake3 digest (no upstream
    Rust-computed digest exists yet for a standalone realizer output),
    and that exact digest resolves back to the same bytes.
    """
    artifact = realize_feature_program(coolant_bracket_program()).danger_ok
    store = PayloadStore(str(tmp_path))
    digest = put_realized_geometry(store, artifact)

    resolved = store.resolve(digest)
    assert resolved.is_ok, resolved.danger_err
    assert resolved.danger_ok == artifact.geometry.model_dump_json().encode("utf-8")

    # Idempotent: putting the same geometry twice returns the same digest.
    assert put_realized_geometry(store, artifact) == digest


def _check_payload_json(path) -> bytes:  # type: ignore[no-untyped-def]
    """The raw `check()` payload bytes for `path` (obligations only need
    the static pass; re-deriving here keeps this test independent of
    `build()`'s internal caching)."""
    from regolith import compiler

    return compiler.check((str(path),)).danger_ok.payload_json


# --- tiers ----------------------------------------------------------------


def test_tiers_are_totally_ordered() -> None:
    assert BuildTier.CHECK < BuildTier.BUILD < BuildTier.OPTIMIZE < BuildTier.RELEASE
    assert BuildTier.RELEASE.includes(BuildTier.CHECK)
    assert not BuildTier.CHECK.includes(BuildTier.BUILD)


# frob:tests python/regolith/orchestrator/tiers.py::BuildTier.runs_discharge
# frob:tests python/regolith/orchestrator/tiers.py::BuildTier.runs_loop
def test_tier_capability_flags() -> None:
    assert not BuildTier.CHECK.runs_discharge
    assert BuildTier.BUILD.runs_discharge
    assert BuildTier.OPTIMIZE.runs_loop
    assert BuildTier.RELEASE.is_release
    assert not BuildTier.BUILD.runs_loop


# --- evidence cache -------------------------------------------------------


def test_cache_key_folds_registry_version() -> None:
    ob = _obligation("stress", "<", "100", "50")
    k1 = obligation_cache_key(ob, "model-registry@1")
    k2 = obligation_cache_key(ob, "model-registry@2")
    assert k1 != k2  # BE-1: a model bump invalidates the key
    assert obligation_cache_key(ob, "model-registry@1") == k1  # deterministic


def test_cache_key_sensitive_to_obligation_content() -> None:
    a = _obligation("stress", "<", "100", "50")
    b = _obligation("stress", "<", "100", "60")  # different load
    assert obligation_cache_key(a, "v") != obligation_cache_key(b, "v")


# frob:tests python/regolith/orchestrator kind="integration"
# frob:tests python/regolith/harness kind="integration"
def test_discharge_hit_then_miss() -> None:
    reg = _registry()
    store = EvidenceStore()
    ob = _obligation("stress", "<", "100", "50")
    first = discharge_one(ob, registry=reg, store=store)
    assert not first.from_cache
    assert first.is_resolved  # 50 <= 100
    assert store.stats.misses == 1
    second = discharge_one(ob, registry=reg, store=store)
    assert second.from_cache
    assert store.stats.hits == 1


def test_cache_persist_round_trip(tmp_path) -> None:
    reg = _registry()
    store = EvidenceStore()
    ob = _obligation("stress", "<", "100", "50")
    discharge_one(ob, registry=reg, store=store)
    assert store.save(str(tmp_path)).is_ok
    reloaded = EvidenceStore.load(str(tmp_path)).danger_ok
    hit = discharge_one(ob, registry=reg, store=reloaded)
    assert hit.from_cache


# --- attestation column (WO-21) -------------------------------------------


def test_cache_attestation_column_round_trip(tmp_path) -> None:
    """A stored attestation persists and reloads beside its evidence."""
    reg = _registry()
    key = generate_signing_key(str(tmp_path), "project-1").danger_ok
    trust = TrustKeySet(
        designations=(
            KeyDesignation(
                key_id=key.key_id,
                public_key_base64=key.public_key_base64(),
                confers=TrustTier.TESTED,
            ),
        )
    )
    store = EvidenceStore()
    ob = _obligation("stress", "<", "100", "50")
    result = discharge_one(ob, registry=reg, store=store, signer=key, trust_keys=trust)
    assert store.attestation_of(result.key) is not None
    assert store.save(str(tmp_path)).is_ok

    reloaded = EvidenceStore.load(str(tmp_path)).danger_ok
    assert reloaded.attestation_of(result.key) == store.attestation_of(result.key)
    hit = discharge_one(ob, registry=reg, store=reloaded, signer=key, trust_keys=trust)
    assert hit.from_cache
    assert isinstance(hit.attestation, Valid)


# frob:tests python/regolith/orchestrator/nogood_cache.py::NogoodCache.cache_path
# frob:tests python/regolith/orchestrator/cache.py::EvidenceStore.cache_path
def test_cache_loads_old_bare_evidence_shape(tmp_path) -> None:
    """A WO-20 bare-Evidence cache row still loads (attestation None)."""
    reg = _registry()
    store = EvidenceStore()
    ob = _obligation("stress", "<", "100", "50")
    result = discharge_one(ob, registry=reg, store=store)
    # Write the OLD shape: `{key: <evidence>}`, no `{evidence, attestation}`.
    path = EvidenceStore.cache_path(str(tmp_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    assert result.evidence is not None
    path.write_text(
        json.dumps({result.key: result.evidence.model_dump(mode="json")}),
        encoding="ascii",
    )
    reloaded = EvidenceStore.load(str(tmp_path)).danger_ok
    assert reloaded.attestation_of(result.key) is None
    hit = discharge_one(ob, registry=reg, store=reloaded)
    assert hit.from_cache


# --- release gate (INV-24) ------------------------------------------------


def test_release_gate_passes_when_all_discharged() -> None:
    reg = _registry()
    store = EvidenceStore()
    results = discharge_all(
        [_obligation("stress", "<", "100", "50")], registry=reg, store=store
    )
    assert release_gate(results).is_ok


def test_release_gate_fails_on_violation() -> None:
    reg = _registry()
    store = EvidenceStore()
    results = discharge_all(
        [_obligation("stress", "<", "100", "150")], registry=reg, store=store
    )
    assert results[0].is_violated
    gate = release_gate(results)
    assert gate.is_err
    assert gate.danger_err.kind == "release_gate_failed"


def test_release_gate_fails_on_no_model_deferral() -> None:
    reg = _registry()
    store = EvidenceStore()
    # A claim kind with no registered model -> honest deferral (never a pass).
    results = discharge_all(
        [_obligation("unknown_kind", "<", "100", "50")], registry=reg, store=store
    )
    assert results[0].deferral is not None
    assert results[0].deferral.reason == "no_model"
    assert release_gate(results).is_err


def test_non_scalar_claim_defers() -> None:
    reg = _registry()
    store = EvidenceStore()
    ob = _obligation("stress", "within", "[0, 10]", "5")  # containment op defers
    result = discharge_one(ob, registry=reg, store=store)
    assert result.deferral is not None
    assert result.deferral.reason == "unsupported_op"


def test_require_placeholder_op_recovers_comparator_from_rhs() -> None:
    """The core lowers a `subject: predicate` claim with a fixed
    `op="require"` and the comparator inside `rhs` (`">= 6"`). translate
    must split it back out so the obligation lowers to a scalar request
    instead of deferring -- the fix that unblocks candidate/discharge."""
    from regolith.orchestrator.translate import translate

    ob = _obligation("margin", "require", ">= 6", "8")
    lowered = translate(ob)
    assert lowered.is_ok, lowered
    assert lowered.danger_ok.limit == 6.0


def _conforms_obligation(loads: list[str]) -> Obligation:
    """A synthetic INV-13 `conforms` obligation carrying `loads` verbatim."""
    return Obligation(
        claim=Claim(
            name="impl:Drive",
            form=ClaimForm1(form=Form.comparison, lhs="Drive", op="conforms", rhs="p"),
            forall=[],
            hints=[],
        ),
        subject_ref="blake3:conforms",
        given=Given(materials=[], loads=loads, backing=[]),
        hints=[],
    )


def test_conforms_spec_only_window_defers_with_the_teaching_reason() -> None:
    """D195 (WO-92): a conforms obligation whose spec side resolved (the
    core threaded `conformance_sense`/`spec_bound`/`conformance_field`)
    but whose impl asserts no bound defers with the DISTINCT
    `conformance_impl_bound_missing` reason, and its detail teaches: the
    resolved spec bound, the field name, and the two honest discharge
    paths (declare an impl-body bound, or realize the quantity)."""
    from regolith.orchestrator.translate import translate

    ob = _conforms_obligation(
        [
            "conformance_sense: upper",
            "spec_bound: 50",
            "conformance_field: power",
        ]
    )
    lowered = translate(ob)
    assert lowered.is_err, lowered
    deferral = lowered.danger_err
    assert deferral.reason == "conformance_impl_bound_missing"
    assert "power <= 50" in deferral.detail
    assert "declare a `power:` comparator bound" in deferral.detail
    assert "realized-fact channel" in deferral.detail


def test_conforms_with_no_window_keeps_the_blanket_deferral_reason() -> None:
    """D195: a conforms obligation with no scalar window on EITHER side
    (module imports, geometric/role promises) keeps the pre-existing
    blanket `conformance_windows_unresolved` reason -- the census
    separates "impl owes a bound" from "nothing scalar to compare"."""
    from regolith.orchestrator.translate import translate

    lowered = translate(_conforms_obligation([]))
    assert lowered.is_err, lowered
    assert lowered.danger_err.reason == "conformance_windows_unresolved"


def test_conforms_with_both_bounds_still_lowers_to_the_conformance_model() -> None:
    """The D104 both-sides window is untouched by the D195 sharpening: a
    resolved spec + impl bound pair still lowers to the harness
    conformance model's request (limit = spec, input = impl)."""
    from regolith.orchestrator.translate import translate

    ob = _conforms_obligation(
        [
            "conformance_sense: upper",
            "spec_bound: 50",
            "impl_bound: 45",
            "conformance_field: power",
        ]
    )
    lowered = translate(ob)
    assert lowered.is_ok, lowered
    request = lowered.danger_ok
    assert request.limit == 50.0
    assert request.inputs["impl_bound"].lo == 45.0


def test_model_pin_threads_from_claim_onto_the_discharge_request() -> None:
    """WO-80 deliverable 2/3: `Claim.model_pin` (the Rust lowering's
    typed field, WO-80 deliverable 1) threads through `translate()`
    onto `DischargeRequest.model_pin` via the ONE `_pin_model` seam, so
    the registry can honor it end to end. Un-pinned claims translate
    with `model_pin=None` unchanged (the baseline)."""
    from regolith.orchestrator.translate import translate

    ob = _obligation("margin", "require", ">= 6", "8")
    ob = ob.model_copy(
        update={"claim": ob.claim.model_copy(update={"model_pin": "fea_contact"})}
    )
    lowered = translate(ob)
    assert lowered.is_ok, lowered
    assert lowered.danger_ok.model_pin == "fea_contact"

    unpinned = _obligation("margin", "require", ">= 6", "8")
    lowered_unpinned = translate(unpinned)
    assert lowered_unpinned.is_ok, lowered_unpinned
    assert lowered_unpinned.danger_ok.model_pin is None


def test_pinned_obligation_that_matches_nothing_discharges_indeterminate() -> None:
    """End-to-end (regolith/12 sec. 2 rung 5's law): a claim pinned to a
    model the registry never registered discharges to the DISTINCT
    `harness.model_pin_unmatched` indeterminate -- never a pass, never a
    silent fallback to whatever model would otherwise have matched
    `margin`'s claim kind."""
    from regolith.harness import MODEL_PIN_UNMATCHED_ID
    from regolith.orchestrator.translate import translate

    ob = _obligation("margin", "require", ">= 6", "8")
    ob = ob.model_copy(
        update={"claim": ob.claim.model_copy(update={"model_pin": "fea_contact"})}
    )
    lowered = translate(ob)
    assert lowered.is_ok, lowered
    reg = _registry()
    evidence = reg.discharge(lowered.danger_ok)
    assert evidence.model_id == MODEL_PIN_UNMATCHED_ID
    assert evidence.status.value == "indeterminate"


# --- WO-33 D98: computed indexed fields ------------------------------------
#
# The non-goal this WO states explicitly: no field-producing MODEL ships
# with this repo (four-bar kinematics, marching thermal solvers -- pack
# territory). The honest interim is that BOTH a `compute` claim's own
# producer obligation AND any ordinary claim that projects one (`max(...)`,
# `<name> at ...`) defer -- not through new orchestrator machinery, but
# because the EXISTING `translate()` total function already has no lowering
# for a `ClaimForm7` (compute) form, and no lowering for a comparison whose
# `rhs` does not open with a bare comparator (a projection head, e.g.
# `max(wall_T) < 800K`). Deliverable 4's "honest interim ... no fake data
# path" therefore falls directly out of `translate()`'s existing totality,
# with no per-form special-casing added -- these tests pin that down so a
# future change cannot silently regress it into a false pass.


def _compute_obligation(name: str, quantity_kind: str, over: str) -> Obligation:
    from regolith._schema.models import Form6

    return Obligation(
        claim=Claim(
            name=name,
            form=ClaimForm7(form=Form6.compute, quantity_kind=quantity_kind, over=over),
            forall=[],
            hints=[],
        ),
        subject_ref=f"blake3:{name}",
        given=Given(materials=[], loads=[], backing=[]),
        hints=[],
    )


def test_compute_obligation_defers_with_no_field_producing_model() -> None:
    """A `compute` claim's own producer obligation is a `Form6.compute`
    claim -- `translate()` has no lowering for it (only the scalar-
    comparison `ClaimForm1` shape lowers), so it defers as `non_scalar_claim`,
    never a silent/fake pass."""
    reg = _registry()
    store = EvidenceStore()
    ob = _compute_obligation("wall_T", "thermo.wall_temperature", "liner.zones")
    result = discharge_one(ob, registry=reg, store=store)
    assert result.deferral is not None
    assert result.deferral.reason == "non_scalar_claim"
    assert result.is_indeterminate
    assert not result.is_resolved


def test_projection_of_a_computed_field_also_defers() -> None:
    """A consumer claim that projects a computed field (`max(wall_T) <
    800K`) is an ordinary scalar-comparison claim whose `rhs` does not
    open with a bare comparator -- `_split_comparator` finds none at the
    head, so it defers as `unsupported_op` (the chain rule of the
    ledger: a projection over an unresolved field is itself unresolved,
    never silently discharged)."""
    reg = _registry()
    store = EvidenceStore()
    ob = _obligation("tip_temp", "require", "max(wall_T) < 800K", "5")
    result = discharge_one(ob, registry=reg, store=store)
    assert result.deferral is not None
    assert result.deferral.reason == "unsupported_op"
    assert result.is_indeterminate
    assert not result.is_resolved


# --- lazy loop ------------------------------------------------------------


class _TightenOnce:
    """A sensitivity hook that tightens a failing load exactly once."""

    def __init__(self) -> None:
        self.calls = 0

    def propose(
        self,
        obligations: tuple[Obligation, ...],
        results: tuple[ObligationResult, ...],
    ) -> tuple[Obligation, ...] | None:
        self.calls += 1
        if all(r.is_resolved for r in results):
            return None
        # Refine: drop the load so the claim discharges next round.
        return (_obligation("stress", "<", "100", "10"),)


# frob:tests python/regolith/orchestrator/loop.py::SensitivityHook.propose
def test_lazy_loop_converges_after_refinement() -> None:
    reg = _registry()
    store = EvidenceStore()
    hook = _TightenOnce()
    outcome = lazy_loop(
        (_obligation("stress", "<", "100", "150"),),
        registry=reg,
        store=store,
        hooks=(hook,),
    )
    assert outcome.is_ok
    result = outcome.danger_ok
    assert result.converged
    assert result.iterations == 2  # violated -> refine -> discharged
    assert all(r.is_resolved for r in result.results)


def test_lazy_loop_single_pass_without_hooks() -> None:
    reg = _registry()
    store = EvidenceStore()
    outcome = lazy_loop(
        (_obligation("stress", "<", "100", "50"),), registry=reg, store=store
    ).danger_ok
    assert outcome.iterations == 1
    assert outcome.converged


# --- WO-42 deliverable 5: the staged build loop -----------------------------

_LOOP_FLUO_SRC = (
    "medium Water: liquid\n"
    "    props: registry(potable_water_nist)\n"
    "flownet Loop(medium=Water):\n"
    "    reference: ambient(101kPa, 293K)\n"
    "    nodes: a, b\n"
    "    edges:\n"
    "        supply: Pipe(from=line.run) (a -> b)\n"
    "require Margin:\n"
    "    dp: fluids.dp(a -> b) <= 40kPa\n"
)


def test_pending_geom_extract_subjects_finds_unbacked_from_ref(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A `from=line.run` edge with no realized input lowers to a
    `GeomExtract` placeholder with an empty record digest -- exactly the
    subject :func:`staged_build` must attempt to realize next."""
    path = tmp_path / "loop.fluo"
    path.write_text(_LOOP_FLUO_SRC, encoding="ascii")
    payload_json = _check_payload_json(path)
    assert _pending_geom_extract_subjects(payload_json) == frozenset({"line.run"})


def test_pending_geom_extract_subjects_empty_for_no_flownets() -> None:
    assert _pending_geom_extract_subjects(b"") == frozenset()
    assert _pending_geom_extract_subjects(b'{"flownets": {}}') == frozenset()


def test_staged_build_without_feature_programs_runs_one_iteration_placeholder_intact(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    """D128's placeholder rule: with no `FeatureProgram` supplied for the
    pending subject, the loop cannot realize anything -- it converges
    after exactly one iteration and the build still ran (obligations
    honestly indeterminate for `line.run`, not attempted)."""
    path = tmp_path / "loop.fluo"
    path.write_text(_LOOP_FLUO_SRC, encoding="ascii")

    result = staged_build((str(path),), BuildTier.BUILD)
    assert result.is_ok, result.danger_err
    report = result.danger_ok
    assert report.iterations == 1
    assert report.realized_inputs == ()
    assert report.lock_rows == ()
    assert report.final.ok


def test_staged_build_realizes_pending_subject_and_reaches_fixed_point(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    """The end-to-end WO-42 deliverable 5 loop: a `FeatureProgram`
    declaring the `line.run` selector is realized, `put` into the WO-30
    store, and fed back as a `RealizedInput` for a second `lower()` pass
    -- after which no subject is left pending, so the loop stops (the
    fixed point: realization added nothing new on the second pass).
    """
    path = tmp_path / "loop.fluo"
    path.write_text(_LOOP_FLUO_SRC, encoding="ascii")
    program = _line_run_program("line_part", "line.run")

    result = staged_build(
        (str(path),), BuildTier.BUILD, feature_programs={"line.run": program}
    )
    assert result.is_ok, result.danger_err
    report = result.danger_ok

    # Iteration 1: lowers with the placeholder, realizes line.run.
    # Iteration 2: re-lowers with the realized input, finds nothing new
    # pending, and stops -- exactly two core passes.
    assert report.iterations == 2
    assert len(report.realized_inputs) == 1
    ri = report.realized_inputs[0]
    assert ri.subject == "line.run"
    assert ri.kind == "geometry.realized"

    # The store actually holds what was put (a real orchestrator-resolved
    # round trip, not a hand-built fixture -- the WO's own acceptance
    # criterion for the mech fixture part).
    store = PayloadStore(str(tmp_path))
    resolved = store.resolve(ri.digest)
    assert resolved.is_ok, resolved.danger_err
    assert resolved.danger_ok == ri.payload_bytes

    # The final build's payload no longer carries an unbacked placeholder
    # for this subject (its record digest is now populated).
    assert _pending_geom_extract_subjects(report.final.payload_json) == frozenset()

    # The acceptance criterion itself: `regolith-lower::extract` actually
    # ran over the realized bytes and replaced the `geom_extract`
    # placeholder with real extracted scalars (not just "a digest is
    # present but unread") -- exact interval bounds matching the fixture's
    # declared measures, cited through the digest this test already
    # verified is in the store.
    final_payload = json.loads(report.final.payload_json)
    edge = final_payload["flownets"]["Loop"]["edges"][0]
    assert edge["params"]["source"] == "scalars"
    values = edge["params"]["values"]
    assert values["area"]["lo"] == values["area"]["hi"] == 1.0e-4
    assert values["length"]["lo"] == pytest.approx(2.0)
    assert values["length"]["hi"] == pytest.approx(2.0)
    assert values["elevation_change"]["lo"] == pytest.approx(0.3)
    assert values["elevation_change"]["hi"] == pytest.approx(0.3)

    # INV-21 lockfile row: cause: realizer(mech).
    assert report.lock_rows == (
        LockRow(slot="line.run.geometry", value=ri.digest, cause="realizer(mech)"),
    )


def test_staged_build_geometry_change_changes_the_digest_and_extracted_values(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    """G42 anti-staleness: a second geometry variant (a different
    declared ``flow_area``) changes the realized-geometry IR digest AND
    the dependent extracted payload values -- proving a geometry change
    is not silently absorbed."""
    path = tmp_path / "loop.fluo"
    path.write_text(_LOOP_FLUO_SRC, encoding="ascii")

    small = staged_build(
        (str(path),),
        BuildTier.BUILD,
        feature_programs={"line.run": _line_run_program("line_part", "line.run")},
    ).danger_ok
    large = staged_build(
        (str(path),),
        BuildTier.BUILD,
        feature_programs={
            "line.run": _line_run_program("line_part", "line.run", flow_area_m2=2.0e-4)
        },
    ).danger_ok

    assert small.realized_inputs[0].digest != large.realized_inputs[0].digest

    small_edge = json.loads(small.final.payload_json)["flownets"]["Loop"]["edges"][0]
    large_edge = json.loads(large.final.payload_json)["flownets"]["Loop"]["edges"][0]
    assert small_edge["params"]["values"]["area"]["lo"] == 1.0e-4
    assert large_edge["params"]["values"]["area"]["lo"] == 2.0e-4


def test_staged_build_is_deterministic_across_two_runs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Same-source determinism (WO-42 acceptance): two staged builds over
    the same inputs produce byte-identical realized-IR digests and
    terminate in the same number of iterations."""
    path = tmp_path / "loop.fluo"
    path.write_text(_LOOP_FLUO_SRC, encoding="ascii")
    program = _line_run_program("line_part", "line.run")

    first = staged_build(
        (str(path),), BuildTier.BUILD, feature_programs={"line.run": program}
    ).danger_ok
    second = staged_build(
        (str(path),), BuildTier.BUILD, feature_programs={"line.run": program}
    ).danger_ok

    assert first.iterations == second.iterations == 2
    assert [ri.digest for ri in first.realized_inputs] == [
        ri.digest for ri in second.realized_inputs
    ]


def test_staged_build_does_not_retry_a_failed_realization(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A `FeatureProgram` that fails to realize (schema-version mismatch,
    the cheapest reliable failure to construct) is attempted exactly
    once, then left pending permanently for this call -- never an
    infinite loop over an input that cannot change."""
    path = tmp_path / "loop.fluo"
    path.write_text(_LOOP_FLUO_SRC, encoding="ascii")
    bad_program = _line_run_program("line_part", "line.run").model_copy(
        update={"schema_version": 999}
    )

    result = staged_build(
        (str(path),), BuildTier.BUILD, feature_programs={"line.run": bad_program}
    )
    assert result.is_ok, result.danger_err
    report = result.danger_ok
    assert report.realized_inputs == ()
    # Iteration 1 attempts and fails the realization (marking it failed);
    # iteration 2 re-lowers, finds the subject no longer in `to_realize`
    # (it is `failed_subjects`, never retried), and stops.
    assert report.iterations == 2


def test_realized_lock_rows_sorted_by_subject() -> None:
    from regolith import compiler

    inputs = (
        compiler.RealizedInput(
            digest="blake3:bb",
            kind="geometry.realized",
            subject="b.run",
            payload_bytes=b"{}",
        ),
        compiler.RealizedInput(
            digest="blake3:aa",
            kind="geometry.realized",
            subject="a.run",
            payload_bytes=b"{}",
        ),
    )
    rows = realized_lock_rows(inputs)
    assert rows == (
        LockRow(slot="a.run.geometry", value="blake3:aa", cause="realizer(mech)"),
        LockRow(slot="b.run.geometry", value="blake3:bb", cause="realizer(mech)"),
    )


# --- WO-52 (D141): gn2_purge's compressible-regime claims ride the D97
# regime channel, honestly indeterminate absent a compressible model -----


def test_fluid_regime_claim_rides_d97_channel_and_stays_indeterminate() -> None:
    """`fluids.mach(line) <= 0.3` (`gn2_purge.fluo`'s `regime:` claim,
    D141) translates through the SAME `_regimes_for`/`DischargeRequest`
    D97 channel every claim kind rides (WO-30 sec. 8.4) -- no new claim
    form was added for the compressible tier, matching the D141 point.
    `_regimes_for` only asserts tags for `mech.*` construction today (no
    `fluids.*` regime-asserting model ships with this repo, feldspar
    WO-20 territory), so the request's `regimes` tuple is honestly
    empty; with no model registered for `fluids.mach`, discharge defers
    rather than guessing -- the exact "indeterminate until the
    compressible tier registers" behavior FOPEN-2's closure (fluorite/04)
    describes."""
    from regolith.orchestrator.translate import translate

    ob = _obligation("fluids.mach", "require", "<= 0.3", "0.1")
    lowered = translate(ob)
    assert lowered.is_ok, lowered
    request = lowered.danger_ok
    assert request.claim_kind == "fluids.mach"
    assert request.regimes == (), (
        "no fluids regime-asserting model ships yet (feldspar WO-20); "
        "the D97 channel must carry that honestly, not invent a tag"
    )

    reg = _registry()  # only the mech _StressModel is registered
    store = EvidenceStore()
    result = discharge_one(ob, registry=reg, store=store)
    assert result.deferral is not None, (
        "a fluids.mach claim must defer, not silently resolve, with no "
        "compressible model registered"
    )


# --- WO-51 deliverable 4: pipeline-produced programs -----------------------

_COOLANT_GALLERY_SRC = (
    Path(__file__).parent.parent.parent
    / "examples"
    / "tracks"
    / "hematite"
    / "coolant_gallery.hema"
).read_text(encoding="ascii")

_GALLERY_LOOP_FLUO = (
    "medium Water: liquid\n"
    "    props: registry(potable_water_nist)\n"
    "flownet CoolantLoop(medium=Water):\n"
    "    reference: ambient(101kPa, 293K)\n"
    "    nodes: a, b\n"
    "    edges:\n"
    "        gallery: Pipe(from=milled.wetted) (a -> b)\n"
    "require Margin:\n"
    "    dp: fluids.dp(a -> b) <= 40kPa\n"
)


def test_emitted_programs_convert_the_d152_exemplar(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """WO-51 d4: the coolant_gallery payload converts into a realizer
    `FeatureProgram` keyed by the emitted `milled.wetted` selector --
    outline from the fully pinned promoted sketch, blank thickness from
    the declared depth, and flow segments from declared facts only."""
    from regolith.orchestrator.programs import emitted_realizer_programs

    path = tmp_path / "coolant_gallery.hema"
    path.write_text(_COOLANT_GALLERY_SRC, encoding="ascii")
    programs = emitted_realizer_programs(_check_payload_json(path))

    assert "milled.wetted" in programs, sorted(programs)
    program = programs["milled.wetted"]
    assert program.part_name == "CoolantGallery"
    stage = program.stages[0]
    assert stage.name == "milled"
    assert stage.process == "cnc_mill"
    blank = stage.features[0]
    assert blank.op == "blank"
    assert blank.thickness.value == pytest.approx(0.030)
    # The outline is the cumulative cardinal walk over declared mm.
    xs = [p.x for p in blank.sketch.outline]
    ys = [p.y for p in blank.sketch.outline]
    assert max(xs) == pytest.approx(0.090)
    assert max(ys) == pytest.approx(0.036)

    (flow_path,) = program.flow_paths
    assert flow_path.selector == "milled.wetted"
    assert len(flow_path.segments) == 3
    gallery = flow_path.segments[1]
    assert gallery.flow_area.value == pytest.approx(math.pi * 0.003**2)
    assert gallery.length.value == pytest.approx(0.066)
    assert gallery.roughness_class == "machined"
    assert gallery.elevation_change.value == 0.0


def test_sheet_bracket_emits_and_realizes_with_no_caller_program() -> None:
    """WO-62 D171/AD-32 deliverable 2 (the WO-22 residue closes):
    `sheet_bracket.hema`'s `BracketFlat` profile has every explicit
    segment pinned (the close edge absorbs the gap, WO-62 d1) and its
    `Blank` op's thickness comes from the stage's `process=laser_cut(
    sheet=1.5mm)` gauge source (`cause: process(laser_cut.sheet)`,
    INV-21) -- so the pipeline emits a program that converts and
    realizes to real STEP geometry with NO hand-authored
    `FeatureProgram` anywhere (the coolant_gallery precedent, applied
    to a cavity-less sheet part)."""
    from regolith.orchestrator.programs import emitted_realizer_programs

    path = Path("examples/tracks/hematite/sheet_bracket.hema")
    programs = emitted_realizer_programs(_check_payload_json(path))

    assert "SensorBracket.blank" in programs, sorted(programs)
    program = programs["SensorBracket.blank"]
    assert program.part_name == "SensorBracket"
    stage = program.stages[0]
    assert stage.name == "cut"
    assert stage.process == "laser_cut"
    blank = stage.features[0]
    assert blank.op == "blank"
    assert blank.thickness.value == pytest.approx(0.0015)
    xs = [p.x for p in blank.sketch.outline]
    ys = [p.y for p in blank.sketch.outline]
    assert max(xs) == pytest.approx(0.080)
    assert max(ys) == pytest.approx(0.050)

    realized = realize_feature_program(program)
    assert realized.is_ok, realized.danger_err
    artifact = realized.danger_ok
    assert artifact.step_bytes, "sheet_bracket must realize real STEP bytes"
    assert artifact.geometry.topology.volume_mm3 > 0.0


#: Every flagship `stock`/`saw_stock(rect(...))` part that converts once
#: `emitted_realizer_programs` gets the source-text fallback (a realizer
#: feature gap fix, this change): (project dir, part name, subject,
#: expected (w_mm, d_mm, h_mm) from the literal `rect(w, d, h)` spec).
#: Locks the gain in place -- a census, not a spot check (regression
#: guard against a future edit silently narrowing the fallback regex).
_STOCK_CENSUS: tuple[tuple[str, str, str, tuple[float, float, float]], ...] = (
    (
        "examples/flagships/cnc_router_r1",
        "BedPlate",
        "BedPlate.body",
        (980.0, 700.0, 20.0),
    ),
    (
        "examples/flagships/cnc_router_r1",
        "IdlerBearingPlate",
        "IdlerBearingPlate.body",
        (90.0, 50.0, 20.0),
    ),
    (
        "examples/flagships/cnc_router_r1",
        "MotorPlate",
        "MotorPlate.body",
        (80.0, 80.0, 10.0),
    ),
    (
        "examples/flagships/cnc_router_r1",
        "SidePlate",
        "SidePlate.body",
        (420.0, 270.0, 20.0),
    ),
    (
        "examples/flagships/cnc_router_r1",
        "Spoilboard",
        "Spoilboard.body",
        (830.0, 520.0, 18.0),
    ),
    (
        "examples/flagships/cnc_router_r1",
        "SpindleMount",
        "SpindleMount.body",
        (160.0, 150.0, 45.0),
    ),
    (
        "examples/flagships/cubesat",
        "DeployerBody",
        "DeployerBody.body",
        (90.0, 14.0, 10.0),
    ),
    ("examples/flagships/cubesat", "Rail", "Rail.body", (10.0, 10.0, 116.0)),
    (
        "examples/flagships/espresso_machine",
        "GroupHead",
        "GroupHead.body",
        (90.0, 90.0, 120.0),
    ),
)

#: `saw_stock` parts that are named non-convertible ON PURPOSE:
#: `CarriagePlate`'s stock is a non-literal expression (`rect(1.1 * w,
#: ...)`) the source-text path never guesses. Asserting it stays OUT
#: keeps the census honest about what did NOT convert. (`BaseFrame` was
#: here; its `RectTube` weldment pieces now convert via the F122
#: weldment-piece path -- see `_WELDMENT_CENSUS`. `GantryBeam` was here
#: too; its custom `extrusion(BeamSection)` tangent-arc walk now
#: resolves via the F123/D231 Rust closure solve -- see
#: `_EXTRUSION_CENSUS`.)
_STOCK_ESCALATED: tuple[tuple[str, str], ...] = (
    ("examples/flagships/cnc_router_r1", "CarriagePlate"),
)

#: Every custom-extrusion `saw_stock(extrusion(<profile>, l=L))` part
#: that converts via the F123/D231/WO116-F1 path: (project dir, subject
#: `<part>.body`, expected outline vertex count, expected arc-edge
#: count). The section's radiused tangent-arc outline is resolved once,
#: in Rust; the part realizes to real STEP with two 6mm fillet arcs.
_EXTRUSION_CENSUS: tuple[tuple[str, str, int, int], ...] = (
    ("examples/flagships/cnc_router_r1", "GantryBeam.body", 11, 2),
)

#: Every weldment `pieces:` RectTube piece that converts via the F122
#: weldment-piece source path: (project dir, subject `<part>.<piece>`,
#: expected outer (w_mm, h_mm, t_wall_mm, l_length_mm) from the literal
#: `RectTube(W x H x T, l=L)` spec). Locks the gain -- a blank outer
#: solid (W x H x L) with one centered RectPocket cavity ((W-2T) x
#: (H-2T) x (L-T)), real STEP end to end.
_WELDMENT_CENSUS: tuple[tuple[str, str, tuple[float, float, float, float]], ...] = (
    (
        "examples/flagships/cnc_router_r1",
        "BaseFrame.rail_l",
        (80.0, 80.0, 4.0, 1050.0),
    ),
    (
        "examples/flagships/cnc_router_r1",
        "BaseFrame.cross_f",
        (80.0, 40.0, 4.0, 680.0),
    ),
    (
        "examples/tracks/hematite/weldment_frame.hema",
        "MachineFrame.rail_l",
        (60.0, 40.0, 3.0, 600.0),
    ),
    (
        "examples/tracks/hematite/weldment_frame.hema",
        "MachineFrame.cross_f",
        (60.0, 40.0, 3.0, 400.0),
    ),
)


@pytest.mark.parametrize(
    ("project_dir", "part_name", "subject", "dims_mm"), _STOCK_CENSUS
)
def test_stock_saw_stock_rect_parts_realize_real_step(
    project_dir: str, part_name: str, subject: str, dims_mm: tuple[float, float, float]
) -> None:
    """A `stock`/`saw_stock(rect(w, d, h))` part with fully literal dims
    now converts (the realizer feature gap this change closes: WO-51's
    IR has no `FeatureOp` for a `then:`-less stock stage) and realizes
    to real STEP geometry with the LITERAL declared dims, never
    guessed. Locks in the gain across every flagship using the idiom."""
    from regolith.orchestrator.programs import emitted_realizer_programs

    payload_json = _check_payload_json(Path(project_dir))
    programs = emitted_realizer_programs(payload_json, (project_dir,))

    assert subject in programs, sorted(programs)
    program = programs[subject]
    assert program.part_name == part_name
    blank = program.stages[0].features[0]
    assert blank.op == "blank"
    w_mm, d_mm, h_mm = dims_mm
    xs = [p.x for p in blank.sketch.outline]
    ys = [p.y for p in blank.sketch.outline]
    assert (max(xs) - min(xs)) * 1000.0 == pytest.approx(w_mm)
    assert (max(ys) - min(ys)) * 1000.0 == pytest.approx(d_mm)
    assert blank.thickness.value * 1000.0 == pytest.approx(h_mm)

    realized = realize_feature_program(program)
    assert realized.is_ok, realized.danger_err
    artifact = realized.danger_ok
    assert artifact.step_bytes, f"{part_name} must realize real STEP bytes"
    assert artifact.geometry.topology.volume_mm3 > 0.0


@pytest.mark.parametrize(("project_dir", "part_name"), _STOCK_ESCALATED)
def test_stock_saw_stock_non_rect_or_non_literal_stays_non_convertible(
    project_dir: str, part_name: str
) -> None:
    """The named escalations (non-literal expression / custom
    `extrusion` tangent-arc profile) stay honestly non-convertible -- the
    source-text path never guesses a dimension it cannot parse as a
    literal spec, and never fabricates the deferred arc-walk closure."""
    from regolith.orchestrator.programs import emitted_realizer_programs

    payload_json = _check_payload_json(Path(project_dir))
    programs = emitted_realizer_programs(payload_json, (project_dir,))

    assert not any(
        program.part_name == part_name or program.part_name.startswith(part_name + ".")
        for program in programs.values()
    ), f"{part_name} unexpectedly converted: {sorted(programs)}"


@pytest.mark.parametrize(("project_dir", "subject", "dims_mm"), _WELDMENT_CENSUS)
def test_weldment_recttube_pieces_realize_real_step(
    project_dir: str,
    subject: str,
    dims_mm: tuple[float, float, float, float],
) -> None:
    """F122: a weldment `pieces:` `RectTube(W x H x T, l=L)` piece now
    converts via the source-text weldment path (WO-51's IR carries no
    `FeatureOp` for a `then:`-less weldment piece) and realizes to real
    STEP geometry -- a blank outer solid (W x H x L) with one centered
    RectPocket cavity ((W-2T) x (H-2T) x (L-T)) -- with the LITERAL
    declared dims, never guessed. Closes WO-104's RectTube-stock half."""
    from regolith.orchestrator.programs import emitted_realizer_programs

    payload_json = _check_payload_json(Path(project_dir))
    programs = emitted_realizer_programs(payload_json, (project_dir,))

    assert subject in programs, sorted(programs)
    program = programs[subject]
    assert program.part_name == subject
    w_mm, h_mm, t_mm, l_mm = dims_mm
    blank, cavity = program.stages[0].features
    assert blank.op == "blank"
    assert cavity.op == "rect_pocket"
    xs = [p.x for p in blank.sketch.outline]
    ys = [p.y for p in blank.sketch.outline]
    assert (max(xs) - min(xs)) * 1000.0 == pytest.approx(w_mm)
    assert (max(ys) - min(ys)) * 1000.0 == pytest.approx(h_mm)
    assert blank.thickness.value * 1000.0 == pytest.approx(l_mm)
    assert cavity.width.value * 1000.0 == pytest.approx(w_mm - 2.0 * t_mm)
    assert cavity.depth_xy.value * 1000.0 == pytest.approx(h_mm - 2.0 * t_mm)
    assert cavity.height.value * 1000.0 == pytest.approx(l_mm - t_mm)

    realized = realize_feature_program(program)
    assert realized.is_ok, realized.danger_err
    artifact = realized.danger_ok
    assert artifact.step_bytes, f"{subject} must realize real STEP bytes"
    assert artifact.geometry.topology.volume_mm3 > 0.0


@pytest.mark.parametrize(
    ("project_dir", "subject", "n_outline", "n_arcs"), _EXTRUSION_CENSUS
)
# frob:tests python/regolith/compiler.py::resolve_extrusion_outline
def test_extrusion_section_parts_realize_real_step(
    project_dir: str, subject: str, n_outline: int, n_arcs: int
) -> None:
    """F123/D231/WO116-F1: a `saw_stock(extrusion(<profile>, l=L))` part
    whose custom section is a radiused tangent-arc walk now converts --
    the section's closed outline + per-arc endpoints are resolved once,
    in Rust (`compiler.resolve_extrusion_outline`, the SAME `arc_chord`
    math the closure verification uses, never a Python re-derivation) --
    and realizes to real STEP geometry with real arc edges. Closes
    WO-104's arc-extrusion half."""
    from regolith.orchestrator.programs import emitted_realizer_programs

    payload_json = _check_payload_json(Path(project_dir))
    programs = emitted_realizer_programs(payload_json, (project_dir,))

    assert subject in programs, sorted(programs)
    program = programs[subject]
    assert program.part_name == subject
    blank = program.stages[0].features[0]
    assert blank.op == "blank"
    assert len(blank.sketch.outline) == n_outline
    assert len(blank.sketch.arcs) == n_arcs
    # Every ProfileArc endpoint is one of the resolved outline vertices
    # (bit-identical), so the interpreter's end-vertex arc lookup matches.
    outline_pts = {(p.x, p.y) for p in blank.sketch.outline}
    for arc in blank.sketch.arcs:
        assert (arc.to.x, arc.to.y) in outline_pts

    realized = realize_feature_program(program)
    assert realized.is_ok, realized.danger_err
    artifact = realized.danger_ok
    assert artifact.step_bytes, f"{subject} must realize real STEP bytes"
    topo = artifact.geometry.topology
    assert topo.volume_mm3 > 0.0
    assert topo.num_solids == 1


def test_staged_build_realizes_the_exemplar_with_no_caller_program(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    """The WO-51 acceptance chain: declarative `.hema` (cavity query) +
    `.fluo` (`Pipe(from=milled.wetted)`) -> emitted FeatureProgram ->
    realized geometry -> fluorite extraction over the staged loop, with
    NO hand-authored program anywhere."""
    (tmp_path / "coolant_gallery.hema").write_text(
        _COOLANT_GALLERY_SRC, encoding="ascii"
    )
    (tmp_path / "coolant_loop.fluo").write_text(_GALLERY_LOOP_FLUO, encoding="ascii")

    result = staged_build(
        (
            str(tmp_path / "coolant_gallery.hema"),
            str(tmp_path / "coolant_loop.fluo"),
        ),
        BuildTier.BUILD,
    )
    assert result.is_ok, result.danger_err
    report = result.danger_ok

    assert report.iterations == 2
    assert len(report.realized_inputs) == 1
    ri = report.realized_inputs[0]
    assert ri.subject == "milled.wetted"
    assert ri.kind == "geometry.realized"
    assert report.lock_rows, "realized input must land as an INV-21 lock row"

    # The final payload's flownet edge is fully EXTRACTED (the
    # GeomExtract placeholder resolved to concrete scalar intervals):
    # the fluorite seam read realizer output over a REAL emitted
    # program end to end -- area is exactly pi*(8mm/2)^2 (the feed
    # bore, the path's first declared section) and length is the
    # summed declared depths (12+66+12mm).
    payload = json.loads(report.final.payload_json)
    edges = [
        edge for flownet in payload["flownets"].values() for edge in flownet["edges"]
    ]
    assert edges
    (gallery_edge,) = [e for e in edges if e["id"] == "gallery"]
    params = gallery_edge["params"]
    assert params["source"] == "scalars", f"still a placeholder: {params!r}"
    assert params["values"]["area"]["lo"] == pytest.approx(math.pi * 0.004**2)
    assert params["values"]["length"]["lo"] == pytest.approx(0.090)


# --- WO-26 D103: the link budget end to end ---------------------------------

# A Kestrel-shaped downlink budget whose four dB terms all resolve from
# declared source values: pa_out from a promise bound, gain from a bound
# field, path_loss/sensitivity from plain values. Margin = 30 + 12 - 140
# - (-110) = 12 dB >= 6 dB demanded + 2 dB model eps -> discharged.
_LINK_SRC = (
    "part Radio:\n"
    "    require Rf:\n"
    "        pa_out: elec.power(rf_conn) >= 30dBm during op = downlink\n"
    "part Dish:\n"
    "    gain: >= 12dBi\n"
    "part Station:\n"
    "    sensitivity: -110dBm\n"
    "    path_loss: 140dB\n"
    "system Sat:\n"
    "    parts:\n"
    "        comms: Radio\n"
    "        ant: Dish\n"
    "        gs: Station\n"
    "    require Link:\n"
    "        margin: comms.pa_out + ant.gain - gs.path_loss\n"
    "                    >= gs.sensitivity + 6dB during op = downlink\n"
)


def test_link_budget_discharges_end_to_end_via_build(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """WO-26 D103 acceptance: a `require Link: margin ... >= ... + 6dB`
    general comparison claim discharges through `elec.link.margin` end
    to end via `orchestrator.build` -- the core resolves the dB terms
    into `given.refs`, translate maps the shape onto the registered
    link-budget pack, and the pack's worst-corner margin clears the
    demanded 6 dB."""
    path = tmp_path / "sat.cupr"
    path.write_text(_LINK_SRC, encoding="ascii")

    report = build((str(path),), BuildTier.BUILD).danger_ok
    assert report.ok, "the link fixture must lower clean"

    link_results = [
        r
        for r in report.results
        if r.evidence is not None and r.evidence.model_id == "link_budget_margin_db@1"
    ]
    assert link_results, "the margin claim must reach the link-budget pack"
    evidence = link_results[0].evidence
    assert evidence is not None
    assert evidence.status.value == "discharged"


def test_link_budget_with_an_unresolved_term_defers_naming_it(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The REAL Kestrel posture: a link-shaped claim whose `gain` names
    nothing the source declares defers as `given_unresolved` NAMING the
    reference -- the pack is reachable, the given is not (never an
    invented number)."""
    src = _LINK_SRC.replace("    gain: >= 12dBi\n", "    mass: 40g\n")
    assert src != _LINK_SRC, "the gain line must actually be removed"
    path = tmp_path / "sat.cupr"
    path.write_text(src, encoding="ascii")

    report = build((str(path),), BuildTier.BUILD).danger_ok
    deferred = [
        r
        for r in report.results
        if r.deferral is not None and r.deferral.reason == "given_unresolved"
    ]
    assert deferred, "the unresolved gain must defer as given_unresolved"
    assert any("ant.gain" in r.deferral.detail for r in deferred if r.deferral)
