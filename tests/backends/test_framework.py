"""Tests for the backend framework: OutputFile, and the no-compiler guard."""

from __future__ import annotations

import hashlib
from pathlib import Path

from regolith.backends.framework import OutputFile

_BACKEND_IMPL_MODULES = ("mech.py", "elec.py")
_FORBIDDEN = ("regolith.compiler", "regolith._core", "regolith import compiler")


def test_output_file_of_computes_sha256():
    out = OutputFile.of("a/b.txt", b"hello")
    assert out.sha256 == hashlib.sha256(b"hello").hexdigest()
    assert out.relpath == "a/b.txt"


def test_output_file_write_under(tmp_path):
    out = OutputFile.of("sub/dir/file.bin", b"\x00\x01")
    out.write_under(tmp_path)
    written = tmp_path / "sub" / "dir" / "file.bin"
    assert written.read_bytes() == b"\x00\x01"


def test_backend_implementations_never_import_the_compiler():
    """Enforced-by-construction (regolith/07 sec. 6): a Backend implementation
    consumes only BackendInputs, never the compiler/CST directly."""
    backends_dir = (
        Path(__file__).resolve().parents[2] / "python" / "regolith" / "backends"
    )
    for name in _BACKEND_IMPL_MODULES:
        text = (backends_dir / name).read_text()
        for forbidden in _FORBIDDEN:
            assert forbidden not in text, f"{name} imports {forbidden!r}"
