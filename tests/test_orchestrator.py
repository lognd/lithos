"""Orchestrator: tiers, evidence cache, discharge routing, loop, release gate.

Exercises the AD-1 orchestrator seam with synthetic obligations and a test
harness model (no compiler pass needed): build-tier progression, cache
hit/miss + registry-version invalidation (INV-1/BE-1), the lazy loop, and
release-gate totality (INV-24).
"""

from __future__ import annotations

from regolith._schema.models import (
    Claim,
    ClaimForm1,
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

    # A `require` predicate with no leading comparator still defers loudly.
    bad = _obligation("stress", "require", "within [0, 10]", "5")
    assert translate(bad).is_err


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
