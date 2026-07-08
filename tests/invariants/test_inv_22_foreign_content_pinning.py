"""INV-22 Foreign-content pinning (regolith/13-invariants.md).

Ledger statement:
    **All foreign content -- imports, externs, registry records, format
    readers, toolchains -- is hash-pinned; drift is an error, never a
    silent rebuild input.**

Mechanism provided by: WO-16 (magnetite). The Python registry client and
vendor store content-address every fetched archive (blake3) and compare
against the demanded pin; a tampered archive served under a pinned hash
fails the comparison before anything consumes it (regolith/11 sec. 10.3).
This is the deliberate-violation fixture the ledger statement requires.
"""

from __future__ import annotations

import blake3
from regolith.magnetite import VendorStore, verify_archive


def _pin(data: bytes) -> str:
    return "blake3:" + blake3.blake3(data).hexdigest()


def test_inv_22_tampered_content_under_pin_is_drift() -> None:
    """Bytes that do not match their pin fail loudly (never a silent input)."""
    good = b"registry-record-bytes"
    pin = _pin(good)
    # Honest bytes verify.
    assert verify_archive(good, pin).is_ok
    # Tampered bytes under the SAME pin are the drift error, not a pass.
    tampered = verify_archive(b"poisoned", pin)
    assert tampered.is_err
    assert tampered.danger_err.kind == "hash_mismatch"


def test_inv_22_vendored_file_reverified_on_read(tmp_path) -> None:
    """An offline vendored archive is re-pinned on load; tampering is caught."""
    data = b"vendored-archive"
    pin = _pin(data)
    store = VendorStore(str(tmp_path))
    assert store.write(pin, data).is_ok
    assert store.read(pin).danger_ok == data
    # Corrupt the on-disk file: the pin comparison must halt the read.
    store.archive_file(pin).write_bytes(b"corrupted")
    assert store.read(pin).is_err
