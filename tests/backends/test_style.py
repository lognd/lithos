"""WO-99 D7 / charter 38 sec. 1.12: style records threaded through the
SVG/DXF/PDF renderers. The NEUTRAL default reproduces every historical
hard-coded constant EXACTLY (byte-identical), and a project ``[style]``
pack overrides a constant end-to-end.
"""

from __future__ import annotations

from regolith._schema.models import (
    DrawingModel,
    EntityIndice,
    Kind,
    Sheet,
    SheetSize1,
    TitleBlock,
    View,
    ViewSource,
)
from regolith._schema.models import (
    Entity1 as SegmentEntity,
)
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.drawings.renderer_dxf import render_dxf
from regolith.backends.drawings.renderer_pdf import render_pdf
from regolith.backends.drawings.style import (
    NEUTRAL_STYLE,
    StyleRecord,
    load_style_pack,
    resolve_style,
)


def _model() -> DrawingModel:
    entities = [
        SegmentEntity(kind=Kind.segment, **{"from": [0.0, 0.0]}, to=[40.0, 0.0]),
        SegmentEntity(kind=Kind.segment, **{"from": [40.0, 0.0]}, to=[40.0, 25.0]),
    ]
    view = View(
        name="front",
        plane="XY",
        scale=1.0,
        source=ViewSource(
            source_digest="local-blake3:x", source_kind="geometry.realized"
        ),
        entity_indices=[EntityIndice(0), EntityIndice(1)],
    )
    sheet = Sheet(
        size=SheetSize1.ansi_a,
        title_block=TitleBlock(
            title="widget",
            drawing_number="DWG-widget",
            revision="A",
            scale_label="1:1",
            subject="widget",
        ),
        views=[view],
        entities=entities,
        dimensions=[],
        annotations=[],
        tables=[],
    )
    return DrawingModel(subject="widget", sheets=[sheet])


class TestNeutralByteIdentical:
    """The neutral default pack reproduces the pre-D7 output exactly:
    passing NEUTRAL_STYLE (or None) must be byte-for-byte identical."""

    def test_svg_none_equals_neutral(self):
        model = _model()
        assert render_svg(model) == render_svg(model, NEUTRAL_STYLE)

    def test_dxf_none_equals_neutral(self):
        model = _model()
        assert render_dxf(model) == render_dxf(model, NEUTRAL_STYLE)

    def test_pdf_none_equals_neutral(self):
        model = _model()
        assert render_pdf(model) == render_pdf(model, NEUTRAL_STYLE)

    def test_svg_two_runs_byte_identical(self):
        model = _model()
        assert render_svg(model) == render_svg(model)


class TestStylePackOverride:
    """A project [style] pack overrides a constant, reaching the renderer."""

    def test_override_changes_render(self):
        model = _model()
        # Overriding the sheet margin moves the frame -> different bytes.
        styled = StyleRecord(margin_mm=25.0)
        assert render_svg(model, styled) != render_svg(model)
        # The frame rect x now reflects the wider margin.
        assert 'x="25.0000"' in render_svg(model, styled).decode("ascii")

    def test_load_style_pack_none_is_neutral(self):
        assert load_style_pack(None, ()) == NEUTRAL_STYLE

    def test_load_style_pack_missing_falls_back_to_neutral(self):
        assert load_style_pack("nonesuch", (".",)) == NEUTRAL_STYLE

    def test_load_style_pack_overlays_toml(self, tmp_path):
        pack = tmp_path / "my.style"
        (pack / "records").mkdir(parents=True)
        (pack / "records" / "style.toml").write_text(
            "[style]\nmargin_mm = 18.0\ntitle_block_w_mm = 90.0\n",
            encoding="ascii",
        )
        resolved = load_style_pack("my.style", (str(tmp_path),))
        assert resolved.margin_mm == 18.0
        assert resolved.title_block_w_mm == 90.0
        # An unmentioned field keeps the neutral value.
        assert resolved.dim_standoff_mm == NEUTRAL_STYLE.dim_standoff_mm

    def test_resolve_style_none(self):
        assert resolve_style(None) is NEUTRAL_STYLE
