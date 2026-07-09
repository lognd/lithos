"""The SVG reference renderer (charter sec. 1 decision 2, mandatory;
DXF/PDF are siblings of the same IR, tracked as future scope for this
dispatch). Deterministic TEXT output: same `DrawingModel` -> byte-
identical SVG (AD-6), the two-runs golden property WO-50 proves.

Consumes ONLY `DrawingModel` -- no geometry computation, no re-reading
of source (AD-27).
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from regolith._schema.models import DrawingModel
from regolith._schema.models import Entity1 as SegmentEntity
from regolith._schema.models import Entity2 as ArcEntity
from regolith._schema.models import Entity3 as PolylineEntity
from regolith._schema.models import Entity4 as SymbolEntity

_NS = "http://www.w3.org/2000/svg"


def _fmt(value: float) -> str:
    """A stable, locale-independent float format for SVG coordinates."""
    return f"{value:.4f}"


def _text(value: str) -> str:
    """XML-escape a text value before it lands inside SVG markup."""
    return escape(value)


def render_svg(model: DrawingModel) -> bytes:
    """Render every sheet of `model` into one deterministic SVG document.

    Sheets are concatenated top-to-bottom as `<g>` groups (v1's
    mechanical, non-aesthetic layout, charter sec. 1 decision 5); each
    sheet's entities, dimensions (as text + a leader dot), annotations,
    and tables (as `<text>` rows) are emitted in the schema's own stable
    order -- never re-sorted here (a renderer never decides order).
    """
    lines: list[str] = [
        f'<svg xmlns="{_NS}" version="1.1">',
    ]
    y_offset = 0.0
    for sheet in model.sheets:
        lines.append(f'<g class="sheet" transform="translate(0,{_fmt(y_offset)})">')
        lines.append(
            f'<text class="title-block" x="0" y="0">{_text(sheet.title_block.title)} '
            f"({_text(sheet.title_block.drawing_number)} "
            f"rev {_text(sheet.title_block.revision)})</text>"
        )
        for entity in sheet.entities:
            lines.append(_render_entity(entity))
        for dim in sheet.dimensions:
            lines.append(
                f'<text class="dimension" x="{_fmt(dim.anchor[0])}" '
                f'y="{_fmt(dim.anchor[1])}">{_text(dim.role)}='
                f"{_fmt(dim.value)}{_text(dim.unit)}</text>"
            )
        for ann in sheet.annotations:
            lines.append(
                f'<text class="annotation" x="{_fmt(ann.anchor[0])}" '
                f'y="{_fmt(ann.anchor[1])}" font-size="{_fmt(ann.text_height_mm)}">'
                f"{_text(ann.text)}</text>"
            )
        for table in sheet.tables:
            lines.append(f'<text class="table-title">{_text(table.title)}</text>')
            for row in table.rows:
                cells = "|".join(_text(c) for c in row.cells)
                lines.append(f'<text class="table-row">{cells}</text>')
        lines.append("</g>")
        y_offset += 300.0
    lines.append("</svg>")
    return ("\n".join(lines) + "\n").encode("ascii", errors="xmlcharrefreplace")


def _render_entity(
    entity: SegmentEntity | ArcEntity | PolylineEntity | SymbolEntity,
) -> str:
    """Render one sheet entity (segment/arc/polyline/symbol) as SVG."""
    if isinstance(entity, SegmentEntity):
        return (
            f'<line class="segment" x1="{_fmt(entity.from_[0])}" '
            f'y1="{_fmt(entity.from_[1])}" x2="{_fmt(entity.to[0])}" '
            f'y2="{_fmt(entity.to[1])}"/>'
        )
    if isinstance(entity, ArcEntity):
        return (
            f'<circle class="arc" cx="{_fmt(entity.center[0])}" '
            f'cy="{_fmt(entity.center[1])}" r="{_fmt(entity.radius)}"/>'
        )
    if isinstance(entity, PolylineEntity):
        points = " ".join(f"{_fmt(p.root[0])},{_fmt(p.root[1])}" for p in entity.points)
        return f'<polyline class="polyline" points="{points}"/>'
    return (
        f'<use class="symbol" x="{_fmt(entity.origin[0])}" '
        f'y="{_fmt(entity.origin[1])}" '
        f'data-record="{entity.record_digest}"/>'
    )
