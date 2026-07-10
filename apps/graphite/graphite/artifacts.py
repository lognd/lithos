"""The ONE disk-scanning module (artifact-only channel, AD-24/AD-22 applied
to UI): every sheet/payload/trace the GUI and TUI show comes from here.
Never imports `regolith.orchestrator`/`regolith.harness` -- only reads
bytes off disk (ship-output `drawings/` directories, `.regolith/payloads/`,
`.regolith/build/` reports) and lets the caller pretty-print/serve them.

Generic by design (WO-59 dispatch note): this module does not hard-code
a dependency on any particular diagram track name (`elec_blocks`,
`contract_graph`, `opt_trace`, ...). It lists whatever
`<subject>.drawing.{json,svg,dxf,pdf,explain.txt}` sibling sets exist
under a `drawings/` directory and reports each one's track from the
`.drawing.json` payload's own `track` field when present, else
`"unknown"`.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from graphite.logging_setup import get_logger

_log = get_logger(__name__)

_DRAWING_JSON_SUFFIX = ".drawing.json"


class SheetEntry(BaseModel):
    """One `<subject>.drawing.*` sibling set discovered under a `drawings/`
    directory. `track` is read from the drawing JSON's own `track` field
    when present (generic: this module never hard-codes track names)."""

    model_config = ConfigDict(frozen=True)

    subject: str
    track: str
    json_path: str | None = None
    svg_path: str | None = None
    dxf_path: str | None = None
    pdf_path: str | None = None
    explain_path: str | None = None


def _track_of(json_path: Path) -> str:
    """Best-effort track name from the drawing JSON's own field; a missing
    or unparsable file just reports `"unknown"` (never raises -- this is a
    listing convenience, not a validator)."""
    try:
        data = json.loads(json_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("artifacts: cannot read track from %s: %s", json_path, exc)
        return "unknown"
    track = data.get("track")
    return str(track) if isinstance(track, str) else "unknown"


def list_sheets(drawings_dir: Path) -> tuple[SheetEntry, ...]:
    """Every `<subject>.drawing.*` sibling set under `drawings_dir`,
    subject-sorted. Absent directory -> empty tuple (not an error: a fresh
    project has no ship output yet)."""
    if not drawings_dir.is_dir():
        _log.info("artifacts: no drawings directory at %s", drawings_dir)
        return ()
    subjects: dict[str, dict[str, Path]] = {}
    for entry in drawings_dir.iterdir():
        name = entry.name
        if name.endswith(_DRAWING_JSON_SUFFIX):
            subject = name[: -len(_DRAWING_JSON_SUFFIX)]
            subjects.setdefault(subject, {})["json"] = entry
        elif name.endswith(".drawing.svg"):
            subjects.setdefault(name[: -len(".drawing.svg")], {})["svg"] = entry
        elif name.endswith(".drawing.dxf"):
            subjects.setdefault(name[: -len(".drawing.dxf")], {})["dxf"] = entry
        elif name.endswith(".drawing.pdf"):
            subjects.setdefault(name[: -len(".drawing.pdf")], {})["pdf"] = entry
        elif name.endswith(".explain.txt"):
            subjects.setdefault(name[: -len(".explain.txt")], {})["explain"] = entry

    sheets: list[SheetEntry] = []
    for subject in sorted(subjects):
        paths = subjects[subject]
        json_path = paths.get("json")
        track = _track_of(json_path) if json_path is not None else "unknown"
        sheets.append(
            SheetEntry(
                subject=subject,
                track=track,
                json_path=str(json_path) if json_path else None,
                svg_path=str(paths["svg"]) if "svg" in paths else None,
                dxf_path=str(paths["dxf"]) if "dxf" in paths else None,
                pdf_path=str(paths["pdf"]) if "pdf" in paths else None,
                explain_path=str(paths["explain"]) if "explain" in paths else None,
            )
        )
    _log.info("artifacts: found %d sheet(s) under %s", len(sheets), drawings_dir)
    return tuple(sheets)


def find_drawings_dirs(root: Path) -> tuple[Path, ...]:
    """Every `drawings/` directory under `root` (a ship `--out` tree may
    nest one per shipped assembly) -- sorted for determinism."""
    if not root.is_dir():
        return ()
    found = sorted({p for p in root.rglob("drawings") if p.is_dir()})
    return tuple(found)


def list_payload_files(payload_store_dir: Path) -> tuple[Path, ...]:
    """Every content-addressed payload file under `.regolith/payloads/`
    (WO-30 D96 sec. 8.3), name-sorted -- pretty-printed by the caller if
    the bytes happen to parse as JSON, served raw otherwise."""
    if not payload_store_dir.is_dir():
        return ()
    return tuple(sorted(p for p in payload_store_dir.iterdir() if p.is_file()))


def find_trace_files(root: Path) -> tuple[Path, ...]:
    """Every on-disk `OptimizationTrace` JSON dump under `root`'s
    `.regolith/` tree (the `optimize --json` / payload-store shape) --
    generic file-glob, does not assume WO-61's sheet exists."""
    regolith_dir = root / ".regolith"
    if not regolith_dir.is_dir():
        return ()
    return tuple(sorted(regolith_dir.rglob("*trace*.json")))


def read_json(path: Path) -> str:
    """Pretty-printed JSON text for `path`, or the raw text if it does not
    parse as JSON (never raises -- a debug dump that fails to parse is
    still worth showing verbatim)."""
    raw = path.read_text()
    try:
        return json.dumps(json.loads(raw), indent=2, sort_keys=True)
    except json.JSONDecodeError:
        return raw
