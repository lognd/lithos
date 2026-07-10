"""std.cam: the CAM plan-verification model-pack family (WO-67, AD-35).

Check-mode only (charter `33-cam-verification.md` D1): supplied G-code
plans verify (never generate) through five models -- `cam.parse`,
`cam.envelope`, `cam.collision_coarse`, `cam.removal`, `cam.coverage`
-- registered per-dialect (`gcode_fanuc`, `gcode_marlin`) in
`register_cam_models`.
"""

from __future__ import annotations

from regolith.harness.models.cam.ir import Dialect
from regolith.harness.models.cam.models import (
    CamCollisionCoarseModel,
    CamCoverageModel,
    CamEnvelopeModel,
    CamParseModel,
    CamRemovalModel,
)
from regolith.harness.registry import ModelRegistry


def register_cam_models(registry: ModelRegistry) -> None:
    """Register the std.cam pack: five models x two dialects (WO-67)."""
    for dialect in (Dialect.fanuc, Dialect.marlin):
        registry.register(CamParseModel(dialect))
        registry.register(CamEnvelopeModel(dialect))
        registry.register(CamCollisionCoarseModel(dialect))
        registry.register(CamRemovalModel(dialect))
        registry.register(CamCoverageModel(dialect))


__all__ = [
    "CamCollisionCoarseModel",
    "CamCoverageModel",
    "CamEnvelopeModel",
    "CamParseModel",
    "CamRemovalModel",
    "register_cam_models",
]
