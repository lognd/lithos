"""The regolith orchestrator: build tiers, evidence cache, and the loop.

Owns everything that drives a build over time (AD-1): the T0..T3 tier
progression (:mod:`~regolith.orchestrator.tiers`), the harness evidence
cache (:mod:`~regolith.orchestrator.cache`, INV-1/BE-1), obligation
routing to the harness (:mod:`~regolith.orchestrator.discharge`), the lazy
loop with sensitivity hooks (:mod:`~regolith.orchestrator.loop`,
regolith/12), the release-gate totality check (INV-24), and the lockfile
(:mod:`~regolith.orchestrator.lockfile`, WO-14). The harness selects and
computes evidence; the orchestrator owns caching, ordering, and the loop.
"""

from __future__ import annotations

from regolith.orchestrator.cache import (
    CacheStats,
    EvidenceStore,
    obligation_cache_key,
)
from regolith.orchestrator.discharge import (
    ObligationResult,
    discharge_all,
    discharge_one,
)
from regolith.orchestrator.lockfile import Lockfile, LockRow, LockSection
from regolith.orchestrator.loop import LoopOutcome, SensitivityHook, lazy_loop
from regolith.orchestrator.orchestrate import (
    REALIZER_PACK_MECH,
    BuildReport,
    StagedBuildReport,
    build,
    realized_lock_rows,
    release_gate,
    staged_build,
)
from regolith.orchestrator.tiers import TIER_BY_VERB, BuildTier
from regolith.orchestrator.translate import Deferral, translate

__all__ = [
    "REALIZER_PACK_MECH",
    "TIER_BY_VERB",
    "BuildReport",
    "BuildTier",
    "CacheStats",
    "Deferral",
    "EvidenceStore",
    "Lockfile",
    "LockRow",
    "LockSection",
    "LoopOutcome",
    "ObligationResult",
    "SensitivityHook",
    "StagedBuildReport",
    "build",
    "discharge_all",
    "discharge_one",
    "lazy_loop",
    "obligation_cache_key",
    "realized_lock_rows",
    "release_gate",
    "staged_build",
    "translate",
]
