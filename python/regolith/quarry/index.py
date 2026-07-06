"""The lodestone sparse index (regolith/11 sec. 10.1).

A registry is an index plus an archive store. The index maps
``(package, version)`` to a manifest digest and an archive hash; it is
append-only and fetched sparsely (per-package paths, the cargo
sparse-index shape). Each package's index file is newline-delimited JSON,
one :class:`IndexEntry` per line, append-only so a yank flips a flag
rather than rewriting history.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import QuarryError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


class IndexEntry(BaseModel):
    """One published ``(package, version)`` row of a sparse-index file."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    manifest_digest: str  # hash of the manifest (INV-22 pin)
    archive_hash: str  # content address of the archive (blake3:...)
    yanked: bool = False  # hidden from new resolution, still fetchable (sec. 10.5)
    advisory: str | None = None  # a security advisory surfaced as a warning


def index_path(package: str) -> str:
    """The sparse-index path for ``package`` (cargo-style shardless form).

    Kept simple and deterministic: the package name is the path. A real
    lodestone may shard by name length; consumers only need a stable
    per-package URL, which this is.
    """
    return package


def parse_index(text: str) -> Result[tuple[IndexEntry, ...], QuarryError]:
    """Parse a package's newline-delimited-JSON sparse index file."""
    entries: list[IndexEntry] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except ValueError as exc:
            _log.warning("malformed index line %d: %s", lineno, exc)
            return Err(
                QuarryError(
                    kind="malformed_index",
                    message=f"line {lineno}: {exc}",
                )
            )
        entries.append(IndexEntry.model_validate(payload))
    _log.debug("parsed %d index entries", len(entries))
    return Ok(tuple(entries))


def select_version(
    entries: tuple[IndexEntry, ...], version: str
) -> Result[IndexEntry, QuarryError]:
    """Pick the entry for an exact ``version``, honoring yank semantics.

    A yanked version is still selectable by exact pin (a lockfile written
    yesterday builds today, sec. 10.5); this returns it and lets the caller
    surface the advisory. An absent version is an error.
    """
    for entry in entries:
        if entry.version == version:
            if entry.yanked:
                _log.info("selected YANKED %s@%s by exact pin", entry.name, version)
            return Ok(entry)
    return Err(
        QuarryError(
            kind="version_not_found",
            message=f"no index entry for version {version!r}",
        )
    )


def latest_version(
    entries: tuple[IndexEntry, ...],
) -> Result[IndexEntry, QuarryError]:
    """Pick the newest non-yanked entry for *new* resolution (sec. 10.5).

    Yanked versions disappear from new resolution but remain fetchable by
    exact pin. Ordering is by the entries' append order (index is
    append-only), so the last non-yanked row is the newest.
    """
    live = [e for e in entries if not e.yanked]
    if not live:
        return Err(
            QuarryError(
                kind="no_live_version",
                message="every version is yanked; pin an exact version to fetch",
            )
        )
    return Ok(live[-1])
