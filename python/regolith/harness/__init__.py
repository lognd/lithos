"""The regolith harness (WO-14/15/16). Package placeholder for WO-01.

Owns the model registry (AD-1: registry/model versions are Python-side).
Until the real registry lands, it declares a single version constant that
the orchestrator threads into `compile` so it is folded into every
evidence-cache key (BE-1/INV-1): bumping this string invalidates all
cached evidence, forcing re-verification under the new models.
"""

# The harness model-registry version. Bump this whenever a discharge
# model is fixed/upgraded so stale evidence is never silently reused
# (BE-1/INV-1). String, not int: it is opaque hash input, and a
# human-readable id (e.g. a semver or content hash) survives review.
MODEL_REGISTRY_VERSION = "model-registry@0.0.0"

# Public surface. Imported AFTER the version constant so the submodules
# (which read MODEL_REGISTRY_VERSION from this package) see it defined --
# `default_registry` pulls in the model packs lazily to avoid a cycle.
from regolith.harness.adapter import (  # noqa: E402
    SolverSpec,
    SubprocessSolverModel,
    solve_via_subprocess,
)
from regolith.harness.attest import (  # noqa: E402
    ATTESTATION_INVALID_ID,
    AttestationStatus,
    Invalid,
    Unsigned,
    Valid,
    conferred_tier,
    evidence_content_address,
    sign_evidence,
    verify_attestation,
)
from regolith.harness.errors import ADAPTER_ERROR_ID  # noqa: E402
from regolith.harness.model import (  # noqa: E402
    DischargeRequest,
    Model,
    Prediction,
)
from regolith.harness.plugin import (  # noqa: E402
    ENTRY_POINT_GROUP,
    PackInfo,
    PackLoadOutcome,
    load_packs,
)
from regolith.harness.quantity import Interval  # noqa: E402
from regolith.harness.registry import (  # noqa: E402
    BUILTIN_PACK_NAME,
    NO_MODEL_ID,
    ModelRegistry,
    default_registry,
)
from regolith.harness.signature import ClaimSense, ModelSignature  # noqa: E402

__all__ = [
    "ADAPTER_ERROR_ID",
    "ATTESTATION_INVALID_ID",
    "BUILTIN_PACK_NAME",
    "ENTRY_POINT_GROUP",
    "MODEL_REGISTRY_VERSION",
    "NO_MODEL_ID",
    "AttestationStatus",
    "ClaimSense",
    "DischargeRequest",
    "Interval",
    "Invalid",
    "Model",
    "ModelRegistry",
    "ModelSignature",
    "PackInfo",
    "PackLoadOutcome",
    "Prediction",
    "SolverSpec",
    "SubprocessSolverModel",
    "Unsigned",
    "Valid",
    "conferred_tier",
    "default_registry",
    "evidence_content_address",
    "load_packs",
    "sign_evidence",
    "solve_via_subprocess",
    "verify_attestation",
]
