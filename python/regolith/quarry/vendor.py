"""``quarry vendor``: copy pinned archives into the tree (regolith/11 sec. 10.3).

Vendoring copies every lockfile-pinned archive into the repo so builds run
offline (air-gapped mirrors, reproducible CI). It needs no trust machinery
of its own: the vendored bytes are content-addressed, so the lockfile pin
still decides acceptance, and a tampered vendored file fails the same
INV-22 hash comparison a tampered mirror would. Files land under
``vendor/<digest>`` -- the digest names the file, so the store is itself
content-addressed and de-duplicated.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import QuarryError
from regolith.logging_setup import get_logger
from regolith.quarry.client import RegistryClient, verify_archive

_log = get_logger(__name__)

_VENDOR_DIRNAME = "vendor"


class VendorPin(BaseModel):
    """One archive to vendor: a package/version label and its content hash."""

    model_config = ConfigDict(frozen=True)

    package: str
    version: str
    archive_hash: str


def _digest(archive_hash: str) -> str:
    """The bare digest of a ``blake3:<digest>`` pin (its vendored filename)."""
    return archive_hash.split(":", 1)[1] if ":" in archive_hash else archive_hash


class VendorStore:
    """A content-addressed on-disk archive store under ``<root>/vendor/``."""

    def __init__(self, project_root: str) -> None:
        """Bind the store to ``<project_root>/vendor/`` (created on write)."""
        self._dir = Path(project_root) / _VENDOR_DIRNAME

    @property
    def directory(self) -> Path:
        """The vendor directory path."""
        return self._dir

    def archive_file(self, archive_hash: str) -> Path:
        """The on-disk path an archive with ``archive_hash`` vendors to."""
        return self._dir / _digest(archive_hash)

    def write(self, archive_hash: str, data: bytes) -> Result[Path, QuarryError]:
        """Verify ``data`` against ``archive_hash`` (INV-22) and store it."""
        verified = verify_archive(data, archive_hash)
        if verified.is_err:
            return Err(verified.danger_err)
        path = self.archive_file(archive_hash)
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(verified.danger_ok)
        except OSError as exc:
            return Err(
                QuarryError(kind="vendor_write_failed", message=f"{path}: {exc}")
            )
        _log.debug("vendored %s (%d bytes)", archive_hash, len(data))
        return Ok(path)

    def read(self, archive_hash: str) -> Result[bytes, QuarryError]:
        """Read a vendored archive, re-verifying its hash on load (INV-22).

        Re-verification is the whole point of an offline store: a tampered
        vendored file must fail exactly like a tampered mirror would.
        """
        path = self.archive_file(archive_hash)
        if not path.is_file():
            return Err(
                QuarryError(
                    kind="not_vendored",
                    message=f"archive {archive_hash} not vendored at {path}",
                )
            )
        return verify_archive(path.read_bytes(), archive_hash)


def vendor(
    pins: tuple[VendorPin, ...],
    *,
    client: RegistryClient,
    project_root: str,
) -> Result[VendorStore, QuarryError]:
    """Fetch and vendor every pinned archive into ``<project_root>/vendor/``.

    Each archive is fetched through ``client`` (verified on fetch, INV-22)
    and written into the content-addressed store (verified again on write).
    A single fetch/verify failure fails the whole vendor pass loudly -- an
    offline build must not start from a partial store.
    """
    store = VendorStore(project_root)
    for pin in pins:
        # Skip re-fetch if already vendored and still valid (idempotent).
        if store.read(pin.archive_hash).is_ok:
            _log.debug("already vendored %s@%s", pin.package, pin.version)
            continue
        fetched = client.fetch_archive(pin.archive_hash)
        if fetched.is_err:
            return Err(fetched.danger_err)
        written = store.write(pin.archive_hash, fetched.danger_ok)
        if written.is_err:
            return Err(written.danger_err)
    _log.debug("vendored %d archive(s) into %s", len(pins), store.directory)
    return Ok(store)
