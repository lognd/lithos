"""Attestation primitives: sign/verify arms, content addressing, key mgmt.

Unit-level coverage of `harness/attest.py` and the quarry local signing-key
extension (WO-21). The three-valued verify is exercised on every arm --
unsigned, unknown key, bad signature, algorithm mismatch, and valid -- so
the totality argument behind INV-28 is proven at the leaf, not just
end-to-end.
"""

from __future__ import annotations

from regolith._schema.models import (
    SignatureAlgorithm,
    SignatureAlgorithm1,
)
from regolith.harness.attest import (
    Invalid,
    Unsigned,
    Valid,
    conferred_tier,
    evidence_content_address,
    sign_evidence,
    verify_attestation,
)
from regolith.harness.evidence import build_evidence
from regolith.quarry import (
    KeyDesignation,
    TrustKeySet,
    TrustTier,
    generate_signing_key,
    load_signing_key,
)
from regolith.quarry.trust import LocalSigningKey


def _evidence(value: float = 50.0):
    """A deterministic discharged evidence value for signing tests."""
    return build_evidence(
        model_id="test.stress",
        claim_kind="stress",
        sense_upper=True,
        value=value,
        eps=0.0,
        limit=100.0,
        coverage=1.0,
        cost=1,
        in_domain=True,
        deterministic=True,
        registry_version="model-registry@attest",
        inputs_digest="digest",
    )


def _key(tmp_path, key_id: str = "project-1") -> LocalSigningKey:
    generated = generate_signing_key(str(tmp_path), key_id)
    assert generated.is_ok
    return generated.danger_ok


def _designating(key: LocalSigningKey, tier: TrustTier) -> TrustKeySet:
    return TrustKeySet(
        designations=(
            KeyDesignation(
                key_id=key.key_id,
                public_key_base64=key.public_key_base64(),
                confers=tier,
            ),
        )
    )


# --- content addressing (envelope) ---------------------------------------


def test_content_address_is_stable_and_tamper_sensitive() -> None:
    """Same payload -> same address; any changed byte -> a different one."""
    ev = _evidence()
    assert evidence_content_address(ev) == evidence_content_address(ev)
    tampered = ev.model_copy(update={"cost": ev.cost + 1})
    assert evidence_content_address(ev) != evidence_content_address(tampered)


# --- verify arms ----------------------------------------------------------


def test_verify_unsigned_is_community_not_error() -> None:
    """Absence of a signature is the community tier, never an error."""
    status = verify_attestation(_evidence(), None, TrustKeySet())
    assert isinstance(status, Unsigned)
    assert conferred_tier(status) == TrustTier.COMMUNITY


def test_verify_valid_confers_designated_tier(tmp_path) -> None:
    """A trusted signature over the exact bytes earns the designated tier."""
    key = _key(tmp_path)
    ev = _evidence()
    att = sign_evidence(ev, key, pack_name="feldspar", pack_version="0.1.0")
    status = verify_attestation(ev, att, _designating(key, TrustTier.TESTED))
    assert isinstance(status, Valid)
    assert status.tier == TrustTier.TESTED


def test_verify_unknown_key_is_invalid(tmp_path) -> None:
    """A signature by a key absent from the trust set is Invalid(unknown_key)."""
    key = _key(tmp_path)
    ev = _evidence()
    att = sign_evidence(ev, key, pack_name="feldspar", pack_version="0.1.0")
    status = verify_attestation(ev, att, TrustKeySet())
    assert isinstance(status, Invalid)
    assert status.reason == "unknown_key"
    assert conferred_tier(status) is None


def test_verify_bad_signature_is_invalid(tmp_path) -> None:
    """A signature that does not cover the evidence bytes is Invalid."""
    key = _key(tmp_path)
    ev = _evidence()
    att = sign_evidence(ev, key, pack_name="feldspar", pack_version="0.1.0")
    tampered = ev.model_copy(update={"cost": ev.cost + 1})
    status = verify_attestation(tampered, att, _designating(key, TrustTier.TESTED))
    assert isinstance(status, Invalid)
    assert status.reason == "bad_signature"


def test_verify_algorithm_mismatch_is_invalid(tmp_path) -> None:
    """A non-ed25519 algorithm is refused before any signature check."""
    key = _key(tmp_path)
    ev = _evidence()
    att = sign_evidence(ev, key, pack_name="feldspar", pack_version="0.1.0")
    # Bypass validation to inject an unsupported algorithm (the schema enum
    # is closed, so this is the only way to reach the mismatch arm).
    foreign = att.model_copy(
        update={
            "algorithm": SignatureAlgorithm.model_construct(root="rsa"),  # type: ignore[arg-type]
        }
    )
    status = verify_attestation(ev, foreign, _designating(key, TrustTier.TESTED))
    assert isinstance(status, Invalid)
    assert status.reason == "algorithm_mismatch"


def test_sign_evidence_stamps_attribution(tmp_path) -> None:
    """The attestation carries the model/pack/key identity for verification."""
    key = _key(tmp_path)
    ev = _evidence()
    att = sign_evidence(ev, key, pack_name="feldspar", pack_version="0.1.0")
    assert att.model_id == ev.model_id
    assert att.pack_name == "feldspar"
    assert att.pack_version == "0.1.0"
    assert att.key_id == key.key_id
    assert att.algorithm.root == SignatureAlgorithm1.ed25519


# --- local signing-key management ----------------------------------------


def test_generate_then_load_round_trip(tmp_path) -> None:
    """A generated key reloads and signs identically (same public key)."""
    key = _key(tmp_path, "project-1")
    reloaded = load_signing_key(str(tmp_path), "project-1")
    assert reloaded.is_ok
    assert reloaded.danger_ok.public_key_base64() == key.public_key_base64()


def test_generate_refuses_to_clobber(tmp_path) -> None:
    """Generating over an existing key id is a value error, not an overwrite."""
    _key(tmp_path, "project-1")
    again = generate_signing_key(str(tmp_path), "project-1")
    assert again.is_err
    assert again.danger_err.kind == "signing_key_exists"


def test_load_missing_key_is_error(tmp_path) -> None:
    """Loading an absent key is a QuarryError value, never an exception."""
    result = load_signing_key(str(tmp_path), "nope")
    assert result.is_err
    assert result.danger_err.kind == "signing_key_missing"


def test_signing_key_repr_redacts_private_material(tmp_path) -> None:
    """The key's repr never leaks private material (log/traceback safety)."""
    key = _key(tmp_path)
    assert "redacted" in repr(key)
    assert key.key_id in repr(key)
