"""The lodestone registry client over httpx (regolith/11 sec. 10; INV-22).

Fetches a package's sparse index and its content-addressed archives, and
verifies every fetched archive against the hash the caller demands
(INV-22 foreign-content pinning): a poisoned mirror can only produce a
loud hash-mismatch error, never a silent substitution. The transport is
injectable (an ``httpx.Client`` passed in), so tests drive it with an
in-memory ``httpx.MockTransport`` and never touch the network.

Trust is NOT decided here: hosting confers nothing (sec. 10.4). This layer
delivers verified bytes; :mod:`regolith.quarry.trust` decides their tier
from signatures.
"""

from __future__ import annotations

import blake3
import httpx
from typani.result import Err, Ok, Result

from regolith.errors import QuarryError
from regolith.logging_setup import get_logger
from regolith.quarry.index import (
    IndexEntry,
    index_path,
    parse_index,
    select_version,
)
from regolith.quarry.sources import Registry

_log = get_logger(__name__)


def _strip_algo(content_hash: str) -> Result[str, QuarryError]:
    """Split a ``blake3:<digest>`` pin into its digest, or error."""
    if ":" not in content_hash:
        return Err(
            QuarryError(
                kind="invalid_hash",
                message=f"content hash {content_hash!r} lacks an algorithm tag",
            )
        )
    algo, digest = content_hash.split(":", 1)
    if algo != "blake3" or not digest:
        return Err(
            QuarryError(
                kind="invalid_hash",
                message=f"unsupported/empty content hash {content_hash!r} "
                "(expected blake3:<digest>)",
            )
        )
    return Ok(digest)


def verify_archive(data: bytes, expected_hash: str) -> Result[bytes, QuarryError]:
    """Check ``data`` hashes to ``expected_hash`` (INV-22), returning it.

    A mismatch is the drift error the whole hosting model rests on
    (sec. 10.3): tampered bytes served under a pinned hash fail here before
    anything consumes them.
    """
    digest_result = _strip_algo(expected_hash)
    if digest_result.is_err:
        return Err(digest_result.danger_err)
    actual = blake3.blake3(data).hexdigest()
    if actual != digest_result.danger_ok:
        _log.warning(
            "archive hash MISMATCH: demanded %s, computed blake3:%s",
            expected_hash,
            actual,
        )
        return Err(
            QuarryError(
                kind="hash_mismatch",
                message=(
                    f"archive drift: demanded {expected_hash}, "
                    f"content hashes to blake3:{actual}"
                ),
            )
        )
    _log.debug("archive verified against %s (%d bytes)", expected_hash, len(data))
    return Ok(data)


class RegistryClient:
    """A client for one lodestone registry (index + archive store)."""

    def __init__(self, registry: Registry, transport: httpx.Client) -> None:
        """Bind a ``registry`` (URLs) to an injected ``httpx.Client``.

        The client owns no network policy of its own: pass a real client
        for production, an ``httpx.Client(transport=httpx.MockTransport(...))``
        for tests. Hosting URLs affect availability, never meaning.
        """
        self._registry = registry
        self._http = transport

    def fetch_index(self, package: str) -> Result[tuple[IndexEntry, ...], QuarryError]:
        """Fetch and parse ``package``'s sparse index (sec. 10.1)."""
        url = f"{self._registry.index_url.rstrip('/')}/{index_path(package)}"
        try:
            response = self._http.get(url)
        except httpx.HTTPError as exc:
            return Err(QuarryError(kind="fetch_failed", message=f"GET {url}: {exc}"))
        if response.status_code != 200:
            return Err(
                QuarryError(
                    kind="index_not_found",
                    message=f"GET {url} -> HTTP {response.status_code}",
                )
            )
        return parse_index(response.text)

    def fetch_archive(self, archive_hash: str) -> Result[bytes, QuarryError]:
        """Fetch a content-addressed archive by hash and verify it (INV-22).

        Always addressable by exact hash, even for yanked versions
        (sec. 10.5): the archive store is dumb content-addressed storage.
        """
        digest_result = _strip_algo(archive_hash)
        if digest_result.is_err:
            return Err(digest_result.danger_err)
        url = f"{self._registry.archive_url.rstrip('/')}/{digest_result.danger_ok}"
        try:
            response = self._http.get(url)
        except httpx.HTTPError as exc:
            return Err(QuarryError(kind="fetch_failed", message=f"GET {url}: {exc}"))
        if response.status_code != 200:
            return Err(
                QuarryError(
                    kind="archive_not_found",
                    message=f"GET {url} -> HTTP {response.status_code}",
                )
            )
        return verify_archive(response.content, archive_hash)

    def fetch_pinned(
        self, package: str, version: str
    ) -> Result[tuple[IndexEntry, bytes], QuarryError]:
        """Resolve an exact ``(package, version)`` pin to its verified archive.

        The end-to-end pinned fetch: index -> exact-version entry (yank is
        surfaced, not blocked, per sec. 10.5) -> verified archive bytes.
        """
        index = self.fetch_index(package)
        if index.is_err:
            return Err(index.danger_err)
        entry = select_version(index.danger_ok, version)
        if entry.is_err:
            return Err(entry.danger_err)
        chosen = entry.danger_ok
        archive = self.fetch_archive(chosen.archive_hash)
        if archive.is_err:
            return Err(archive.danger_err)
        return Ok((chosen, archive.danger_ok))
