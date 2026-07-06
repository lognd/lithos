"""INV-28 Evidence attribution (regolith/13-invariants.md).

Ledger statement:
    **Computed evidence is attributable: a solver signs the evidence it
    produces, the consumer verifies that signature against its own key
    set, and a claim's trust floor applies to computed evidence exactly
    as it does to records (INV-14) -- an unverifiable signature is
    indeterminate, never a silent pass.**

Mechanism provided by: WO-21 (`harness/attest.py` sign/verify + the
orchestrator release gate). The three fixtures the ledger names are the
proving cases here: an honest signed round trip earns `Valid(tested)`;
a tampered evidence byte yields `Invalid` -> indeterminate, DISTINCT
from violated; a `certified` floor over a `tested`-designated key is
release-gated until the key is re-designated (a consumer-side change
that flips it -- INV-14 semantics on computed evidence).
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
from regolith.harness.attest import Invalid, Valid, conferred_tier
from regolith.harness.errors import HarnessError
from regolith.harness.model import Model
from regolith.orchestrator import (
    EvidenceStore,
    discharge_all,
    obligation_cache_key,
    release_gate,
)
from regolith.quarry import (
    KeyDesignation,
    LocalSigningKey,
    TrustKeySet,
    TrustTier,
    generate_signing_key,
)
from typani.result import Ok, Result

# --- fixtures -------------------------------------------------------------


class _StressModel(Model):
    """A trivial upper-bound model: predicts its input's worst corner."""

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
    reg = ModelRegistry(version="model-registry@inv28")
    reg.register(_StressModel())
    return reg


def _obligation(load: str, *, trust_floor: str | None = None) -> Obligation:
    return Obligation(
        claim=Claim(
            name="stress",
            form=ClaimForm1(form=Form.comparison, lhs="stress", op="<", rhs="100"),
            forall=[],
            hints=[],
            trust_floor=trust_floor,
        ),
        subject_ref="blake3:stress",
        given=Given(materials=[], loads=[f"load: {load}"], backing=[]),
        hints=[],
    )


def _project_key(tmp_path, key_id: str) -> LocalSigningKey:
    """A fresh throwaway signing key under a temp ``.regolith/keys/`` (I4)."""
    generated = generate_signing_key(str(tmp_path), key_id)
    assert generated.is_ok
    return generated.danger_ok


def _designating(key: LocalSigningKey, tier: TrustTier) -> TrustKeySet:
    return TrustKeySet(
        designations=(
            KeyDesignation(
                key_id=key.key_id,
                public_key_base64=key.public_key_base64(),
                confers=tier,
            ),
        )
    )


# --- (a) honest pass ------------------------------------------------------


def test_inv_28_signed_round_trip_earns_designated_tier(tmp_path) -> None:
    """Signed evidence verified against a designated key earns its tier."""
    reg = _registry()
    key = _project_key(tmp_path, "project-1")
    trust = _designating(key, TrustTier.TESTED)
    store = EvidenceStore()
    ob = _obligation("50", trust_floor="tested")

    (result,) = discharge_all(
        [ob], registry=reg, store=store, signer=key, trust_keys=trust
    )

    assert result.is_resolved
    assert isinstance(result.attestation, Valid)
    assert result.attestation.tier == TrustTier.TESTED
    assert conferred_tier(result.attestation) == TrustTier.TESTED
    # The release gate accepts: the tested floor is met by a tested key.
    assert release_gate((result,)).is_ok


def test_inv_28_attestation_is_an_envelope(tmp_path) -> None:
    """The cache key and evidence hash are identical with and without a sig."""
    reg = _registry()
    key = _project_key(tmp_path, "project-1")
    trust = _designating(key, TrustTier.TESTED)
    ob = _obligation("50")

    signed_store = EvidenceStore()
    (signed,) = discharge_all(
        [ob], registry=reg, store=signed_store, signer=key, trust_keys=trust
    )
    unsigned_store = EvidenceStore()
    (unsigned,) = discharge_all([ob], registry=_registry(), store=unsigned_store)

    # Signing perturbs neither the obligation cache key nor the evidence hash.
    assert (
        signed.key == unsigned.key == obligation_cache_key(ob, "model-registry@inv28")
    )
    assert signed.evidence is not None and unsigned.evidence is not None
    assert signed.evidence.hash == unsigned.evidence.hash


# --- (b) tamper -> indeterminate (distinct from violated) -----------------


def test_inv_28_tamper_is_indeterminate_not_violated(tmp_path) -> None:
    """A tampered evidence byte makes the read Invalid -> indeterminate."""
    reg = _registry()
    key = _project_key(tmp_path, "project-1")
    trust = _designating(key, TrustTier.TESTED)
    store = EvidenceStore()
    ob = _obligation("50")

    (fresh,) = discharge_all(
        [ob], registry=reg, store=store, signer=key, trust_keys=trust
    )
    assert isinstance(fresh.attestation, Valid)

    # Tamper: swap the stored evidence for a one-field-different copy while
    # keeping the original attestation (signature now covers other bytes).
    assert fresh.evidence is not None
    tampered = fresh.evidence.model_copy(update={"cost": fresh.evidence.cost + 1})
    store.put(fresh.key, tampered, store.attestation_of(fresh.key))

    (reread,) = discharge_all(
        [ob], registry=reg, store=store, signer=key, trust_keys=trust
    )
    assert reread.from_cache
    assert isinstance(reread.attestation, Invalid)
    assert reread.attestation.reason == "bad_signature"
    # Indeterminate, DISTINCT from violated, and never resolved.
    assert reread.is_indeterminate
    assert not reread.is_violated
    assert not reread.is_resolved
    # The release gate refuses it -- an unverifiable result is not a pass.
    assert release_gate((reread,)).is_err


# --- (c) trust-floor refusal + re-designation flip ------------------------


def test_inv_28_trust_floor_refused_then_flips_on_redesignation(tmp_path) -> None:
    """A certified floor over a tested key is gated until the key is raised."""
    reg = _registry()
    key = _project_key(tmp_path, "project-1")
    ob = _obligation("50", trust_floor="certified")

    # As `tested`: the physics discharges, but the certified floor is unmet.
    tested = _designating(key, TrustTier.TESTED)
    store = EvidenceStore()
    (low,) = discharge_all(
        [ob], registry=reg, store=store, signer=key, trust_keys=tested
    )
    assert isinstance(low.attestation, Valid)
    assert low.is_resolved  # the discharge itself succeeded
    gate_low = release_gate((low,))
    assert gate_low.is_err
    # A trust-floor refusal is named distinctly from violated (D-E).
    assert "below-trust-floor" in gate_low.danger_err.message

    # Re-designate the SAME key certified (consumer-side change, same
    # evidence, no re-signing): the cache hit re-verifies and now passes.
    certified = tested.designate(
        KeyDesignation(
            key_id=key.key_id,
            public_key_base64=key.public_key_base64(),
            confers=TrustTier.CERTIFIED,
        )
    )
    (high,) = discharge_all(
        [ob], registry=reg, store=store, signer=key, trust_keys=certified
    )
    assert high.from_cache
    assert isinstance(high.attestation, Valid)
    assert high.attestation.tier == TrustTier.CERTIFIED
    assert release_gate((high,)).is_ok
