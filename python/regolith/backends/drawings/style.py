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
    title_block_w_mm: float = 80.0
    title_block_h_mm: float = 28.0
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
    overrides: dict[str, float] = {}
    for key, value in table.items():
        if key in _STYLE_FIELDS:
            overrides[key] = float(value)
        else:
            _log.warning("style pack %s: ignoring unknown field %r", path, key)
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
