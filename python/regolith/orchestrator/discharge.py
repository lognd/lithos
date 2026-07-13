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

import json

from pydantic import BaseModel, ConfigDict, Field

from regolith import compiler
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
from regolith.orchestrator.costing import CostContext
from regolith.orchestrator.frame_resolve import FrameContext
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.plan_staging import PlanContext
from regolith.orchestrator.si_stackups import SiContext
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
    # The obligation's AD-18 canonical content address (WO-98): the SAME
    # hash a `WaiverRecord.matched` entry records, so the release gate can
    # decide which unresolved results an evidence-carrying waiver accepts.
    # Empty when the caller did not thread the hash in (e.g. a hand-built
    # test result); such a result can never be waiver-accepted.
    content_hash: str = ""
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
    payload_store: PayloadStore | None = None,
    cost_context: CostContext | None = None,
    frame_context: FrameContext | None = None,
    plan_context: PlanContext | None = None,
    si_context: SiContext | None = None,
    content_hash: str = "",
) -> ObligationResult:
    """Discharge one obligation: cache lookup, else lower + route + store.

    ``content_hash`` (WO-98) is the obligation's AD-18 content address,
    threaded straight onto the result so the release gate can match a
    ledger deviation to it; empty when the caller has no hash to thread.

    Deterministic and total. A cache hit returns the stored evidence; a
    miss lowers the obligation (deferring honestly if it will not lower)
    and asks the registry for a verdict, which is itself total (no model
    -> indeterminate). The registry version is threaded through the key so
    a model bump is a guaranteed miss (BE-1/INV-1); per AD-19 the key
    also folds the would-discharge model's ``(pack_name, pack_version)``
    (selection is deterministic and cheap), so bumping ONE pack misses
    exactly its own cached evidence -- a deferral or no-model obligation
    keys at the built-in identity.

    ``payload_store`` (D96/D154) is this build's WO-30 content-addressed
    payload store, if any; when given, its bound ``resolve`` handle
    (:meth:`PayloadStore.resolver`) is threaded to the registry so a
    matched model that opted into the ``resolver`` parameter (`Model.
    discharge`'s capability check) can resolve `DischargeRequest.
    payloads` refs to their schema-versioned JSON bytes. ``None`` means
    no store is configured for this discharge -- an opted-in model then
    receives ``resolver=None`` and honestly indeterminates its own
    payload lookups, same as before this channel existed.
    """
    keys = trust_keys if trust_keys is not None else TrustKeySet()
    trust_floor = obligation.claim.trust_floor
    lowered = translate(
        obligation,
        cost_context=cost_context,
        frame_context=frame_context,
        plan_context=plan_context,
        si_context=si_context,
    )
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
            content_hash=content_hash,
            evidence=cached,
            from_cache=True,
            attestation=status,
            trust_floor=trust_floor,
        )

    if lowered.is_err:
        deferral = lowered.danger_err
        # subject_ref is legitimately empty for some obligation kinds
        # (e.g. `conforms` obligations before refinement-bound extraction,
        # WO-12 cut) -- fall back to the cache key so the log line never
        # names nothing.
        log_ref = obligation.subject_ref or key
        # WO-107: per-obligation deferral detail is DEBUG noise at scale
        # (the same record prints 2-4x per obligation); `discharge_all`
        # emits ONE INFO aggregate by reason bucket. `-v` restores this.
        _log.debug(
            "obligation %s deferred: %s (%s)",
            log_ref,
            deferral.reason,
            deferral.detail,
        )
        return ObligationResult(
            key=key,
            subject_ref=obligation.subject_ref,
            content_hash=content_hash,
            deferral=deferral,
            trust_floor=trust_floor,
        )

    request = lowered.danger_ok
    _log.debug("dispatching claim_kind=%s to harness", request.claim_kind)
    resolver = payload_store.resolver() if payload_store is not None else None
    evidence = registry.discharge(request, resolver=resolver)

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
        # WO-107: DEBUG detail; folded into `discharge_all`'s INFO
        # aggregate under the reason bucket.
        _log.debug("obligation %s has no matching model", obligation.subject_ref)
        # WO-109 deliverable 4: distinguish (b) "the claim's CALL PATH
        # matched no registered model" (translate routed the request by
        # the call's dotted path, so the kind differs from the author's
        # label -- name the path) from (a) "the claim carries no model
        # call form at all" (the kind IS the label; only a new model or
        # call form can ever route it).
        label = obligation.claim.name
        if label is not None and request.claim_kind != label:
            deferral = Deferral(
                reason="unmatched_call_path",
                detail=(
                    f"call path {request.claim_kind!r} (claim label "
                    f"{label!r}) matches no registered harness model"
                ),
            )
        else:
            no_call_note = (
                " (label-only claim: no model call form)" if label is not None else ""
            )
            deferral = Deferral(
                reason="no_model",
                detail=(
                    f"no harness model for claim kind "
                    f"{request.claim_kind!r}{no_call_note}"
                ),
            )
        return ObligationResult(
            key=key,
            subject_ref=obligation.subject_ref,
            content_hash=content_hash,
            evidence=evidence,
            attestation=status,
            trust_floor=trust_floor,
            deferral=deferral,
        )
    return ObligationResult(
        key=key,
        subject_ref=obligation.subject_ref,
        content_hash=content_hash,
        evidence=evidence,
        attestation=status,
        trust_floor=trust_floor,
    )


def _obligation_content_hashes(obligations: list[Obligation]) -> list[str]:
    """The AD-18 content hash of every obligation, in order (WO-98).

    Delegates to the ONE canonical encoder across the FFI
    (:func:`regolith.compiler.obligation_content_hashes`) -- reproducing
    the CBOR address in Python would be a forbidden second encoder. An
    empty obligation set short-circuits (no FFI call).
    """
    if not obligations:
        return []
    obligations_json = json.dumps([o.model_dump(mode="json") for o in obligations])
    return compiler.obligation_content_hashes(obligations_json)


def discharge_all(
    obligations: list[Obligation],
    *,
    registry: ModelRegistry,
    store: EvidenceStore,
    signer: LocalSigningKey | None = None,
    trust_keys: TrustKeySet | None = None,
    payload_store: PayloadStore | None = None,
    cost_context: CostContext | None = None,
    frame_context: FrameContext | None = None,
    plan_context: PlanContext | None = None,
    si_context: SiContext | None = None,
) -> tuple[ObligationResult, ...]:
    """Discharge every obligation in source order (INV-10 determinism).

    ``payload_store`` (D96/D154), ``cost_context`` (WO-54),
    ``frame_context`` (WO-48 close-out follow-up), ``plan_context``
    (WO-69), and ``si_context`` (WO-78) are forwarded to every
    :func:`discharge_one` call unchanged.

    WO-98: each obligation's AD-18 content hash is computed once (the
    ONE encoder, over the FFI) and threaded onto its result by source
    index, so the release gate can match a ledger deviation to it.
    """
    content_hashes = _obligation_content_hashes(obligations)
    results = tuple(
        discharge_one(
            o,
            registry=registry,
            store=store,
            signer=signer,
            trust_keys=trust_keys,
            payload_store=payload_store,
            cost_context=cost_context,
            frame_context=frame_context,
            plan_context=plan_context,
            si_context=si_context,
            content_hash=content_hashes[i],
        )
        for i, o in enumerate(obligations)
    )
    _log.debug(
        "discharged %d obligations (cache hits=%d, misses=%d)",
        len(results),
        store.stats.hits,
        store.stats.misses,
    )
    _log_deferral_aggregate(results)
    return results


def _log_deferral_aggregate(results: tuple[ObligationResult, ...]) -> None:
    """Emit ONE INFO line summarizing deferrals by reason bucket (WO-107).

    The per-obligation detail rides DEBUG (`discharge_one`); this is the
    at-a-glance replacement -- ``deferred N: reason X, reason Y, ...`` with
    reasons ordered by descending count then name (deterministic, INV-10).
    Silent when nothing deferred: a clean pass adds no noise."""
    from collections import Counter

    reasons: Counter[str] = Counter(
        r.deferral.reason for r in results if r.deferral is not None
    )
    total = sum(reasons.values())
    if total == 0:
        return
    ordered = sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))
    breakdown = ", ".join(f"{reason} {count}" for reason, count in ordered)
    _log.info("discharge: %d obligation(s) deferred: %s", total, breakdown)
