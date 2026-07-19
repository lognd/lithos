"""Human sign-off over `DrawingModel` content (charter sec. 1.7,
AD-20/INV-28): a release drawing may carry a reviewer's signed
attestation over the sheet set's content address; regeneration that
changes the content changes the address, so re-signing the OLD
attestation over a NEW address is impossible by construction -- stale
approvals are unrepresentable.

Mirrors `regolith.harness.attest`'s envelope pattern (`Attestation`,
`LocalSigningKey`, ed25519) but signs a `DrawingModel` address rather
than an `Evidence` address -- the WO-21 machinery generalizes to any
addressable payload; this module is that generalization for sheets.
"""

from __future__ import annotations

import base64

import blake3
from cryptography.exceptions import InvalidSignature

from regolith._schema.models import (
    Attestation,
    DrawingModel,
    SignatureAlgorithm,
    SignatureAlgorithm1,
)
from regolith.logging_setup import get_logger
from regolith.magnetite.trust import LocalSigningKey, TrustKeySet

_log = get_logger(__name__)

_ADDRESS_DOMAIN = "regolith.backends.drawings.attest"


# frob:doc docs/modules/py-backends.md#drawings-attest
def drawing_content_address(model: DrawingModel) -> str:
    """A domain-tagged blake3 address over `model`'s canonical JSON.

    Any changed field (including a changed dimension's provenance)
    changes this address (the same anti-staleness property the Rust
    `DrawingModel::content_digest` documents) -- the message a sheet
    attestation signs.
    """
    canonical = model.model_dump_json(by_alias=True)
    tagged = _ADDRESS_DOMAIN + "\n" + canonical
    return "blake3:" + blake3.blake3(tagged.encode("utf-8")).hexdigest()


# frob:doc docs/modules/py-backends.md#drawings-attest
def sign_drawing(
    model: DrawingModel,
    key: LocalSigningKey,
    *,
    pack_name: str,
    pack_version: str,
) -> Attestation:
    """Sign `model`'s content address, returning an attestation envelope."""
    address = drawing_content_address(model)
    signature = key.sign(address.encode("ascii"))
    _log.debug("signed drawing %s with key %s", model.subject, key.key_id)
    return Attestation(
        model_id=model.subject,
        pack_name=pack_name,
        pack_version=pack_version,
        key_id=key.key_id,
        algorithm=SignatureAlgorithm(SignatureAlgorithm1.ed25519),
        signature_base64=base64.b64encode(signature).decode("ascii"),
    )


# frob:doc docs/modules/py-backends.md#drawings-attest
def verify_drawing(model: DrawingModel, att: Attestation, keys: TrustKeySet) -> bool:
    """True iff `att` verifies over `model`'s CURRENT content address.

    A regenerated drawing (any changed field) has a different address
    than the one the attestation signed, so this returns False without
    any special-case staleness check -- the invalidation is structural.
    """
    designation = keys.designation(att.key_id)
    if designation is None:
        _log.info("drawing attestation: untrusted key %s", att.key_id)
        return False
    address = drawing_content_address(model)
    try:
        designation.public_key().verify(
            base64.b64decode(att.signature_base64.encode("ascii")),
            address.encode("ascii"),
        )
    except InvalidSignature:
        _log.warning(
            "drawing attestation for %s by key %s FAILED verification "
            "(tamper or stale regeneration)",
            model.subject,
            att.key_id,
        )
        return False
    return True
