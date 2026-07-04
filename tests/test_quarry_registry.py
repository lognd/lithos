"""Quarry/lodestone: sparse index, content-hash pinning, trust, vendoring.

Uses an in-memory ``httpx.MockTransport`` (never the network, per the
sandbox rule): a fake index + archive store served by hash, driving the
INV-22 pinning path, yank semantics, INV-14 trust, and ``quarry vendor``.
"""

from __future__ import annotations

import json

import blake3
import httpx
from regolith.quarry import (
    KeySet,
    Registry,
    RegistryClient,
    Signature,
    Sources,
    TrustTier,
    VendorPin,
    VendorStore,
    parse_index,
    select_version,
    vendor,
    verify_archive,
    verify_trust,
)
from regolith.quarry.index import latest_version

# --- fake registry over MockTransport -------------------------------------


def _hash(data: bytes) -> str:
    return "blake3:" + blake3.blake3(data).hexdigest()


def _mock_registry(
    package: str,
    archives: dict[str, bytes],
    index_lines: list[dict[str, object]],
    *,
    tamper: bool = False,
) -> RegistryClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == f"/index/{package}":
            body = "\n".join(json.dumps(line) for line in index_lines)
            return httpx.Response(200, text=body)
        if path.startswith("/archive/"):
            digest = path.rsplit("/", 1)[1]
            for h, data in archives.items():
                if h.split(":", 1)[1] == digest:
                    served = b"TAMPERED" if tamper else data
                    return httpx.Response(200, content=served)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    registry = Registry(
        name="lodestone",
        index_url="https://reg.test/index",
        archive_url="https://reg.test/archive",
    )
    return RegistryClient(registry, client)


def test_sparse_index_fetch_and_pinned_archive() -> None:
    data = b"archive-bytes-v1"
    h = _hash(data)
    client = _mock_registry(
        "std.materials",
        {h: data},
        [
            {
                "name": "std.materials",
                "version": "1.0.0",
                "manifest_digest": "blake3:aa",
                "archive_hash": h,
            }
        ],
    )
    result = client.fetch_pinned("std.materials", "1.0.0")
    assert result.is_ok
    entry, bytes_ = result.danger_ok
    assert entry.version == "1.0.0"
    assert bytes_ == data


def test_content_hash_mismatch_is_loud_drift() -> None:
    data = b"archive-bytes-v1"
    h = _hash(data)
    client = _mock_registry(
        "p",
        {h: data},
        [
            {
                "name": "p",
                "version": "1.0.0",
                "manifest_digest": "blake3:aa",
                "archive_hash": h,
            }
        ],
        tamper=True,  # server returns different bytes under the pinned hash
    )
    result = client.fetch_archive(h)
    assert result.is_err
    assert result.danger_err.kind == "hash_mismatch"  # INV-22


def test_verify_archive_roundtrip() -> None:
    data = b"hello"
    assert verify_archive(data, _hash(data)).is_ok
    assert verify_archive(b"other", _hash(data)).is_err


# --- yank semantics -------------------------------------------------------


def test_yank_hides_from_latest_but_pins_still_fetch() -> None:
    lines = (
        '{"name":"p","version":"1.0.0","manifest_digest":"blake3:a","archive_hash":"blake3:b"}\n'
        '{"name":"p","version":"1.1.0","manifest_digest":"blake3:c","archive_hash":"blake3:d","yanked":true}'
    )
    entries = parse_index(lines).danger_ok
    # latest for new resolution skips the yanked 1.1.0
    assert latest_version(entries).danger_ok.version == "1.0.0"
    # exact pin still resolves the yanked version (sec. 10.5)
    yanked = select_version(entries, "1.1.0").danger_ok
    assert yanked.yanked


# --- trust / signing (INV-14) ---------------------------------------------


def test_hosting_confers_no_trust_signature_does() -> None:
    content = "blake3:record1"
    keyset = KeySet(ceilings=(("vendor.ti", TrustTier.CERTIFIED),))
    # unsigned -> community floor
    assert verify_trust(content, (), keyset) == TrustTier.COMMUNITY
    # signed by a trusted vendor key -> certified
    sig = Signature(key_id="vendor.ti", grants=TrustTier.CERTIFIED, over_hash=content)
    assert verify_trust(content, (sig,), keyset) == TrustTier.CERTIFIED


def test_untrusted_key_and_wrong_bytes_do_not_upgrade() -> None:
    content = "blake3:record1"
    keyset = KeySet(ceilings=(("vendor.ti", TrustTier.CERTIFIED),))
    # unknown signing key -> ignored
    stranger = Signature(key_id="who?", grants=TrustTier.CERTIFIED, over_hash=content)
    assert verify_trust(content, (stranger,), keyset) == TrustTier.COMMUNITY
    # signature over different bytes -> ignored (INV-22 binding)
    off = Signature(
        key_id="vendor.ti", grants=TrustTier.CERTIFIED, over_hash="blake3:x"
    )
    assert verify_trust(content, (off,), keyset) == TrustTier.COMMUNITY


def test_trust_tiers_compare_totally() -> None:
    assert TrustTier.CERTIFIED.meets(TrustTier.TESTED)
    assert not TrustTier.COMMUNITY.meets(TrustTier.TESTED)


# --- vendoring ------------------------------------------------------------


def test_vendor_copies_verified_archives_offline(tmp_path) -> None:
    data = b"archive-bytes-v1"
    h = _hash(data)
    client = _mock_registry(
        "p",
        {h: data},
        [
            {
                "name": "p",
                "version": "1.0.0",
                "manifest_digest": "blake3:a",
                "archive_hash": h,
            }
        ],
    )
    result = vendor(
        (VendorPin(package="p", version="1.0.0", archive_hash=h),),
        client=client,
        project_root=str(tmp_path),
    )
    assert result.is_ok
    store = result.danger_ok
    # offline read re-verifies the hash and returns the bytes
    assert store.read(h).danger_ok == data


def test_vendor_store_rejects_tampered_file(tmp_path) -> None:
    data = b"good"
    h = _hash(data)
    store = VendorStore(str(tmp_path))
    store.write(h, data)
    # corrupt the vendored file on disk
    store.archive_file(h).write_bytes(b"evil")
    assert store.read(h).is_err  # INV-22 re-verification catches it


def test_sources_route_longest_prefix_and_default() -> None:
    reg_pub = Registry(name="lodestone", index_url="i", archive_url="a")
    reg_corp = Registry(name="corp", index_url="ci", archive_url="ca")
    sources = Sources(
        registries=(reg_pub, reg_corp),
        routes=(("acme", "corp"),),
        default="lodestone",
    )
    assert sources.route("acme.widgets").danger_ok.name == "corp"
    assert sources.route("std.materials").danger_ok.name == "lodestone"
