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
