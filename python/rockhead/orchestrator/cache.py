"""The harness evidence cache (substrate/09 sec. 2-3; INV-1/INV-10/BE-1).

The Rust core caches the *static* discharge subset under ``.rockhead/``;
this is the orchestrator's cache for the *harness* discharge it owns
(AD-1). It is keyed the same way the Rust obligation key is keyed -- the
obligation's own content plus the harness model-registry version folded
in -- so the two caches agree on what invalidates evidence: any semantic
change to the obligation, OR a model-registry bump, is a cache MISS
(INV-1). Bit-reproducible: canonical JSON (sorted keys) hashed with
blake3, matching the core's hasher, so identical inputs give an identical
key on every platform (INV-10).

The store is a plain content-addressed map persisted as JSON. It never
raises for a recoverable condition: a corrupt or unreadable cache file is
an ``OrchestratorError`` value the caller decides about (rebuild vs fail).
"""

from __future__ import annotations

import json
from pathlib import Path

import blake3
from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from rockhead._schema.models import Evidence, Obligation
from rockhead.errors import OrchestratorError
from rockhead.logging_setup import get_logger

_log = get_logger(__name__)

# Domain tag prefixing every key so a harness-cache key can never collide
# with any other content address in the system (mirrors the Rust core's
# domain-tagged addressing, AD-18).
_KEY_DOMAIN = "rockhead.orchestrator.harness_evidence"

# The on-disk cache lives beside the core's cache under `.rockhead/`
# (AD-10; gitignored). Distinct filename: the core owns `evidence.json`.
_CACHE_FILENAME = "harness-evidence.json"


def obligation_cache_key(obligation: Obligation, registry_version: str) -> str:
    """Content-address ``obligation`` under ``registry_version`` (INV-1/BE-1).

    Folds the model-registry version into the hash exactly as the Rust
    ``Obligation::evidence_cache_key`` does: a model upgrade (new version)
    or any semantic change to the obligation yields a DIFFERENT key, so
    stale evidence is never silently reused. Canonical JSON (sorted keys,
    no whitespace) hashed with blake3 -- deterministic across platforms.
    """
    canonical = json.dumps(
        {
            "domain": _KEY_DOMAIN,
            "registry_version": registry_version,
            "obligation": obligation.model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "blake3:" + blake3.blake3(canonical.encode("ascii")).hexdigest()


class CacheStats(BaseModel):
    """Hit/miss counters for one orchestration run (observability)."""

    model_config = ConfigDict(frozen=True)

    hits: int = 0
    misses: int = 0

    def with_hit(self) -> CacheStats:
        """A copy with the hit counter advanced (frozen model)."""
        return CacheStats(hits=self.hits + 1, misses=self.misses)

    def with_miss(self) -> CacheStats:
        """A copy with the miss counter advanced (frozen model)."""
        return CacheStats(hits=self.hits, misses=self.misses + 1)


class EvidenceStore:
    """A content-addressed cache of harness ``Evidence`` (get/put + persist)."""

    def __init__(self, entries: dict[str, Evidence] | None = None) -> None:
        """Start from ``entries`` (obligation key -> evidence), or empty."""
        self._entries: dict[str, Evidence] = dict(entries or {})
        self._stats = CacheStats()

    @property
    def stats(self) -> CacheStats:
        """The running hit/miss counters."""
        return self._stats

    def get(self, key: str) -> Evidence | None:
        """Fetch cached evidence for ``key``; counts a hit or a miss."""
        hit = self._entries.get(key)
        if hit is None:
            self._stats = self._stats.with_miss()
            _log.debug("evidence cache MISS for %s", key)
            return None
        self._stats = self._stats.with_hit()
        _log.debug("evidence cache HIT for %s", key)
        return hit

    def put(self, key: str, evidence: Evidence) -> None:
        """Store ``evidence`` under ``key`` (content-addressed, idempotent)."""
        self._entries[key] = evidence
        _log.debug("evidence cache STORE for %s (status=%s)", key, evidence.status)

    def as_dict(self) -> dict[str, Evidence]:
        """The current entries (sorted-key copy, deterministic serialization)."""
        return {k: self._entries[k] for k in sorted(self._entries)}

    @staticmethod
    def cache_path(project_root: str) -> Path:
        """The cache file path under ``<project_root>/.rockhead/`` (AD-10)."""
        return Path(project_root) / ".rockhead" / _CACHE_FILENAME

    @classmethod
    def load(cls, project_root: str) -> Result[EvidenceStore, OrchestratorError]:
        """Load the persisted cache, or an empty store if none exists.

        A missing cache is a fresh, empty store (``Ok``); a present-but-
        corrupt cache is an ``Err`` value so the caller can rebuild it
        rather than silently trust garbage.
        """
        path = cls.cache_path(project_root)
        if not path.is_file():
            _log.debug("no harness evidence cache at %s; starting empty", path)
            return Ok(cls())
        try:
            raw = json.loads(path.read_text(encoding="ascii"))
        except (OSError, ValueError) as exc:
            _log.warning("corrupt harness evidence cache at %s: %s", path, exc)
            return Err(
                OrchestratorError(
                    kind="corrupt_cache",
                    message=f"cannot read evidence cache {path}: {exc}",
                )
            )
        entries = {key: Evidence.model_validate(val) for key, val in raw.items()}
        _log.debug("loaded %d harness evidence entries from %s", len(entries), path)
        return Ok(cls(entries))

    def save(self, project_root: str) -> Result[None, OrchestratorError]:
        """Persist the cache under ``.rockhead/`` deterministically (INV-10)."""
        path = self.cache_path(project_root)
        payload = {k: v.model_dump(mode="json") for k, v in self.as_dict().items()}
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="ascii")
        except OSError as exc:
            _log.warning("cannot persist evidence cache to %s: %s", path, exc)
            return Err(
                OrchestratorError(
                    kind="cache_write_failed",
                    message=f"cannot write evidence cache {path}: {exc}",
                )
            )
        _log.debug("persisted %d harness evidence entries to %s", len(payload), path)
        return Ok(None)
