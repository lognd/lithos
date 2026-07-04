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
from regolith.harness.model import (  # noqa: E402
    DischargeRequest,
    Model,
    Prediction,
)
from regolith.harness.quantity import Interval  # noqa: E402
from regolith.harness.registry import (  # noqa: E402
    NO_MODEL_ID,
    ModelRegistry,
    default_registry,
)
from regolith.harness.signature import ClaimSense, ModelSignature  # noqa: E402

__all__ = [
    "MODEL_REGISTRY_VERSION",
    "NO_MODEL_ID",
    "ClaimSense",
    "DischargeRequest",
    "Interval",
    "Model",
    "ModelRegistry",
    "ModelSignature",
    "Prediction",
    "default_registry",
]
