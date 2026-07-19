"""Evidence attestation: sign at discharge, verify at consumption (INV-28).

The signing half of INV-14 extended to computed evidence
(``20-solver-abstraction.md`` D-E/D-G). A solver signs the evidence it
produces over the evidence's AD-18 content address -- an ENVELOPE, never
a hash input, so a signed and an unsigned copy of the same evidence key
identically. Verification is a CONSUMER-side act against the local magnetite
:class:`~regolith.magnetite.TrustKeySet`: signing carries trust, storage does
not (regolith/11 sec. 10.6 rule 4).

``verify_attestation`` is TOTAL and three-valued -- ``Valid(tier)`` /
``Unsigned`` / ``Invalid(reason)``. A present-but-invalid signature is
INDETERMINATE with its own diagnostic family (``ATTESTATION_INVALID_ID``):
never violated (the result might be fine; we cannot trust it), never
silently accepted. Absence of a signature is not an error -- it is the
``community`` tier. Every fallible primitive returns a value; exceptions
stay for programmer bugs (house rule / AD-7).
"""

from __future__ import annotations

import base64
import json
from typing import Annotated, Literal

import blake3
from cryptography.exceptions import InvalidSignature
from pydantic import BaseModel, ConfigDict, Field

from regolith._schema.models import (
    Attestation,
    Evidence,
    SignatureAlgorithm,
    SignatureAlgorithm1,
)
from regolith.logging_setup import get_logger
from regolith.magnetite.trust import LocalSigningKey, TrustKeySet, TrustTier

_log = get_logger(__name__)

# Domain tag prefixing the signed content address so an attestation
# signature can never be replayed against any other content address in
# the system (mirrors the cache's domain-tagged addressing, AD-18).
_ADDRESS_DOMAIN = "regolith.harness.evidence_attestation"

# The synthetic diagnostic marker for a present-but-invalid attestation:
# an honest, greppable INDETERMINATE family (the `harness.adapter_error`
# precedent), never a pass, never a violation (D-E).
# frob:doc docs/modules/py-harness.md#attest
ATTESTATION_INVALID_ID = "harness.attestation_invalid"

# Why a present signature failed verification (design sec. 4).
InvalidReason = Literal["bad_signature", "unknown_key", "algorithm_mismatch"]


# frob:doc docs/modules/py-harness.md#attest
class Valid(BaseModel):
    """A verified attestation: the evidence earns ``tier`` from a trusted key."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["valid"] = "valid"
    tier: TrustTier


# frob:doc docs/modules/py-harness.md#attest
class Unsigned(BaseModel):
    """No attestation present -- the honest ``community`` tier, not an error."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["unsigned"] = "unsigned"


# frob:doc docs/modules/py-harness.md#attest
class Invalid(BaseModel):
    """A present-but-unverifiable attestation: INDETERMINATE, never a verdict."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["invalid"] = "invalid"
    reason: InvalidReason
    detail: str


# The total three-valued attestation outcome (discriminated on ``kind``):
# every verify path lands in exactly one arm (D-G totality argument).
AttestationStatus = Annotated[Valid | Unsigned | Invalid, Field(discriminator="kind")]


# frob:doc docs/modules/py-harness.md#attest
def evidence_content_address(evidence: Evidence) -> str:
    """Domain-tagged blake3 over the FULL evidence payload (the signed message).

    This is the message an attestation signs. Because it hashes every
    evidence field, tampering ANY byte flips it (the tamper fixture);
    because it is a pure function of the payload, attaching or detaching
    an attestation cannot perturb it (the envelope property). Canonical
    JSON (sorted keys, no whitespace) hashed with blake3 -- deterministic
    across platforms, matching the cache's addressing (AD-18/INV-10).
    """
    canonical = json.dumps(
        {"domain": _ADDRESS_DOMAIN, "evidence": evidence.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "blake3:" + blake3.blake3(canonical.encode("ascii")).hexdigest()


# frob:doc docs/modules/py-harness.md#attest
def sign_evidence(
    evidence: Evidence,
    key: LocalSigningKey,
    *,
    pack_name: str,
    pack_version: str,
) -> Attestation:
    """Sign ``evidence``'s content address, returning an attestation envelope.

    The signature is over :func:`evidence_content_address` (never the
    evidence bytes directly and never a hash input), so re-signing on key
    rotation never invalidates a cache (D-E). Attribution metadata (model
    id, pack identity, key id) travels with the signature for verification.
    """
    address = evidence_content_address(evidence)
    signature = key.sign(address.encode("ascii"))
    _log.debug(
        "signed evidence for model %s with key %s (pack %s@%s)",
        evidence.model_id,
        key.key_id,
        pack_name,
        pack_version,
    )
    return Attestation(
        model_id=evidence.model_id,
        pack_name=pack_name,
        pack_version=pack_version,
        key_id=key.key_id,
        algorithm=SignatureAlgorithm(SignatureAlgorithm1.ed25519),
        signature_base64=base64.b64encode(signature).decode("ascii"),
    )


# frob:doc docs/modules/py-harness.md#attest
def verify_attestation(
    evidence: Evidence,
    att: Attestation | None,
    keys: TrustKeySet,
) -> AttestationStatus:
    """Verify ``att`` over ``evidence`` against the consumer key set (total).

    Absent -> ``Unsigned`` (community, not an error). Unknown key ->
    ``Invalid(unknown_key)``. Non-ed25519 -> ``Invalid(algorithm_mismatch)``.
    Signature failure -> ``Invalid(bad_signature)``. Success ->
    ``Valid(designation.confers)``. Every outcome is logged; key material
    never is.
    """
    if att is None:
        _log.debug("evidence for model %s is unsigned (community)", evidence.model_id)
        return Unsigned()

    if att.algorithm.root != SignatureAlgorithm1.ed25519:
        _log.info(
            "attestation for %s uses unsupported algorithm %s",
            evidence.model_id,
            att.algorithm.root,
        )
        return Invalid(
            reason="algorithm_mismatch",
            detail=f"unsupported signature algorithm {att.algorithm.root!r}",
        )

    designation = keys.designation(att.key_id)
    if designation is None:
        _log.info(
            "attestation for %s signed by untrusted key %s",
            evidence.model_id,
            att.key_id,
        )
        return Invalid(
            reason="unknown_key",
            detail=f"key {att.key_id!r} is not designated in the trust key set",
        )

    address = evidence_content_address(evidence)
    try:
        designation.public_key().verify(
            base64.b64decode(att.signature_base64.encode("ascii")),
            address.encode("ascii"),
        )
    except InvalidSignature:
        _log.warning(
            "attestation for %s by key %s FAILED verification (tamper?)",
            evidence.model_id,
            att.key_id,
        )
        return Invalid(
            reason="bad_signature",
            detail=f"signature by {att.key_id!r} does not verify over the evidence",
        )
    _log.debug(
        "attestation for %s verified: key %s confers %s",
        evidence.model_id,
        att.key_id,
        designation.confers.name,
    )
    return Valid(tier=designation.confers)


# frob:doc docs/modules/py-harness.md#attest
def conferred_tier(status: AttestationStatus) -> TrustTier | None:
    """The tier an attestation status confers: ``None`` iff indeterminate.

    ``Valid`` confers its verified tier; ``Unsigned`` confers ``community``
    (the honest floor); ``Invalid`` confers NOTHING -- the evidence is
    indeterminate, so no trust floor can be satisfied by it (D-E).
    """
    if isinstance(status, Valid):
        return status.tier
    if isinstance(status, Unsigned):
        return TrustTier.COMMUNITY
    return None
