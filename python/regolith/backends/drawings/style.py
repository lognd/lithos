"""Style records (WO-99 D7 / charter 38 sec. 1.12): the drafting aesthetic
constants a renderer consumes, as hash-pinnable DATA rather than hard-coded
module literals.

The ``NEUTRAL_STYLE`` default reproduces every historical hard-coded
constant of the SVG/DXF/PDF renderers EXACTLY, so a drawing rendered with
the default pack is byte-identical to the pre-style renderer output (the
charter's byte-identical-goldens rule, proven mechanically by
``tests/backends/test_style.py``). A project ``[style]`` pack (magnetite
manifest, WO-99 D7 config half) overrides any field; renderers hold NO
aesthetic constant beyond this neutral default (charter 38 sec. 1.12).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The one home for the neutral drafting constants. Each field's default IS
# the value the renderers hard-coded before WO-99 D7; changing a default
# here is a visible, reviewed style change, never an accident.


class StyleRecord(BaseModel):
    """The resolved drafting style a renderer applies to a ``DrawingModel``.

    Frozen and fully-defaulted: an omitted field takes the neutral value,
    so a partial project ``[style]`` pack overrides only what it names.
    """

    model_config = ConfigDict(frozen=True)

    # Sheet furniture / layout (mm).
    margin_mm: float = 10.0
    title_block_w_mm: float = 100.0
    title_block_h_mm: float = 80.0
    title_line_height_mm: float = 5.0
    content_gap_mm: float = 5.0
    cell_pad_mm: float = 6.0
    dim_standoff_mm: float = 3.0
    sheet_gap_mm: float = 15.0
    fallback_extent_mm: float = 10.0
    symbol_radius_mm: float = 5.0
    symbol_half_mm: float = 1.5
    # Text heights (mm).
    title_text_height_mm: float = 3.5
    text_height_default_mm: float = 3.0
    table_line_height_mm: float = 5.0

    # WO-123 (charter 41) presentation-v2 additions. Every new field is
    # additive DATA on this Python-only style record (no wire-schema
    # bump, D225/D239): the neutral defaults below are chosen so a
    # style-less render still satisfies charter 41's minimum-text-height
    # and non-overlap rules, not to reproduce any prior pixel output
    # (there is no prior "gorgeous" baseline to stay byte-identical to).

    # Typography scale (mm): caption < body < subtitle < title, charter
    # 41 sec. 1.1/1.3. Title-block field LABELS render at caption size,
    # values at body size.
    caption_text_height_mm: float = 2.5
    body_text_height_mm: float = 3.2
    subtitle_text_height_mm: float = 4.0
    sheet_title_text_height_mm: float = 5.5
    min_text_height_mm: float = 2.5

    # Deterministic text-measurement model: an average glyph width as a
    # fraction of the nominal text height (base-14 Helvetica has no
    # embedded metrics table here, AD-27 -- this is a conservative,
    # monospace-like upper bound so wrap/shrink never UNDER-estimates
    # width and lets a run clip).
    glyph_width_factor: float = 0.62

    # Line weights (mm, stroke width) -- frame/border vs. thinner
    # standard lines vs. extension/dimension lines (charter 41 sec. 1.3).
    line_weight_border_mm: float = 0.5
    line_weight_normal_mm: float = 0.25
    line_weight_thin_mm: float = 0.15

    # Table primitive (charter 41 sec. 1.5): ruled header + body rows.
    table_cell_pad_mm: float = 1.5
    table_min_col_w_mm: float = 14.0
    table_header_line_h_mm: float = 5.0
    table_row_line_h_mm: float = 4.5

    # Dimension entities (charter 41 sec. 2): extension-line offset from
    # the witnessed geometry, extension-line overshoot past the
    # dimension line, and arrowhead size.
    dim_extension_offset_mm: float = 2.0
    dim_extension_overshoot_mm: float = 1.5
    dim_arrow_len_mm: float = 2.5
    dim_arrow_half_w_mm: float = 0.8

    # Chart primitive (charter 41 sec. 2, opt traces): plot-area
    # padding for axis labels/ticks, tick length, and gridline count on
    # each axis (charter's "gridlines at minor emphasis").
    chart_axis_pad_mm: float = 18.0
    chart_tick_len_mm: float = 1.5
    chart_gridlines: int = 4

    # Style pack identity (charter 41 sec. 1.1's title-block "style pack
    # id" field, sec. 5): a hash-pinnable label, not a wire-schema
    # field -- the ONE home for the drafting look's name.
    pack_id: str = "neutral"


# The neutral default pack: byte-identical to the pre-D7 renderers.
NEUTRAL_STYLE = StyleRecord()


def resolve_style(style: StyleRecord | None) -> StyleRecord:
    """The style a renderer applies: the caller's pack, or the neutral
    default when ``None`` (WO-99 D7 -- a renderer never runs style-less)."""
    return style if style is not None else NEUTRAL_STYLE


# The float fields a `[style]` pack may override (every non-config field).
_STYLE_FIELDS = frozenset(StyleRecord.model_fields)


def _style_from_toml(path: Path) -> StyleRecord:
    """Overlay a ``[style]`` TOML table onto ``NEUTRAL_STYLE``.

    Only known style fields are read; an omitted field keeps its neutral
    value (so a partial pack overrides only what it names). An unknown key
    is logged and ignored -- a typo never silently changes an aesthetic.
    """
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    table = data.get("style", data)
    overrides: dict[str, float | int | str] = {}
    for key, value in table.items():
        if key not in _STYLE_FIELDS:
            _log.warning("style pack %s: ignoring unknown field %r", path, key)
            continue
        field_type = StyleRecord.model_fields[key].annotation
        if field_type is str:
            overrides[key] = str(value)
        elif field_type is int:
            overrides[key] = int(value)
        else:
            overrides[key] = float(value)
    return NEUTRAL_STYLE.model_copy(update=overrides)


def load_style_pack(pack_ref: str | None, search_paths: tuple[str, ...]) -> StyleRecord:
    """Resolve a project ``[style] pack`` reference (WO-99 D7 / charter 38
    sec. 1.12) into a :class:`StyleRecord`.

    ``None`` (no ``[style]`` in the manifest) is the neutral default pack
    (``NEUTRAL_STYLE``) -- so a project with no style config renders
    byte-identically to the pre-D7 output. A named pack is a ``[style]``
    TOML table found as ``<root>/<pack>/records/style.toml``,
    ``<root>/<pack>/style.toml``, or ``<root>/<pack>.toml`` under any
    ``search_paths`` root; a ref that resolves to no file is logged and
    falls back to the neutral default (never a crash).
    """
    if pack_ref is None:
        return NEUTRAL_STYLE
    for root in search_paths:
        base = Path(root)
        for candidate in (
            base / pack_ref / "records" / "style.toml",
            base / pack_ref / "style.toml",
            base / f"{pack_ref}.toml",
        ):
            if candidate.is_file():
                _log.debug("resolved style pack %r -> %s", pack_ref, candidate)
                return _style_from_toml(candidate)
    _log.warning(
        "style pack %r not found under %r; using neutral default",
        pack_ref,
        search_paths,
    )
    return NEUTRAL_STYLE
