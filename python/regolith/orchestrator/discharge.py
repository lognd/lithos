"""Route obligations to the harness, with caching and honest deferral.

This is the orchestrator's half of the AD-1 split: the harness *selects
and computes* evidence; the orchestrator *owns caching, ordering, and the
loop*. Each obligation is (1) keyed (registry version folded in, INV-1),
(2) served from cache on a hit, else (3) lowered to a
:class:`DischargeRequest` and handed to the model registry -- which is
TOTAL, so a no-model obligation comes back as an explicit ``indeterminate``
evidence value, surfaced here as a :class:`Deferral`, never a silent pass.

Obligations are consumed in the source order the core emitted them (INV-10
determinism); results carry the obligation key so the lockfile and the
release gate can reason over them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from regolith._schema.models import Evidence, Obligation, Status3
from regolith.harness import ModelRegistry
from regolith.harness.attest import (
    AttestationStatus,
    Invalid,
    Unsigned,
    sign_evidence,
    verify_attestation,
)
from regolith.harness.registry import NO_MODEL_ID
from regolith.logging_setup import get_logger
from regolith.magnetite.trust import LocalSigningKey, TrustKeySet
from regolith.orchestrator.cache import EvidenceStore, obligation_cache_key
from regolith.orchestrator.translate import Deferral, translate

_log = get_logger(__name__)


class ObligationResult(BaseModel):
    """The outcome of routing one obligation through the harness.

    Exactly one of ``evidence`` / ``deferral`` is set: ``evidence`` when a
    model (or the total no-model path) produced a verdict, ``deferral``
    when the obligation could not even be lowered to a numeric request.
    ``from_cache`` records whether this was a cache hit (observability).
    """

    model_config = ConfigDict(frozen=True)

    key: str
    subject_ref: str
    evidence: Evidence | None = None
    deferral: Deferral | None = None
    from_cache: bool = False
    # The verified trust status of this evidence's attestation (WO-21). An
    # `Invalid` status makes the result INDETERMINATE regardless of the
    # discharge verdict -- the physics may be fine but we cannot attribute
    # it (D-E), so it is never resolved and never violated.
    attestation: AttestationStatus = Field(default_factory=Unsigned)
    # The claim's `trust: >= tier` floor on computed evidence, if any; the
    # release gate compares it against the conferred tier (INV-14/INV-28).
    trust_floor: str | None = None

    @property
    def is_attestation_invalid(self) -> bool:
        """True iff a present attestation failed verification (indeterminate)."""
        return isinstance(self.attestation, Invalid)

    @property
    def is_resolved(self) -> bool:
        """True iff a model discharged this AND its attestation is not invalid."""
        return (
            self.evidence is not None
            and self.evidence.status == "discharged"
            and not self.is_attestation_invalid
        )

    @property
    def is_indeterminate(self) -> bool:
        """True iff indeterminate/deferred OR the attestation is unverifiable."""
        if self.deferral is not None or self.is_attestation_invalid:
            return True
        return self.evidence is not None and self.evidence.status == "indeterminate"

    @property
    def is_violated(self) -> bool:
        """True iff a model proved the claim violated (and it is attributable).

        An unverifiable attestation makes the result INDETERMINATE, not
        violated (D-E): we cannot trust the verdict either way.
        """
        return (
            self.evidence is not None
            and self.evidence.status == "violated"
            and not self.is_attestation_invalid
        )


def discharge_one(
    obligation: Obligation,
    *,
    registry: ModelRegistry,
    store: EvidenceStore,
    signer: LocalSigningKey | None = None,
    trust_keys: TrustKeySet | None = None,
) -> ObligationResult:
    """Discharge one obligation: cache lookup, else lower + route + store.

    Deterministic and total. A cache hit returns the stored evidence; a
    miss lowers the obligation (deferring honestly if it will not lower)
    and asks the registry for a verdict, which is itself total (no model
    -> indeterminate). The registry version is threaded through the key so
    a model bump is a guaranteed miss (BE-1/INV-1); per AD-19 the key
    also folds the would-discharge model's ``(pack_name, pack_version)``
    (selection is deterministic and cheap), so bumping ONE pack misses
    exactly its own cached evidence -- a deferral or no-model obligation
    keys at the built-in identity.
    """
    keys = trust_keys if trust_keys is not None else TrustKeySet()
    trust_floor = obligation.claim.trust_floor
    lowered = translate(obligation)
    pack_name, pack_version = "regolith", registry.version
    if lowered.is_ok:
        selected = registry.select(lowered.danger_ok)
        if selected.is_ok:
            pack_name, pack_version = registry.pack_of(selected.danger_ok.model_id)
    key = obligation_cache_key(
        obligation,
        registry.version,
        pack_name=pack_name,
        pack_version=pack_version,
    )
    cached = store.get(key)
    if cached is not None:
        # Verify at READ against the consumer key set (D-E): trust is a
        # consumption-time decision, so a re-designation flips a cache hit.
        status = verify_attestation(cached, store.attestation_of(key), keys)
        return ObligationResult(
            key=key,
            subject_ref=obligation.subject_ref,
            evidence=cached,
            from_cache=True,
            attestation=status,
            trust_floor=trust_floor,
        )

    if lowered.is_err:
        deferral = lowered.danger_err
        _log.info(
            "obligation %s deferred: %s (%s)",
            obligation.subject_ref,
            deferral.reason,
            deferral.detail,
        )
        return ObligationResult(
            key=key,
            subject_ref=obligation.subject_ref,
            deferral=deferral,
            trust_floor=trust_floor,
        )

    request = lowered.danger_ok
    _log.debug("dispatching claim_kind=%s to harness", request.claim_kind)
    evidence = registry.discharge(request)

    # Sign the fresh evidence when a signer is configured (attribution at
    # discharge), then verify it exactly as a later read would -- the
    # attestation is an envelope, so it never perturbs the cache key.
    status: AttestationStatus = Unsigned()
    if signer is not None:
        attestation = sign_evidence(
            evidence, signer, pack_name=pack_name, pack_version=pack_version
        )
        store.put(key, evidence, attestation)
        status = verify_attestation(evidence, attestation, keys)
    else:
        store.put(key, evidence)

    # A no-model verdict is an honest deferral surface (INV-24): keep the
    # indeterminate evidence AND flag it so the release gate can name it.
    if evidence.model_id == NO_MODEL_ID and evidence.status == Status3.indeterminate:
        _log.info("obligation %s has no matching model", obligation.subject_ref)
        return ObligationResult(
            key=key,
            subject_ref=obligation.subject_ref,
            evidence=evidence,
            attestation=status,
            trust_floor=trust_floor,
            deferral=Deferral(
                reason="no_model",
                detail=f"no harness model for claim kind {request.claim_kind!r}",
            ),
        )
    return ObligationResult(
        key=key,
        subject_ref=obligation.subject_ref,
        evidence=evidence,
        attestation=status,
        trust_floor=trust_floor,
    )


def discharge_all(
    obligations: list[Obligation],
    *,
    registry: ModelRegistry,
    store: EvidenceStore,
    signer: LocalSigningKey | None = None,
    trust_keys: TrustKeySet | None = None,
) -> tuple[ObligationResult, ...]:
    """Discharge every obligation in source order (INV-10 determinism)."""
    results = tuple(
        discharge_one(
            o,
            registry=registry,
            store=store,
            signer=signer,
            trust_keys=trust_keys,
        )
        for o in obligations
    )
    _log.debug(
        "discharged %d obligations (cache hits=%d, misses=%d)",
        len(results),
        store.stats.hits,
        store.stats.misses,
    )
    return results
