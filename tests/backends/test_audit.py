"""WO-123 / charter 41 sec. 4 / INV-31: negative fixtures proving each
geometry-measured drafting rule BITES, plus the gating `assert_ship_ready`
seam. One deliberately-violating `DrawingModel` per F135 defect class --
the fixture set that would have REFUSED the pre-WO-123 renderer output.
"""

from __future__ import annotations

from regolith._codes import DRAFTING_AUDIT_REFUSED
from regolith._schema.models import (
    Annotation,
    Dimension,
    DrawingModel,
    EntityIndice,
    Kind,
    Kind4,
    Provenance1,
    Sheet,
    SheetSize1,
    Table,
    TableRow,
    TitleBlock,
    View,
    ViewSource,
)
from regolith._schema.models import Entity1 as SegmentEntity
from regolith.backends.drawings.audit import (
    assert_ship_ready,
    run_drafting_rules,
)


def _title_block(number: str = "NEG-001") -> TitleBlock:
    return TitleBlock(
        title="Negative Fixture",
        drawing_number=number,
        revision="A",
        scale_label="NTS",
        subject="negative_fixture",
    )


def _sheet(**overrides) -> Sheet:
    base = {
        "size": SheetSize1.ansi_a,
        "title_block": _title_block(),
        "views": [],
        "entities": [],
        "dimensions": [],
        "annotations": [],
        "tables": [],
    }
    base.update(overrides)
    return Sheet(**base)


def _model(sheet: Sheet) -> DrawingModel:
    return DrawingModel(subject="negative_fixture", sheets=[sheet])


def _failed_rules(model: DrawingModel) -> set[str]:
    return {r.rule for r in run_drafting_rules(model) if not r.passed}


class TestNegativeFixtures:
    """Each F135 defect class has a fixture the audit REFUSES with the
    named rule (charter 41 sec. 4: 'negative fixtures prove each rule
    bites')."""

    def test_clipping_annotation_is_refused(self):
        # F135.1/F135.2 class: a text run whose measured extent cannot
        # fit between its anchor and the page edge even at the floor
        # height (identity transform: no view). ANSI A is 279.4mm wide;
        # anchored 4mm from the right edge. WO-123's hard-split wrap
        # folds even an unbreakable token into the floor-width column,
        # so the reachable clip is now VERTICAL (F143: no continuation
        # sheet) -- enough text that the wrapped stack runs past the
        # frame bottom even at the floor height.
        sheet = _sheet(
            annotations=[
                Annotation(
                    text="UNBREAKABLE_" + "X" * 2000,
                    anchor=[275.0, 100.0],
                    text_height_mm=3.0,
                    datum_refs=[],
                    per=None,
                )
            ]
        )
        assert "no-clipping" in _failed_rules(_model(sheet))

    def test_overlapping_measured_bboxes_are_refused(self):
        # F135.3 class: two annotations with DISTINCT anchors whose
        # measured text boxes still collide (the old anchor-equality
        # rule passed exactly this).
        sheet = _sheet(
            annotations=[
                Annotation(
                    text="a long first annotation line of text",
                    anchor=[50.0, 100.0],
                    text_height_mm=4.0,
                    datum_refs=[],
                    per=None,
                ),
                Annotation(
                    text="a second annotation printed right on top",
                    anchor=[52.0, 101.0],
                    text_height_mm=4.0,
                    datum_refs=[],
                    per=None,
                ),
            ]
        )
        assert "geometric-overlap" in _failed_rules(_model(sheet))

    def test_pipe_delimited_table_cell_is_refused(self):
        # F135.2/F135.3 class: pipe-joined prose masquerading as a table
        # row (charter 41 sec. 1.5 bans it outright).
        sheet = _sheet(
            tables=[
                Table(
                    title="Bad Table",
                    columns=["row"],
                    rows=[TableRow(cells=["0|decoder_board|2.4|True|ok"])],
                )
            ]
        )
        assert "no-pipe-delimited-cells" in _failed_rules(_model(sheet))

    def test_dimension_running_off_page_is_refused(self):
        # F135.1 class: dimension text so wide no in-bounds placement
        # exists. WO-123 D238.3 defect 6 dropped the payload-path `role`
        # from the printed dimension text (human value only, "80.00
        # mm"), so the overflow fixture now pathologizes `unit` -- the
        # field the printed text still carries.
        entity = SegmentEntity(
            kind=Kind.segment, **{"from": [0.0, 0.0]}, to=[10.0, 0.0]
        )
        view = View(
            name="front",
            plane="XY",
            scale=1.0,
            source=ViewSource(source_digest="sha256:00", source_kind="test"),
            entity_indices=[EntityIndice(0)],
        )
        sheet = _sheet(
            views=[view],
            entities=[entity],
            dimensions=[
                Dimension(
                    anchor=[5.0, 0.0],
                    provenance=Provenance1(kind=Kind4.cause, label="test"),
                    role="bbox.width",
                    unit="an-absurdly-long-unit-string-" + "x" * 300,
                    value=10.0,
                    view_name="front",
                )
            ],
        )
        assert "dimension-in-bounds" in _failed_rules(_model(sheet))


class TestGatingSeam:
    """`assert_ship_ready` (D238.1): a failing sheet REFUSES with a
    named `BackendError` value -- never a raised exception -- and a
    clean sheet passes."""

    def test_failing_sheet_returns_named_error(self):
        sheet = _sheet(
            tables=[
                Table(
                    title="Bad Table",
                    columns=["row"],
                    rows=[TableRow(cells=["a|b|c"])],
                )
            ]
        )
        error = assert_ship_ready(_model(sheet), "negative_fixture")
        assert error is not None
        assert error.kind == DRAFTING_AUDIT_REFUSED
        assert "no-pipe-delimited-cells" in error.message
        assert "NEG-001" in error.message

    def test_clean_sheet_passes(self):
        sheet = _sheet(
            annotations=[
                Annotation(
                    text="a well-placed note",
                    anchor=[50.0, 100.0],
                    text_height_mm=3.0,
                    datum_refs=[],
                    per=None,
                )
            ],
            tables=[
                Table(
                    title="Good Table",
                    columns=["name", "qty"],
                    rows=[TableRow(cells=["bolt", "4"])],
                )
            ],
        )
        assert assert_ship_ready(_model(sheet), "negative_fixture") is None

    def test_rules_are_deterministic_across_runs(self):
        # INV-31's determinism leg: the audit is a pure function of
        # (model, style) -- two runs agree rule-for-rule.
        sheet = _sheet(
            annotations=[
                Annotation(
                    text="deterministic note",
                    anchor=[40.0, 90.0],
                    text_height_mm=3.0,
                    datum_refs=[],
                    per=None,
                )
            ]
        )
        model = _model(sheet)
        first = run_drafting_rules(model)
        second = run_drafting_rules(model)
        assert first == second
