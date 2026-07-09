"""Tests for the pinned native-artifact store."""

from __future__ import annotations

import hashlib

from regolith.backends.artifacts import NativeArtifactStore


def test_put_resolve_roundtrip(tmp_path):
    store = NativeArtifactStore(str(tmp_path))
    digest = store.put(b"step bytes")
    resolved = store.resolve(digest)
    assert resolved.is_ok
    assert resolved.danger_ok == b"step bytes"


def test_put_is_idempotent(tmp_path):
    store = NativeArtifactStore(str(tmp_path))
    d1 = store.put(b"same bytes")
    d2 = store.put(b"same bytes")
    assert d1 == d2


def test_put_at_pins_caller_digest(tmp_path):
    store = NativeArtifactStore(str(tmp_path))
    digest = hashlib.sha256(b"pcb bytes").hexdigest()
    store.put_at(digest, b"pcb bytes")
    resolved = store.resolve(digest)
    assert resolved.is_ok
    assert resolved.danger_ok == b"pcb bytes"


def test_resolve_missing_is_err(tmp_path):
    store = NativeArtifactStore(str(tmp_path))
    resolved = store.resolve("deadbeef")
    assert resolved.is_err
    assert resolved.danger_err.kind == "native_artifact_not_found"


def test_put_verified_accepts_matching_bytes(tmp_path):
    store = NativeArtifactStore(str(tmp_path))
    digest = hashlib.sha256(b"honest pcb bytes").hexdigest()
    result = store.put_verified(digest, b"honest pcb bytes")
    assert result.is_ok
    resolved = store.resolve(digest)
    assert resolved.is_ok
    assert resolved.danger_ok == b"honest pcb bytes"


def test_put_verified_refuses_tampered_bytes(tmp_path):
    """A pinned digest that no longer matches on-disk bytes must refuse (H1)."""
    store = NativeArtifactStore(str(tmp_path))
    digest = hashlib.sha256(b"original pcb bytes").hexdigest()
    result = store.put_verified(digest, b"tampered pcb bytes")
    assert result.is_err
    assert result.danger_err.kind == "native_artifact_hash_mismatch"
    # Refused bytes must never land in the store.
    assert store.resolve(digest).is_err


def test_put_verified_accepts_matching_bytes_with_sha256_prefix(tmp_path):
    """elec's kicad_pcb_content_hash is always "sha256:"-prefixed (H1 regression).

    Before the fix, put_verified compared the prefixed digest against a
    bare recomputed hash and refused every clean elec board as
    tampered. It must accept a matching digest in either form, and
    store the bytes under the caller's ORIGINAL (prefixed) digest so
    resolve-by-IR-digest still works.
    """
    store = NativeArtifactStore(str(tmp_path))
    bare = hashlib.sha256(b"honest pcb bytes").hexdigest()
    digest = f"sha256:{bare}"
    result = store.put_verified(digest, b"honest pcb bytes")
    assert result.is_ok
    assert result.danger_ok == digest
    resolved = store.resolve(digest)
    assert resolved.is_ok
    assert resolved.danger_ok == b"honest pcb bytes"


def test_put_verified_refuses_tampered_bytes_with_sha256_prefix(tmp_path):
    """A tampered board must still be refused when the digest is prefixed."""
    store = NativeArtifactStore(str(tmp_path))
    bare = hashlib.sha256(b"original pcb bytes").hexdigest()
    digest = f"sha256:{bare}"
    result = store.put_verified(digest, b"tampered pcb bytes")
    assert result.is_err
    assert result.danger_err.kind == "native_artifact_hash_mismatch"
    assert store.resolve(digest).is_err
