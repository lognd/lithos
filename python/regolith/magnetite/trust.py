"""Trust tiers and signature verification (regolith/11 sec. 7 + 10; INV-14).

Trust is a property of *signatures on a record*, verified locally against
the consumer's key set -- never a property of where a package was fetched
from (regolith/11 sec. 10.4). A certified MMPDS record is certified from
any mirror; no registry operator can mint certification by hosting. The
tiers form a total order (``certified > tested > community``) so a claim
group's trust floor compares totally (INV-14): a signature below the floor
is not an error, it downgrades the usable tier.
"""

from __future__ import annotations

import base64
from enum import IntEnum
from pathlib import Path

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import MagnetiteError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


class TrustTier(IntEnum):
    """The total order of evidence trust (regolith/11 sec. 7).

    The integer value IS the rank, so ``TrustTier.CERTIFIED > TrustTier.
    TESTED`` and floor comparison are the same fact (INV-14 totality).
    """

    COMMUNITY = 0  # unsigned
    TESTED = 1  # attached test reports
    CERTIFIED = 2  # authority/vendor-signed

    def meets(self, floor: TrustTier) -> bool:
        """True iff this tier satisfies a required ``floor`` (>= in order)."""
        return self >= floor


_TIER_BY_NAME = {t.name.lower(): t for t in TrustTier}


def tier_from_name(name: str) -> Result[TrustTier, MagnetiteError]:
    """Parse a tier name (``certified``/``tested``/``community``) totally."""
    tier = _TIER_BY_NAME.get(name.strip().lower())
    if tier is None:
        return Err(
            MagnetiteError(
                kind="unknown_trust_tier", message=f"unknown trust tier {name!r}"
            )
        )
    return Ok(tier)


class Signature(BaseModel):
    """A signature on a record: which key signed it, and the tier it grants."""

    model_config = ConfigDict(frozen=True)

    key_id: str
    grants: TrustTier
    # The signed content hash the signature vouches for (INV-22 binding):
    # a signature is only meaningful against the exact bytes it covers.
    over_hash: str


class KeySet(BaseModel):
    """The consumer's trusted keys and the maximum tier each may grant.

    A key present here is trusted up to its mapped tier; a signature by an
    unknown key, or one claiming a tier above its key's ceiling, does not
    count. Hosting is deliberately absent -- trust is decided entirely by
    this local set (regolith/11 sec. 10.4).
    """

    model_config = ConfigDict(frozen=True)

    ceilings: tuple[tuple[str, TrustTier], ...] = ()

    def ceiling(self, key_id: str) -> TrustTier | None:
        """The maximum tier ``key_id`` may grant, or ``None`` if untrusted."""
        for kid, tier in self.ceilings:
            if kid == key_id:
                return tier
        return None


def verify_trust(
    content_hash: str,
    signatures: tuple[Signature, ...],
    keyset: KeySet,
) -> TrustTier:
    """The tier a record earns from its signatures, verified locally.

    Returns the HIGHEST tier for which some signature (a) is over exactly
    ``content_hash`` (INV-22: the signature must cover the pinned bytes),
    (b) is by a key in ``keyset``, and (c) claims a tier at or below that
    key's ceiling. Unsigned or unverifiable content is ``community`` -- the
    honest floor, never a silent upgrade.
    """
    earned = TrustTier.COMMUNITY
    for sig in signatures:
        if sig.over_hash != content_hash:
            _log.debug("signature by %s ignored: covers other bytes", sig.key_id)
            continue
        ceiling = keyset.ceiling(sig.key_id)
        if ceiling is None:
            _log.debug("signature by untrusted key %s ignored", sig.key_id)
            continue
        granted = min(sig.grants, ceiling)
        if granted > earned:
            earned = granted
    _log.debug("verified trust tier %s for %s", earned.name, content_hash)
    return earned


class KeyDesignation(BaseModel):
    """A consumer statement: this key, if it signs, confers this tier.

    The signing-carries-trust half of INV-14 applied to computed evidence
    (INV-28): a solver's attestation earns ``confers`` only when the
    consumer has designated the signing key here -- storage/hosting never
    does. ``public_key_base64`` is the ed25519 raw public key the consumer
    checks signatures against; naming the key is not enough.
    """

    model_config = ConfigDict(frozen=True)

    key_id: str
    public_key_base64: str
    confers: TrustTier

    def public_key(self) -> Ed25519PublicKey:
        """The ed25519 public key this designation verifies signatures with."""
        return Ed25519PublicKey.from_public_bytes(
            base64.b64decode(self.public_key_base64.encode("ascii"))
        )


class TrustKeySet(BaseModel):
    """The consumer's designated signing keys for computed-evidence trust.

    Distinct from :class:`KeySet` (registry records): this set maps a
    solver signing ``key_id`` to the tier its attestation confers, and is
    a pure CONSUMER-side artifact -- re-designating a key (INV-28 fixture)
    changes the earned tier of already-signed evidence without re-signing.
    """

    model_config = ConfigDict(frozen=True)

    designations: tuple[KeyDesignation, ...] = ()

    def designation(self, key_id: str) -> KeyDesignation | None:
        """The designation for ``key_id``, or ``None`` if the key is untrusted."""
        for designation in self.designations:
            if designation.key_id == key_id:
                return designation
        return None

    def designate(self, designation: KeyDesignation) -> TrustKeySet:
        """A NEW set with ``designation`` added or replacing the same key id.

        Frozen: returns a copy so a consumer re-designating a key (raising
        or lowering the tier it confers) is a value change the caller
        threads forward, never a mutation of shared trust state.
        """
        kept = tuple(d for d in self.designations if d.key_id != designation.key_id)
        return TrustKeySet(designations=(*kept, designation))


# Local signing keys live under `<project>/.regolith/keys/` -- gitignored
# via `.regolith/` (never committed, never logged). PEM (PKCS8) on disk.
_KEYS_SUBDIR = ("keys",)
_KEY_SUFFIX = ".pem"


def keys_dir(project_root: str) -> Path:
    """The local signing-key directory under ``<project_root>/.regolith/``."""
    return Path(project_root).joinpath(".regolith", *_KEYS_SUBDIR)


class LocalSigningKey:
    """A local ed25519 signing key: private material that NEVER leaves memory.

    A plain class, not a model: the private key is a live cryptography
    object that must not be serialized, dumped, or logged. ``__repr__``
    redacts it so an accidental log line or traceback never leaks it.
    """

    def __init__(self, key_id: str, private_key: Ed25519PrivateKey) -> None:
        """Hold ``private_key`` under ``key_id`` (identity used in attestations)."""
        self.key_id = key_id
        self._private_key = private_key

    def __repr__(self) -> str:
        """Redacted representation -- private key material is never shown."""
        return f"LocalSigningKey(key_id={self.key_id!r}, private_key=<redacted>)"

    def sign(self, message: bytes) -> bytes:
        """The ed25519 signature over ``message`` (the evidence content address)."""
        return self._private_key.sign(message)

    def public_key_base64(self) -> str:
        """The raw ed25519 public key, base64 -- for building a designation."""
        raw = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw).decode("ascii")


def _key_path(project_root: str, key_id: str) -> Path:
    """The PEM path for ``key_id`` under the local keys directory."""
    return keys_dir(project_root) / f"{key_id}{_KEY_SUFFIX}"


def generate_signing_key(
    project_root: str, key_id: str
) -> Result[LocalSigningKey, MagnetiteError]:
    """Generate a fresh ed25519 keypair, persist the private PEM, return it.

    Writes an unencrypted PKCS8 PEM under ``.regolith/keys/<key_id>.pem``
    (a local dev key, gitignored). An IO failure is a ``MagnetiteError``
    value, never an exception (house rule).
    """
    existing = _key_path(project_root, key_id)
    if existing.exists():
        return Err(
            MagnetiteError(
                kind="signing_key_exists",
                message=f"signing key {key_id!r} already exists at {existing}",
            )
        )
    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    try:
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(pem)
    except OSError as exc:
        _log.warning("cannot write signing key %s to %s: %s", key_id, existing, exc)
        return Err(
            MagnetiteError(
                kind="signing_key_write_failed",
                message=f"cannot write signing key {key_id!r} to {existing}: {exc}",
            )
        )
    _log.info("generated signing key %s at %s", key_id, existing)
    return Ok(LocalSigningKey(key_id, private_key))


def load_signing_key(
    project_root: str, key_id: str
) -> Result[LocalSigningKey, MagnetiteError]:
    """Load a previously generated local signing key by id.

    A missing or unreadable key file is a ``MagnetiteError`` value the caller
    decides about (generate a fresh one, or fail the signed build).
    """
    path = _key_path(project_root, key_id)
    if not path.is_file():
        return Err(
            MagnetiteError(
                kind="signing_key_missing",
                message=f"no signing key {key_id!r} at {path}",
            )
        )
    try:
        loaded = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError, UnsupportedAlgorithm) as exc:
        _log.warning("cannot load signing key %s from %s: %s", key_id, path, exc)
        return Err(
            MagnetiteError(
                kind="signing_key_unreadable",
                message=f"cannot load signing key {key_id!r} from {path}: {exc}",
            )
        )
    if not isinstance(loaded, Ed25519PrivateKey):
        return Err(
            MagnetiteError(
                kind="signing_key_wrong_type",
                message=f"signing key {key_id!r} at {path} is not an ed25519 key",
            )
        )
    _log.debug("loaded signing key %s from %s", key_id, path)
    return Ok(LocalSigningKey(key_id, loaded))
