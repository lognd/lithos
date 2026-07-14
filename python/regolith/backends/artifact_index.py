"""The universal artifact index (WO-130, D244/AD-41, charter 42 secs. 6-7).

Every file `ship`/`preview`/`build` emits is described here, WITHOUT the
consumer needing to know what family it belongs to: `family`, `kind`,
`relpath`, `content_hash`, `bytes`, `media_type`, a CLOSED-vocabulary
`viewer` hint, and the `source_refs` that produced it. This is the
structural fix for F145 (graphite rendered 5 of 8 families and previewed
only `Edge.Cuts` of a 14-layer fab set because IT carried a hardcoded
family list): a viewer that reads THIS index instead never needs one.

Two-step classification per file: the file's top-level path segment
resolves its `family` (`family_of`), and the family's registered default
viewer (`regolith.backends.registry.ArtifactFamilyRegistry`, one home per
AD-41 ruling 2) is the STARTING viewer hint; `classify` may narrow both
`kind` and `viewer` for a specific file within that family (e.g. a gerber
layer under `boards/gerbers/` keeps `boards`' own `gerber` default, but
`boards/board_status.json` narrows to `json`) -- narrowing is never a
silent gap because the family default always resolves first, and an
unregistered family is a loud `Err`, never an omitted row.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.backends.framework import OutputFile
from regolith.backends.registry import (
    ArtifactFamilyRegistry,
    Viewer,
    default_artifact_family_registry,
)
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

#: The package-root side files package.py emits (WO-99) plus this WO's own
#: index file -- every one of these has no family directory of its own, so
#: `family_of` resolves them to the `"ledgers"` family (registry.py).
LEDGER_FILENAMES = frozenset(
    {
        "manifest.json",
        "index.md",
        "gate_summary.json",
        "parity_ledger.json",
        "acceptance_ledger.json",
    }
)

#: The relpath this index itself ships under, sibling to `manifest.json`
#: (WO-130 deliverable 5: `regolith artifacts` reads this file from the
#: SHIPPED package, never re-running a build).
INDEX_FILENAME = "artifact_index.json"


class ArtifactRow(BaseModel):
    """One emitted file, described well enough to render without knowing
    what family it is (charter 42 sec. 6)."""

    model_config = ConfigDict(frozen=True)

    family: str
    kind: str
    relpath: str
    content_hash: str
    bytes: int
    media_type: str
    viewer: Viewer
    source_refs: tuple[str, ...] = ()


class ArtifactIndex(BaseModel):
    """One package's whole artifact index (WO-130 deliverable 1), rows
    sorted by `relpath` (determinism, AD-6)."""

    model_config = ConfigDict(frozen=True)

    project: str
    rows: tuple[ArtifactRow, ...] = ()


def family_of(relpath: str) -> str:
    """The family a path resolves to: its top-level directory segment, or
    ``"ledgers"`` for a root-level side file (no directory, or one of the
    named `LEDGER_FILENAMES`/`INDEX_FILENAME`)."""
    if relpath in LEDGER_FILENAMES or relpath == INDEX_FILENAME:
        return "ledgers"
    head, sep, _ = relpath.partition("/")
    return head if sep else "ledgers"


# Extension -> (kind, viewer override or None [use the family default],
# media type). Deliberately conservative: an extension not in the CLOSED
# viewer vocabulary (DXF, PDF, HTML, s-expression `.kicad_pcb`, Excellon
# drill, the JSON-bodied `.gbrjob`) resolves to the honest fallback ladder
# member closest to true (WO-130 deliverable 3) rather than a fabricated
# richer viewer.
_EXT_CLASSIFY: dict[str, tuple[str, Viewer | None, str]] = {
    ".svg": ("svg", "svg", "image/svg+xml"),
    ".dxf": ("dxf", "text", "image/vnd.dxf"),
    ".pdf": ("pdf", "binary", "application/pdf"),
    ".json": ("json", "json", "application/json"),
    ".md": ("markdown", "markdown", "text/markdown"),
    ".csv": ("csv", "table", "text/csv"),
    ".glb": ("glb", "glb", "model/gltf-binary"),
    ".html": ("html", "text", "text/html"),
    ".step": ("step", "binary", "model/step"),
    ".kicad_pcb": ("kicad_pcb", "text", "text/plain"),
    ".v": ("hdl_source", "text", "text/plain"),
    ".sv": ("hdl_source", "text", "text/plain"),
    ".vh": ("hdl_source", "text", "text/plain"),
    ".elf": ("elf", "binary", "application/x-elf"),
    ".bin": ("firmware_image", "binary", "application/octet-stream"),
    ".h": ("source", "text", "text/plain"),
    ".c": ("source", "text", "text/plain"),
    ".txt": ("text", "text", "text/plain"),
    ".sigrok-cli": ("capture_config", "text", "text/plain"),
}

#: Gerber X2 layer suffixes (WO-124's `GERBER_LAYER_FILES`, this module
#: does not import that list to avoid a boards<->artifact_index cycle --
#: the extension set is stable Gerber X2/RS-274X convention).
_GERBER_LAYER_EXT = frozenset(
    {".gtl", ".gbl", ".gts", ".gbs", ".gtp", ".gbp", ".gto", ".gbo", ".gm1", ".gbr"}
)


def classify(relpath: str, family: str) -> tuple[str, Viewer | None, str]:
    """``(kind, viewer_override, media_type)`` for one file.

    ``viewer_override`` is ``None`` when the family's own registered
    default viewer already describes this file honestly (the common
    case) -- the caller applies the family default in that case, never a
    fabricated richer hint.
    """
    name = relpath.rsplit("/", 1)[-1]
    _, ext = os.path.splitext(name)
    ext = ext.lower()

    if family == "boards" and "/gerbers/" in f"/{relpath}":
        if ext == ".gbrjob":
            # The job file is JSON-bodied (Gerber X2 `.gbrjob` convention)
            # despite its extension -- an honest `json` hint, not `gerber`.
            return ("job_file", "json", "application/json")
        if ext in _GERBER_LAYER_EXT:
            stem = name.removeprefix("board-")
            stem = stem[: -len(ext)] if ext else stem
            return (f"gerber_layer.{stem}", None, "application/vnd.gerber")
    if family == "boards" and "/drill/" in f"/{relpath}":
        stem = name.removeprefix("board-")
        stem = stem.rsplit(".", 1)[0] if "." in stem else stem
        return (f"drill.{stem}", None, "application/vnd.excellon-drill")

    mapped = _EXT_CLASSIFY.get(ext)
    if mapped is not None:
        return mapped
    _log.debug(
        "artifact_index: classify: no extension mapping for %r (family %r) -- "
        "honest binary fallback",
        relpath,
        family,
    )
    return ("file", "binary", "application/octet-stream")


def build_index(
    project: str,
    files: Sequence[OutputFile],
    *,
    family_registry: ArtifactFamilyRegistry | None = None,
    source_refs: Mapping[str, tuple[str, ...]] | None = None,
) -> Result[ArtifactIndex, BackendError]:
    """Build the index over one package's already-emitted `files`.

    ``family_registry`` defaults to the built-in twelve-family set
    (:func:`regolith.backends.registry.default_artifact_family_registry`).
    A file whose family is NOT registered there is a loud `Err`
    (``artifact_family_unregistered``) -- never a silently-dropped row
    (charter 42 sec. 6: "forgetting [a hint] is a registration error, not
    a silent gap"). ``source_refs`` is keyed by `relpath`, defaulting to
    empty (a caller with no provenance for a file leaves that field at
    its honest default, never an invented value).
    """
    registry = (
        family_registry
        if family_registry is not None
        else default_artifact_family_registry()
    )
    refs = source_refs or {}
    rows: list[ArtifactRow] = []
    for f in sorted(files, key=lambda x: x.relpath):
        family = family_of(f.relpath)
        registration = registry.get(family)
        if registration is None:
            _log.error(
                "artifact index: family %r (from %s) has no registered viewer "
                "hint -- refusing to build a lossy index",
                family,
                f.relpath,
            )
            return Err(
                BackendError(
                    kind="artifact_family_unregistered",
                    message=(
                        f"family {family!r} (file {f.relpath!r}) has no viewer "
                        "hint registered in the AD-36 emission registry -- "
                        "register it beside the family's producer/renderer "
                        "(charter 42 sec. 6); a family without a hint is a "
                        "registration error, never a silent gap"
                    ),
                )
            )
        kind, viewer_override, media_type = classify(f.relpath, family)
        viewer = viewer_override if viewer_override is not None else registration.viewer
        rows.append(
            ArtifactRow(
                family=family,
                kind=kind,
                relpath=f.relpath,
                content_hash=f.sha256,
                bytes=len(f.content),
                media_type=media_type,
                viewer=viewer,
                source_refs=tuple(refs.get(f.relpath, ())),
            )
        )
    _log.info("artifact index: built %d row(s) for %r", len(rows), project)
    return Ok(ArtifactIndex(project=project, rows=tuple(rows)))


def index_bytes(index: ArtifactIndex) -> bytes:
    """Canonical deterministic JSON bytes for `index` (sorted keys,
    ASCII, no whitespace drift) -- what `artifact_index.json` ships and
    what `regolith artifacts --json` prints."""
    return index.model_dump_json(indent=2).encode("ascii") + b"\n"


def check_index_consistency(
    index: ArtifactIndex,
    files: Sequence[OutputFile],
    *,
    family_registry: ArtifactFamilyRegistry | None = None,
) -> Result[None, BackendError]:
    """WO-130 deliverable 6: the health consistency check.

    Every emitted file must appear in the index; every index row must
    resolve to an emitted file; every row's family must carry a
    registered viewer hint. Any one of these failing is drift -- an
    `Err`, never a warning.
    """
    registry = (
        family_registry
        if family_registry is not None
        else default_artifact_family_registry()
    )
    file_paths = {f.relpath for f in files}
    index_paths = {r.relpath for r in index.rows}
    missing_from_index = sorted(file_paths - index_paths)
    unresolved_rows = sorted(index_paths - file_paths)
    known_families = set(registry.families())
    hintless_families = sorted({r.family for r in index.rows} - known_families)
    if missing_from_index or unresolved_rows or hintless_families:
        _log.error(
            "artifact index drift: missing_from_index=%s unresolved_rows=%s "
            "hintless_families=%s",
            missing_from_index,
            unresolved_rows,
            hintless_families,
        )
        return Err(
            BackendError(
                kind="artifact_index_drift",
                message=(
                    f"missing_from_index={missing_from_index} "
                    f"unresolved_rows={unresolved_rows} "
                    f"hintless_families={hintless_families}"
                ),
            )
        )
    _log.debug(
        "artifact index consistency: OK (%d file(s), %d row(s))",
        len(file_paths),
        len(index.rows),
    )
    return Ok(None)
