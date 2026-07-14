"""The SVG reference renderer (charter sec. 1 decision 2, mandatory;
DXF/PDF are siblings of the same IR, see `renderer_dxf.py`/`renderer_pdf.py`).
Deterministic TEXT output: same `DrawingModel` -> byte-identical SVG
(AD-6), the two-runs golden property WO-50 proves.

Consumes ONLY `DrawingModel` -- no geometry computation, no re-reading
of source (AD-27). Layout (sheet frame, title block, view grid cells,
dimension standoff) is a deterministic mechanical HEURISTIC over the
already-projected entities (charter sec. 1 decision 5: grid layout, no
aesthetics) -- it moves and scales what the producer already computed;
it never invents geometry.
"""

from __future__ import annotations

import hashlib
import math
from xml.sax.saxutils import escape

from regolith._schema import SCHEMA_VERSION
from regolith._schema.models import (
    Annotation,
    Dimension,
    DrawingModel,
    Sheet,
    Table,
    View,
)
from regolith._schema.models import Entity1 as SegmentEntity
from regolith._schema.models import Entity2 as ArcEntity
from regolith._schema.models import Entity3 as PolylineEntity
from regolith._schema.models import Entity4 as SymbolEntity
from regolith.backends.drawings.style import StyleRecord, resolve_style
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

_NS = "http://www.w3.org/2000/svg"

# Sheet size -> (width_mm, height_mm), landscape orientation (charter's
# drafting convention). Every `SheetSize*` enum value the schema defines
# maps here; an unmapped value is a schema/renderer drift bug.
_SHEET_SIZES_MM: dict[str, tuple[float, float]] = {
    "ansi_a": (279.4, 215.9),  # 11x8.5 in
    "ansi_b": (431.8, 279.4),  # 17x11 in
    "ansi_c": (558.8, 431.8),  # 22x17 in
    "iso_a4": (297.0, 210.0),
    "iso_a3": (420.0, 297.0),
}

# WO-99 D7 / charter 38 sec. 1.12: the drafting aesthetic constants now
# live in `StyleRecord` (style.py), threaded through the renderers. The
# NEUTRAL_STYLE default reproduces every historical value exactly, so a
# default-styled render is byte-identical to the pre-D7 output. Sheet page
# sizes (`_SHEET_SIZES_MM`) stay module-level: they map the schema's own
# `SheetSize` enum, not a single overridable style scalar.

_Entity = SegmentEntity | ArcEntity | PolylineEntity | SymbolEntity


def _fmt(value: float) -> str:
    """A stable, locale-independent float format for SVG coordinates."""
    return f"{value:.4f}"


def _text(value: str) -> str:
    """XML-escape a text value before it lands inside SVG markup."""
    return escape(value)


class _Transform:
    """A view's local-space -> sheet-space affine map: uniform `scale`
    then `translate` (charter's grid layout is mechanical, never
    rotated/skewed -- a single scalar + offset is the whole heuristic).
    """

    __slots__ = ("scale", "tx", "ty")

    def __init__(self, scale: float, tx: float, ty: float) -> None:
        self.scale = scale
        self.tx = tx
        self.ty = ty

    def point(self, x: float, y: float) -> tuple[float, float]:
        """Map one local-space point into sheet-space."""
        return (self.scale * x + self.tx, self.scale * y + self.ty)

    def attr(self) -> str:
        """This transform as an SVG `transform` attribute value."""
        return f"translate({_fmt(self.tx)},{_fmt(self.ty)}) scale({_fmt(self.scale)})"


_IDENTITY = _Transform(1.0, 0.0, 0.0)


class TitleBlockField:
    """One title-block cell (charter 41 sec. 1.1): a caption-face LABEL
    line above a body-face VALUE line (wrapped to the cell width so a
    long value never overruns the next field, INV-31), at a fixed x --
    so a renderer never emits an unlabeled text line.
    """

    __slots__ = ("label", "label_pos", "value_line_h", "value_lines", "value_pos")

    def __init__(
        self,
        label: str,
        value: str,
        x: float,
        y: float,
        width: float,
        style: StyleRecord,
    ) -> None:
        self.label = label.upper()
        self.value_lines = wrap_to_width(value, style.body_text_height_mm, width, style)
        self.value_line_h = style.body_text_height_mm + 1.0
        self.label_pos = (x, y)
        self.value_pos = (x, y + style.caption_text_height_mm + 1.0)

    @property
    def row_height(self) -> float:
        """The vertical space this field's wrapped value needs."""
        return len(self.value_lines) * self.value_line_h


def _sheet_furniture(
    sheet: Sheet,
    w: float,
    h: float,
    style: StyleRecord,
    *,
    sheet_index: int = 0,
    sheet_count: int = 1,
    content_digest: str = "",
    schema_version: int = 0,
) -> tuple[
    list[tuple[str, float, float, float, float]],
    list[TitleBlockField],
    tuple[float, float, str],
]:
    """The sheet furniture every renderer must emit identically: the
    frame border + title-block rectangles as `(name, x, y, w, h)`, the
    NAMED title-block fields (charter 41 sec. 1.1 -- label line + value
    line per field, never a bare unlabeled line), and the provenance
    footer `(x, y, text)` (design content address, schema version,
    style pack id, sheet n/N -- charter 41 sec. 2's footer rule). ONE
    home for this layout math so SVG/DXF/PDF cannot diverge on it.
    """
    margin = style.margin_mm
    tb_w = style.title_block_w_mm
    tb_h = style.title_block_h_mm
    rects = [
        ("frame", margin, margin, w - 2 * margin, h - 2 * margin),
    ]
    box_x = w - margin - tb_w
    box_y = h - margin - tb_h
    rects.append(("title-block-frame", box_x, box_y, tb_w, tb_h))

    tb = sheet.title_block
    field_defs = [
        ("Title", tb.title),
        ("Dwg No.", tb.drawing_number),
        ("Rev", tb.revision),
        ("Scale", tb.scale_label),
        ("Subject", tb.subject),
        ("Sheet", f"{sheet_index + 1} / {sheet_count}"),
    ]
    text_x = box_x + 2.0
    text_y = box_y + style.caption_text_height_mm + 1.0
    value_width = tb_w - 4.0
    fields: list[TitleBlockField] = []
    for label, value in field_defs:
        field = TitleBlockField(label, value, text_x, text_y, value_width, style)
        fields.append(field)
        text_y += style.caption_text_height_mm + 1.0 + field.row_height + 1.5

    footer_text = (
        f"design {content_digest[:12]}  |  schema v{schema_version}  |  "
        f"style {style.pack_id}"
    )
    footer: tuple[float, float, str] = (margin + 1.0, h - margin - 1.5, footer_text)
    return rects, fields, footer


def _zone_marks(
    w: float, h: float, style: StyleRecord
) -> list[tuple[float, float, str]]:
    """Sheet-border zone reference marks (charter 41 sec. 1.2): letters
    along one axis, digits along the other, evenly spaced outside the
    printable frame so a callout can cite a zone (e.g. "see B3") the way
    a real drafting border does.
    """
    margin = style.margin_mm
    n_cols = 4
    n_rows = 4
    marks: list[tuple[float, float, str]] = []
    col_w = (w - 2 * margin) / n_cols
    for i in range(n_cols):
        x = margin + col_w * (i + 0.5)
        marks.append((x, margin - 1.5, str(i + 1)))
        marks.append((x, h - margin + style.caption_text_height_mm + 1.0, str(i + 1)))
    row_h = (h - 2 * margin) / n_rows
    for i in range(n_rows):
        y = margin + row_h * (i + 0.5)
        letter = chr(ord("A") + i)
        marks.append((margin - 3.0, y, letter))
        marks.append((w - margin + 1.5, y, letter))
    return marks


def _view_label_text(view: View) -> str:
    """A per-view label + scale line (charter 41 sec. 1.2): e.g.
    ``"TOP  1:1"``. Scale >= 1 renders ``N:1``; a fractional scale
    renders as ``1:N`` (the ASME convention for a reduced view) -- read
    straight off the view's own `scale` field, never invented.
    """
    scale = view.scale
    scale_text = f"{scale:g}:1" if scale >= 1.0 else f"1:{(1.0 / scale):g}"
    return f"{view.name.upper()}  {scale_text}"


def _sheet_size_mm(sheet: Sheet) -> tuple[float, float]:
    """The sheet's (width_mm, height_mm), landscape, from its size enum."""
    size = _SHEET_SIZES_MM.get(sheet.size.value)
    if size is None:
        _log.warning("unmapped sheet size %r; falling back to ANSI A", sheet.size.value)
        return _SHEET_SIZES_MM["ansi_a"]
    return size


def _entity_bbox(
    entity: _Entity, style: StyleRecord
) -> tuple[float, float, float, float]:
    """The local-space (min_x, min_y, max_x, max_y) of one entity."""
    if isinstance(entity, SegmentEntity):
        xs = (entity.from_[0], entity.to[0])
        ys = (entity.from_[1], entity.to[1])
        return (min(xs), min(ys), max(xs), max(ys))
    if isinstance(entity, ArcEntity):
        cx, cy = entity.center[0], entity.center[1]
        r = entity.radius
        return (cx - r, cy - r, cx + r, cy + r)
    if isinstance(entity, PolylineEntity):
        xs = [p.root[0] for p in entity.points]
        ys = [p.root[1] for p in entity.points]
        if not xs:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))
    ox, oy = entity.origin[0], entity.origin[1]
    r = style.symbol_radius_mm
    return (ox - r, oy - r, ox + r, oy + r)


def _view_bbox(
    view: View, entities: list[_Entity], style: StyleRecord
) -> tuple[float, float, float, float]:
    """The union local-space bbox of every entity `view` references, in
    the schema's own stable `entity_indices` order (never re-sorted).
    """
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for idx in view.entity_indices:
        bbox = _entity_bbox(entities[int(idx.root)], style)
        min_x = min(min_x, bbox[0])
        min_y = min(min_y, bbox[1])
        max_x = max(max_x, bbox[2])
        max_y = max(max_y, bbox[3])
    if min_x > max_x:
        return (0.0, 0.0, 0.0, 0.0)
    return (min_x, min_y, max_x, max_y)


def _grid_cell(
    index: int,
    cols: int,
    content_x: float,
    content_y: float,
    cell_w: float,
    cell_h: float,
) -> tuple[float, float]:
    """The (x, y) origin of the `index`-th cell in a row-major grid."""
    row, col = divmod(index, cols)
    return (content_x + col * cell_w, content_y + row * cell_h)


def _view_transforms(
    sheet: Sheet, content_area: tuple[float, float, float, float], style: StyleRecord
) -> dict[str, _Transform]:
    """One deterministic grid-cell transform per view (charter sec. 1
    decision 5): views laid out in declaration order, equal cells,
    each view's local bbox scaled to fit and centered in its cell.
    """
    content_x, content_y, content_w, content_h = content_area
    n = len(sheet.views)
    if n == 0:
        return {}
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    cell_w = content_w / cols
    cell_h = content_h / rows
    pad = style.cell_pad_mm

    transforms: dict[str, _Transform] = {}
    for i, view in enumerate(sheet.views):
        cell_x, cell_y = _grid_cell(i, cols, content_x, content_y, cell_w, cell_h)
        inner_w = max(cell_w - 2 * pad, 1.0)
        inner_h = max(cell_h - 2 * pad, 1.0)

        min_x, min_y, max_x, max_y = _view_bbox(view, list(sheet.entities), style)
        bbox_w = max_x - min_x
        bbox_h = max_y - min_y
        if bbox_w <= 0.0 or bbox_h <= 0.0:
            bbox_w = bbox_h = style.fallback_extent_mm
            min_x = min_y = 0.0

        scale = min(inner_w / bbox_w, inner_h / bbox_h)
        # Center the scaled bbox inside the inner (padded) cell area.
        tx = cell_x + pad + (inner_w - scale * bbox_w) / 2.0 - scale * min_x
        ty = cell_y + pad + (inner_h - scale * bbox_h) / 2.0 - scale * min_y
        transforms[view.name] = _Transform(scale, tx, ty)
    return transforms


def _view_cells(
    sheet: Sheet, content_area: tuple[float, float, float, float], style: StyleRecord
) -> dict[str, tuple[float, float, float, float]]:
    """The same grid-cell rectangles `_view_transforms` scales views into,
    exposed by view name (WO-123: the chart primitive needs the cell's
    own rect, not just the point transform, to place axes/gridlines).
    """
    content_x, content_y, content_w, content_h = content_area
    n = len(sheet.views)
    if n == 0:
        return {}
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    cell_w = content_w / cols
    cell_h = content_h / rows
    cells: dict[str, tuple[float, float, float, float]] = {}
    for i, view in enumerate(sheet.views):
        cell_x, cell_y = _grid_cell(i, cols, content_x, content_y, cell_w, cell_h)
        cells[view.name] = (cell_x, cell_y, cell_w, cell_h)
    return cells


# ---------------------------------------------------------------------------
# WO-123 (charter 41) shared layout primitives: text measurement, table
# ruling, dimension-entity geometry, and chart geometry. ONE home (this
# module) so SVG/PDF/DXF renderers and the drafting audit (which needs
# to MEASURE the same geometry the renderer will draw, to catch clipping
# and overlap before a sheet ships) never diverge on the math.
# ---------------------------------------------------------------------------


def measure_text_width_mm(text: str, height_mm: float, style: StyleRecord) -> float:
    """A deterministic, conservative (never-under-estimating) text-width
    model: base-14 Helvetica carries no metrics table here (AD-27), so
    every glyph is charged `glyph_width_factor * height_mm` -- wide
    enough that a wrap/shrink decision made against it never lets a
    real glyph run clip past the page edge.
    """
    return len(text) * height_mm * style.glyph_width_factor


def wrap_to_width(
    text: str, height_mm: float, max_width_mm: float, style: StyleRecord
) -> list[str]:
    """Greedy word-wrap `text` into lines that each fit `max_width_mm`
    at `height_mm` (charter 41 sec. 1.4: wrap before shrink). A single
    word wider than `max_width_mm` is HARD-SPLIT into width-fitting
    chunks (WO-123 D238.3 iteration: an unbroken 77-char content
    address kept whole overflowed its table cell straight across the
    title block -- a hash token carries no hyphenation semantics to
    lose, so a hard break is honest; no hyphen character is invented).
    """
    glyph_w = height_mm * style.glyph_width_factor
    max_chars = max(int(max_width_mm / glyph_w), 1)
    words: list[str] = []
    for word in text.split():
        while len(word) > max_chars:
            words.append(word[:max_chars])
            word = word[max_chars:]
        words.append(word)
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if measure_text_width_mm(candidate, height_mm, style) <= max_width_mm:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def fit_text(
    text: str,
    max_width_mm: float,
    max_height_mm: float,
    requested_height_mm: float,
    style: StyleRecord,
) -> tuple[float, list[str]]:
    """Charter 41 sec. 1.4's placement ladder for one text run: wrap at
    the requested height; if the wrapped block still exceeds
    `max_height_mm`, shrink the text height (never below
    `style.min_text_height_mm`) and re-wrap. Returns the chosen
    `(height_mm, lines)` -- the caller overflows to a continuation
    sheet if even the floor height does not fit (never renders below
    the floor, INV-31).
    """
    height = requested_height_mm
    lines = wrap_to_width(text, height, max_width_mm, style)

    def _too_wide() -> bool:
        # `wrap_to_width` never hyphenates: a single word wider than
        # `max_width_mm` stays whole on its own line (documented), so
        # shrinking height is the only lever left to bring IT under
        # budget too (INV-31: a run that clips because its widest word
        # alone exceeds the column is still a clip).
        return any(
            measure_text_width_mm(line, height, style) > max_width_mm for line in lines
        )

    while (
        len(lines) * height > max_height_mm or _too_wide()
    ) and height > style.min_text_height_mm:
        height = max(style.min_text_height_mm, height - 0.25)
        lines = wrap_to_width(text, height, max_width_mm, style)
    return (height, lines)


class TableLayout:
    """The ruled geometry of one `Table`: column x-positions/widths
    (content-measured, `table_min_col_w_mm` floor), per-column alignment
    ("right" when every cell in the column parses as a number, else
    "left" -- charter 41 sec. 1.5), and row y-positions (header + body).
    Shared by every table consumer so BOM/cost/SI/opt-trace/calc-input
    tables all rule identically.
    """

    __slots__ = (
        "cell_lines",
        "col_aligns",
        "col_widths",
        "col_x",
        "header_h",
        "row_h",
        "row_heights",
        "row_y",
        "total_h",
        "total_w",
    )

    def __init__(
        self,
        table: Table,
        x: float,
        y: float,
        style: StyleRecord,
        *,
        max_width: float | None = None,
    ) -> None:
        n_cols = len(table.columns)
        widths = []
        for c in range(n_cols):
            header_w = measure_text_width_mm(
                table.columns[c], style.caption_text_height_mm, style
            )
            body_w = max(
                (
                    measure_text_width_mm(
                        row.cells[c] if c < len(row.cells) else "",
                        style.body_text_height_mm,
                        style,
                    )
                    for row in table.rows
                ),
                default=0.0,
            )
            widths.append(
                max(style.table_min_col_w_mm, header_w, body_w)
                + 2 * style.table_cell_pad_mm
            )

        # Charter 41 sec. 1.4/1.5: a table never runs off the page. If
        # the content-measured widths overflow `max_width`, cap the
        # SINGLE widest column (the common case: one free-text/claim
        # column dwarfs the rest) down to what's left and wrap ITS
        # cells -- every other column keeps its measured width.
        wrapped_col: int | None = None
        if max_width is not None and sum(widths) > max_width and widths:
            wrapped_col = max(range(n_cols), key=lambda c: widths[c])
            other = sum(w for i, w in enumerate(widths) if i != wrapped_col)
            widths[wrapped_col] = max(style.table_min_col_w_mm, max_width - other)

        aligns = []
        for c in range(n_cols):
            numeric = True
            saw_any = False
            for row in table.rows:
                if c >= len(row.cells):
                    continue
                saw_any = True
                if not _looks_numeric(row.cells[c]):
                    numeric = False
                    break
            aligns.append("right" if (numeric and saw_any) else "left")

        col_x = [x]
        for w in widths:
            col_x.append(col_x[-1] + w)

        self.col_widths = widths
        self.col_x = col_x[:-1]
        self.col_aligns = aligns
        self.header_h = style.table_header_line_h_mm
        self.row_h = style.table_row_line_h_mm

        cell_lines: dict[tuple[int, int], list[str]] = {}
        row_heights: list[float] = []
        for r, row in enumerate(table.rows):
            max_lines = 1
            for c in range(n_cols):
                cell = row.cells[c] if c < len(row.cells) else ""
                if c == wrapped_col:
                    inner_w = max(widths[c] - 2 * style.table_cell_pad_mm, 1.0)
                    lines = wrap_to_width(
                        cell, style.body_text_height_mm, inner_w, style
                    )
                else:
                    lines = [cell]
                cell_lines[(r, c)] = lines
                max_lines = max(max_lines, len(lines))
            row_heights.append(max_lines * self.row_h)
        self.cell_lines = cell_lines
        self.row_heights = row_heights

        row_y = []
        cursor = y + self.header_h
        for rh in row_heights:
            cursor += rh
            row_y.append(cursor)
        self.row_y = row_y
        self.total_w = sum(widths)
        self.total_h = self.header_h + sum(row_heights)


def table_fit_max_width(
    table: Table,
    x: float,
    y_first_row: float,
    style: StyleRecord,
    w: float,
    h: float,
) -> float:
    """The max width a table at `y_first_row` may rule to WITHOUT
    entering the title-block region (WO-123 D238.3 iteration finding:
    a wide hash table cascading down the sheet printed straight across
    the title block -- an INV-31 overlap). Full content width when the
    table's measured height stays above the title-block band; narrowed
    to stop short of the title block (with a content gap) when it
    would enter it. ONE home for the rule so SVG/PDF/audit agree.
    """
    full = w - style.margin_mm - x
    probe = TableLayout(table, x, y_first_row, style, max_width=full)
    tb_top = h - style.margin_mm - style.title_block_h_mm
    if y_first_row + probe.total_h <= tb_top:
        return full
    box_x = w - style.margin_mm - style.title_block_w_mm
    return max(box_x - x - style.content_gap_mm, 2 * style.table_min_col_w_mm)


def _looks_numeric(cell: str) -> bool:
    """True iff `cell` parses as a plain float or a float with a
    trailing unit-like suffix (`"12.4mm"`, `"3"`) -- the audit-visible
    heuristic `TableLayout` uses for right-aligning numeric columns
    (charter 41 sec. 1.5); a renderer never invents typed cell data, it
    only reads the display string the schema already carries.
    """
    stripped = cell.strip()
    if not stripped:
        return False
    head = stripped.rstrip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ%/")
    try:
        float(head)
        return True
    except ValueError:
        return False


class DimensionGeometry:
    """One dimension's real drafting entities (charter 41 sec. 2):
    the witness/extension line, the dimension line, an arrowhead
    (drawn as two short strokes), and the value+unit(+tolerance) text
    placed clear of the witnessed point and clamped inside `bounds` so
    it never clips the page edge (INV-31). All points are sheet-space
    mm, post-transform.
    """

    __slots__ = (
        "arrow_lines",
        "extension_lines",
        "leader_line",
        "text",
        "text_pos",
    )

    def __init__(
        self,
        anchor: tuple[float, float],
        text: str,
        style: StyleRecord,
        bounds: tuple[float, float, float, float],
        span_mm: float | None = None,
        axis: str = "x",
        outward: float | None = None,
    ) -> None:
        ax, ay = anchor
        min_x, min_y, max_x, max_y = bounds
        offset = style.dim_extension_offset_mm
        overshoot = style.dim_extension_overshoot_mm
        # WO-123 D238.3 defect 5: a REAL dimension spans between the two
        # measured edges (`span_mm`, when the caller knows the feature's
        # own measured length -- the mech producer anchors a width/depth
        # dimension at the edge's own midpoint, so half the span reaches
        # exactly the two edge endpoints); a caller with no span falls
        # back to the old fixed stand-off (fluid/civil callers with a
        # single witnessed point and no edge-to-edge length).
        # `axis` is the direction the measured span RUNS ("x": a width
        # measured along x, dimension line horizontal; "y": a depth/
        # height measured along y, dimension line vertical). `outward`
        # (+/-1) pushes the dimension line AWAY from the view content
        # (a dimension belongs outside the outline, never across it);
        # `None` keeps the legacy toward-page-top preference. Either
        # way the direction flips if it would cross the page edge
        # (charter 41 sec. 1.4 / INV-31).
        min_half_span = style.dim_arrow_len_mm * 1.5
        half_span = max(min_half_span, (span_mm or 0.0) / 2.0)
        arrow_len = style.dim_arrow_len_mm * 0.4
        arrow_w = style.dim_arrow_half_w_mm
        width = measure_text_width_mm(text, style.body_text_height_mm, style)

        if axis == "y":
            direction = outward if outward is not None else -1.0
            if not (min_x <= ax + direction * (offset + overshoot) <= max_x):
                direction = -direction
            dim_x = ax + direction * offset
            ext_end = dim_x + direction * overshoot
            self.extension_lines = (
                ((ax, ay - half_span), (ext_end, ay - half_span)),
                ((ax, ay + half_span), (ext_end, ay + half_span)),
            )
            self.leader_line = ((dim_x, ay - half_span), (dim_x, ay + half_span))
            self.arrow_lines = (
                (
                    (dim_x, ay - half_span),
                    (dim_x - direction * arrow_len, ay - half_span + arrow_w),
                ),
                (
                    (dim_x, ay - half_span),
                    (dim_x + direction * arrow_len, ay - half_span + arrow_w),
                ),
                (
                    (dim_x, ay + half_span),
                    (dim_x - direction * arrow_len, ay + half_span - arrow_w),
                ),
                (
                    (dim_x, ay + half_span),
                    (dim_x + direction * arrow_len, ay + half_span - arrow_w),
                ),
            )
            # Horizontal text beside the vertical dimension line,
            # centered on the span, on the line's outward side.
            text_x = dim_x - 1.0 - width if direction < 0 else dim_x + 1.0
            text_x = min(max(text_x, min_x), max_x - width)
            text_y = ay + style.body_text_height_mm / 3.0
            text_y = min(max(text_y, min_y + style.body_text_height_mm), max_y)
            self.text = text
            self.text_pos = (text_x, text_y)
            return

        direction = outward if outward is not None else None
        if direction is None:
            up_y = ay - offset - overshoot
            direction = -1.0 if up_y >= min_y else 1.0
        if not (min_y <= ay + direction * (offset + overshoot) <= max_y):
            direction = -direction
        dim_y = ay + direction * offset
        ext_end = dim_y + direction * overshoot

        # TWO extension lines, one projecting from each measured edge
        # (charter 41 sec. 2): left edge at `ax - half_span`, right edge
        # at `ax + half_span`, both witnessed from the feature's own `ay`.
        self.extension_lines = (
            ((ax - half_span, ay), (ax - half_span, ext_end)),
            ((ax + half_span, ay), (ax + half_span, ext_end)),
        )
        self.leader_line = (
            (ax - half_span, dim_y),
            (ax + half_span, dim_y),
        )
        # Arrowheads at BOTH ends of the dimension line, pointing along
        # the line toward its ends.
        self.arrow_lines = (
            (
                (ax - half_span, dim_y),
                (ax - half_span + arrow_len, dim_y - arrow_w),
            ),
            (
                (ax - half_span, dim_y),
                (ax - half_span + arrow_len, dim_y + arrow_w),
            ),
            (
                (ax + half_span, dim_y),
                (ax + half_span - arrow_len, dim_y - arrow_w),
            ),
            (
                (ax + half_span, dim_y),
                (ax + half_span - arrow_len, dim_y + arrow_w),
            ),
        )

        # Text CENTERED on the span, baseline just ABOVE the dimension
        # line (charter 41 sec. 2 -- never struck through by its own
        # line), clamped inside `bounds` (INV-31).
        text_x = ax - width / 2.0
        text_x = min(max(text_x, min_x), max_x - width)
        text_y = dim_y - 0.8
        text_y = min(max(text_y, min_y + style.body_text_height_mm), max_y)
        self.text = text
        self.text_pos = (text_x, text_y)


def dimension_placement(
    dim: Dimension, sheet: Sheet, style: StyleRecord
) -> tuple[str, float | None]:
    """The (axis, outward) placement hint for one dimension, read from
    where the PRODUCER anchored it relative to its view's own bbox
    (never invented data, D224 -- the anchor position already encodes
    which edge the dimension witnesses): an anchor on the view's left/
    right edge measures a span running along y (vertical dimension
    line, pushed further left/right, outward); an anchor on the top/
    bottom edge measures a span along x (horizontal line, pushed up/
    down, outward). An anchor not on any bbox edge keeps the legacy
    horizontal-with-page-top-preference placement.
    """
    view = next((v for v in sheet.views if v.name == dim.view_name), None)
    if view is None:
        return ("x", None)
    min_x, min_y, max_x, max_y = _view_bbox(view, list(sheet.entities), style)
    if max_x <= min_x or max_y <= min_y:
        return ("x", None)
    eps = 1e-6
    ax, ay = dim.anchor[0], dim.anchor[1]
    if abs(ax - min_x) < eps and min_y < ay < max_y:
        return ("y", -1.0)
    if abs(ax - max_x) < eps and min_y < ay < max_y:
        return ("y", 1.0)
    if abs(ay - min_y) < eps:
        return ("x", -1.0)
    if abs(ay - max_y) < eps:
        return ("x", 1.0)
    return ("x", None)


class ChartGeometry:
    """Axes-with-ticks, unit-labeled titles, and gridlines for a series
    sheet (charter 41 sec. 1.6/2: opt traces). Computed from the plot
    points already in the `DrawingModel` (a chart never invents data
    points, only the axis frame around them).
    """

    __slots__ = (
        "axis_lines",
        "gridlines",
        "plot_rect",
        "x_label",
        "x_max",
        "x_min",
        "x_ticks",
        "y_label",
        "y_max",
        "y_min",
        "y_ticks",
    )

    def __init__(
        self,
        points: list[tuple[float, float]],
        cell: tuple[float, float, float, float],
        style: StyleRecord,
        y_label: str,
        x_label: str = "candidate index",
    ) -> None:
        cell_x, cell_y, cell_w, cell_h = cell
        pad = style.chart_axis_pad_mm
        plot_x = cell_x + pad
        plot_y = cell_y + style.subtitle_text_height_mm + 2.0
        plot_w = max(cell_w - pad - 4.0, 10.0)
        plot_h = max(cell_h - pad - style.subtitle_text_height_mm - 6.0, 10.0)
        self.plot_rect = (plot_x, plot_y, plot_w, plot_h)

        xs = [p[0] for p in points] or [0.0, 1.0]
        ys = [p[1] for p in points] or [0.0, 1.0]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        if x_max <= x_min:
            x_max = x_min + 1.0
        if y_max <= y_min:
            y_max = y_min + 1.0
        # The data bounds are computed ONCE, from the full series, and
        # stored -- `data_to_plot`/`point` must map every later caller
        # (a single winner point included) against the SAME bounds the
        # axes were built from, or a one-point mapping degenerates to
        # the plot origin (the D238.3 iteration pass caught the winner
        # marker landing bottom-left instead of on the winning point).
        self.x_min, self.x_max = x_min, x_max
        self.y_min, self.y_max = y_min, y_max

        n = max(style.chart_gridlines, 1)
        self.gridlines: list[tuple[tuple[float, float], tuple[float, float]]] = []
        self.y_ticks: list[tuple[float, str]] = []
        for i in range(n + 1):
            frac = i / n
            gy = plot_y + plot_h - frac * plot_h
            self.gridlines.append(((plot_x, gy), (plot_x + plot_w, gy)))
            value = y_min + frac * (y_max - y_min)
            self.y_ticks.append((gy, f"{value:.4g}"))

        # WO-123 D238.3 defect 9: candidate index is an INTEGER domain --
        # integer tick steps only, and every label DISTINCT (no "0 0 1 2
        # 2" from fractional rounding). Step by whole candidates, never
        # finer than 1, and never more ticks than there are integers in
        # range.
        x_span = int(round(x_max - x_min))
        n_x = max(1, min(n, x_span)) if x_span > 0 else 1
        step = max(1, math.ceil(x_span / n_x)) if x_span > 0 else 1
        self.x_ticks = []
        seen_x: set[str] = set()
        i = 0
        while True:
            value = x_min + i * step
            if value > x_max and i > 0:
                break
            frac = 0.0 if x_max <= x_min else (value - x_min) / (x_max - x_min)
            gx = plot_x + frac * plot_w
            label = f"{value:.0f}"
            if label not in seen_x:
                seen_x.add(label)
                self.x_ticks.append((gx, label))
            if value >= x_max:
                break
            i += 1

        self.axis_lines = (
            ((plot_x, plot_y), (plot_x, plot_y + plot_h)),  # y axis
            ((plot_x, plot_y + plot_h), (plot_x + plot_w, plot_y + plot_h)),  # x axis
        )
        self.y_label = y_label
        self.x_label = x_label

    def point(self, x: float, y: float) -> tuple[float, float]:
        """Map one data-space point into this chart's plot rectangle,
        CLAMPED to the plot rect (a `_Transform`-shaped single-point
        convenience so dimensions/annotations anchored in the chart's
        data space place correctly -- charter 41 sec. 1.6: "the winner
        marked ON the chart"). A summary annotation anchored outside
        the plotted series' own data range (e.g. a termination-status
        caption anchored below every real point, WO-58's convention)
        would otherwise map outside the visible axes and collide with
        the tick labels below them (INV-31); clamping keeps every
        chart annotation ON the chart, never off it.
        """
        px, py = self.data_to_plot([(x, y)])[0]
        plot_x, plot_y, plot_w, plot_h = self.plot_rect
        # The y clamp stops one text height short of the axis line so a
        # bottom-clamped caption's baseline never coincides with the x
        # axis (which would strike the text through -- a legibility
        # defect the D238.3 visual pass caught).
        px = min(max(px, plot_x), plot_x + plot_w)
        py = min(max(py, plot_y), plot_y + plot_h - 4.0)
        return (px, py)

    @property
    def scale(self) -> float:
        """A nominal 1.0 (chart annotations are not view-scaled; their
        text height is requested as-is, matching the chart's own fixed
        typography)."""
        return 1.0

    def data_to_plot(
        self, points: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        """Map data-space `points` into this chart's plot rectangle,
        against the FULL-SERIES bounds stored at construction (so a
        single point maps to the same spot it plotted at in the series).
        """
        plot_x, plot_y, plot_w, plot_h = self.plot_rect
        x_min, x_max = self.x_min, self.x_max
        y_min, y_max = self.y_min, self.y_max
        out = []
        for x, y in points:
            px = plot_x + (x - x_min) / (x_max - x_min) * plot_w
            py = plot_y + plot_h - (y - y_min) / (y_max - y_min) * plot_h
            out.append((px, py))
        return out


def content_digest(model: DrawingModel) -> str:
    """The `DrawingModel`'s own content address (charter 41 sec. 1.1's
    title-block "design content address" field / sec. 2's provenance
    footer): a deterministic sha256 of the model's canonical JSON --
    read from the model's own bytes, never a second hand-authored id,
    and stable across runs (AD-6, no timestamp/host input).
    """
    payload = model.model_dump_json(by_alias=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def render_svg(model: DrawingModel, style: StyleRecord | None = None) -> bytes:
    """Render every sheet of `model` into one deterministic SVG document.

    Each sheet gets: a real page (`width`/`height`/`viewBox` in mm from
    its `SheetSize`), a frame border, a title block box (bottom-right)
    with the title/drawing-number/revision/scale/subject fields, and a
    deterministic view grid (charter sec. 1 decision 5) with dimension
    text offset by a fixed standoff so it never sits on top of geometry.
    Sheets are stacked top-to-bottom; entities, dimensions, annotations,
    and tables are emitted in the schema's own stable order (a renderer
    never decides order).

    `style` (WO-99 D7) supplies the drafting constants; `None` resolves to
    the neutral default pack, byte-identical to the pre-D7 output.
    """
    style = resolve_style(style)
    sheet_boxes: list[tuple[Sheet, float, float, float]] = []
    total_h = 0.0
    max_w = 0.0
    y_cursor = 0.0
    for sheet in model.sheets:
        w, h = _sheet_size_mm(sheet)
        sheet_boxes.append((sheet, w, h, y_cursor))
        y_cursor += h + style.sheet_gap_mm
        max_w = max(max_w, w)
        total_h = y_cursor - style.sheet_gap_mm if model.sheets else 0.0

    lines: list[str] = [
        f'<svg xmlns="{_NS}" version="1.1" '
        f'width="{_fmt(max_w)}mm" height="{_fmt(total_h)}mm" '
        f'viewBox="0 0 {_fmt(max_w)} {_fmt(total_h)}">',
    ]
    for i, (sheet, w, h, y_offset) in enumerate(sheet_boxes):
        lines.append(f'<g class="sheet" transform="translate(0,{_fmt(y_offset)})">')
        lines.extend(_render_sheet(sheet, w, h, style, i, len(sheet_boxes), model))
        lines.append("</g>")
    lines.append("</svg>")
    return ("\n".join(lines) + "\n").encode("ascii", errors="xmlcharrefreplace")


def _render_sheet(
    sheet: Sheet,
    w: float,
    h: float,
    style: StyleRecord,
    sheet_index: int,
    sheet_count: int,
    model: DrawingModel,
) -> list[str]:
    """The frame, title block, views, dimensions, annotations, and
    tables of one sheet, positioned within its own `w` x `h` mm page.
    """
    lines: list[str] = []
    digest = content_digest(model)
    rects, fields, footer = _sheet_furniture(
        sheet,
        w,
        h,
        style,
        sheet_index=sheet_index,
        sheet_count=sheet_count,
        content_digest=digest,
        schema_version=SCHEMA_VERSION,
    )
    for name, rx, ry, rw, rh in rects:
        lines.append(
            f'<rect class="{name}" x="{_fmt(rx)}" y="{_fmt(ry)}" '
            f'width="{_fmt(rw)}" height="{_fmt(rh)}" fill="none" stroke="black"/>'
        )
    for field in fields:
        lx, ly = field.label_pos
        vx, vy = field.value_pos
        lines.append(
            f'<text class="title-block-label" x="{_fmt(lx)}" y="{_fmt(ly)}" '
            f'font-size="{_fmt(style.caption_text_height_mm)}">{_text(field.label)}</text>'
        )
        for line in field.value_lines:
            lines.append(
                f'<text class="title-block-value" x="{_fmt(vx)}" y="{_fmt(vy)}" '
                f'font-size="{_fmt(style.body_text_height_mm)}">{_text(line)}</text>'
            )
            vy += field.value_line_h
    fx, fy, ftext = footer
    lines.append(
        f'<text class="footer" x="{_fmt(fx)}" y="{_fmt(fy)}" '
        f'font-size="{_fmt(style.caption_text_height_mm)}">{_text(ftext)}</text>'
    )
    for zx, zy, ztext in _zone_marks(w, h, style):
        lines.append(
            f'<text class="zone-mark" x="{_fmt(zx)}" y="{_fmt(zy)}" '
            f'font-size="{_fmt(style.caption_text_height_mm)}">{_text(ztext)}</text>'
        )

    margin = style.margin_mm
    content_x = margin
    content_y = margin
    content_w = w - 2 * margin
    if sheet.views:
        content_h = h - 2 * margin - style.title_block_h_mm - style.content_gap_mm
    else:
        content_h = 1.0
    content_area = (content_x, content_y, content_w, max(content_h, 1.0))
    transforms = _view_transforms(sheet, content_area, style)
    cells = _view_cells(sheet, content_area, style)
    bounds = (margin, margin, w - margin, h - margin - style.title_block_h_mm)

    is_chart = any(v.source.source_kind == "optimize.trace" for v in sheet.views)
    chart_geometry: ChartGeometry | None = None
    for view in sheet.views:
        transform = transforms.get(view.name, _IDENTITY)
        if is_chart:
            entities = [sheet.entities[int(i.root)] for i in view.entity_indices]
            points = [
                (e.from_[0], e.from_[1])
                for e in entities
                if isinstance(e, SegmentEntity)
            ]
            if entities and isinstance(entities[-1], SegmentEntity):
                last_to = entities[-1].to
                points.append((last_to[0], last_to[1]))
            chart_geometry = ChartGeometry(
                points, cells.get(view.name, bounds), style, "objective"
            )
            lines.extend(_render_chart_svg(chart_geometry, points, view.name, style))
        else:
            lines.append(
                f'<g class="view" data-view="{_text(view.name)}" '
                f'transform="{transform.attr()}">'
            )
            for idx in view.entity_indices:
                lines.append(_render_entity(sheet.entities[int(idx.root)]))
            lines.append("</g>")
        # Charter 41 sec. 1.2: per-view label + scale under each view.
        cell_x, cell_y, cell_w, cell_h = cells.get(view.name, bounds)
        lines.append(
            f'<text class="view-label" x="{_fmt(cell_x + cell_w / 2.0)}" '
            f'y="{_fmt(cell_y + cell_h - 1.0)}" text-anchor="middle" '
            f'font-size="{_fmt(style.caption_text_height_mm)}">'
            f"{_text(_view_label_text(view))}</text>"
        )

    for dim in sheet.dimensions:
        transform = transforms.get(dim.view_name, _IDENTITY)
        lines.append(_render_dimension(dim, transform, style, bounds, sheet))

    if chart_geometry is not None:
        for ann in sheet.annotations:
            if ann.text.startswith("winner:"):
                mx, my = chart_geometry.point(ann.anchor[0], ann.anchor[1])
                for (x1, y1), (x2, y2) in _chart_marker_lines(mx, my, 2.0):
                    lines.append(
                        f'<line class="chart-winner-marker" x1="{_fmt(x1)}" '
                        f'y1="{_fmt(y1)}" x2="{_fmt(x2)}" y2="{_fmt(y2)}" '
                        f'stroke="black" stroke-width="0.4"/>'
                    )

    annotation_transform: _Transform | ChartGeometry = (
        chart_geometry
        if chart_geometry is not None
        else (next(iter(transforms.values())) if len(transforms) == 1 else _IDENTITY)
    )
    for ann_index, ann in enumerate(sheet.annotations):
        lines.extend(
            _render_annotation(
                ann, annotation_transform, style, bounds, ladder_index=ann_index
            )
        )

    table_y = content_y + content_h + style.content_gap_mm
    for table in sheet.tables:
        table_max_w = table_fit_max_width(
            table,
            content_x,
            table_y + style.subtitle_text_height_mm + 1.0,
            style,
            w,
            h,
        )
        table_y = _render_table_svg(
            lines, table, content_x, table_y, style, table_max_w
        )
    return lines


def _render_table_svg(
    lines: list[str],
    table: Table,
    x: float,
    y: float,
    style: StyleRecord,
    max_width: float,
) -> float:
    """One ruled table (charter 41 sec. 1.5): a bordered header row +
    body rows with per-column alignment, wrapped (never clipped,
    INV-31) within `max_width`, appended to `lines`. Returns the next
    free y below the rendered block.
    """
    lines.append(
        f'<text class="table-title" x="{_fmt(x)}" y="{_fmt(y)}" '
        f'font-size="{_fmt(style.subtitle_text_height_mm)}">{_text(table.title)}</text>'
    )
    y += style.subtitle_text_height_mm + 1.0
    layout = TableLayout(table, x, y, style, max_width=max_width)
    lines.append(
        f'<rect class="table-frame" x="{_fmt(x)}" y="{_fmt(y)}" '
        f'width="{_fmt(layout.total_w)}" height="{_fmt(layout.total_h)}" '
        f'fill="none" stroke="black"/>'
    )
    for cx in [x, *[x + w for w in _cumulative(layout.col_widths)]]:
        lines.append(
            f'<line class="table-rule" x1="{_fmt(cx)}" y1="{_fmt(y)}" '
            f'x2="{_fmt(cx)}" y2="{_fmt(y + layout.total_h)}" stroke="black"/>'
        )
    header_y = y + layout.header_h
    lines.append(
        f'<line class="table-rule" x1="{_fmt(x)}" y1="{_fmt(header_y)}" '
        f'x2="{_fmt(x + layout.total_w)}" y2="{_fmt(header_y)}" stroke="black"/>'
    )
    for c, name in enumerate(table.columns):
        cx = layout.col_x[c] + style.table_cell_pad_mm
        lines.append(
            f'<text class="table-header" x="{_fmt(cx)}" '
            f'y="{_fmt(y + layout.header_h - 1.5)}" '
            f'font-size="{_fmt(style.caption_text_height_mm)}">{_text(name)}</text>'
        )
    for r in range(len(table.rows)):
        row_top = layout.row_y[r] - layout.row_heights[r]
        for c in range(len(table.columns)):
            cx = layout.col_x[c] + style.table_cell_pad_mm
            cy = row_top + style.body_text_height_mm
            for line in layout.cell_lines[(r, c)]:
                lines.append(
                    f'<text class="table-cell" x="{_fmt(cx)}" y="{_fmt(cy)}" '
                    f'font-size="{_fmt(style.body_text_height_mm)}">{_text(line)}</text>'
                )
                cy += style.body_text_height_mm + 0.5
    return y + layout.total_h + style.content_gap_mm


def _cumulative(widths: list[float]) -> list[float]:
    """Running totals of `widths` (excluding the trailing edge)."""
    total = 0.0
    out = []
    for w in widths:
        total += w
        out.append(total)
    return out


def _render_chart_svg(
    chart: ChartGeometry,
    points: list[tuple[float, float]],
    view_name: str,
    style: StyleRecord,
) -> list[str]:
    """Axes, ticks, gridlines, and the plotted polyline for one chart
    view (charter 41 sec. 1.6)."""
    lines = [f'<g class="chart" data-view="{_text(view_name)}">']
    for (x1, y1), (x2, y2) in chart.gridlines:
        lines.append(
            f'<line class="chart-gridline" x1="{_fmt(x1)}" y1="{_fmt(y1)}" '
            f'x2="{_fmt(x2)}" y2="{_fmt(y2)}" stroke="gray" stroke-width="0.1"/>'
        )
    for gy, label in chart.y_ticks:
        lines.append(
            f'<text class="chart-tick" x="{_fmt(chart.plot_rect[0] - 2.0)}" '
            f'y="{_fmt(gy)}" font-size="{_fmt(style.caption_text_height_mm)}">'
            f"{_text(label)}</text>"
        )
    tick_y = (
        chart.plot_rect[1] + chart.plot_rect[3] + style.caption_text_height_mm + 1.0
    )
    for gx, label in chart.x_ticks:
        lines.append(
            f'<text class="chart-tick" x="{_fmt(gx)}" y="{_fmt(tick_y)}" '
            f'font-size="{_fmt(style.caption_text_height_mm)}">{_text(label)}</text>'
        )
    for (x1, y1), (x2, y2) in chart.axis_lines:
        lines.append(
            f'<line class="chart-axis" x1="{_fmt(x1)}" y1="{_fmt(y1)}" '
            f'x2="{_fmt(x2)}" y2="{_fmt(y2)}" stroke="black" stroke-width="0.3"/>'
        )
    # Charter 41 sec. 1.6: unit-labeled axis titles.
    plot_x, plot_y, plot_w, plot_h = chart.plot_rect
    lines.append(
        f'<text class="chart-axis-title" x="{_fmt(plot_x + plot_w / 2.0)}" '
        f'y="{_fmt(tick_y + style.caption_text_height_mm + 2.0)}" '
        f'text-anchor="middle" font-size="{_fmt(style.caption_text_height_mm)}">'
        f"{_text(chart.x_label)}</text>"
    )
    # The y title sits a full caption line ABOVE the top tick label so
    # the two never collide (D238.3 iteration finding).
    y_title_x = plot_x - style.chart_axis_pad_mm + 2.0
    lines.append(
        f'<text class="chart-axis-title" x="{_fmt(y_title_x)}" '
        f'y="{_fmt(plot_y - style.caption_text_height_mm - 2.0)}" '
        f'font-size="{_fmt(style.caption_text_height_mm)}">'
        f"{_text(chart.y_label)}</text>"
    )
    plotted = chart.data_to_plot(points)
    if len(plotted) > 1:
        pts = " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in plotted)
        lines.append(
            f'<polyline class="chart-series" points="{pts}" '
            f'fill="none" stroke="black"/>'
        )
    lines.append("</g>")
    return lines


def _chart_marker_lines(
    cx: float, cy: float, half: float
) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    """A small diamond marker (two crossed strokes) at one chart point --
    the WINNER marker (charter 41 sec. 1.6/2: "the winner marked ON the
    chart"), shared by SVG/PDF so both mark the same point identically.
    """
    return (
        ((cx - half, cy), (cx, cy - half)),
        ((cx, cy - half), (cx + half, cy)),
        ((cx + half, cy), (cx, cy + half)),
        ((cx, cy + half), (cx - half, cy)),
    )


def _render_dimension(
    dim: Dimension,
    transform: _Transform,
    style: StyleRecord,
    bounds: tuple[float, float, float, float],
    sheet: Sheet,
) -> str:
    """A dimension as real extension lines + a dimension line spanning
    between them + arrowheads at both ends + value(+unit+tolerance)
    text, clamped inside `bounds` (charter 41 sec. 2 / INV-31: never on
    top of the geometry, never off the page).
    """
    anchor = transform.point(dim.anchor[0], dim.anchor[1])
    tol = f" +/-{dim.tolerance[0]:.4g}/{dim.tolerance[1]:.4g}" if dim.tolerance else ""
    # WO-123 D238.3 defect 6: human value only ("80.00 mm"), no payload-
    # path prefix -- matches `renderer_pdf._render_dimension`.
    text = f"{dim.value:.2f} {dim.unit}{tol}"
    span_mm = dim.value * transform.scale
    axis, outward = dimension_placement(dim, sheet, style)
    geo = DimensionGeometry(
        anchor, text, style, bounds, span_mm=span_mm, axis=axis, outward=outward
    )
    (lx1, ly1), (lx2, ly2) = geo.leader_line
    tx, ty = geo.text_pos
    parts = [
        f'<line class="dim-line" x1="{_fmt(lx1)}" y1="{_fmt(ly1)}" '
        f'x2="{_fmt(lx2)}" y2="{_fmt(ly2)}" stroke="black" stroke-width="0.15"/>',
    ]
    for (ex1, ey1), (ex2, ey2) in geo.extension_lines:
        parts.append(
            f'<line class="dim-extension" x1="{_fmt(ex1)}" y1="{_fmt(ey1)}" '
            f'x2="{_fmt(ex2)}" y2="{_fmt(ey2)}" stroke="black" stroke-width="0.15"/>'
        )
    for (ax1, ay1), (ax2, ay2) in geo.arrow_lines:
        parts.append(
            f'<line class="dim-arrow" x1="{_fmt(ax1)}" y1="{_fmt(ay1)}" '
            f'x2="{_fmt(ax2)}" y2="{_fmt(ay2)}" stroke="black" stroke-width="0.15"/>'
        )
    parts.append(
        f'<text class="dimension" x="{_fmt(tx)}" y="{_fmt(ty)}" '
        f'font-size="{_fmt(style.body_text_height_mm)}">{_text(geo.text)}</text>'
    )
    return "".join(parts)


def _render_annotation(
    ann: Annotation,
    transform: _Transform | ChartGeometry,
    style: StyleRecord,
    bounds: tuple[float, float, float, float],
    *,
    ladder_index: int = 0,
) -> list[str]:
    """One annotation, wrapped/shrunk to fit inside `bounds` (charter 41
    sec. 1.4 / INV-31 -- an annotation never clips the page edge) and
    mapped through its owning view's transform (v1 simplification:
    `Annotation` carries no `view_name`, so a sheet with more than one
    view falls back to identity placement -- every current producer
    emits at most one view per sheet). `ladder_index` staggers
    successive CHART annotations (see `renderer_pdf._render_annotation`'s
    matching docstring).
    """
    x, y = transform.point(ann.anchor[0], ann.anchor[1])
    min_x, min_y, max_x, max_y = bounds
    if ladder_index:
        # A laddered CHART caption additionally clears the x-tick label
        # row below the axis (caption height + padding) so it never
        # prints through a tick label (D238.3 visual-pass finding).
        tick_clearance = (
            style.caption_text_height_mm + 3.0
            if isinstance(transform, ChartGeometry)
            else 0.0
        )
        y = min(
            y + ladder_index * (style.body_text_height_mm * 2.0 + 2.0) + tick_clearance,
            max_y,
        )
    # INV-31: clamp the ANCHOR itself inside the frame first -- an
    # extreme-aspect-ratio view (a long thin part) can place a
    # feature-local annotation anchor outside the fit-to-cell entity
    # bbox's own placement, landing off-page before any wrap/shrink
    # even runs (the `no-clipping` rule's own regression, F135.1).
    floor_width = style.min_text_height_mm * 8.0
    if isinstance(transform, ChartGeometry) and ann.text.startswith("winner:"):
        # WO-123 (D238.4 defect 3): the winner label anchors at the SAME
        # point as `_chart_marker_lines`' diamond (half-size 2.0mm) --
        # unoffset, the label prints on top of its own marker. Offset
        # clear of the marker on whichever side leaves room inside the
        # frame (right by default, flipping left -- ending BEFORE the
        # marker using the label's own measured width, not just the
        # generic floor width -- near the right edge) so neither the
        # marker nor the label touches the other or the frame.
        gap = 2.0 + 2.0
        label_w = measure_text_width_mm(ann.text, ann.text_height_mm, style)
        if x + gap + max(label_w, floor_width) <= max_x:
            x = x + gap
        else:
            x = max(x - gap - label_w, min_x)
    x = min(max(x, min_x), max_x - floor_width)
    max_width = max(max_x - x, floor_width)
    requested_height = ann.text_height_mm * min(transform.scale, 1.0)
    height, lines_of_text = fit_text(
        ann.text, max_width, max_y - y, requested_height, style
    )
    out = []
    ty = min(max(y, min_y + height), max_y)
    for line in lines_of_text:
        out.append(
            f'<text class="annotation" x="{_fmt(x)}" y="{_fmt(ty)}" '
            f'font-size="{_fmt(height)}">{_text(line)}</text>'
        )
        ty += height + 0.5
    return out


def _render_entity(entity: _Entity) -> str:
    """Render one sheet entity (segment/arc/polyline/symbol) as SVG, in
    its owning view's local space (the enclosing `<g transform=...>`
    maps it into sheet space).
    """
    if isinstance(entity, SegmentEntity):
        return (
            f'<line class="segment" x1="{_fmt(entity.from_[0])}" '
            f'y1="{_fmt(entity.from_[1])}" x2="{_fmt(entity.to[0])}" '
            f'y2="{_fmt(entity.to[1])}" stroke="black"/>'
        )
    if isinstance(entity, ArcEntity):
        return (
            f'<circle class="arc" cx="{_fmt(entity.center[0])}" '
            f'cy="{_fmt(entity.center[1])}" r="{_fmt(entity.radius)}" '
            f'fill="none" stroke="black"/>'
        )
    if isinstance(entity, PolylineEntity):
        points = " ".join(f"{_fmt(p.root[0])},{_fmt(p.root[1])}" for p in entity.points)
        return (
            f'<polyline class="polyline" points="{points}" fill="none" stroke="black"/>'
        )
    return (
        f'<use class="symbol" x="{_fmt(entity.origin[0])}" '
        f'y="{_fmt(entity.origin[1])}" '
        f'data-record="{entity.record_digest}"/>'
    )
