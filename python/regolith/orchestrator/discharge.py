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

from pydantic import BaseModel, ConfigDict

from regolith._schema.models import Evidence, Obligation, Status3
from regolith.harness import ModelRegistry
from regolith.harness.registry import NO_MODEL_ID
from regolith.logging_setup import get_logger
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

    @property
    def is_resolved(self) -> bool:
        """True iff a model discharged this obligation (status ``discharged``)."""
        return self.evidence is not None and self.evidence.status == "discharged"

    @property
    def is_indeterminate(self) -> bool:
        """True iff the verdict is indeterminate OR the obligation deferred."""
        if self.deferral is not None:
            return True
        return self.evidence is not None and self.evidence.status == "indeterminate"

    @property
    def is_violated(self) -> bool:
        """True iff a model proved the claim violated."""
        return self.evidence is not None and self.evidence.status == "violated"


def discharge_one(
    obligation: Obligation,
    *,
    registry: ModelRegistry,
    store: EvidenceStore,
) -> ObligationResult:
    """Discharge one obligation: cache lookup, else lower + route + store.

    Deterministic and total. A cache hit returns the stored evidence; a
    miss lowers the obligation (deferring honestly if it will not lower)
    and asks the registry for a verdict, which is itself total (no model
    -> indeterminate). The registry version is threaded through the key so
    a model bump is a guaranteed miss (BE-1/INV-1).
    """
    key = obligation_cache_key(obligation, registry.version)
    cached = store.get(key)
    if cached is not None:
        return ObligationResult(
            key=key,
            subject_ref=obligation.subject_ref,
            evidence=cached,
            from_cache=True,
        )

    lowered = translate(obligation)
    if lowered.is_err:
        deferral = lowered.danger_err
        _log.info(
            "obligation %s deferred: %s (%s)",
            obligation.subject_ref,
            deferral.reason,
            deferral.detail,
        )
        return ObligationResult(
            key=key, subject_ref=obligation.subject_ref, deferral=deferral
        )

    request = lowered.danger_ok
    _log.debug("dispatching claim_kind=%s to harness", request.claim_kind)
    evidence = registry.discharge(request)
    store.put(key, evidence)

    # A no-model verdict is an honest deferral surface (INV-24): keep the
    # indeterminate evidence AND flag it so the release gate can name it.
    if evidence.model_id == NO_MODEL_ID and evidence.status == Status3.indeterminate:
        _log.info("obligation %s has no matching model", obligation.subject_ref)
        return ObligationResult(
            key=key,
            subject_ref=obligation.subject_ref,
            evidence=evidence,
            deferral=Deferral(
                reason="no_model",
                detail=f"no harness model for claim kind {request.claim_kind!r}",
            ),
        )
    return ObligationResult(
        key=key, subject_ref=obligation.subject_ref, evidence=evidence
    )


def discharge_all(
    obligations: list[Obligation],
    *,
    registry: ModelRegistry,
    store: EvidenceStore,
) -> tuple[ObligationResult, ...]:
    """Discharge every obligation in source order (INV-10 determinism)."""
    results = tuple(
        discharge_one(o, registry=registry, store=store) for o in obligations
    )
    _log.debug(
        "discharged %d obligations (cache hits=%d, misses=%d)",
        len(results),
        store.stats.hits,
        store.stats.misses,
    )
    return results
