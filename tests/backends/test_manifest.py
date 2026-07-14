"""Tests for the signed ship manifest."""

from __future__ import annotations

from regolith.backends.framework import OutputFile
from regolith.backends.manifest import (
    build_manifest,
    release_gate_refuses_debug_evidence,
    sign_manifest,
    verify_file_hashes,
    verify_manifest,
)
from regolith.magnetite import (
    KeyDesignation,
    TrustKeySet,
    TrustTier,
    generate_signing_key,
)


def _key(tmp_path, key_id: str = "ship-1"):
    generated = generate_signing_key(str(tmp_path), key_id)
    assert generated.is_ok
    return generated.danger_ok


def _designating(key, tier=TrustTier.COMMUNITY) -> TrustKeySet:
    return TrustKeySet(
        designations=(
            KeyDesignation(
                key_id=key.key_id,
                public_key_base64=key.public_key_base64(),
                confers=tier,
            ),
        )
    )


def _manifest(files=()):
    return build_manifest(
        design_hash="blake3:aaaa",
        lockfile_hash="blake3:bbbb",
        evidence_rollup=(("subject.a", "discharged"),),
        files=files,
    )


def test_build_manifest_sorts_files_and_rollup():
    files = (OutputFile.of("b.txt", b"2"), OutputFile.of("a.txt", b"1"))
    manifest = build_manifest(
        design_hash="blake3:x",
        lockfile_hash="blake3:y",
        evidence_rollup=(("z", "discharged"), ("a", "indeterminate")),
        files=files,
    )
    assert [f.relpath for f in manifest.files] == ["a.txt", "b.txt"]
    assert manifest.evidence_rollup[0] == ("a", "indeterminate")


def test_sign_and_verify_manifest_roundtrip(tmp_path):
    key = _key(tmp_path)
    manifest = sign_manifest(_manifest(), key)
    assert manifest.signature is not None
    keys = _designating(key)
    verified = verify_manifest(manifest, keys)
    assert verified.is_ok


def test_build_manifest_default_profile_is_release():
    assert _manifest().profile == "release"


def test_release_gate_accepts_release_profile():
    manifest = build_manifest(
        design_hash="blake3:x",
        lockfile_hash="blake3:y",
        evidence_rollup=(),
        files=(),
        profile="release",
    )
    result = release_gate_refuses_debug_evidence(manifest)
    assert result.is_ok


def test_release_gate_refuses_debug_profile():
    manifest = build_manifest(
        design_hash="blake3:x",
        lockfile_hash="blake3:y",
        evidence_rollup=(),
        files=(),
        profile="debug",
    )
    result = release_gate_refuses_debug_evidence(manifest)
    assert result.is_err
    assert result.danger_err.kind == "debug_not_release_evidence"


def test_verify_unsigned_manifest_is_err():
    verified = verify_manifest(_manifest(), TrustKeySet())
    assert verified.is_err
    assert verified.danger_err.kind == "unsigned"


def test_verify_manifest_unknown_key_is_err(tmp_path):
    key = _key(tmp_path)
    manifest = sign_manifest(_manifest(), key)
    verified = verify_manifest(manifest, TrustKeySet())
    assert verified.is_err
    assert verified.danger_err.kind == "unknown_key"


def test_verify_manifest_tamper_is_bad_signature(tmp_path):
    key = _key(tmp_path)
    manifest = sign_manifest(_manifest(), key)
    tampered = manifest.model_copy(update={"design_hash": "blake3:tampered"})
    keys = _designating(key)
    verified = verify_manifest(tampered, keys)
    assert verified.is_err
    assert verified.danger_err.kind == "bad_signature"


def test_verify_file_hashes_ok():
    files = (OutputFile.of("a.txt", b"1"),)
    manifest = _manifest(files)
    assert verify_file_hashes(manifest, files).is_ok


def test_verify_file_hashes_detects_tamper():
    files = (OutputFile.of("a.txt", b"1"),)
    manifest = _manifest(files)
    tampered_files = (OutputFile.of("a.txt", b"TAMPERED"),)
    result = verify_file_hashes(manifest, tampered_files)
    assert result.is_err
    assert result.danger_err.kind == "hash_mismatch"


def test_verify_file_hashes_detects_missing_and_extra():
    files = (OutputFile.of("a.txt", b"1"),)
    manifest = _manifest(files)
    result = verify_file_hashes(manifest, ())
    assert result.is_err
    assert result.danger_err.kind == "file_set_mismatch"
