"""Package-wide doc extraction: enumerate sources, walk each (WO-41).

One ``regolith.compiler.doc_extract`` FFI call per source file (the ONE
door stays per-file, matching ``debug_dump``'s shape); this module
enumerates the package's source files (mirroring the Rust session's
own file-discovery convention: files or roots, recognized extensions
only, lexicographic order for determinism, AD-6) and assembles the
per-file results into one :class:`~regolith.docgen.models.PackageDoc`.
"""

from __future__ import annotations

import json
from pathlib import Path

from typani.result import Err, Ok, Result

from regolith import compiler
from regolith.docgen.models import DeclDoc, PackageDoc, SourceDoc
from regolith.errors import DocError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


def _recognized_extensions() -> frozenset[str]:
    """The registry's extension set (ground rule 6): never hard-coded."""
    return frozenset(ext for ext, _lang in compiler.extensions())


def _discover_one(root: Path, exts: frozenset[str], out: list[Path]) -> None:
    """Recursively collect recognized source files under ``root`` into
    ``out`` (mirrors ``regolith_api::session::discover_one``)."""
    if root.is_file():
        if root.suffix.lstrip(".") in exts:
            out.append(root)
        return
    for child in sorted(root.iterdir()):
        _discover_one(child, exts, out)


# frob:doc docs/modules/py-docgen.md#extract
# frob:waive TEST001 reason="docgen helper, tested transitively via render tests"
def discover_sources(paths: tuple[str, ...]) -> Result[tuple[Path, ...], DocError]:
    """Every recognized source file under ``paths`` (files or roots),
    sorted for deterministic output (AD-6). ``Err`` when a root does not
    exist (an infrastructure failure, matching ``check``/``debug``)."""
    exts = _recognized_extensions()
    out: list[Path] = []
    for raw in paths:
        root = Path(raw)
        if not root.exists():
            _log.error("doc: no such path %s", root)
            return Err(DocError(kind="not_found", message=f"no such path: {root}"))
        _discover_one(root, exts, out)
    return Ok(tuple(sorted(set(out))))


# frob:doc docs/modules/py-docgen.md#extract
def extract_package(paths: tuple[str, ...]) -> Result[PackageDoc, DocError]:
    """Extract every recognized source file under ``paths`` into a
    :class:`PackageDoc`, in deterministic (sorted-path) order.

    A source file that fails to extract (unreadable) is an ``Err`` value
    -- a doc build never partially renders and calls it done.
    """
    discovered = discover_sources(paths)
    if discovered.is_err:
        return Err(discovered.danger_err)
    sources = discovered.danger_ok
    _log.info("doc: extracting %d source file(s)", len(sources))
    source_docs: list[SourceDoc] = []
    for path in sources:
        result = compiler.doc_extract(str(path))
        if result.is_err:
            failure = result.danger_err
            _log.error("doc: extraction failed for %s: %s", path, failure.message)
            return Err(DocError(kind="extract_failed", message=failure.message))
        payload = json.loads(result.danger_ok)
        decls_raw = payload.get("decls", [])
        source_docs.append(
            SourceDoc(
                path=str(path),
                decls=tuple(DeclDoc.model_validate(d) for d in decls_raw),
            )
        )
    return Ok(PackageDoc(sources=tuple(source_docs)))
