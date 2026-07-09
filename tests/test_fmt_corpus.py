"""Corpus/canon reconciliation gate.

The corpus under ``examples/`` and ``stdlib/`` is the de-facto house
style for source formatting; the normalizer (WO-05, ``regolith fmt``)
must reproduce it byte-for-byte, never fight it. This test iterates
every recognized source file in the corpus and asserts ``format`` is a
byte no-op -- so a future normalizer change that drifts from the
corpus fails CI immediately instead of silently rewriting checked-in
files the next time someone runs `regolith fmt`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from regolith import compiler

REPO_ROOT = Path(__file__).resolve().parent.parent


def _corpus_files() -> list[Path]:
    """Every corpus source file under a recognized extension, from both
    ``examples/`` (the acceptance corpus) and ``stdlib/`` (if it holds
    source files, not just manifests/metadata)."""
    extensions = {ext for ext, _lang in compiler.extensions()}
    files: list[Path] = []
    for root_name in ("examples", "stdlib"):
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lstrip(".") in extensions:
                files.append(path)
    return files


_CORPUS_FILES = _corpus_files()


@pytest.mark.parametrize(
    "path", _CORPUS_FILES, ids=[str(p.relative_to(REPO_ROOT)) for p in _CORPUS_FILES]
)
def test_fmt_is_a_noop_on_corpus_file(path: Path) -> None:
    """`regolith fmt` over a checked-in corpus file changes nothing --
    the canonical normalizer form and the corpus house style are one
    and the same, enforced so they can never silently drift apart."""
    original = path.read_text()
    formatted = compiler.format(original)
    assert formatted == original, (
        f"{path.relative_to(REPO_ROOT)} is not canonical: `regolith fmt` "
        "would rewrite it. Either the file has drifted from house style "
        "(reformat it) or the normalizer has drifted from the corpus "
        "(fix the normalizer)."
    )


def test_corpus_is_non_empty() -> None:
    """Sanity: the parametrized test above is not silently vacuous."""
    assert _CORPUS_FILES, "expected at least one corpus source file"
