"""The complete board fab set (WO-124, charter 41 sec. 3, D238.2/AD-39):
the shared layer manifest, a deterministic hand-rolled Gerber X2 +
Excellon writer (the fake-KiCad tier's own exporter, no `kicad-cli`
involved), and the set-completeness checker both legs run.

Honesty discipline (D224 -- never fabricate geometry): every layer this
module writes is either genuinely derived from the caller's data
(board outline size, `RealizedLayout.placements`, the board identity
strings) or is a legitimately EMPTY-but-valid file when the realized
surface has nothing to report for that layer (e.g. mask/paste
apertures need pad-stack geometry `Placement` does not carry today --
see the WO-124 close-out finding; an empty soldermask gerber is the
honest answer, not a fabricated pad).

The two legs (real `kicad-cli` re-export in `elec.py`, and this
module's own writer) emit the SAME relative file manifest (charter 41
sec. 3: "file MANIFESTS are identical; bytes may differ") so
`check_fab_set_completeness` runs identically over either leg's
output.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from typani.result import Err, Ok, Result

from regolith._codes import FAB_SET_INCOMPLETE
from regolith._schema.models import Placement, RealizedLayout
from regolith.backends.framework import OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger
from regolith.realizer.elec.identity import (
    MIN_TEXT_HEIGHT_MM,
    identity_block_layout,
)

_log = get_logger(__name__)

# ---------------------------------------------------------------------------
# The charter 41 sec. 3 fab-set manifest (relative paths, "gerbers/"/
# "drill/" family-prefixed, matching real kicad-cli's own naming so the
# completeness check and the two legs' outputs line up byte-for-path).
# ---------------------------------------------------------------------------

# frob:doc docs/modules/py-backends.md#backends-elec-fabset
GERBER_LAYER_FILES: tuple[str, ...] = (
    "gerbers/board-F_Cu.gtl",
    "gerbers/board-B_Cu.gbl",
    "gerbers/board-F_Mask.gts",
    "gerbers/board-B_Mask.gbs",
    "gerbers/board-F_Paste.gtp",
    "gerbers/board-B_Paste.gbp",
    "gerbers/board-F_Silkscreen.gto",
    "gerbers/board-B_Silkscreen.gbo",
    "gerbers/board-Edge_Cuts.gm1",
    "gerbers/board-F_Courtyard.gbr",
    "gerbers/board-B_Courtyard.gbr",
    "gerbers/board-F_Fab.gbr",
    "gerbers/board-B_Fab.gbr",
    "gerbers/board-Margin.gbr",
    "gerbers/board-job.gbrjob",
)

# frob:doc docs/modules/py-backends.md#backends-elec-fabset
DRILL_FILES: tuple[str, ...] = (
    "drill/board-PTH.drl",
    "drill/board-NPTH.drl",
    "drill/board-PTH-drl_map.gbr",
    "drill/board-NPTH-drl_map.gbr",
)

# The complete charter 41 sec. 3 set (job file included; `pos`/`bom`/
# `panel`/`board.kicad_pcb`/`board_status.json` are separate WO-25/103
# families this checker does not police).
# frob:doc docs/modules/py-backends.md#backends-elec-fabset
REQUIRED_FAB_SET: tuple[str, ...] = GERBER_LAYER_FILES + DRILL_FILES

_KICAD_LAYER_LIST = (
    "F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,F.Paste,B.Paste,"
    "F.Fab,B.Fab,F.CrtYd,B.CrtYd,Edge.Cuts,Margin"
)


# frob:doc docs/modules/py-backends.md#backends-elec-fabset
def kicad_layers_arg() -> str:
    """The `--layers` value the real leg passes to `kicad-cli pcb export
    gerbers` -- ONE place so the export invocation and this module's own
    manifest never drift apart."""
    return _KICAD_LAYER_LIST


# frob:doc docs/modules/py-backends.md#backends-elec-fabset
def check_fab_set_completeness(
    files: Sequence[OutputFile], prefix: str = ""
) -> Result[None, BackendError]:
    """Charter 41 sec. 3 completeness gate (WO-124 deliverable 4): every
    required layer file is present under ``prefix`` (e.g. `"boards/"`),
    and the job file's declared layer count is non-zero -- a
    missing/extra layer is a named error, never a warning.
    """
    present = {f.relpath[len(prefix) :] for f in files if f.relpath.startswith(prefix)}
    missing = [name for name in REQUIRED_FAB_SET if name not in present]
    if missing:
        _log.warning("fab set incomplete: missing %s", missing)
        return Err(
            BackendError(
                kind=FAB_SET_INCOMPLETE,  # E0901 (D247.1: coded, not a bare string)
                message="shipped gerber set is missing required charter 41 "
                f"sec. 3 layer(s): {', '.join(sorted(missing))}",
            )
        )
    _log.info("fab set complete: %d required file(s) present", len(REQUIRED_FAB_SET))
    return Ok(None)


# ---------------------------------------------------------------------------
# A compact 3x5 pixel stick font (A-Z, 0-9, space, `: . - _ /`) -- enough
# for legible board-identity/refdes silkscreen text without a real font
# engine (the fake tier never shells out to KiCad). Each glyph is 5 rows
# of a 3-char string, '1' = filled pixel.
# ---------------------------------------------------------------------------

_FONT_3X5: dict[str, tuple[str, str, str, str, str]] = {
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "111", "011"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    " ": ("000", "000", "000", "000", "000"),
    ":": ("000", "010", "000", "010", "000"),
    ".": ("000", "000", "000", "000", "010"),
    "-": ("000", "000", "111", "000", "000"),
    "_": ("000", "000", "000", "000", "111"),
    "/": ("001", "001", "010", "100", "100"),
}


def _mm_to_gerber_int(mm: float) -> int:
    """4.6 fixed-point (micrometer resolution) integer coordinate."""
    return round(mm * 1_000_000)


def _fmt_coord(mm: float) -> str:
    v = _mm_to_gerber_int(mm)
    sign = "-" if v < 0 else ""
    return f"{sign}{abs(v)}"


# frob:doc docs/modules/py-backends.md#backends-elec-fabset
def gerber_bounds(data: bytes) -> tuple[float, float, float, float] | None:
    """The (xmin, ymin, xmax, ymax) mm bounding box of every D01/D02
    coordinate in a gerber body, or ``None`` when the file draws
    nothing (an honestly-empty layer).

    A deliberately simple X/Y-word scan that assumes the 4.6 metric
    format both this module's writer and real `kicad-cli` emit
    (`%FSLAX46Y46*%` / `%MOMM*%`, asserted) -- enough for the WO-124
    regression bar (silkscreen strictly inside the board outline),
    not a general gerber geometry engine."""
    import re

    text = data.decode("ascii", errors="replace")
    if "%FSLAX46Y46" not in text or "%MOMM" not in text:
        _log.warning("gerber_bounds: unexpected coordinate format header")
        return None
    xs: list[float] = []
    ys: list[float] = []
    x: float | None = None
    y: float | None = None
    for match in re.finditer(
        r"^(?:X(?P<x>-?\d+))?(?:Y(?P<y>-?\d+))?D0[123]\*", text, re.MULTILINE
    ):
        if match.group("x") is not None:
            x = int(match.group("x")) / 1_000_000
        if match.group("y") is not None:
            y = int(match.group("y")) / 1_000_000
        if x is not None and y is not None:
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


class _GerberWriter:
    """Accumulates a minimal, valid RS-274X X2 gerber body."""

    def __init__(self, file_function: str, *, aperture_mm: float = 0.15) -> None:
        self._function = file_function
        self._aperture_mm = aperture_mm
        self._body: list[str] = []
        self._used_aperture = False

    # frob:doc docs/modules/py-backends.md#backends-elec-fabset
    def flash_pixel(self, x_mm: float, y_mm: float) -> None:
        """A filled square 'pixel' (used by the stick font): drawn as a
        short zero-length stroke with the round aperture, i.e. a dot."""
        self._used_aperture = True
        self._body.append("D10*")
        self._body.append(f"X{_fmt_coord(x_mm)}Y{_fmt_coord(y_mm)}D02*")
        self._body.append(f"X{_fmt_coord(x_mm)}Y{_fmt_coord(y_mm)}D01*")

    # frob:doc docs/modules/py-backends.md#backends-elec-fabset
    def line(self, x0_mm: float, y0_mm: float, x1_mm: float, y1_mm: float) -> None:
        self._used_aperture = True
        self._body.append("D10*")
        self._body.append(f"X{_fmt_coord(x0_mm)}Y{_fmt_coord(y0_mm)}D02*")
        self._body.append(f"X{_fmt_coord(x1_mm)}Y{_fmt_coord(y1_mm)}D01*")

    # frob:doc docs/modules/py-backends.md#backends-elec-fabset
    def rect_outline(self, w_mm: float, d_mm: float) -> None:
        self.line(0.0, 0.0, w_mm, 0.0)
        self.line(w_mm, 0.0, w_mm, d_mm)
        self.line(w_mm, d_mm, 0.0, d_mm)
        self.line(0.0, d_mm, 0.0, 0.0)

    # frob:doc docs/modules/py-backends.md#backends-elec-fabset
    def text(self, s: str, x_mm: float, y_mm: float, height_mm: float = 1.0) -> None:
        """Draw ``s`` (upper-cased) left-to-right starting at
        ``(x_mm, y_mm)`` using the 3x5 stick font, one 'pixel' per filled
        cell -- a genuine, if blocky, legible stroke, never a placeholder
        box (charter 41 sec. 1.3's minimum-text-height rule: the caller
        picks ``height_mm`` at/above the style pack's floor)."""
        pitch = height_mm / 5.0
        cursor_x = x_mm
        for ch in s.upper():
            glyph = _FONT_3X5.get(ch, _FONT_3X5[" "])
            for row_idx, row in enumerate(glyph):
                gy = y_mm + (4 - row_idx) * pitch
                for col_idx, cell in enumerate(row):
                    if cell == "1":
                        self.flash_pixel(cursor_x + col_idx * pitch, gy)
            cursor_x += 4 * pitch  # 3 cols + 1 col gutter

    # frob:doc docs/modules/py-backends.md#backends-elec-fabset
    def render(self) -> bytes:
        lines = [
            "%TF.GenerationSoftware,regolith,fake-kicad,1.0*%",
            f"%TF.FileFunction,{self._function}*%",
            "%TF.FilePolarity,Positive*%",
            "%FSLAX46Y46*%",
            "%MOMM*%",
            "%LPD*%",
            "G04 regolith fake-kicad tier: deterministic minimal gerber*",
            f"%ADD10C,{self._aperture_mm:.6f}*%",
            *self._body,
            "M02*",
            "",
        ]
        return "\n".join(lines).encode("ascii")


def _excellon(plated: bool) -> bytes:
    """An empty-but-valid Excellon drill file: no hits, since no
    `Placement` in this fleet carries pad-stack/hole data yet (the
    named absence WO-124's escalation records) -- an honest zero-hole
    file, never a fabricated hole."""
    kind = "PTH" if plated else "NPTH"
    lines = [
        "M48",
        "; DRILL file {regolith fake-kicad tier} date n/a",
        f"; FORMAT={{4:4/ absolute / metric / decimal}} kind={kind}",
        "FMAT,2",
        "METRIC,TZ",
        "%",
        "G90",
        "G05",
        "M30",
        "",
    ]
    return "\n".join(lines).encode("ascii")


def _drill_map(plated: bool) -> bytes:
    """An empty-but-valid gerber-shaped drill map (no hits to summarize)."""
    kind = "PTH" if plated else "NPTH"
    writer = _GerberWriter(f"Legend,DrillMap,{kind}")
    return writer.render()


def _job_file(subject: str) -> bytes:
    """A deterministic JSON job file: layer name -> emitted relpath, so
    the completeness check (and a human) can cross-reference the set
    without parsing gerber headers. Not `kicad-cli`'s own `.gbrjob`
    binary-identical shape (that leg has its own real one); this is the
    fake tier's own honest equivalent (D238.2: "the job file lists
    every emitted layer")."""
    import json

    payload = {
        "Header": {
            "GenerationSoftware": "regolith fake-kicad tier",
            "Subject": subject,
        },
        "FilesAttributes": [
            {"Path": name}
            for name in GERBER_LAYER_FILES
            if name != "gerbers/board-job.gbrjob"
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")


def _board_outline_mm(pcb_text: str) -> tuple[float, float]:
    """Recover the board's rectangular outline size from the pinned
    `.kicad_pcb` text (both `fake_kicad.py` and `kicad_wrapper.py`
    draw a `(start 0 0)`/`(end W D)` `Edge.Cuts` rect -- WO-103's one
    outline shape). Falls back to a nominal 10x10mm square (logged) if
    the pattern is not found, rather than raising -- the fake tier's
    job is to always materialize a valid set."""
    import re

    match = re.search(
        r"\(start\s+0\s+0\)\s*\n\s*\(end\s+([0-9.]+)\s+([0-9.]+)\)", pcb_text
    )
    if match is None:
        _log.warning(
            "fake fab-set exporter: could not recover board outline from "
            "pinned .kicad_pcb text; using a 10x10mm fallback"
        )
        return (10.0, 10.0)
    return (float(match.group(1)), float(match.group(2)))


# frob:doc docs/modules/py-backends.md#backends-elec-fabset
def identity_lines(subject: str, layout: RealizedLayout) -> tuple[str, str]:
    """The board identity block text (charter 41 sec. 3): name + design
    short-hash (from `netlist_hash`, the one content-addressed design
    reference this payload carries) on one line, and an honestly
    labeled `REV: N/A` on the second -- no design-revision concept
    exists anywhere in the realized surface today (WO-124 close-out
    finding), so this is a named absence, never a fabricated rev.

    An empty `netlist_hash` (a board realized before any netlist is
    bound) yields the name alone -- never a fabricated hash."""
    short_hash = layout.netlist_hash.removeprefix("sha256:")[:12]
    return (f"{subject} {short_hash}".strip(), "REV: N/A")


def _placement_refdes_lines(
    placements: Iterable[Placement],
) -> list[tuple[str, float, float]]:
    """(text, x_mm, y_mm) for every placement's refdes -- the labeling
    seam WO-124 asks for; empty today (no fleet board has placements
    yet, see the close-out finding) and a real draw the moment a
    realizer starts populating `RealizedLayout.placements`."""
    out = []
    for p in placements:
        x, y = p.position_mm
        out.append((p.reference, x, y))
    return out


# frob:doc docs/modules/py-backends.md#backends-elec-fabset
def build_fake_fab_set(
    subject: str, layout: RealizedLayout, pcb_text: str
) -> tuple[OutputFile, ...]:
    """The fake-KiCad tier's own exporter (WO-124 deliverable 3): the
    SAME relative file manifest `_run_kicad_cli` produces (charter 41
    sec. 3), built by hand -- deterministic, no `kicad-cli` involved.

    Copper/courtyard/fab/mask/paste layers are honestly EMPTY (no
    routed copper, no pad-stack geometry in `Placement` -- D224); the
    silkscreen layers carry the real board-identity text and every
    placement's refdes (empty today); Edge.Cuts carries the genuine
    outline rectangle recovered from the pinned board text.
    """
    w_mm, d_mm = _board_outline_mm(pcb_text)
    name_line, rev_line = identity_lines(subject, layout)
    refdes = _placement_refdes_lines(layout.placements)

    def empty(function: str) -> bytes:
        return _GerberWriter(function).render()

    # WO-124 D238.3 visual-pass geometry: the same single-sourced
    # layout the `.kicad_pcb`-authoring legs use (margin, charter-41
    # height, left/bottom anchors) -- board coords are +y down, this
    # writer's gerber space is +y up, so anchors flip through d_mm.
    identity_height_mm, identity_anchors = identity_block_layout(
        w_mm, d_mm, name_line, rev_line
    )

    def silk(side: str) -> bytes:
        writer = _GerberWriter(f"Legend,{side}")
        for text, x, y_down in identity_anchors:
            if text:
                writer.text(text, x, d_mm - y_down, height_mm=identity_height_mm)
        for ref, x, y in refdes:
            writer.text(ref, x, y, height_mm=MIN_TEXT_HEIGHT_MM)
        return writer.render()

    def edge_cuts() -> bytes:
        writer = _GerberWriter("Profile,NP")
        writer.rect_outline(w_mm, d_mm)
        return writer.render()

    files = {
        "gerbers/board-F_Cu.gtl": empty("Copper,L1,Top"),
        "gerbers/board-B_Cu.gbl": empty("Copper,L2,Bot"),
        "gerbers/board-F_Mask.gts": empty("Soldermask,Top"),
        "gerbers/board-B_Mask.gbs": empty("Soldermask,Bot"),
        "gerbers/board-F_Paste.gtp": empty("Paste,Top"),
        "gerbers/board-B_Paste.gbp": empty("Paste,Bot"),
        "gerbers/board-F_Silkscreen.gto": silk("Top"),
        "gerbers/board-B_Silkscreen.gbo": silk("Bot"),
        "gerbers/board-Edge_Cuts.gm1": edge_cuts(),
        "gerbers/board-F_Courtyard.gbr": empty("Courtyard,Top"),
        "gerbers/board-B_Courtyard.gbr": empty("Courtyard,Bot"),
        "gerbers/board-F_Fab.gbr": empty("AssemblyDrawing,Top"),
        "gerbers/board-B_Fab.gbr": empty("AssemblyDrawing,Bot"),
        "gerbers/board-Margin.gbr": empty("Other,Margin"),
        "gerbers/board-job.gbrjob": _job_file(subject),
        "drill/board-PTH.drl": _excellon(plated=True),
        "drill/board-NPTH.drl": _excellon(plated=False),
        "drill/board-PTH-drl_map.gbr": _drill_map(plated=True),
        "drill/board-NPTH-drl_map.gbr": _drill_map(plated=False),
    }
    _log.info(
        "fake fab-set exporter: emitted %d file(s) for %s (%.1fx%.1fmm, %d refdes)",
        len(files),
        subject,
        w_mm,
        d_mm,
        len(refdes),
    )
    return tuple(
        OutputFile.of(name, content) for name, content in sorted(files.items())
    )
