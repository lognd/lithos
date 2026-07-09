"""The pinned native-artifact store (STEP bytes, `.kicad_pcb` bytes).

AD-25/WO-25's amendment: the realized-domain IR (``RealizedGeometry``,
``RealizedLayout``) is the semantic content every pass/pack/backend reads;
the native artifact (STEP, `.kicad_pcb`) stays a pinned SIDE artifact,
addressed by the SHA-256 hex digest already carried on the IR
(``step_content_hash`` / ``kicad_pcb_content_hash`` -- plain SHA-256 hex,
NOT the `blake3:`-prefixed WO-30 payload-store convention, so this store
uses its own digest scheme rather than overload
:class:`~regolith.orchestrator.payload_store.PayloadStore`). Realizer
adapters (mech, elec) hold native bytes only transiently today (WO-22/24
never persist them); this store is WO-25's own seam so a backend can
resolve the bytes a realizer pass produced earlier in the SAME process or
a caller explicitly pinned via :meth:`NativeArtifactStore.put_at`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from typani.result import Err, Ok, Result

from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

_ARTIFACTS_DIRNAME = "artifacts"


class NativeArtifactStore:
    """A content-addressed (SHA-256 hex) store for pinned native bytes.

    Rooted under ``<project_root>/.regolith/artifacts/`` (beside the
    WO-30 payload store and the evidence cache, AD-10; gitignored).
    """

    def __init__(self, project_root: str) -> None:
        """Root the store under ``<project_root>/.regolith/artifacts/``."""
        self._root = Path(project_root) / ".regolith" / _ARTIFACTS_DIRNAME

    @property
    def root(self) -> Path:
        """The directory native-artifact files are written under."""
        return self._root

    def _path_for(self, digest: str) -> Path:
        return self._root / digest

    def put(self, data: bytes) -> str:
        """Store ``data`` under its own SHA-256 hex digest (idempotent)."""
        digest = hashlib.sha256(data).hexdigest()
        return self.put_at(digest, data)

    def put_at(self, digest: str, data: bytes) -> str:
        """Store ``data`` under a caller-pinned digest (idempotent).

        Used when the digest already lives on a realized-domain IR
        (``RealizedGeometry.step_content_hash``,
        ``RealizedLayout.kicad_pcb_content_hash``) so this store never
        recomputes a second hash that could desync from the IR's own.
        """
        path = self._path_for(digest)
        if path.is_file():
            _log.debug("native artifact store PUT %s: already present", digest)
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        _log.debug("native artifact store PUT %s (%d bytes)", digest, len(data))
        return digest

    def put_verified(self, digest: str, data: bytes) -> Result[str, BackendError]:
        """Store ``data`` under ``digest`` only if its own SHA-256 matches.

        Unlike :meth:`put_at`, this recomputes the hash over the actual
        bytes and refuses a mismatch instead of trusting the caller's
        pinned digest -- used at ship time, where ``data`` is read back
        off disk and may have gone stale/tampered since the digest was
        recorded on the realized-domain IR.

        ``digest`` may be a bare SHA-256 hex string (mech's
        ``step_content_hash`` convention) or a ``"sha256:"``-prefixed
        one (elec's ``kicad_pcb_content_hash`` convention, from
        :func:`regolith.realizer.elec.kicad.hash_pcb_file`) -- both
        compare correctly against the recomputed bare hash. The bytes
        are stored under ``digest`` UNCHANGED (whichever form the
        caller passed) so the resolve key stays consistent with
        callers that look artifacts up by the IR's own digest string.
        """
        actual = hashlib.sha256(data).hexdigest()
        if actual != digest.removeprefix("sha256:"):
            _log.error(
                "native artifact store: content hash mismatch for %s "
                "(on-disk bytes hash to %s)",
                digest,
                actual,
            )
            return Err(
                BackendError(
                    kind="native_artifact_hash_mismatch",
                    message=(
                        f"native artifact bytes do not match pinned digest "
                        f"{digest!r} (bytes hash to {actual!r})"
                    ),
                )
            )
        return Ok(self.put_at(digest, data))

    def resolve(self, digest: str) -> Result[bytes, BackendError]:
        """Read back the bytes pinned under ``digest``, or an honest ``Err``.

        A missing digest is never a crash -- it is the mech/elec
        backend's ``ir_unavailable`` failure arm, matching the "record,
        do not fake" discipline the realizer WOs established.
        """
        path = self._path_for(digest)
        if not path.is_file():
            _log.debug("native artifact store MISS for %s", digest)
            return Err(
                BackendError(
                    kind="native_artifact_not_found",
                    message=f"no native artifact pinned under digest {digest!r}",
                )
            )
        try:
            data = path.read_bytes()
        except OSError as exc:
            _log.error("native artifact store: cannot read %s: %s", path, exc)
            return Err(
                BackendError(
                    kind="native_artifact_unreadable",
                    message=f"cannot read native artifact {digest!r}: {exc}",
                )
            )
        return Ok(data)
