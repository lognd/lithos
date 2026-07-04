"""The rockhead orchestrator: build tiers, evidence cache, and the loop.

Owns everything that drives a build over time (AD-1): the T0..T3 tier
progression (:mod:`~rockhead.orchestrator.tiers`), the harness evidence
cache (:mod:`~rockhead.orchestrator.cache`, INV-1/BE-1), obligation
routing to the harness (:mod:`~rockhead.orchestrator.discharge`), the lazy
loop with sensitivity hooks (:mod:`~rockhead.orchestrator.loop`,
substrate/12), the release-gate totality check (INV-24), and the lockfile
(:mod:`~rockhead.orchestrator.lockfile`, WO-14). The harness selects and
computes evidence; the orchestrator owns caching, ordering, and the loop.
"""

from __future__ import annotations

from rockhead.orchestrator.cache import (
    CacheStats,
    EvidenceStore,
    obligation_cache_key,
)
from rockhead.orchestrator.discharge import (
    ObligationResult,
    discharge_all,
    discharge_one,
)
from rockhead.orchestrator.lockfile import Lockfile, LockRow, LockSection
from rockhead.orchestrator.loop import LoopOutcome, SensitivityHook, lazy_loop
from rockhead.orchestrator.orchestrate import BuildReport, build, release_gate
from rockhead.orchestrator.tiers import TIER_BY_VERB, BuildTier
from rockhead.orchestrator.translate import Deferral, translate

__all__ = [
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
    "build",
    "discharge_all",
    "discharge_one",
    "lazy_loop",
    "obligation_cache_key",
    "release_gate",
    "translate",
]
