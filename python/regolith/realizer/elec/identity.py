"""Board-identity silkscreen geometry: the ONE home for text height,
margin, and placement math shared by every board-authoring leg
(WO-124 visual-pass fixes; charter 41 sec. 3).

Three legs draw the identity block -- `fake_kicad._kicad_pcb_text`
(gr_text), `kicad_wrapper._draw_identity_text` (pcbnew), and
`backends.elec_fabset.build_fake_fab_set` (the hand-rolled gerber
writer) -- and the coordinator's D238.3 inspection found them
agreeing on the WRONG numbers (center-anchored text hanging off the
board edge, ~1.2mm line height below the charter minimum). This
module makes the corrected numbers single-sourced so the legs cannot
drift apart again.
"""

from __future__ import annotations

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# Charter 41 sec. 1.3 minimum rendered text height. Deliberately the
# same 2.5mm value as `backends.drawings.audit._MIN_TEXT_HEIGHT_MM`
# (ASME Y14.2 lettering); kept as its own named constant here because
# board silkscreen is a different artifact family from sheet
# annotations and the drawings audit module must stay import-free of
# realizer concerns (and vice versa -- no layering cycle).
# frob:doc docs/modules/py-realizer.md#elec-identity
MIN_TEXT_HEIGHT_MM = 2.5

# Identity text never needs to shout: cap the scaled height.
# frob:doc docs/modules/py-realizer.md#elec-identity
MAX_TEXT_HEIGHT_MM = 5.0

# Approximate advance width per character as a fraction of text
# height. Holds for BOTH text engines in play: KiCad's newstroke font
# at default width (~0.9h incl. spacing) and the 3x5 stick font
# (4/5 h advance) -- the larger estimate is used so the fit check is
# conservative for either.
# frob:doc docs/modules/py-realizer.md#elec-identity
CHAR_ADVANCE_FRACTION = 0.9

# Vertical gap between the two identity lines, as a fraction of the
# text height (baseline-to-baseline is 1 + this).
# frob:doc docs/modules/py-realizer.md#elec-identity
LINE_GAP_FRACTION = 0.6


# frob:doc docs/modules/py-realizer.md#elec-identity
def identity_margin_mm(w_mm: float, d_mm: float) -> float:
    """The identity block's ANCHOR clearance from the board edge: 3mm
    minimum, growing gently with board size. The floor is 3mm (not the
    D238.3 inspection bar of 2mm) because rendered strokes overshoot
    the anchor by up to ~0.5mm (half stroke thickness + glyph
    descenders, measured against real kicad-cli 10.0.4 plots), and the
    INK must clear 2mm, not just the anchor."""
    return max(3.0, 0.012 * min(w_mm, d_mm))


# frob:doc docs/modules/py-realizer.md#elec-identity
def identity_text_height_mm(w_mm: float, d_mm: float, longest_line_chars: int) -> float:
    """The identity block's per-line text height: scaled to the board
    (1.8% of the short side), clamped to [2.5mm, 5mm], then
    shrunk-to-floor if the longest line would not fit the board width
    inside the margins (charter 41 sec. 1.4's shrink rule -- never
    below the 2.5mm minimum, even if that means a long line on a tiny
    board overruns; an overrun at the floor is the honest outcome the
    drafting audit exists to flag, not a reason to render illegible
    text)."""
    h = min(MAX_TEXT_HEIGHT_MM, max(MIN_TEXT_HEIGHT_MM, 0.018 * min(w_mm, d_mm)))
    if longest_line_chars > 0:
        available = w_mm - 2.0 * identity_margin_mm(w_mm, d_mm)
        fit = available / (CHAR_ADVANCE_FRACTION * longest_line_chars)
        if fit < h:
            shrunk = max(MIN_TEXT_HEIGHT_MM, fit)
            _log.debug(
                "identity text shrink-to-fit: %.2fmm -> %.2fmm (%d chars in %.1fmm)",
                h,
                shrunk,
                longest_line_chars,
                available,
            )
            h = shrunk
    return h


# frob:doc docs/modules/py-realizer.md#elec-identity
def identity_block_layout(
    w_mm: float, d_mm: float, name_line: str, rev_line: str
) -> tuple[float, tuple[tuple[str, float, float], ...]]:
    """Bottom-left-inside placement for the two identity lines.

    Returns ``(text_height_mm, ((text, x_mm, y_down_mm), ...))`` in
    BOARD coordinates with +y DOWN (the `.kicad_pcb` convention; a
    gerber-space caller flips y itself). Each anchor is the LEFT end
    of the line's BOTTOM edge -- the drawing leg must left/bottom
    justify (this is exactly the D238.3 off-board defect: KiCad's
    default center anchor pushed half the text past x=0)."""
    longest = max(len(name_line), len(rev_line))
    h = identity_text_height_mm(w_mm, d_mm, longest)
    m = identity_margin_mm(w_mm, d_mm)
    rev_y = d_mm - m
    name_y = rev_y - (1.0 + LINE_GAP_FRACTION) * h
    return h, ((name_line, m, name_y), (rev_line, m, rev_y))
