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

import math
from xml.sax.saxutils import escape

from regolith._schema.models import Annotation, Dimension, DrawingModel, Sheet, View
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


def _sheet_furniture(
    sheet: Sheet, w: float, h: float, style: StyleRecord
) -> tuple[
    list[tuple[str, float, float, float, float]],
    list[tuple[str, float, float, str]],
]:
    """The sheet furniture every renderer must emit identically: the
    frame border + title-block rectangles as `(name, x, y, w, h)` and
    the title-block field text lines as `(field, x, y, value)` -- ONE
    home for this layout math so SVG/DXF/PDF cannot diverge on it.
    """
    margin = style.margin_mm
    tb_w = style.title_block_w_mm
    tb_h = style.title_block_h_mm
    line_h = style.title_line_height_mm
    rects = [
        ("frame", margin, margin, w - 2 * margin, h - 2 * margin),
    ]
    box_x = w - margin - tb_w
    box_y = h - margin - tb_h
    rects.append(("title-block-frame", box_x, box_y, tb_w, tb_h))

    tb = sheet.title_block
    fields = [
        ("title", tb.title),
        ("drawing_number", tb.drawing_number),
        ("revision", f"rev {tb.revision}"),
        ("scale_label", f"scale {tb.scale_label}"),
        ("subject", tb.subject),
    ]
    texts: list[tuple[str, float, float, str]] = []
    text_x = box_x + 2.0
    text_y = box_y + line_h
    for field, value in fields:
        texts.append((field, text_x, text_y, value))
        text_y += line_h
    return rects, texts


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
    for sheet, w, h, y_offset in sheet_boxes:
        lines.append(f'<g class="sheet" transform="translate(0,{_fmt(y_offset)})">')
        lines.extend(_render_sheet(sheet, w, h, style))
        lines.append("</g>")
    lines.append("</svg>")
    return ("\n".join(lines) + "\n").encode("ascii", errors="xmlcharrefreplace")


def _render_sheet(sheet: Sheet, w: float, h: float, style: StyleRecord) -> list[str]:
    """The frame, title block, views, dimensions, annotations, and
    tables of one sheet, positioned within its own `w` x `h` mm page.
    """
    lines: list[str] = []
    rects, tb_texts = _sheet_furniture(sheet, w, h, style)
    for name, rx, ry, rw, rh in rects:
        lines.append(
            f'<rect class="{name}" x="{_fmt(rx)}" y="{_fmt(ry)}" '
            f'width="{_fmt(rw)}" height="{_fmt(rh)}" fill="none" stroke="black"/>'
        )
    for field, tx, ty, value in tb_texts:
        lines.append(
            f'<text class="title-block-{field}" x="{_fmt(tx)}" '
            f'y="{_fmt(ty)}">{_text(value)}</text>'
        )

    margin = style.margin_mm
    content_x = margin
    content_y = margin
    content_w = w - 2 * margin
    content_h = h - 2 * margin - style.title_block_h_mm - style.content_gap_mm
    transforms = _view_transforms(
        sheet, (content_x, content_y, content_w, max(content_h, 1.0)), style
    )

    for view in sheet.views:
        transform = transforms.get(view.name, _IDENTITY)
        lines.append(
            f'<g class="view" data-view="{_text(view.name)}" '
            f'transform="{transform.attr()}">'
        )
        for idx in view.entity_indices:
            lines.append(_render_entity(sheet.entities[int(idx.root)]))
        lines.append("</g>")

    for dim in sheet.dimensions:
        transform = transforms.get(dim.view_name, _IDENTITY)
        lines.append(_render_dimension(dim, transform, style))

    annotation_transform = (
        next(iter(transforms.values())) if len(transforms) == 1 else _IDENTITY
    )
    for ann in sheet.annotations:
        lines.append(_render_annotation(ann, annotation_transform))

    table_y = content_y + content_h + style.content_gap_mm
    for table in sheet.tables:
        lines.append(
            f'<text class="table-title" x="{_fmt(content_x)}" y="{_fmt(table_y)}">'
            f"{_text(table.title)}</text>"
        )
        table_y += style.title_line_height_mm
        for row in table.rows:
            cells = "|".join(_text(c) for c in row.cells)
            lines.append(
                f'<text class="table-row" x="{_fmt(content_x)}" y="{_fmt(table_y)}">'
                f"{cells}</text>"
            )
            table_y += style.title_line_height_mm
    return lines


def _render_dimension(
    dim: Dimension, transform: _Transform, style: StyleRecord
) -> str:
    """A dimension as a leader dot at its true anchor plus text offset
    by a small deterministic standoff (charter sec. 1 decision 5) so
    the label never sits directly on top of the geometry it describes.
    """
    dot_x, dot_y = transform.point(dim.anchor[0], dim.anchor[1])
    text_x, text_y = transform.point(
        dim.anchor[0], dim.anchor[1] - style.dim_standoff_mm
    )
    return (
        f'<circle class="dimension-leader" cx="{_fmt(dot_x)}" '
        f'cy="{_fmt(dot_y)}" r="0.5"/>'
        f'<text class="dimension" x="{_fmt(text_x)}" y="{_fmt(text_y)}">'
        f"{_text(dim.role)}={_fmt(dim.value)}{_text(dim.unit)}</text>"
    )


def _render_annotation(ann: Annotation, transform: _Transform) -> str:
    """One annotation, mapped through its owning view's transform (v1
    simplification: `Annotation` carries no `view_name`, so a sheet
    with more than one view falls back to identity placement -- every
    current producer emits at most one view per sheet).
    """
    x, y = transform.point(ann.anchor[0], ann.anchor[1])
    return (
        f'<text class="annotation" x="{_fmt(x)}" y="{_fmt(y)}" '
        f'font-size="{_fmt(ann.text_height_mm)}">{_text(ann.text)}</text>'
    )


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
