"""The PDF renderer: a sibling of the SVG reference renderer over the
SAME `DrawingModel` IR (charter sec. 1 decision 2). A minimal,
dependency-free, hand-rolled PDF 1.4: one page per sheet, `m`/`l`/`S`
line operators for projected geometry, `re` rectangles for the sheet
frame + title-block furniture, `Tj` text operators for title-block/
dimension/annotation/table text, base-14 Helvetica (no font embedding).
Deterministic byte output: no `/CreationDate`, no `/ID` (both are
time/host-derived in a normal PDF writer and would break AD-6's
byte-identical-goldens rule). Reuses the SVG renderer's own view
grid-cell layout math (no second layout mechanism).
"""

from __future__ import annotations

import math

from regolith._schema import SCHEMA_VERSION
from regolith._schema.models import Annotation, Dimension, DrawingModel, Sheet, Table
from regolith._schema.models import Entity1 as SegmentEntity
from regolith._schema.models import Entity2 as ArcEntity
from regolith._schema.models import Entity3 as PolylineEntity
from regolith._schema.models import Entity4 as SymbolEntity
from regolith.backends.drawings.renderer import (
    _IDENTITY,
    ChartGeometry,
    DimensionGeometry,
    TableLayout,
    _chart_marker_lines,
    _sheet_furniture,
    _sheet_size_mm,
    _Transform,
    _view_cells,
    _view_label_text,
    _view_transforms,
    _zone_marks,
    content_digest,
    dimension_placement,
    fit_text,
    measure_text_width_mm,
    table_fit_max_width,
)
from regolith.backends.drawings.style import StyleRecord, resolve_style
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# 1 mm = 1/25.4 in = 72/25.4 pt (a fixed rounding rule, applied at
# every mm -> pt conversion so the same input always rounds the same
# way -- AD-6).
_MM_TO_PT = 72.0 / 25.4


def _pt(mm: float) -> float:
    """Convert one mm value to PDF points under the fixed rounding rule."""
    return round(mm * _MM_TO_PT, 4)


def _num(value: float) -> str:
    """A stable, locale-independent float format for PDF content-stream
    operands and array entries.
    """
    return f"{value:.4f}"


def _pdf_text(value: str) -> str:
    """Escape a string for a PDF literal-string text-show operand.

    Non-ASCII characters are lossily replaced with `?` (documented,
    logged contract, L2 -- the drawings backend has no `Result`-return
    seam at this leaf); parens/backslashes are backslash-escaped per
    the PDF literal-string grammar, which is what makes embedded
    newlines safe here (unlike DXF's line-paired text groups, M2).
    """
    escaped = value.encode("ascii", errors="replace").decode("ascii")
    if escaped != value:
        _log.warning("PDF text: non-ASCII character(s) replaced with '?' in %r", value)
    return escaped.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


class _ContentBuilder:
    """Accumulates one page's content-stream operators in emission order
    (the schema's own stable order; a renderer never re-sorts, AD-27).
    """

    def __init__(self) -> None:
        self._ops: list[str] = []

    # frob:doc docs/modules/py-backends.md#drawings-renderer-pdf
    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        width_pt: float | None = None,
        gray: float | None = None,
    ) -> None:
        """One stroked line segment: `moveto` + `lineto` + `stroke`.

        `width_pt` (WO-123 D238.3 defect 12) sets the PDF `w` line-width
        operator before stroking so gridlines can render at a lighter,
        minor-emphasis weight than axes/series -- omitted, it leaves the
        content stream's current (default) width untouched.

        `gray` (WO-123 D238.4 defect 2) sets the PDF `G` stroke-gray
        operator (0.0 black .. 1.0 white) before stroking -- a THIN line
        width alone reads identically to a normal-weight line once
        rasterized at typical review resolution (the coordinator's own
        finding), so gridlines additionally need a genuinely lighter
        gray, not just a thinner black stroke. Omitted, it leaves the
        content stream's current (default black) color untouched.
        """
        if gray is not None:
            self._ops.append(f"{_num(gray)} G")
        if width_pt is not None:
            self._ops.append(f"{_num(width_pt)} w")
        self._ops.append(f"{_num(x1)} {_num(y1)} m")
        self._ops.append(f"{_num(x2)} {_num(y2)} l")
        self._ops.append("S")

    # frob:doc docs/modules/py-backends.md#drawings-renderer-pdf
    def rect(self, x: float, y: float, w: float, h: float) -> None:
        """One stroked rectangle via the `re` path operator."""
        self._ops.append(f"{_num(x)} {_num(y)} {_num(w)} {_num(h)} re")
        self._ops.append("S")

    # frob:doc docs/modules/py-backends.md#drawings-renderer-pdf
    def text(self, x: float, y: float, size_pt: float, value: str) -> None:
        """One text-show operator at an absolute page position."""
        self._ops.append("BT")
        self._ops.append(f"/F1 {_num(size_pt)} Tf")
        self._ops.append(f"{_num(x)} {_num(y)} Td")
        self._ops.append(f"({_pdf_text(value)}) Tj")
        self._ops.append("ET")

    # frob:doc docs/modules/py-backends.md#drawings-renderer-pdf
    def to_bytes(self) -> bytes:
        """The finished content stream as PDF-safe (ASCII) bytes."""
        return ("\n".join(self._ops) + "\n").encode("ascii", errors="replace")


def _entity_index_transforms(
    sheet: Sheet, transforms: dict[str, _Transform]
) -> dict[int, _Transform]:
    """Map each entity index to its owning view's transform (identity
    for an entity no view references -- never happens for a well-formed
    producer output, but stays total; matches `renderer_dxf`'s helper).
    """
    by_index: dict[int, _Transform] = {}
    for view in sheet.views:
        transform = transforms.get(view.name, _IDENTITY)
        for idx in view.entity_indices:
            by_index[int(idx.root)] = transform
    return by_index


def _content_area(
    sheet: Sheet, w: float, h: float, style: StyleRecord
) -> tuple[float, float, float, float]:
    """The same content-area rectangle the SVG/DXF renderers lay views
    into (kept identical so all three renderers agree on placement).

    A sheet with NO views (charter 41 sec. 2: a calc sheet has no
    drawing view, only tables) reserves no view real estate -- tables
    start right under the margin instead of after a blank page-height
    gap sized for a view that was never going to be drawn.
    """
    margin = style.margin_mm
    content_x = margin
    content_y = margin
    content_w = w - 2 * margin
    if not sheet.views:
        return (content_x, content_y, content_w, 1.0)
    content_h = h - 2 * margin - style.title_block_h_mm - style.content_gap_mm
    return (content_x, content_y, content_w, max(content_h, 1.0))


def _to_page(x_mm: float, y_mm: float, page_h_pt: float) -> tuple[float, float]:
    """mm (y-down, this codebase's sheet-space convention) -> PDF pt
    (y-up, PDF page-space convention): scale then flip about the page
    height.
    """
    return (_pt(x_mm), page_h_pt - _pt(y_mm))


def _render_entity(
    entity: SegmentEntity | ArcEntity | PolylineEntity | SymbolEntity,
    transform: _Transform,
    page_h_pt: float,
    builder: _ContentBuilder,
    style: StyleRecord,
) -> None:
    """One sheet entity as PDF line operators: segment/polyline -> one
    line per segment; arc -> an octagon stand-in (no curve operator
    needed for v1's straight-line-only content stream); symbol -> a
    small square marker (v1 has no per-symbol glyph to place).
    """
    if isinstance(entity, SegmentEntity):
        x1, y1 = transform.point(entity.from_[0], entity.from_[1])
        x2, y2 = transform.point(entity.to[0], entity.to[1])
        p1 = _to_page(x1, y1, page_h_pt)
        p2 = _to_page(x2, y2, page_h_pt)
        builder.line(p1[0], p1[1], p2[0], p2[1])
        return
    if isinstance(entity, PolylineEntity):
        points = [transform.point(p.root[0], p.root[1]) for p in entity.points]
        for (x1, y1), (x2, y2) in zip(points, points[1:], strict=False):
            p1 = _to_page(x1, y1, page_h_pt)
            p2 = _to_page(x2, y2, page_h_pt)
            builder.line(p1[0], p1[1], p2[0], p2[1])
        return
    if isinstance(entity, ArcEntity):
        cx, cy = transform.point(entity.center[0], entity.center[1])
        r = entity.radius * transform.scale
        sides = 8
        verts = [
            (
                cx + r * math.cos(2 * math.pi * i / sides),
                cy + r * math.sin(2 * math.pi * i / sides),
            )
            for i in range(sides + 1)
        ]
        for (x1, y1), (x2, y2) in zip(verts, verts[1:], strict=False):
            p1 = _to_page(x1, y1, page_h_pt)
            p2 = _to_page(x2, y2, page_h_pt)
            builder.line(p1[0], p1[1], p2[0], p2[1])
        return
    ox, oy = transform.point(entity.origin[0], entity.origin[1])
    half = style.symbol_half_mm
    corners = [
        (ox - half, oy - half),
        (ox + half, oy - half),
        (ox + half, oy + half),
        (ox - half, oy + half),
        (ox - half, oy - half),
    ]
    for (x1, y1), (x2, y2) in zip(corners, corners[1:], strict=False):
        p1 = _to_page(x1, y1, page_h_pt)
        p2 = _to_page(x2, y2, page_h_pt)
        builder.line(p1[0], p1[1], p2[0], p2[1])


def _render_dimension(
    dim: Dimension,
    transform: _Transform,
    page_h_pt: float,
    builder: _ContentBuilder,
    style: StyleRecord,
    bounds: tuple[float, float, float, float],
    sheet: Sheet,
) -> None:
    """A real dimension entity (charter 41 sec. 2): two extension
    lines, a dimension line spanning between them, arrowheads at both
    ends, and value+unit(+tolerance) text -- clamped inside `bounds`
    so it never clips the page edge or sits on top of the witnessed
    geometry (INV-31).
    """
    anchor = transform.point(dim.anchor[0], dim.anchor[1])
    tol = f" +/-{dim.tolerance[0]:.4g}/{dim.tolerance[1]:.4g}" if dim.tolerance else ""
    # WO-123 D238.3 defect 6: the human-readable value, not the payload
    # path -- "80.00 mm", never "bbox.depth=80.0000mm" (the `role` path
    # is still on the schema's `Dimension.role` field for a consumer
    # that wants it; the renderer just stops printing it inline).
    text = f"{dim.value:.2f} {dim.unit}{tol}"
    span_mm = dim.value * transform.scale
    axis, outward = dimension_placement(dim, sheet, style)
    geo = DimensionGeometry(
        anchor, text, style, bounds, span_mm=span_mm, axis=axis, outward=outward
    )
    for (x1, y1), (x2, y2) in (
        geo.leader_line,
        *geo.extension_lines,
        *geo.arrow_lines,
    ):
        p1 = _to_page(x1, y1, page_h_pt)
        p2 = _to_page(x2, y2, page_h_pt)
        builder.line(p1[0], p1[1], p2[0], p2[1])
    tx, ty = geo.text_pos
    px, py = _to_page(tx, ty, page_h_pt)
    builder.text(px, py, _pt(style.body_text_height_mm), geo.text)


def _render_annotation(
    ann: Annotation,
    transform: _Transform | ChartGeometry,
    page_h_pt: float,
    builder: _ContentBuilder,
    style: StyleRecord,
    bounds: tuple[float, float, float, float],
    *,
    ladder_index: int = 0,
) -> None:
    """An annotation's text, wrapped/shrunk-to-floor to fit inside
    `bounds` (charter 41 sec. 1.4 / INV-31): never clips the page edge.
    `ladder_index` (charter 25's standoff-ladder convention, reused
    here) staggers successive CHART annotations vertically so two
    summary captions anchored near the same clamped chart edge (e.g.
    "winner" + "termination", WO-58's convention) do not print on top
    of each other.
    """
    x, y = transform.point(ann.anchor[0], ann.anchor[1])
    min_x, min_y, max_x, max_y = bounds
    if ladder_index:
        # Mirror `renderer._render_annotation`: a laddered CHART caption
        # additionally clears the x-tick label row (D238.3 finding).
        tick_clearance = (
            style.caption_text_height_mm + 3.0
            if isinstance(transform, ChartGeometry)
            else 0.0
        )
        y = min(
            y + ladder_index * (style.body_text_height_mm * 2.0 + 2.0) + tick_clearance,
            max_y,
        )
    # INV-31: clamp the ANCHOR itself inside the frame first (mirrors
    # `renderer._render_annotation`'s matching comment).
    floor_width = style.min_text_height_mm * 8.0
    if isinstance(transform, ChartGeometry) and ann.text.startswith("winner:"):
        # WO-123 (D238.4 defect 3): mirrors `renderer._render_annotation`
        # -- offset the winner label clear of its own marker (half-size
        # 2.0mm, `_chart_marker_lines`), flipping to the left of the
        # marker (ending BEFORE it, using the label's own measured
        # width -- not just the generic floor width) when there is no
        # room to the right before the frame edge.
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
    ty = min(max(y, min_y + height), max_y)
    for line in lines_of_text:
        px, py = _to_page(x, ty, page_h_pt)
        builder.text(px, py, _pt(height), line)
        ty += height + 0.5


def _render_table(
    table: Table,
    x_mm: float,
    y_mm: float,
    page_h_pt: float,
    builder: _ContentBuilder,
    style: StyleRecord,
    max_width: float,
) -> float:
    """A ruled table (charter 41 sec. 1.5): bordered header + body rows
    with per-column alignment, no pipe-delimited prose, wrapped (never
    clipped, INV-31) within `max_width`. Returns the next free y (mm,
    sheet-space) below the rendered block.
    """
    py_title = _to_page(x_mm, y_mm, page_h_pt)
    builder.text(
        py_title[0], py_title[1], _pt(style.subtitle_text_height_mm), table.title
    )
    y = y_mm + style.subtitle_text_height_mm + 1.0
    layout = TableLayout(table, x_mm, y, style, max_width=max_width)

    top = _to_page(x_mm, y, page_h_pt)
    builder.rect(
        top[0], top[1] - _pt(layout.total_h), _pt(layout.total_w), _pt(layout.total_h)
    )
    col_edges = [x_mm]
    running = x_mm
    for w in layout.col_widths:
        running += w
        col_edges.append(running)
    for cx in col_edges:
        p1 = _to_page(cx, y, page_h_pt)
        p2 = _to_page(cx, y + layout.total_h, page_h_pt)
        builder.line(p1[0], p1[1], p2[0], p2[1])
    header_bottom = y + layout.header_h
    p1 = _to_page(x_mm, header_bottom, page_h_pt)
    p2 = _to_page(x_mm + layout.total_w, header_bottom, page_h_pt)
    builder.line(p1[0], p1[1], p2[0], p2[1])

    for c, name in enumerate(table.columns):
        cx = layout.col_x[c] + style.table_cell_pad_mm
        px, py = _to_page(cx, y + layout.header_h - 1.5, page_h_pt)
        builder.text(px, py, _pt(style.caption_text_height_mm), name)
    for r in range(len(table.rows)):
        row_top = layout.row_y[r] - layout.row_heights[r]
        for c in range(len(table.columns)):
            cx = layout.col_x[c] + style.table_cell_pad_mm
            cy = row_top + style.body_text_height_mm
            for line in layout.cell_lines[(r, c)]:
                px, py = _to_page(cx, cy, page_h_pt)
                builder.text(px, py, _pt(style.body_text_height_mm), line)
                cy += style.body_text_height_mm + 0.5
    return y + layout.total_h + style.content_gap_mm

# frob:waive PERF003 reason="O(1) check against a fixed small set, not nested"
def _render_chart(
    chart: ChartGeometry,
    points: list[tuple[float, float]],
    page_h_pt: float,
    builder: _ContentBuilder,
    style: StyleRecord,
    winner_anchor: tuple[float, float] | None = None,
) -> None:
    """Axes with ticks, gridlines, and the plotted series (charter 41
    sec. 1.6 / sec. 2: opt-trace convergence charts). Gridlines render
    at the style's thin (minor-emphasis) weight AND a lighter gray
    (D238.4 defect 2: a thinner black stroke alone reads identically to
    a normal-weight line once rasterized at review resolution) so data
    reads first and the grid recedes; axes/series render at normal
    weight, solid black. `winner_anchor` (data-space), when given,
    marks the winning candidate ON the chart (defect 11).
    """
    grid_w = _pt(style.line_weight_thin_mm)
    normal_w = _pt(style.line_weight_normal_mm)
    for (x1, y1), (x2, y2) in chart.gridlines:
        p1 = _to_page(x1, y1, page_h_pt)
        p2 = _to_page(x2, y2, page_h_pt)
        builder.line(p1[0], p1[1], p2[0], p2[1], width_pt=grid_w, gray=0.65)
    for gy, label in chart.y_ticks:
        px, py = _to_page(chart.plot_rect[0] - 8.0, gy, page_h_pt)
        builder.text(px, py, _pt(style.caption_text_height_mm), label)
    for gx, label in chart.x_ticks:
        py_y = (
            chart.plot_rect[1] + chart.plot_rect[3] + style.caption_text_height_mm + 1.0
        )
        px, py = _to_page(gx, py_y, page_h_pt)
        builder.text(px, py, _pt(style.caption_text_height_mm), label)
    for i, ((x1, y1), (x2, y2)) in enumerate(chart.axis_lines):
        p1 = _to_page(x1, y1, page_h_pt)
        p2 = _to_page(x2, y2, page_h_pt)
        # Explicit black reset (D238.4 defect 2): the gridline loop above
        # left the PDF stroke-gray state at 0.65 -- the FIRST axis line
        # resets it to solid black so axes/series never inherit the
        # grid's lighter color.
        builder.line(
            p1[0], p1[1], p2[0], p2[1], width_pt=normal_w, gray=0.0 if i == 0 else None
        )
    # Charter 41 sec. 1.6: unit-labeled axis titles.
    plot_x, plot_y, plot_w, plot_h = chart.plot_rect
    title_y = (
        chart.plot_rect[1] + chart.plot_rect[3] + 2 * style.caption_text_height_mm + 2.0
    )
    tpx, tpy = _to_page(plot_x + plot_w / 2.0, title_y, page_h_pt)
    builder.text(tpx, tpy, _pt(style.caption_text_height_mm), chart.x_label)
    # The y title sits a full caption line ABOVE the top tick label so
    # the two never collide (D238.3 iteration finding).
    ypx, ypy = _to_page(
        plot_x - style.chart_axis_pad_mm + 2.0,
        plot_y - style.caption_text_height_mm - 2.0,
        page_h_pt,
    )
    builder.text(ypx, ypy, _pt(style.caption_text_height_mm), chart.y_label)
    plotted = chart.data_to_plot(points)
    for (x1, y1), (x2, y2) in zip(plotted, plotted[1:], strict=False):
        p1 = _to_page(x1, y1, page_h_pt)
        p2 = _to_page(x2, y2, page_h_pt)
        builder.line(p1[0], p1[1], p2[0], p2[1], width_pt=normal_w)
    if winner_anchor is not None:
        mx, my = chart.point(winner_anchor[0], winner_anchor[1])
        for (x1, y1), (x2, y2) in _chart_marker_lines(mx, my, 2.0):
            p1 = _to_page(x1, y1, page_h_pt)
            p2 = _to_page(x2, y2, page_h_pt)
            builder.line(p1[0], p1[1], p2[0], p2[1], width_pt=normal_w)


def _render_furniture(
    sheet: Sheet,
    w_mm: float,
    h_mm: float,
    page_h_pt: float,
    builder: _ContentBuilder,
    style: StyleRecord,
    *,
    sheet_index: int,
    sheet_count: int,
    digest: str,
) -> None:
    """The sheet frame + NAMED title-block fields + provenance footer
    (`renderer._sheet_furniture`, the one shared layout home) as `re`
    rectangle operators + text lines (charter 41 sec. 1.1).
    """
    rects, fields, footer = _sheet_furniture(
        sheet,
        w_mm,
        h_mm,
        style,
        sheet_index=sheet_index,
        sheet_count=sheet_count,
        content_digest=digest,
        schema_version=SCHEMA_VERSION,
    )
    for _name, rx, ry, rw, rh in rects:
        # A sheet-space (y-down) rect's bottom edge is ry + rh; in PDF
        # page space (y-up) that edge is the rect origin.
        px, py = _to_page(rx, ry + rh, page_h_pt)
        builder.rect(px, py, _pt(rw), _pt(rh))
    for field in fields:
        lx, ly = field.label_pos
        vx, vy = field.value_pos
        plx, ply = _to_page(lx, ly, page_h_pt)
        builder.text(plx, ply, _pt(style.caption_text_height_mm), field.label)
        for line in field.value_lines:
            pvx, pvy = _to_page(vx, vy, page_h_pt)
            builder.text(pvx, pvy, _pt(style.body_text_height_mm), line)
            vy += field.value_line_h
    fx, fy, ftext = footer
    pfx, pfy = _to_page(fx, fy, page_h_pt)
    builder.text(pfx, pfy, _pt(style.caption_text_height_mm), ftext)
    for zx, zy, ztext in _zone_marks(w_mm, h_mm, style):
        pzx, pzy = _to_page(zx, zy, page_h_pt)
        builder.text(pzx, pzy, _pt(style.caption_text_height_mm), ztext)


def _sheet_content(
    sheet: Sheet,
    w_mm: float,
    h_mm: float,
    style: StyleRecord,
    *,
    sheet_index: int,
    sheet_count: int,
    digest: str,
) -> bytes:
    """One sheet's full content stream (furniture, geometry, dimensions,
    annotations, tables), in the schema's own stable order.
    """
    page_h_pt = _pt(h_mm)
    builder = _ContentBuilder()

    _render_furniture(
        sheet,
        w_mm,
        h_mm,
        page_h_pt,
        builder,
        style,
        sheet_index=sheet_index,
        sheet_count=sheet_count,
        digest=digest,
    )
    content_area = _content_area(sheet, w_mm, h_mm, style)
    transforms = _view_transforms(sheet, content_area, style)
    cells = _view_cells(sheet, content_area, style)
    margin = style.margin_mm
    bounds = (margin, margin, w_mm - margin, h_mm - margin - style.title_block_h_mm)

    is_chart = any(v.source.source_kind == "optimize.trace" for v in sheet.views)
    chart_geometry: ChartGeometry | None = None
    if is_chart:
        for view in sheet.views:
            entities = [sheet.entities[int(i.root)] for i in view.entity_indices]
            points: list[tuple[float, float]] = [
                (e.from_[0], e.from_[1])
                for e in entities
                if isinstance(e, SegmentEntity)
            ]
            if entities and isinstance(entities[-1], SegmentEntity):
                points.append((entities[-1].to[0], entities[-1].to[1]))
            chart_geometry = ChartGeometry(
                points, cells.get(view.name, bounds), style, "objective"
            )
            winner_anchor = next(
                (
                    (a.anchor[0], a.anchor[1])
                    for a in sheet.annotations
                    if a.text.startswith("winner:")
                ),
                None,
            )
            _render_chart(
                chart_geometry,
                points,
                page_h_pt,
                builder,
                style,
                winner_anchor=winner_anchor,
            )
    else:
        index_transforms = _entity_index_transforms(sheet, transforms)
        for i, entity in enumerate(sheet.entities):
            _render_entity(
                entity, index_transforms.get(i, _IDENTITY), page_h_pt, builder, style
            )

    # Charter 41 sec. 1.2: per-view label + scale under each view.
    for view in sheet.views:
        cell_x, cell_y, cell_w, cell_h = cells.get(view.name, bounds)
        lx, ly = cell_x + 1.0, cell_y + cell_h - 1.0
        plx, ply = _to_page(lx, ly, page_h_pt)
        builder.text(
            plx, ply, _pt(style.caption_text_height_mm), _view_label_text(view)
        )

    for dim in sheet.dimensions:
        _render_dimension(
            dim,
            transforms.get(dim.view_name, _IDENTITY),
            page_h_pt,
            builder,
            style,
            bounds,
            sheet,
        )

    annotation_transform = (
        chart_geometry
        if chart_geometry is not None
        else (next(iter(transforms.values())) if len(transforms) == 1 else _IDENTITY)
    )
    for ann_index, ann in enumerate(sheet.annotations):
        _render_annotation(
            ann,
            annotation_transform,
            page_h_pt,
            builder,
            style,
            bounds,
            ladder_index=ann_index,
        )

    # Tables sit below the view content area (the same placement rule
    # the SVG renderer uses -- one convention, three renderers), each
    # narrowed when it would enter the title-block band (INV-31).
    table_y = content_area[1] + content_area[3] + style.content_gap_mm
    for table in sheet.tables:
        table_max_w = table_fit_max_width(
            table,
            style.margin_mm,
            table_y + style.subtitle_text_height_mm + 1.0,
            style,
            w_mm,
            h_mm,
        )
        table_y = _render_table(
            table, style.margin_mm, table_y, page_h_pt, builder, style, table_max_w
        )

    return builder.to_bytes()


# frob:doc docs/modules/py-backends.md#drawings-renderer-pdf
def render_pdf(model: DrawingModel, style: StyleRecord | None = None) -> bytes:
    """Render every sheet of `model` into one deterministic single-page-
    per-sheet PDF 1.4 document: header, objects (Catalog/Pages/Font/one
    Page+Content per sheet), xref table, trailer, `%%EOF`. No
    `/CreationDate` or `/ID` (both would break byte-identical goldens).

    `style` (WO-99 D7) supplies the drafting constants; `None` resolves to
    the neutral default pack, byte-identical to the pre-D7 output.
    """
    style = resolve_style(style)
    n = len(model.sheets)
    catalog_obj = 1
    pages_obj = 2
    font_obj = 3
    first_page_obj = 4  # page_obj = first_page_obj + 2*i, content_obj = +1

    page_kids = " ".join(f"{first_page_obj + 2 * i} 0 R" for i in range(n))
    objects: dict[int, bytes] = {
        catalog_obj: f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode("ascii"),
        pages_obj: f"<< /Type /Pages /Kids [{page_kids}] /Count {n} >>".encode("ascii"),
        font_obj: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }

    digest = content_digest(model)
    for i, sheet in enumerate(model.sheets):
        w_mm, h_mm = _sheet_size_mm(sheet)
        w_pt, h_pt = _pt(w_mm), _pt(h_mm)
        content_bytes = _sheet_content(
            sheet, w_mm, h_mm, style, sheet_index=i, sheet_count=n, digest=digest
        )
        page_obj = first_page_obj + 2 * i
        content_obj = page_obj + 1
        objects[page_obj] = (
            f"<< /Type /Page /Parent {pages_obj} 0 R "
            f"/MediaBox [0 0 {_num(w_pt)} {_num(h_pt)}] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
            f"/Contents {content_obj} 0 R >>"
        ).encode("ascii")
        objects[content_obj] = (
            f"<< /Length {len(content_bytes)} >>\nstream\n".encode("ascii")
            + content_bytes
            + b"endstream"
        )

    return _serialize_pdf(objects)


def _serialize_pdf(objects: dict[int, bytes]) -> bytes:
    """Write the header, numbered `obj`/`endobj` bodies, xref table, and
    trailer, tracking exact byte offsets for a parseable xref -- the
    one place object order and byte position must agree.
    """
    header = b"%PDF-1.4\n"
    out = bytearray(header)
    offsets: dict[int, int] = {}
    for obj_num in sorted(objects):
        offsets[obj_num] = len(out)
        out += f"{obj_num} 0 obj\n".encode("ascii")
        out += objects[obj_num]
        out += b"\nendobj\n"

    xref_offset = len(out)
    max_obj = max(objects) if objects else 0
    out += f"xref\n0 {max_obj + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for obj_num in range(1, max_obj + 1):
        offset = offsets.get(obj_num, 0)
        out += f"{offset:010d} 00000 n \n".encode("ascii")

    out += (
        f"trailer\n<< /Size {max_obj + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)
