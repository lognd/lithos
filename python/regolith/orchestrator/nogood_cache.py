"""Cross-run nogood cache (cuprite/08 EOPEN-13, D75).

D75 closes EOPEN-13 on one soundness rule: learned nogoods are per-run
solver state in v1 (never lockfile content), and cross-run reuse of a
nogood is sound IFF the cache key includes every catalog record
revision the nogood's blame set consumed -- the INV-1 discipline
(``regolith/07`` sec. 7) applied to search state instead of evidence.

This module is the persistence layer implementing that rule. A nogood
is addressed by the rejected ``(block, record_key)`` pair PLUS the full
blamed trial: every candidate's ``record_key``/``content_hash`` that
entered the budget computation the trial violated, and the budget set
itself. Mutate any blamed record (a new revision, hence a new content
hash) and the key changes, so a stale nogood is a natural MISS -- there
is no separate invalidation pass, exactly the same content-addressing
argument `regolith.orchestrator.cache.EvidenceStore` already makes for
harness evidence.

The store lives beside the harness evidence cache under `.regolith/`
(AD-10; gitignored, project-local) in its own file so the two caches
never share rows.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import blake3
from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# Domain tag prefixing every key so a nogood-cache key can never collide
# with any other content address in the system (mirrors the harness
# evidence cache's domain tag, AD-18).
_KEY_DOMAIN = "regolith.orchestrator.nogood_cache"

# Distinct filename beside the harness evidence cache under `.regolith/`.
_CACHE_FILENAME = "nogood-cache.json"


# frob:doc docs/modules/py-orchestrator.md#nogood_cache
class BlamedRecord(BaseModel):
    """One catalog record the blame set consumed (D75's soundness unit).

    ``record_key`` is the ``package/key@revision`` string; ``content_hash``
    is the record's own content address. Both are folded into the cache
    key so a revision bump OR a same-revision content drift (an
    integrity anomaly elsewhere, but this cache does not assume it away)
    each yield a different key.
    """

    model_config = ConfigDict(frozen=True)

    record_key: str
    content_hash: str


# frob:doc docs/modules/py-orchestrator.md#nogood_cache
def nogood_cache_key(
    block: str,
    rejected_record_key: str,
    blamed: Sequence[BlamedRecord],
    budget_signature: Sequence[tuple[str, float]],
) -> str:
    """Content-address a nogood under its full blame set (D75).

    ``blamed`` is every candidate's ``(record_key, content_hash)`` that
    entered the budget sum the rejected trial violated; ``budget_signature``
    is the ``(capability, limit)`` pairs the derivation checked against.
    Sound reuse: this key differs the instant ANY blamed record's content
    hash changes, so a stale nogood can never silently persist across runs
    (INV-1 discipline applied to search state, D75). Canonical JSON
    (sorted keys, no whitespace) hashed with blake3, matching the harness
    evidence cache's hasher -- deterministic across platforms (INV-10).
    """
    canonical = json.dumps(
        {
            "domain": _KEY_DOMAIN,
            "block": block,
            "rejected": rejected_record_key,
            "blamed": sorted((b.record_key, b.content_hash) for b in blamed),
            "budgets": sorted(budget_signature),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "blake3:" + blake3.blake3(canonical.encode("ascii")).hexdigest()


# frob:doc docs/modules/py-orchestrator.md#nogood_cache
class NogoodStats(BaseModel):
    """Hit/miss/store counters for one solver run (observability)."""

    model_config = ConfigDict(frozen=True)

    hits: int = 0
    misses: int = 0
    stores: int = 0

    # frob:doc docs/modules/py-orchestrator.md#nogood_cache
    def with_hit(self) -> NogoodStats:
        """A copy with the hit counter advanced (frozen model)."""
        return NogoodStats(hits=self.hits + 1, misses=self.misses, stores=self.stores)

    # frob:doc docs/modules/py-orchestrator.md#nogood_cache
    def with_miss(self) -> NogoodStats:
        """A copy with the miss counter advanced (frozen model)."""
        return NogoodStats(hits=self.hits, misses=self.misses + 1, stores=self.stores)

    # frob:doc docs/modules/py-orchestrator.md#nogood_cache
    def with_store(self) -> NogoodStats:
        """A copy with the store counter advanced (frozen model)."""
        return NogoodStats(hits=self.hits, misses=self.misses, stores=self.stores + 1)


# frob:doc docs/modules/py-orchestrator.md#nogood_cache
class NogoodCache:
    """A content-addressed, cross-run cache of D75 nogoods.

    Membership only: the presence of a key IS the cached nogood -- the
    key already encodes the full blame set (:func:`nogood_cache_key`),
    so there is nothing else to store or re-validate on a hit. This
    mirrors why `EvidenceStore` never needs a separate invalidation
    pass: content-addressing makes staleness structurally impossible,
    not merely checked for.
    """

    def __init__(self, keys: set[str] | None = None) -> None:
        """Start from `keys` (already-known nogood cache keys), or empty."""
        self._keys: set[str] = set(keys or ())
        self._stats = NogoodStats()

    @property
    # frob:doc docs/modules/py-orchestrator.md#nogood_cache
    def stats(self) -> NogoodStats:
        """The running hit/miss/store counters."""
        return self._stats

    # frob:doc docs/modules/py-orchestrator.md#nogood_cache
    def get(self, key: str) -> bool:
        """True iff `key` is a known nogood (a cross-run cache HIT)."""
        hit = key in self._keys
        if hit:
            self._stats = self._stats.with_hit()
            _log.info("nogood cache HIT for %s (D75 re-derivation skipped)", key)
        else:
            self._stats = self._stats.with_miss()
            _log.debug("nogood cache MISS for %s", key)
        return hit

    # frob:doc docs/modules/py-orchestrator.md#nogood_cache
    def put(self, key: str) -> None:
        """Record `key` as a known nogood (idempotent; logs new stores only)."""
        is_new = key not in self._keys
        self._keys.add(key)
        if is_new:
            self._stats = self._stats.with_store()
            _log.debug("nogood cache STORE for %s", key)

    @staticmethod
    # frob:doc docs/modules/py-orchestrator.md#nogood_cache
    def cache_path(project_root: str) -> Path:
        """The cache file path under ``<project_root>/.regolith/`` (AD-10)."""
        return Path(project_root) / ".regolith" / _CACHE_FILENAME

    @classmethod
    # frob:doc docs/modules/py-orchestrator.md#nogood_cache
    def load(cls, project_root: str) -> Result[NogoodCache, OrchestratorError]:
        """Load the persisted cache, or an empty store if none exists.

        A missing cache is a fresh, empty store (``Ok``); a present-but-
        corrupt cache is an ``Err`` value so the caller can rebuild it
        rather than silently trust garbage (matches `EvidenceStore.load`).
        """
        path = cls.cache_path(project_root)
        if not path.is_file():
            _log.debug("no nogood cache at %s; starting empty", path)
            return Ok(cls())
        try:
            raw = json.loads(path.read_text(encoding="ascii"))
        except (OSError, ValueError) as exc:
            _log.warning("corrupt nogood cache at %s: %s", path, exc)
            return Err(
                OrchestratorError(
                    kind="corrupt_cache",
                    message=f"cannot read nogood cache {path}: {exc}",
                )
            )
        if not isinstance(raw, list) or not all(isinstance(k, str) for k in raw):
            _log.warning("malformed nogood cache at %s: expected a list of keys", path)
            return Err(
                OrchestratorError(
                    kind="corrupt_cache",
                    message=f"malformed nogood cache {path}: expected a list of keys",
                )
            )
        _log.debug("loaded %d nogood entries from %s", len(raw), path)
        keys: set[str] = {str(k) for k in raw}
        return Ok(cls(keys))

    # frob:doc docs/modules/py-orchestrator.md#nogood_cache
    def save(self, project_root: str) -> Result[None, OrchestratorError]:
        """Persist the cache under ``.regolith/`` deterministically (INV-10)."""
        path = self.cache_path(project_root)
        text = json.dumps(sorted(self._keys), separators=(",", ":"))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="ascii")
        except OSError as exc:
            _log.warning("cannot persist nogood cache to %s: %s", path, exc)
            return Err(
                OrchestratorError(
                    kind="cache_write_failed",
                    message=f"cannot write nogood cache {path}: {exc}",
                )
            )
        _log.debug("persisted %d nogood entries to %s", len(self._keys), path)
        return Ok(None)
