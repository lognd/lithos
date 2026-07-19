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

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._codes import ARTIFACT_INDEX_DRIFT
from regolith.backends.framework import ArtifactProvenance, OutputFile
from regolith.backends.registry import (
    ArtifactFamilyRegistry,
    Viewer,
    default_artifact_family_registry,
    match_path_pattern,
)
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

#: The package-root side files package.py emits (WO-99) plus this WO's own
#: index file -- every one of these has no family directory of its own, so
#: `family_of` resolves them to the `"ledgers"` family (registry.py).
# frob:doc docs/modules/py-backends.md#backends-artifact-index
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
# frob:doc docs/modules/py-backends.md#backends-artifact-index
INDEX_FILENAME = "artifact_index.json"


# frob:doc docs/modules/py-backends.md#backends-artifact-index
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
    provenance: ArtifactProvenance
    source_refs: tuple[str, ...] = ()


# frob:doc docs/modules/py-backends.md#backends-artifact-index
class ArtifactIndex(BaseModel):
    """One package's whole artifact index (WO-130 deliverable 1), rows
    sorted by `relpath` (determinism, AD-6)."""

    model_config = ConfigDict(frozen=True)

    project: str
    rows: tuple[ArtifactRow, ...] = ()


# frob:doc docs/modules/py-backends.md#backends-artifact-index
def family_of(relpath: str) -> str:
    """The family a path resolves to: its top-level directory segment, or
    ``"ledgers"`` for a root-level side file (no directory, or one of the
    named `LEDGER_FILENAMES`/`INDEX_FILENAME`)."""
    if relpath in LEDGER_FILENAMES or relpath == INDEX_FILENAME:
        return "ledgers"
    head, sep, _ = relpath.partition("/")
    return head if sep else "ledgers"


# frob:doc docs/modules/py-backends.md#backends-artifact-index
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
    a silent gap"). Per-file classification (WO-161) comes from the
    registration's own ``path_patterns`` (:func:`regolith.backends.
    registry.match_path_pattern`) -- a family registered with NO pattern
    that matches a given file is the same loud `Err`
    (``artifact_path_unclassified``), never a silent gap; every built-in
    registration ends with a catch-all pattern so this never fires for a
    known family. ``source_refs`` is keyed by `relpath`, defaulting to
    empty (a caller with no source refs for a file leaves that field at
    its honest default, never an invented value). ``provenance``
    (WO-160) comes from each `OutputFile`'s own ``provenance`` field; an
    untagged file (``None``) resolves to the honest ``deterministic``
    tier default, never an invented ``real_tool`` claim.
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
        matched = match_path_pattern(f.relpath, registration)
        if matched is None:
            _log.error(
                "artifact index: family %r has no path_patterns entry matching "
                "%s -- refusing to build a lossy index",
                family,
                f.relpath,
            )
            return Err(
                BackendError(
                    kind="artifact_path_unclassified",
                    message=(
                        f"family {family!r} has no path_patterns entry matching "
                        f"{f.relpath!r} -- register a pattern beside the family's "
                        "producer (charter 42 sec. 6); an unclassified file is a "
                        "registration error, never a silent gap"
                    ),
                )
            )
        kind, viewer_override, media_type = matched
        viewer = viewer_override if viewer_override is not None else registration.viewer
        provenance = (
            f.provenance
            if f.provenance is not None
            else ArtifactProvenance(tier="deterministic", tool=None)
        )
        rows.append(
            ArtifactRow(
                family=family,
                kind=kind,
                relpath=f.relpath,
                content_hash=f.sha256,
                bytes=len(f.content),
                media_type=media_type,
                viewer=viewer,
                provenance=provenance,
                source_refs=tuple(refs.get(f.relpath, ())),
            )
        )
    _log.info("artifact index: built %d row(s) for %r", len(rows), project)
    return Ok(ArtifactIndex(project=project, rows=tuple(rows)))


# frob:doc docs/modules/py-backends.md#backends-artifact-index
def index_bytes(index: ArtifactIndex) -> bytes:
    """Canonical deterministic JSON bytes for `index` (sorted keys,
    ASCII, no whitespace drift) -- what `artifact_index.json` ships and
    what `regolith artifacts --json` prints."""
    return index.model_dump_json(indent=2).encode("ascii") + b"\n"


# frob:doc docs/modules/py-backends.md#backends-artifact-index
def check_index_consistency(
    index: ArtifactIndex,
    files: Sequence[OutputFile],
    *,
    family_registry: ArtifactFamilyRegistry | None = None,
) -> Result[None, BackendError]:
    """WO-130 deliverable 6: the health consistency check.

    Every emitted file must appear in the index; every index row must
    resolve to an emitted file; every row's family must carry a
    registered viewer hint; every row's family must carry a
    ``path_patterns`` entry that actually matches its relpath (WO-161:
    with `classify()` deleted, this is the ONE remaining place a NEW
    artifact type could sneak in without registering patterns at all);
    every row's ``provenance`` must be internally consistent -- ``tool``
    present iff ``tier == "real_tool"`` (WO-160). Any one of these
    failing is drift -- an `Err`, never a warning.
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
    unmatched_patterns = []
    for r in index.rows:
        if r.family not in known_families:
            continue
        registration = registry.get(r.family)
        # `r.family in known_families` (built from `registry.families()`)
        # guarantees this lookup hits -- but ty can't correlate a set
        # membership test against a separate dict lookup, so narrow
        # explicitly rather than re-suppressing a real None-ability check.
        assert registration is not None, (
            f"family {r.family!r} in known_families but missing from registry"
        )
        if match_path_pattern(r.relpath, registration) is None:
            unmatched_patterns.append(r.relpath)
    unmatched_patterns = sorted(unmatched_patterns)
    malformed_provenance = sorted(
        r.relpath
        for r in index.rows
        if (r.provenance.tier == "real_tool") != (r.provenance.tool is not None)
    )
    if (
        missing_from_index
        or unresolved_rows
        or hintless_families
        or unmatched_patterns
        or malformed_provenance
    ):
        _log.error(
            "artifact index drift: missing_from_index=%s unresolved_rows=%s "
            "hintless_families=%s unmatched_patterns=%s malformed_provenance=%s",
            missing_from_index,
            unresolved_rows,
            hintless_families,
            unmatched_patterns,
            malformed_provenance,
        )
        return Err(
            BackendError(
                kind=ARTIFACT_INDEX_DRIFT,
                message=(
                    f"missing_from_index={missing_from_index} "
                    f"unresolved_rows={unresolved_rows} "
                    f"hintless_families={hintless_families} "
                    f"unmatched_patterns={unmatched_patterns} "
                    f"malformed_provenance={malformed_provenance}"
                ),
            )
        )
    _log.debug(
        "artifact index consistency: OK (%d file(s), %d row(s))",
        len(file_paths),
        len(index.rows),
    )
    return Ok(None)
