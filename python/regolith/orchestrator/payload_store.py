"""The orchestrator-owned content-addressed payload store (D96, sec. 8.3).

The generalized payload-ref channel (`PayloadRef.digest`) is a blake3
digest into THIS store: packs never do their own storage IO (AD-17
lowering stays IO-free too) -- they receive a resolver handle at
discharge and call :meth:`PayloadStore.resolve`. Files live under
``.regolith/payloads/`` (beside the evidence cache, AD-10; gitignored),
named by their digest so a re-``put`` of identical bytes is a no-op.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import blake3
from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.harness.model import DischargeRequest
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The resolver handle `discharge_one` passes down the existing discharge
# call path (WO-30 deliverable 2): a model that consumes a payload calls
# this rather than doing its own storage IO (AD-17 stays IO-free too).
PayloadResolver = Callable[[str], "Result[bytes, OrchestratorError]"]

# Payloads live beside the evidence cache under `.regolith/` (AD-10).
_PAYLOADS_DIRNAME = "payloads"


def _digest_of(data: bytes) -> str:
    """The blake3 content digest of ``data``, in the repo's `blake3:`-prefixed form."""
    return "blake3:" + blake3.blake3(data).hexdigest()


# frob:doc docs/modules/py-orchestrator.md#payload_store
# frob:waive TEST001 reason="digest helper, tested via cache round-trip tests"
# frob:waive TEST005 reason="measured 50.0% branch on 2026-07-19; backfill T-0036"
def payload_digest(data: bytes) -> str:
    """The store's digest scheme as a public function (WO-124): callers
    that need the SAME `blake3:`-prefixed digest a `put` would mint
    (e.g. the staged loop deriving a board's design short-hash from the
    build payload bytes) use this, never a second hashing recipe."""
    return _digest_of(data)


# frob:doc docs/modules/py-orchestrator.md#payload_store
class PayloadStore:
    """A minimal content-addressed store for D96 payload refs.

    ``put`` writes bytes under their own digest (idempotent: writing
    the same bytes twice is a no-op); ``resolve`` reads them back by
    digest, returning an ``Err`` value (never raising) for a missing or
    unreadable digest.
    """

    def __init__(self, project_root: str) -> None:
        """Root the store under ``<project_root>/.regolith/payloads/``."""
        self._root = Path(project_root) / ".regolith" / _PAYLOADS_DIRNAME

    @property
    # frob:doc docs/modules/py-orchestrator.md#payload_store
    # frob:waive TEST005 reason="measured 50.0% branch on 2026-07-19; backfill T-0036"
    def root(self) -> Path:
        """The directory payload files are written under."""
        return self._root

    def _path_for(self, digest: str) -> Path:
        """The on-disk path for a digest (strips the `blake3:` prefix)."""
        bare = digest.removeprefix("blake3:")
        return self._root / bare

    # frob:doc docs/modules/py-orchestrator.md#payload_store
    def put(self, data: bytes) -> str:
        """Store ``data``, returning its content digest (idempotent).

        Never fails for a recoverable reason on the happy path; a write
        failure (e.g. a read-only filesystem) is logged and re-raised
        only as a last resort -- callers that need a `Result` should
        catch at the orchestrator boundary same as `EvidenceStore.save`.
        """
        digest = _digest_of(data)
        path = self._path_for(digest)
        if path.is_file():
            _log.debug("payload store PUT %s: already present (idempotent)", digest)
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        _log.debug("payload store PUT %s (%d bytes)", digest, len(data))
        return digest

    # frob:doc docs/modules/py-orchestrator.md#payload_store
    def put_at(self, digest: str, data: bytes) -> str:
        """Store ``data`` under a CALLER-SUPPLIED ``digest`` (idempotent).

        Unlike :meth:`put`, this never recomputes a digest from ``data``:
        it exists for content the Rust core already content-addressed
        through the AD-18 canonical encoder (e.g. `FlownetPayload
        .content_digest()`, folded with `SCHEMA_VERSION` and the
        `flownet` domain tag over canonical CBOR of the Rust struct --
        not the JSON bytes this method is handed). Recomputing a SECOND
        digest here over JSON bytes would both duplicate the canonical
        encoder (AD-18: "nothing hashes JSON, anywhere") and silently
        desync from the digest a `PayloadRef` already carries in an
        emitted obligation, breaking discharge-time `resolve` lookups
        (WO-32 D4b: the first orchestrator `PayloadStore` producer).
        """
        path = self._path_for(digest)
        if path.is_file():
            _log.debug("payload store PUT %s: already present (idempotent)", digest)
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        _log.debug("payload store PUT (pinned digest) %s (%d bytes)", digest, len(data))
        return digest

    # frob:doc docs/modules/py-orchestrator.md#payload_store
    def resolve(self, digest: str) -> Result[bytes, OrchestratorError]:
        """Read back the bytes stored under ``digest``, or an ``Err`` value.

        A missing digest, or an unreadable file, is an explicit
        ``Err(OrchestratorError)`` -- never an exception -- so a caller
        can map it to an INDETERMINATE discharge rather than crash.
        """
        path = self._path_for(digest)
        if not path.is_file():
            _log.debug("payload store MISS for %s", digest)
            return Err(
                OrchestratorError(
                    kind="payload_not_found",
                    message=f"no payload stored under digest {digest!r}",
                )
            )
        try:
            data = path.read_bytes()
        except OSError as exc:
            _log.warning("payload store read failure for %s: %s", digest, exc)
            return Err(
                OrchestratorError(
                    kind="payload_read_failed",
                    message=f"cannot read payload {digest!r}: {exc}",
                )
            )
        _log.debug("payload store RESOLVE %s (%d bytes)", digest, len(data))
        return Ok(data)

    # frob:doc docs/modules/py-orchestrator.md#payload_store
    def resolver(self) -> PayloadResolver:
        """A bound ``digest -> bytes`` handle (the resolver the discharge
        call path passes to models, deliverable 2): packs never do their
        own storage IO -- they call this instead of touching the
        filesystem.
        """
        return self.resolve


# frob:doc docs/modules/py-orchestrator.md#payload_store
def resolve_request_payloads(
    request: DischargeRequest, resolve: PayloadResolver
) -> Result[Mapping[str, bytes], OrchestratorError]:
    """Resolve every payload ref a request carries to its bytes.

    Total over the request's ``payloads`` mapping: the first
    unresolvable digest is an ``Err`` (never a partial/silent result),
    naming the port whose payload could not be read.
    """
    resolved: dict[str, bytes] = {}
    for port, ref in request.payloads.items():
        got = resolve(ref.digest)
        if got.is_err:
            _log.info(
                "payload port %r (digest=%s) unresolved: %s",
                port,
                ref.digest,
                got.danger_err,
            )
            return Err(got.danger_err)
        resolved[port] = got.danger_ok
    return Ok(resolved)
