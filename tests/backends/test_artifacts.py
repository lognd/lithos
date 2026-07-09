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
