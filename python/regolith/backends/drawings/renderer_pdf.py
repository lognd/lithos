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

from regolith._schema.models import Annotation, Dimension, DrawingModel, Sheet, Table
from regolith._schema.models import Entity1 as SegmentEntity
from regolith._schema.models import Entity2 as ArcEntity
from regolith._schema.models import Entity3 as PolylineEntity
from regolith._schema.models import Entity4 as SymbolEntity
from regolith.backends.drawings.renderer import (
    _CONTENT_GAP_MM,
    _IDENTITY,
    _MARGIN_MM,
    _TITLE_BLOCK_H_MM,
    _TITLE_TEXT_HEIGHT_MM,
    _sheet_furniture,
    _sheet_size_mm,
    _Transform,
    _view_transforms,
)
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# 1 mm = 1/25.4 in = 72/25.4 pt (a fixed rounding rule, applied at
# every mm -> pt conversion so the same input always rounds the same
# way -- AD-6).
_MM_TO_PT = 72.0 / 25.4
_TABLE_LINE_HEIGHT_MM = 5.0
_TEXT_HEIGHT_DEFAULT_MM = 3.0
_SYMBOL_HALF_MM = 1.5


def _pt(mm: float) -> float:
    """Convert one mm value to PDF points under the fixed rounding rule."""
    return round(mm * _MM_TO_PT, 4)


def _num(value: float) -> str:
    """A stable, locale-independent float format for PDF content-stream
    operands and array entries.
    """
    return f"{value:.4f}"


def _pdf_text(value: str) -> str:
    """Escape a string for a PDF literal-string text-show operand."""
    escaped = value.encode("ascii", errors="replace").decode("ascii")
    return escaped.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


class _ContentBuilder:
    """Accumulates one page's content-stream operators in emission order
    (the schema's own stable order; a renderer never re-sorts, AD-27).
    """

    def __init__(self) -> None:
        self._ops: list[str] = []

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """One stroked line segment: `moveto` + `lineto` + `stroke`."""
        self._ops.append(f"{_num(x1)} {_num(y1)} m")
        self._ops.append(f"{_num(x2)} {_num(y2)} l")
        self._ops.append("S")

    def rect(self, x: float, y: float, w: float, h: float) -> None:
        """One stroked rectangle via the `re` path operator."""
        self._ops.append(f"{_num(x)} {_num(y)} {_num(w)} {_num(h)} re")
        self._ops.append("S")

    def text(self, x: float, y: float, size_pt: float, value: str) -> None:
        """One text-show operator at an absolute page position."""
        self._ops.append("BT")
        self._ops.append(f"/F1 {_num(size_pt)} Tf")
        self._ops.append(f"{_num(x)} {_num(y)} Td")
        self._ops.append(f"({_pdf_text(value)}) Tj")
        self._ops.append("ET")

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
    sheet: Sheet, w: float, h: float
) -> tuple[float, float, float, float]:
    """The same content-area rectangle the SVG/DXF renderers lay views
    into (kept identical so all three renderers agree on placement).
    """
    content_x = _MARGIN_MM
    content_y = _MARGIN_MM
    content_w = w - 2 * _MARGIN_MM
    content_h = h - 2 * _MARGIN_MM - _TITLE_BLOCK_H_MM - _CONTENT_GAP_MM
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
    corners = [
        (ox - _SYMBOL_HALF_MM, oy - _SYMBOL_HALF_MM),
        (ox + _SYMBOL_HALF_MM, oy - _SYMBOL_HALF_MM),
        (ox + _SYMBOL_HALF_MM, oy + _SYMBOL_HALF_MM),
        (ox - _SYMBOL_HALF_MM, oy + _SYMBOL_HALF_MM),
        (ox - _SYMBOL_HALF_MM, oy - _SYMBOL_HALF_MM),
    ]
    for (x1, y1), (x2, y2) in zip(corners, corners[1:], strict=False):
        p1 = _to_page(x1, y1, page_h_pt)
        p2 = _to_page(x2, y2, page_h_pt)
        builder.line(p1[0], p1[1], p2[0], p2[1])


def _render_dimension(
    dim: Dimension, transform: _Transform, page_h_pt: float, builder: _ContentBuilder
) -> None:
    """A dimension's value+unit as one text operator."""
    x, y = transform.point(dim.anchor[0], dim.anchor[1])
    px, py = _to_page(x, y, page_h_pt)
    value = f"{dim.role}={_num(dim.value)}{dim.unit}"
    builder.text(px, py, _pt(_TEXT_HEIGHT_DEFAULT_MM), value)


def _render_annotation(
    ann: Annotation, transform: _Transform, page_h_pt: float, builder: _ContentBuilder
) -> None:
    """An annotation's text as one text operator."""
    x, y = transform.point(ann.anchor[0], ann.anchor[1])
    px, py = _to_page(x, y, page_h_pt)
    builder.text(px, py, _pt(ann.text_height_mm), ann.text)


def _render_table(
    table: Table, x_mm: float, y_mm: float, page_h_pt: float, builder: _ContentBuilder
) -> float:
    """A schedule table's title + rows as text operators; returns the
    next free y (mm, sheet-space) below the rendered block.
    """
    px, py = _to_page(x_mm, y_mm, page_h_pt)
    builder.text(px, py, _pt(_TABLE_LINE_HEIGHT_MM), table.title)
    row_y = y_mm + _TABLE_LINE_HEIGHT_MM
    for row in table.rows:
        px, py = _to_page(x_mm, row_y, page_h_pt)
        builder.text(px, py, _pt(_TABLE_LINE_HEIGHT_MM), "|".join(row.cells))
        row_y += _TABLE_LINE_HEIGHT_MM
    return row_y


def _render_furniture(
    sheet: Sheet, w_mm: float, h_mm: float, page_h_pt: float, builder: _ContentBuilder
) -> None:
    """The sheet frame + title-block furniture (`renderer._sheet_furniture`,
    the one shared layout home) as `re` rectangle operators + text lines.
    """
    rects, tb_texts = _sheet_furniture(sheet, w_mm, h_mm)
    for _name, rx, ry, rw, rh in rects:
        # A sheet-space (y-down) rect's bottom edge is ry + rh; in PDF
        # page space (y-up) that edge is the rect origin.
        px, py = _to_page(rx, ry + rh, page_h_pt)
        builder.rect(px, py, _pt(rw), _pt(rh))
    for _field, tx, ty, value in tb_texts:
        px, py = _to_page(tx, ty, page_h_pt)
        builder.text(px, py, _pt(_TITLE_TEXT_HEIGHT_MM), value)


def _sheet_content(sheet: Sheet, w_mm: float, h_mm: float) -> bytes:
    """One sheet's full content stream (furniture, geometry, dimensions,
    annotations, tables), in the schema's own stable order.
    """
    page_h_pt = _pt(h_mm)
    builder = _ContentBuilder()

    _render_furniture(sheet, w_mm, h_mm, page_h_pt, builder)
    transforms = _view_transforms(sheet, _content_area(sheet, w_mm, h_mm))
    index_transforms = _entity_index_transforms(sheet, transforms)
    for i, entity in enumerate(sheet.entities):
        _render_entity(entity, index_transforms.get(i, _IDENTITY), page_h_pt, builder)

    for dim in sheet.dimensions:
        _render_dimension(
            dim, transforms.get(dim.view_name, _IDENTITY), page_h_pt, builder
        )

    annotation_transform = (
        next(iter(transforms.values())) if len(transforms) == 1 else _IDENTITY
    )
    for ann in sheet.annotations:
        _render_annotation(ann, annotation_transform, page_h_pt, builder)

    # Tables sit below the view content area (the same placement rule
    # the SVG renderer uses -- one convention, three renderers).
    content = _content_area(sheet, w_mm, h_mm)
    table_y = content[1] + content[3] + _CONTENT_GAP_MM
    for table in sheet.tables:
        table_y = _render_table(table, _MARGIN_MM, table_y, page_h_pt, builder)

    return builder.to_bytes()


def render_pdf(model: DrawingModel) -> bytes:
    """Render every sheet of `model` into one deterministic single-page-
    per-sheet PDF 1.4 document: header, objects (Catalog/Pages/Font/one
    Page+Content per sheet), xref table, trailer, `%%EOF`. No
    `/CreationDate` or `/ID` (both would break byte-identical goldens).
    """
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

    for i, sheet in enumerate(model.sheets):
        w_mm, h_mm = _sheet_size_mm(sheet)
        w_pt, h_pt = _pt(w_mm), _pt(h_mm)
        content_bytes = _sheet_content(sheet, w_mm, h_mm)
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
