"""The harness evidence cache (regolith/09 sec. 2-3; INV-1/INV-10/BE-1).

The Rust core caches the *static* discharge subset under ``.regolith/``;
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

from regolith._schema.models import Attestation, Evidence, Obligation
from regolith.errors import OrchestratorError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# Domain tag prefixing every key so a harness-cache key can never collide
# with any other content address in the system (mirrors the Rust core's
# domain-tagged addressing, AD-18).
_KEY_DOMAIN = "regolith.orchestrator.harness_evidence"

# The on-disk cache lives beside the core's cache under `.regolith/`
# (AD-10; gitignored). Distinct filename: the core owns `evidence.json`.
_CACHE_FILENAME = "harness-evidence.json"


# frob:doc docs/modules/py-orchestrator.md#cache
def obligation_cache_key(
    obligation: Obligation,
    registry_version: str,
    *,
    pack_name: str = "regolith",
    pack_version: str | None = None,
) -> str:
    """Content-address ``obligation`` under ``registry_version`` (INV-1/BE-1).

    Folds the model-registry version into the hash exactly as the Rust
    ``Obligation::evidence_cache_key`` does: a model upgrade (new version)
    or any semantic change to the obligation yields a DIFFERENT key, so
    stale evidence is never silently reused. AD-19 extends the fold with
    the discharging model's ``(pack_name, pack_version)`` -- mirroring
    ``Obligation::evidence_cache_key_for_pack`` -- so upgrading ONE pack
    misses exactly its own cached evidence; the defaults are the
    built-in identity ``("regolith", registry_version)``. Canonical JSON
    (sorted keys, no whitespace) hashed with blake3 -- deterministic
    across platforms.
    """
    canonical = json.dumps(
        {
            "domain": _KEY_DOMAIN,
            "registry_version": registry_version,
            # AD-19 (BE-1 extended): the discharging model's pack pair.
            "pack_name": pack_name,
            "pack_version": pack_version
            if pack_version is not None
            else registry_version,
            "obligation": obligation.model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "blake3:" + blake3.blake3(canonical.encode("ascii")).hexdigest()


# frob:doc docs/modules/py-orchestrator.md#cache
class CacheStats(BaseModel):
    """Hit/miss counters for one orchestration run (observability)."""

    model_config = ConfigDict(frozen=True)

    hits: int = 0
    misses: int = 0

    # frob:doc docs/modules/py-orchestrator.md#cache
    def with_hit(self) -> CacheStats:
        """A copy with the hit counter advanced (frozen model)."""
        return CacheStats(hits=self.hits + 1, misses=self.misses)

    # frob:doc docs/modules/py-orchestrator.md#cache
    def with_miss(self) -> CacheStats:
        """A copy with the miss counter advanced (frozen model)."""
        return CacheStats(hits=self.hits, misses=self.misses + 1)


# frob:doc docs/modules/py-orchestrator.md#cache
class EvidenceStore:
    """A content-addressed cache of harness ``Evidence`` (get/put + persist).

    Each row optionally carries an ``Attestation`` alongside its evidence
    (WO-21): the attestation is an ENVELOPE and NEVER part of the cache key
    (D-E), so a signed and an unsigned copy of the same evidence share the
    row -- the key is a pure function of the obligation payload (INV-1).
    """

    def __init__(
        self,
        entries: dict[str, Evidence] | None = None,
        attestations: dict[str, Attestation] | None = None,
    ) -> None:
        """Start from ``entries`` (obligation key -> evidence), or empty."""
        self._entries: dict[str, Evidence] = dict(entries or {})
        self._attestations: dict[str, Attestation] = dict(attestations or {})
        self._stats = CacheStats()

    @property
    # frob:doc docs/modules/py-orchestrator.md#cache
    def stats(self) -> CacheStats:
        """The running hit/miss counters."""
        return self._stats

    # frob:doc docs/modules/py-orchestrator.md#cache
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

    # frob:doc docs/modules/py-orchestrator.md#cache
    def put(
        self, key: str, evidence: Evidence, attestation: Attestation | None = None
    ) -> None:
        """Store ``evidence`` (and optional ``attestation``) under ``key``.

        Content-addressed and idempotent. The attestation is stored beside
        the evidence, never folded into ``key`` (envelope property, D-E).
        """
        self._entries[key] = evidence
        if attestation is not None:
            self._attestations[key] = attestation
        else:
            self._attestations.pop(key, None)
        _log.debug(
            "evidence cache STORE for %s (status=%s, attested=%s)",
            key,
            evidence.status,
            attestation is not None,
        )

    # frob:doc docs/modules/py-orchestrator.md#cache
    def attestation_of(self, key: str) -> Attestation | None:
        """The attestation stored with ``key``, or ``None`` if unsigned."""
        return self._attestations.get(key)

    # frob:doc docs/modules/py-orchestrator.md#cache
    def as_dict(self) -> dict[str, Evidence]:
        """The current entries (sorted-key copy, deterministic serialization)."""
        return {k: self._entries[k] for k in sorted(self._entries)}

    @staticmethod
    # frob:doc docs/modules/py-orchestrator.md#cache
    def cache_path(project_root: str) -> Path:
        """The cache file path under ``<project_root>/.regolith/`` (AD-10)."""
        return Path(project_root) / ".regolith" / _CACHE_FILENAME

    @classmethod
    # frob:doc docs/modules/py-orchestrator.md#cache
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
        entries: dict[str, Evidence] = {}
        attestations: dict[str, Attestation] = {}
        for key, val in raw.items():
            # New shape wraps `{evidence, attestation}`; the WO-20 bare-
            # Evidence row (no top-level "evidence" key) still loads, with
            # a `None` attestation -- existing caches stay readable.
            if isinstance(val, dict) and "evidence" in val:
                entries[key] = Evidence.model_validate(val["evidence"])
                att = val.get("attestation")
                if att is not None:
                    attestations[key] = Attestation.model_validate(att)
            else:
                entries[key] = Evidence.model_validate(val)
        _log.debug("loaded %d harness evidence entries from %s", len(entries), path)
        return Ok(cls(entries, attestations))

    # frob:doc docs/modules/py-orchestrator.md#cache
    def save(self, project_root: str) -> Result[None, OrchestratorError]:
        """Persist the cache under ``.regolith/`` deterministically (INV-10)."""
        path = self.cache_path(project_root)
        payload = {
            k: {
                "evidence": v.model_dump(mode="json"),
                "attestation": (
                    self._attestations[k].model_dump(mode="json")
                    if k in self._attestations
                    else None
                ),
            }
            for k, v in self.as_dict().items()
        }
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
