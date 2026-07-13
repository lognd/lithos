"""The DXF renderer: a sibling of the SVG reference renderer over the
SAME `DrawingModel` IR (charter sec. 1 decision 2 -- "DXF and PDF are
sibling renderers"). Minimal ASCII DXF R12 (AC1009), hand-written,
dependency-free: `LINE` entities for segments/polylines, `TEXT` for
dimension/annotation/table text, one layer per entity class
(GEOMETRY/DIMENSIONS/ANNOTATIONS/TABLES, plus SHEET for the frame and
title-block furniture). Consumes ONLY `DrawingModel`
-- no geometry computation (AD-27); reuses the SVG renderer's own view
grid-cell layout math so the two renderers place the same entity at
the same sheet-space point (no second layout mechanism, CLAUDE.md's
no-duplication rule).
"""

from __future__ import annotations

from regolith._schema.models import Annotation, Dimension, DrawingModel, Sheet, Table
from regolith._schema.models import Entity1 as SegmentEntity
from regolith._schema.models import Entity2 as ArcEntity
from regolith._schema.models import Entity3 as PolylineEntity
from regolith._schema.models import Entity4 as SymbolEntity
from regolith.backends.drawings.renderer import (
    _IDENTITY,
    _sheet_furniture,
    _sheet_size_mm,
    _Transform,
    _view_transforms,
)
from regolith.backends.drawings.style import StyleRecord, resolve_style
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

_LAYER_GEOMETRY = "GEOMETRY"
_LAYER_DIMENSIONS = "DIMENSIONS"
_LAYER_ANNOTATIONS = "ANNOTATIONS"
_LAYER_TABLES = "TABLES"
_LAYER_SHEET = "SHEET"
_LAYERS = (
    _LAYER_GEOMETRY,
    _LAYER_DIMENSIONS,
    _LAYER_ANNOTATIONS,
    _LAYER_TABLES,
    _LAYER_SHEET,
)


def _fmt(value: float) -> str:
    """A stable, locale-independent float format for DXF group values."""
    return f"{value:.4f}"


def _group(code: int, value: str) -> list[str]:
    """One DXF group: code line then value line (R12's plain-text pairs)."""
    return [str(code), value]


def _entity_index_transforms(
    sheet: Sheet, transforms: dict[str, _Transform]
) -> dict[int, _Transform]:
    """Map each entity index to the transform of the (one) view that
    references it; an entity no view references gets identity (never
    happens for a well-formed producer output, but stays total).
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
    """The same content-area rectangle the SVG renderer lays views into
    (kept identical so both renderers place geometry at the same point).
    """
    margin = style.margin_mm
    content_x = margin
    content_y = margin
    content_w = w - 2 * margin
    content_h = h - 2 * margin - style.title_block_h_mm - style.content_gap_mm
    return (content_x, content_y, content_w, max(content_h, 1.0))


def render_dxf(model: DrawingModel, style: StyleRecord | None = None) -> bytes:
    """Render every sheet of `model` into one deterministic ASCII DXF
    R12 document: `HEADER`/`TABLES`/`ENTITIES` sections, sheets stacked
    top-to-bottom (same convention as the SVG renderer), entities in
    the schema's own stable order.

    `style` (WO-99 D7) supplies the drafting constants; `None` resolves to
    the neutral default pack, byte-identical to the pre-D7 output.
    """
    style = resolve_style(style)
    out: list[str] = []
    out += _group(0, "SECTION")
    out += _group(2, "HEADER")
    out += _group(9, "$ACADVER")
    out += _group(1, "AC1009")
    out += _group(0, "ENDSEC")

    out += _group(0, "SECTION")
    out += _group(2, "TABLES")
    out += _group(0, "TABLE")
    out += _group(2, "LAYER")
    out += _group(70, str(len(_LAYERS)))
    for layer in _LAYERS:
        out += _group(0, "LAYER")
        out += _group(2, layer)
        out += _group(70, "0")
        out += _group(62, "7")
        out += _group(6, "CONTINUOUS")
    out += _group(0, "ENDTAB")
    out += _group(0, "ENDSEC")

    out += _group(0, "SECTION")
    out += _group(2, "ENTITIES")
    y_cursor = 0.0
    for sheet in model.sheets:
        w, h = _sheet_size_mm(sheet)
        transforms = _view_transforms(sheet, _content_area(sheet, w, h, style), style)
        index_transforms = _entity_index_transforms(sheet, transforms)
        out += _render_sheet_entities(
            sheet, index_transforms, transforms, y_cursor, style
        )
        y_cursor += h + style.sheet_gap_mm
    out += _group(0, "ENDSEC")
    out += _group(0, "EOF")

    return ("\n".join(out) + "\n").encode("ascii", errors="replace")


def _render_sheet_entities(
    sheet: Sheet,
    index_transforms: dict[int, _Transform],
    view_transforms: dict[str, _Transform],
    y_offset: float,
    style: StyleRecord,
) -> list[str]:
    """The `LINE`/`TEXT`/`POINT` entities for one sheet's geometry,
    dimensions, annotations, and tables, all offset by `y_offset` (the
    SVG renderer's per-sheet stacking, applied here without a `<g>`).
    """
    out: list[str] = []
    w, h = _sheet_size_mm(sheet)
    out += _render_furniture(sheet, w, h, y_offset, style)
    for i, entity in enumerate(sheet.entities):
        transform = index_transforms.get(i, _IDENTITY)
        out += _render_entity(entity, transform, y_offset)

    for dim in sheet.dimensions:
        transform = view_transforms.get(dim.view_name, _IDENTITY)
        out += _render_dimension_text(dim, transform, y_offset, style)

    annotation_transform = (
        next(iter(view_transforms.values())) if len(view_transforms) == 1 else _IDENTITY
    )
    for ann in sheet.annotations:
        out += _render_annotation_text(ann, annotation_transform, y_offset)

    # Tables sit below the view content area (the same placement rule
    # the SVG renderer uses -- one convention, three renderers).
    content = _content_area(sheet, w, h, style)
    table_y = content[1] + content[3] + style.content_gap_mm + y_offset
    for table in sheet.tables:
        out += _render_table_text(table, style.margin_mm, table_y, style)
        table_y += style.table_line_height_mm * (1 + len(table.rows))
    return out


def _render_furniture(
    sheet: Sheet, w: float, h: float, y_offset: float, style: StyleRecord
) -> list[str]:
    """The sheet frame + title-block furniture (`renderer._sheet_furniture`,
    the one shared layout home) as `LINE` rect edges + `TEXT` field lines
    on the `SHEET` layer.
    """
    out: list[str] = []
    rects, tb_texts = _sheet_furniture(sheet, w, h, style)
    for _name, rx, ry, rw, rh in rects:
        y0 = ry + y_offset
        out += _line(rx, y0, rx + rw, y0, _LAYER_SHEET)
        out += _line(rx + rw, y0, rx + rw, y0 + rh, _LAYER_SHEET)
        out += _line(rx + rw, y0 + rh, rx, y0 + rh, _LAYER_SHEET)
        out += _line(rx, y0 + rh, rx, y0, _LAYER_SHEET)
    for _field, tx, ty, value in tb_texts:
        out += _text_entity(
            tx, ty + y_offset, style.title_text_height_mm, value, _LAYER_SHEET
        )
    return out


def _line(x1: float, y1: float, x2: float, y2: float, layer: str) -> list[str]:
    """One `LINE` entity (R12 group codes 10/20/30 start, 11/21/31 end)."""
    out: list[str] = []
    out += _group(0, "LINE")
    out += _group(8, layer)
    out += _group(10, _fmt(x1))
    out += _group(20, _fmt(y1))
    out += _group(30, "0.0")
    out += _group(11, _fmt(x2))
    out += _group(21, _fmt(y2))
    out += _group(31, "0.0")
    return out


def _sanitize_text_value(value: str) -> str:
    """Make `value` a safe single-line DXF group-1 string (M2, L2).

    Two lossy passes, both logged: non-ASCII characters become `?`
    (DXF R12 text groups are plain ASCII; the deterministic-golden
    contract here is documented lossy replacement, not rejection --
    the drawings backend has no `Result`-return seam at this leaf, sec.
    L2), then any `\\n`/`\\r`/other control character is replaced with a
    space (R12 is strictly line-paired: an embedded newline desyncs
    every following code/value pair, M2). Order matters: control-char
    replacement runs AFTER the ASCII pass so a `?` substitution can
    never itself introduce a raw control byte.
    """
    ascii_value = value.encode("ascii", errors="replace").decode("ascii")
    if ascii_value != value:
        _log.warning("DXF text: non-ASCII character(s) replaced with '?' in %r", value)
    sanitized = "".join(
        " " if (ch in "\r\n" or ord(ch) < 0x20) else ch for ch in ascii_value
    )
    if sanitized != ascii_value:
        _log.warning(
            "DXF text: control character(s) replaced with space in %r", ascii_value
        )
    return sanitized


def _text_entity(
    x: float, y: float, height: float, value: str, layer: str
) -> list[str]:
    """One `TEXT` entity (group 1 is the text string, ASCII-only, single-line).

    Non-ASCII and control characters (including newlines) are lossily
    replaced rather than rejected -- see `_sanitize_text_value`.
    """
    out: list[str] = []
    out += _group(0, "TEXT")
    out += _group(8, layer)
    out += _group(10, _fmt(x))
    out += _group(20, _fmt(y))
    out += _group(30, "0.0")
    out += _group(40, _fmt(height))
    out += _group(1, _sanitize_text_value(value))
    return out


def _render_entity(
    entity: SegmentEntity | ArcEntity | PolylineEntity | SymbolEntity,
    transform: _Transform,
    y_offset: float,
) -> list[str]:
    """One sheet entity as DXF: segment/polyline -> `LINE`(s), arc ->
    `CIRCLE`, symbol -> `POINT` (v1 has no per-symbol block definition).
    """
    if isinstance(entity, SegmentEntity):
        x1, y1 = transform.point(entity.from_[0], entity.from_[1])
        x2, y2 = transform.point(entity.to[0], entity.to[1])
        return _line(x1, y1 + y_offset, x2, y2 + y_offset, _LAYER_GEOMETRY)
    if isinstance(entity, ArcEntity):
        cx, cy = transform.point(entity.center[0], entity.center[1])
        out: list[str] = []
        out += _group(0, "CIRCLE")
        out += _group(8, _LAYER_GEOMETRY)
        out += _group(10, _fmt(cx))
        out += _group(20, _fmt(cy + y_offset))
        out += _group(30, "0.0")
        out += _group(40, _fmt(entity.radius * transform.scale))
        return out
    if isinstance(entity, PolylineEntity):
        points = [transform.point(p.root[0], p.root[1]) for p in entity.points]
        out = []
        for (x1, y1), (x2, y2) in zip(points, points[1:], strict=False):
            out += _line(x1, y1 + y_offset, x2, y2 + y_offset, _LAYER_GEOMETRY)
        return out
    ox, oy = transform.point(entity.origin[0], entity.origin[1])
    out = []
    out += _group(0, "POINT")
    out += _group(8, _LAYER_GEOMETRY)
    out += _group(10, _fmt(ox))
    out += _group(20, _fmt(oy + y_offset))
    out += _group(30, "0.0")
    return out


def _render_dimension_text(
    dim: Dimension, transform: _Transform, y_offset: float, style: StyleRecord
) -> list[str]:
    """A dimension's value+unit as one `TEXT` entity on `DIMENSIONS`."""
    x, y = transform.point(dim.anchor[0], dim.anchor[1])
    value = f"{dim.role}={_fmt(dim.value)}{dim.unit}"
    return _text_entity(
        x, y + y_offset, style.text_height_default_mm, value, _LAYER_DIMENSIONS
    )


def _render_annotation_text(
    ann: Annotation, transform: _Transform, y_offset: float
) -> list[str]:
    """An annotation's text as one `TEXT` entity on `ANNOTATIONS`."""
    x, y = transform.point(ann.anchor[0], ann.anchor[1])
    return _text_entity(
        x, y + y_offset, ann.text_height_mm, ann.text, _LAYER_ANNOTATIONS
    )


def _render_table_text(
    table: Table, x: float, y: float, style: StyleRecord
) -> list[str]:
    """A schedule table's title + rows as `TEXT` entities on `TABLES`."""
    line_h = style.table_line_height_mm
    out = _text_entity(x, y, line_h, table.title, _LAYER_TABLES)
    row_y = y + line_h
    for row in table.rows:
        cells = "|".join(row.cells)
        out += _text_entity(x, row_y, line_h, cells, _LAYER_TABLES)
        row_y += line_h
    return out
