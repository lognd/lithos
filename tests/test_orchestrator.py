"""Orchestrator: tiers, evidence cache, discharge routing, loop, release gate.

Exercises the AD-1 orchestrator seam with synthetic obligations and a test
harness model (no compiler pass needed): build-tier progression, cache
hit/miss + registry-version invalidation (INV-1/BE-1), the lazy loop, and
release-gate totality (INV-24).
"""

from __future__ import annotations

import json

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
from regolith.orchestrator import (
    BuildTier,
    EvidenceStore,
    ObligationResult,
    discharge_all,
    discharge_one,
    lazy_loop,
    obligation_cache_key,
    release_gate,
)
from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.payload_store import PayloadStore
from regolith.quarry import (
    KeyDesignation,
    TrustKeySet,
    TrustTier,
    generate_signing_key,
)
from typani.result import Ok, Result

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
