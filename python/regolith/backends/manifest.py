"""The signed ship manifest: the package's own attestation (WO-25).

Same envelope discipline as `regolith.harness.attest` (INV-28's
evidence-signing machinery, reused here rather than duplicated): a
signature is computed over a domain-tagged content address of the
manifest's UNSIGNED fields, never over the raw bytes and never folding
the signature itself back into what it signs -- so re-signing on key
rotation never perturbs the manifest's own identity.
"""

from __future__ import annotations

import base64
import json
from typing import Literal

import blake3
from cryptography.exceptions import InvalidSignature
from pydantic import BaseModel, ConfigDict, Field
from typani.result import Err, Ok, Result

from regolith._codes import RELEASE_GATE_REFUSES_DEBUG_EVIDENCE
from regolith.backends.framework import OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger
from regolith.magnetite.trust import LocalSigningKey, TrustKeySet

_log = get_logger(__name__)

# Mirrors `regolith.harness.attest._ADDRESS_DOMAIN`'s discipline: a
# distinct domain tag so a ship-manifest signature can never be replayed
# as an evidence attestation or vice versa.
_ADDRESS_DOMAIN = "regolith.backends.ship_manifest"

InvalidReason = Literal["bad_signature", "unknown_key", "algorithm_mismatch"]

# D237.1 (WO-125, charter 40 sec. 1): the debug emission profile
# AUGMENTS what a release build emits and never changes verdict/claim
# math; it is otherwise ordinary package metadata, tracked here so a
# debug package is never mistakable for release-gate evidence.
ShipProfile = Literal["release", "debug"]


# frob:doc docs/modules/py-backends.md#backends-manifest
class FileHash(BaseModel):
    """One packaged file's path and SHA-256 hash (sorted by ``relpath``)."""

    model_config = ConfigDict(frozen=True)

    relpath: str
    sha256: str

    # frob:doc docs/modules/py-backends.md#backends-manifest
    @classmethod
    def of(cls, output: OutputFile) -> FileHash:
        """The ``FileHash`` for one emitted ``OutputFile``."""
        return cls(relpath=output.relpath, sha256=output.sha256)


# frob:doc docs/modules/py-backends.md#backends-manifest
class ManifestSignature(BaseModel):
    """The ed25519 envelope over a manifest's content address."""

    model_config = ConfigDict(frozen=True)

    key_id: str
    algorithm: Literal["ed25519"] = "ed25519"
    signature_base64: str


# frob:doc docs/modules/py-backends.md#backends-manifest
class ShipManifest(BaseModel):
    """The signed attestation for one ``regolith ship`` package.

    ``design_hash``/``lockfile_hash`` pin the exact source + resolved
    state the package was produced from; ``evidence_rollup`` is a
    sorted mapping of subject -> discharge status naming what backed
    the release gate; ``files`` is every emitted file's hash, sorted by
    ``relpath`` (determinism, AD-6). ``signature`` is ``None`` until
    :func:`sign_manifest` runs.
    """

    model_config = ConfigDict(frozen=True)

    design_hash: str
    lockfile_hash: str
    evidence_rollup: tuple[tuple[str, str], ...] = Field(
        default=(), description="Sorted (subject, status) pairs."
    )
    files: tuple[FileHash, ...] = ()
    signature: ManifestSignature | None = None
    # D237.1: default `"release"` keeps every pre-WO-125 manifest call
    # site byte-shape-compatible in spirit (the field is new, so JSON
    # goldens still gain one key -- documented in WO-125's plan as the
    # one expected manifest.json diff; artifact FILE bytes elsewhere are
    # unaffected).
    profile: ShipProfile = "release"

    # frob:doc docs/modules/py-backends.md#backends-manifest
    def unsigned(self) -> ShipManifest:
        """This manifest with its signature stripped (the signed message)."""
        return self.model_copy(update={"signature": None})


def _content_address(manifest: ShipManifest) -> str:
    """Domain-tagged blake3 over the manifest's UNSIGNED fields."""
    canonical = json.dumps(
        {
            "domain": _ADDRESS_DOMAIN,
            "manifest": manifest.unsigned().model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "blake3:" + blake3.blake3(canonical.encode("ascii")).hexdigest()


# frob:doc docs/modules/py-backends.md#backends-manifest
def build_manifest(
    *,
    design_hash: str,
    lockfile_hash: str,
    evidence_rollup: tuple[tuple[str, str], ...],
    files: tuple[OutputFile, ...],
    profile: ShipProfile = "release",
) -> ShipManifest:
    """Assemble an unsigned manifest, sorting rollup + file entries (AD-6)."""
    return ShipManifest(
        design_hash=design_hash,
        lockfile_hash=lockfile_hash,
        evidence_rollup=tuple(sorted(evidence_rollup)),
        files=tuple(sorted((FileHash.of(f) for f in files), key=lambda h: h.relpath)),
        profile=profile,
    )


# frob:doc docs/modules/py-backends.md#backends-manifest
def release_gate_refuses_debug_evidence(
    manifest: ShipManifest,
) -> Result[None, BackendError]:
    """D237.1: a debug-profile package is never valid release-gate evidence.

    ``Ok`` iff ``manifest.profile == "release"``; otherwise a named
    ``debug_not_release_evidence`` error. Debug packages remain fully
    verifiable by :func:`verify_manifest`/:func:`verify_file_hashes`
    (signature/hash integrity is orthogonal to release-evidence
    eligibility) -- this check is the SEPARATE gate a caller runs when
    consuming a package specifically AS release evidence (e.g. a
    downstream acceptance/jig-mating flow), not a blanket verify step.
    """
    if manifest.profile != "release":
        _log.warning(
            "release_gate_refuses_debug_evidence: manifest profile=%r is "
            "not release-gate evidence",
            manifest.profile,
        )
        return Err(
            BackendError(
                kind=RELEASE_GATE_REFUSES_DEBUG_EVIDENCE,  # E1102 (D247.1/D237.1)
                message=f"package profile={manifest.profile!r} is a debug "
                "build; debug packages are never valid release-gate "
                "evidence (D237.1)",
            )
        )
    return Ok(None)


# frob:doc docs/modules/py-backends.md#backends-manifest
def sign_manifest(manifest: ShipManifest, key: LocalSigningKey) -> ShipManifest:
    """Sign ``manifest``'s content address, returning it with a signature attached."""
    address = _content_address(manifest)
    signature = key.sign(address.encode("ascii"))
    _log.info("signed ship manifest with key %s", key.key_id)
    return manifest.model_copy(
        update={
            "signature": ManifestSignature(
                key_id=key.key_id,
                signature_base64=base64.b64encode(signature).decode("ascii"),
            )
        }
    )


# frob:doc docs/modules/py-backends.md#backends-manifest
def verify_manifest(
    manifest: ShipManifest, keys: TrustKeySet
) -> Result[None, BackendError]:
    """Verify ``manifest.signature`` over its content address (total, never raises).

    ``Ok`` iff a signature is present, its key is trust-designated, and
    it verifies. Every other case (missing signature, unknown key,
    algorithm mismatch, tamper) is an honest ``Err`` naming why.
    """
    sig = manifest.signature
    if sig is None:
        return Err(BackendError(kind="unsigned", message="ship manifest is unsigned"))
    designation = keys.designation(sig.key_id)
    if designation is None:
        return Err(
            BackendError(
                kind="unknown_key",
                message=f"key {sig.key_id!r} is not designated in the trust key set",
            )
        )
    address = _content_address(manifest)
    try:
        designation.public_key().verify(
            base64.b64decode(sig.signature_base64.encode("ascii")),
            address.encode("ascii"),
        )
    except InvalidSignature:
        _log.warning("ship manifest signature by %s FAILED verification", sig.key_id)
        return Err(
            BackendError(
                kind="bad_signature",
                message=f"signature by {sig.key_id!r} does not verify "
                "over the manifest",
            )
        )
    _log.debug("ship manifest signature by %s verified", sig.key_id)
    return Ok(None)


# frob:doc docs/modules/py-backends.md#backends-manifest
def verify_file_hashes(
    manifest: ShipManifest, files: tuple[OutputFile, ...]
) -> Result[None, BackendError]:
    """Re-hash ``files`` and check them against ``manifest.files`` (``ship --verify``).

    Every manifest-listed path must be present with a matching hash,
    and no extra file may be present -- either direction is a tamper
    signal, named in the ``Err``.
    """
    by_path = {f.relpath: f.sha256 for f in files}
    manifest_paths = {fh.relpath: fh.sha256 for fh in manifest.files}
    if by_path.keys() != manifest_paths.keys():
        missing = sorted(manifest_paths.keys() - by_path.keys())
        extra = sorted(by_path.keys() - manifest_paths.keys())
        return Err(
            BackendError(
                kind="file_set_mismatch",
                message=f"missing={missing} extra={extra}",
            )
        )
    mismatched = sorted(
        path for path, sha in by_path.items() if sha != manifest_paths[path]
    )
    if mismatched:
        return Err(
            BackendError(
                kind="hash_mismatch",
                message=f"hash mismatch for: {mismatched}",
            )
        )
    return Ok(None)
