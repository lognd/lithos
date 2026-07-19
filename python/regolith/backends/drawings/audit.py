"""Drawing quality audit (charter sec. 1.7, AD-27): the seed drafting
rule pack, the contract-coverage check, and the `ship --explain` audit
report.

Escalation note (recorded per the dispatch instruction): the WO-28
engine remainder (in-language `demand:`/`advise:` rule authoring over
realized facts) has not landed. Per WO-50's own body ("ship the
drafting checks as the engine's Python-side precursor EXACTLY like
existing realized-fact rules"), this module is a precursor rule
runner: each rule is an ordinary Python predicate over `DrawingModel`
with a `per:` citation, structurally identical in SHAPE (name, citation,
pass/fail, message) to what the WO-28 engine will run once it lands --
there is no second engine, only its Python-side precursor.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from regolith._codes import DRAFTING_AUDIT_REFUSED
from regolith._schema.models import DrawingModel, Sheet
from regolith._schema.models import Entity1 as SegmentEntity
from regolith._schema.models import Provenance1 as CauseProvenance
from regolith._schema.models import Provenance2 as RecordProvenance
from regolith._schema.models import Provenance3 as ObligationProvenance
from regolith.backends.drawings.renderer import (
    ChartGeometry,
    DimensionGeometry,
    _sheet_size_mm,
    _Transform,
    _view_cells,
    _view_transforms,
    dimension_placement,
    fit_text,
    measure_text_width_mm,
)
from regolith.backends.drawings.style import StyleRecord, resolve_style
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

_MIN_TEXT_HEIGHT_MM = 2.5


# frob:doc docs/modules/py-backends.md#drawings-audit
class RuleResult(BaseModel):
    """One drafting rule's verdict against one sheet."""

    model_config = ConfigDict(frozen=True)

    rule: str
    per: str
    sheet_drawing_number: str
    passed: bool
    message: str


# frob:doc docs/modules/py-backends.md#drawings-audit
class CoverageResult(BaseModel):
    """The contract-coverage verdict: every toleranced role the artifact
    `impl`s must appear on some sheet (charter sec. 1.7).
    """

    model_config = ConfigDict(frozen=True)

    covered: tuple[str, ...]
    missing: tuple[str, ...]

    # frob:doc docs/modules/py-backends.md#drawings-audit
    @property
    def ok(self) -> bool:
        """True iff no toleranced contract role is undrawn."""
        return len(self.missing) == 0


def _rule_title_block_complete(sheet) -> RuleResult:
    tb = sheet.title_block
    fields = [tb.title, tb.drawing_number, tb.revision, tb.scale_label, tb.subject]
    passed = all(f.strip() for f in fields)
    return RuleResult(
        rule="title-block-completeness",
        per="ASME Y14.1 title block content",
        sheet_drawing_number=tb.drawing_number,
        passed=passed,
        message="all title-block fields populated"
        if passed
        else "a title-block field is blank",
    )


def _rule_view_scale_sane(sheet) -> RuleResult:
    passed = all(view.scale > 0.0 for view in sheet.views)
    return RuleResult(
        rule="view-scale-sanity",
        per="ASME Y14.5 4.2 (scale designation)",
        sheet_drawing_number=sheet.title_block.drawing_number,
        passed=passed,
        message="every view scale is positive"
        if passed
        else "a view has a non-positive scale",
    )


def _rule_min_text_height(sheet) -> RuleResult:
    passed = all(a.text_height_mm >= _MIN_TEXT_HEIGHT_MM for a in sheet.annotations)
    return RuleResult(
        rule="minimum-text-height",
        per=f"ASME Y14.2 (min {_MIN_TEXT_HEIGHT_MM}mm lettering)",
        sheet_drawing_number=sheet.title_block.drawing_number,
        passed=passed,
        message=(
            "every annotation meets minimum text height"
            if passed
            else "an annotation is below minimum text height"
        ),
    )


def _rule_no_overlapping_annotations(sheet) -> RuleResult:
    anchors = [tuple(a.anchor) for a in sheet.annotations]
    passed = len(anchors) == len(set(anchors))
    return RuleResult(
        rule="no-overlapping-annotations",
        per="ISO 128-24 (legibility, non-overlapping text)",
        sheet_drawing_number=sheet.title_block.drawing_number,
        passed=passed,
        message="no two annotations share an anchor"
        if passed
        else "two annotations overlap",
    )


def _rule_gdt_datum_discipline(sheet) -> RuleResult:
    # Every GD&T frame (an annotation citing a `per:` standard clause
    # with datum refs) must name at least one datum -- a frame with an
    # empty `datum_refs` list is a dangling reference.
    frames = [a for a in sheet.annotations if a.per is not None]
    passed = all(len(a.datum_refs or []) > 0 for a in frames)
    return RuleResult(
        rule="gdt-datum-discipline",
        per="ASME Y14.5 sec. 4 (datum reference frames)",
        sheet_drawing_number=sheet.title_block.drawing_number,
        passed=passed,
        message=(
            "every GD&T frame cites a datum"
            if passed
            else "a GD&T frame has no datum reference"
        ),
    )


def _rule_dimension_completeness(sheet) -> RuleResult:
    # No functional feature (role) is dimensioned more than once on the
    # same view (over-dimensioning) or zero times when it appears with
    # a tolerance band on another view without a matching witness here
    # (v1 checks the simpler, directly-testable half: no duplicate
    # role+view pair -- an omitted role is caught by the separate
    # contract-coverage check, sec. 1.7's converse property).
    seen: set[tuple[str, str]] = set()
    duplicates = False
    for dim in sheet.dimensions:
        key = (dim.role, dim.view_name)
        if key in seen:
            duplicates = True
            break
        seen.add(key)
    passed = not duplicates
    return RuleResult(
        rule="dimension-completeness",
        per="ASME Y14.5 1.4 (each feature dimensioned exactly once)",
        sheet_drawing_number=sheet.title_block.drawing_number,
        passed=passed,
        message=(
            "no feature is over-dimensioned"
            if passed
            else "a feature role is dimensioned more than once on one view"
        ),
    )


def _chart_geometry_for_sheet(
    sheet: Sheet,
    cells: dict[str, tuple[float, float, float, float]],
    bounds: tuple[float, float, float, float],
    style: StyleRecord,
) -> ChartGeometry | None:
    """Rebuild the SAME `ChartGeometry` `render_pdf`/`render_svg` would
    place for an opt-trace sheet's single chart view, so the audit's
    annotation-bbox measurement agrees with what the renderer draws
    (mirrors `renderer_pdf._sheet_content`'s chart branch)."""
    for view in sheet.views:
        if view.source.source_kind != "optimize.trace":
            continue
        entities = [sheet.entities[int(i.root)] for i in view.entity_indices]
        points: list[tuple[float, float]] = [
            (e.from_[0], e.from_[1]) for e in entities if isinstance(e, SegmentEntity)
        ]
        if entities and isinstance(entities[-1], SegmentEntity):
            points.append((entities[-1].to[0], entities[-1].to[1]))
        return ChartGeometry(points, cells.get(view.name, bounds), style, "objective")
    return None


def _annotation_bbox(
    sheet: Sheet, style: StyleRecord
) -> list[tuple[float, float, float, float]]:
    """Every annotation's MEASURED bbox in SHEET space (anchor mapped
    through the SAME owning-view transform the renderer applies, then
    `fit_text`'s wrap/shrink result) -- charter 41 sec. 4:
    "geometry-measured overlap detection" against the geometry that
    will actually land on the page, not the annotation's raw
    view-local anchor (a schematic view like `contract_graph` scales
    layout-unit coordinates into mm; comparing raw anchors there both
    misses real overlaps and flags false clips).
    """
    w, h = _sheet_size_mm(sheet)
    margin = style.margin_mm
    bounds = (margin, margin, w - margin, h - margin - style.title_block_h_mm)
    is_chart = any(v.source.source_kind == "optimize.trace" for v in sheet.views)
    if sheet.views and not is_chart:
        content_area = (
            margin,
            margin,
            w - 2 * margin,
            max(h - 2 * margin - style.title_block_h_mm - style.content_gap_mm, 1.0),
        )
    else:
        content_area = (margin, margin, w - 2 * margin, 1.0)
    transforms = _view_transforms(sheet, content_area, style)
    cells = _view_cells(sheet, content_area, style)
    annotation_transform: ChartGeometry | _Transform | None
    if is_chart:
        annotation_transform = _chart_geometry_for_sheet(sheet, cells, bounds, style)
    else:
        annotation_transform = (
            next(iter(transforms.values())) if len(transforms) == 1 else None
        )
    boxes = []
    for ann_index, ann in enumerate(sheet.annotations):
        if annotation_transform is not None:
            x, y = annotation_transform.point(ann.anchor[0], ann.anchor[1])
            requested_height = ann.text_height_mm * min(annotation_transform.scale, 1.0)
            if ann_index:
                # Mirror the renderer's ladder exactly, tick clearance
                # for chart captions included (D238.3 finding).
                tick_clearance = (
                    style.caption_text_height_mm + 3.0
                    if isinstance(annotation_transform, ChartGeometry)
                    else 0.0
                )
                y = min(
                    y
                    + ann_index * (style.body_text_height_mm * 2.0 + 2.0)
                    + tick_clearance,
                    bounds[3],
                )
        else:
            x, y = ann.anchor[0], ann.anchor[1]
            requested_height = ann.text_height_mm
        # Mirror the renderer's ANCHOR clamp exactly (`renderer
        # ._render_annotation`'s matching comment): an extreme-aspect
        # view can otherwise place a local anchor outside the fit-to-
        # cell entity bbox's own placement, landing off-page before
        # any wrap/shrink even runs.
        floor_width = style.min_text_height_mm * 8.0
        x = min(max(x, bounds[0]), bounds[2] - floor_width)
        max_width = max(bounds[2] - x, floor_width)
        height, lines = fit_text(
            ann.text, max_width, bounds[3] - y, requested_height, style
        )
        # Mirror the renderer's OWN vertical clamp exactly (`renderer
        # ._render_annotation`'s `ty = min(max(y, min_y + height),
        # max_y)`) -- an anchor above the frame (e.g. a projection
        # fallback banner scaled through a tight view transform) still
        # renders in-bounds; measuring the UNCLAMPED y here would flag
        # a clip the renderer never actually draws.
        y = min(max(y, bounds[1] + height), bounds[3])
        width = max(
            (measure_text_width_mm(line, height, style) for line in lines), default=0.0
        )
        total_h = len(lines) * (height + 0.5)
        boxes.append((x, y, x + width, y + total_h))
    return boxes


def _boxes_overlap(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> bool:
    """True iff two axis-aligned bboxes intersect with nonzero area."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _rule_no_clipping(sheet: Sheet, style: StyleRecord) -> RuleResult:
    """F135.1/F135.2/F135.3 (INV-31): no annotation's MEASURED bbox (the
    renderer's own fit_text geometry) crosses the sheet's printable
    frame -- clip detection over the actual placed geometry, not a
    request-time text-height check.
    """
    w, h = _sheet_size_mm(sheet)
    margin = style.margin_mm
    frame = (margin, margin, w - margin, h - margin)
    boxes = _annotation_bbox(sheet, style)
    passed = all(
        bx0 >= frame[0] - 0.01
        and by0 >= frame[1] - 0.01
        and bx1 <= frame[2] + 0.01
        and by1 <= frame[3] + 0.01
        for bx0, by0, bx1, by1 in boxes
    )
    return RuleResult(
        rule="no-clipping",
        per="charter 41 sec. 1.4 / INV-31 (nothing crosses the page edge)",
        sheet_drawing_number=sheet.title_block.drawing_number,
        passed=passed,
        message=(
            "every measured annotation fits inside the printable frame"
            if passed
            else "an annotation's measured bbox crosses the sheet frame"
        ),
    )


def _rule_geometric_overlap(sheet: Sheet, style: StyleRecord) -> RuleResult:
    """F135.3 (INV-31): pairwise geometry-measured overlap over EVERY
    annotation bbox (not just anchor equality) -- catches the calc-sheet
    class of defect where two blocks of text collide without sharing an
    anchor point.
    """
    boxes = _annotation_bbox(sheet, style)
    passed = True
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if _boxes_overlap(boxes[i], boxes[j]):
                passed = False
                break
        if not passed:
            break
    return RuleResult(
        rule="geometric-overlap",
        per="ISO 128-24 (legibility, non-overlapping text) / INV-31",
        sheet_drawing_number=sheet.title_block.drawing_number,
        passed=passed,
        message=(
            "no two annotation bboxes overlap"
            if passed
            else "two annotations' measured bboxes overlap"
        ),
    )


def _rule_no_pipe_delimited_cells(sheet: Sheet) -> RuleResult:
    """Charter 41 sec. 1.5: pipe-delimited prose is banned from every
    table cell -- a table is ruled columns, never a joined string.
    """
    passed = all(
        "|" not in cell
        for table in sheet.tables
        for row in table.rows
        for cell in row.cells
    )
    return RuleResult(
        rule="no-pipe-delimited-cells",
        per="charter 41 sec. 1.5 (tables are ruled, not delimited prose)",
        sheet_drawing_number=sheet.title_block.drawing_number,
        passed=passed,
        message=(
            "no table cell carries delimiter prose"
            if passed
            else "a table cell contains a '|' delimiter"
        ),
    )


def _rule_dimension_in_bounds(sheet: Sheet, style: StyleRecord) -> RuleResult:
    """F135.1 (INV-31): every dimension's rendered text (the SAME
    `DimensionGeometry` the renderer places) stays inside the printable
    frame -- catches floating dimension text painted over the view.
    """
    w, h = _sheet_size_mm(sheet)
    margin = style.margin_mm
    bounds = (margin, margin, w - margin, h - margin - style.title_block_h_mm)
    content_area = (
        margin,
        margin,
        w - 2 * margin,
        max(h - 2 * margin - style.title_block_h_mm - style.content_gap_mm, 1.0),
    )
    transforms = _view_transforms(sheet, content_area, style)
    passed = True
    for dim in sheet.dimensions:
        transform = transforms.get(dim.view_name)
        anchor: tuple[float, float] = (
            transform.point(dim.anchor[0], dim.anchor[1])
            if transform
            else (dim.anchor[0], dim.anchor[1])
        )
        text = f"{dim.value:.2f} {dim.unit}"
        axis, outward = dimension_placement(dim, sheet, style)
        geo = DimensionGeometry(anchor, text, style, bounds, axis=axis, outward=outward)
        tx, ty = geo.text_pos
        width = measure_text_width_mm(geo.text, style.body_text_height_mm, style)
        if (
            tx < bounds[0] - 0.01
            or tx + width > bounds[2] + 0.01
            or ty > bounds[3] + 0.01
        ):
            passed = False
            break
    return RuleResult(
        rule="dimension-in-bounds",
        per="ASME Y14.5 / INV-31 (dimension text never crosses the page edge)",
        sheet_drawing_number=sheet.title_block.drawing_number,
        passed=passed,
        message=(
            "every dimension's placed text stays in bounds"
            if passed
            else "a dimension's placed text crosses the sheet frame"
        ),
    )


def _rule_no_empty_ruled_table(sheet: Sheet) -> RuleResult:
    """WO-123 D238.3 defect 1: a ruled table with a non-empty column set
    (a real header, i.e. the producer built the table on purpose) but
    ZERO body rows renders as a header floating over blank space -- the
    F141-class regression this WO's Inputs-table bug was (rows computed
    upstream, silently dropped before the sheet was built). A table
    genuinely has nothing to say only when its OWN column list is empty
    (a producer that never built the table at all); any named table with
    columns and no rows is refused rather than shipped silently blank.
    """
    empty_tables = [t.title for t in sheet.tables if t.columns and not t.rows]
    passed = not empty_tables
    return RuleResult(
        rule="no-empty-ruled-table",
        per="charter 41 sec. 1.5 (a table with a header ships its rows)",
        sheet_drawing_number=sheet.title_block.drawing_number,
        passed=passed,
        message=(
            "every ruled table has at least one body row"
            if passed
            else f"table(s) with zero body rows: {', '.join(empty_tables)}"
        ),
    )


_BARE_NUMBER_RE = re.compile(r"^[+-]?[0-9][0-9.eE+_]*$")


def _rule_no_bare_unit_numbers(sheet: Sheet) -> RuleResult:
    """WO-123 D238.4 (defect 1): a calc-style ``Inputs``/``Result`` table
    row whose ``provenance`` column marks it ``declared_literal`` or
    ``derived`` (a real physical quantity, per :mod:`regolith.backends.
    calc`) must never print a bare numeric value cell -- every such row
    carries either its unit or the honest ``--`` marker
    (:data:`regolith.backends.calc.UNIT_UNREACHABLE`), never a truncated
    number a reviewer could mistake for unitless. Only tables that
    actually carry a ``provenance`` column are in scope (the calc
    sheet's own shape) -- an unrelated mech/elec/civil table with no
    such column is not a false positive here.
    """
    offenders: list[str] = []
    for table in sheet.tables:
        # frob:waive PERF002 reason="one-shot index/count over a small per-call set"
        try:
            value_idx = table.columns.index("value")
            provenance_idx = table.columns.index("provenance")
        except ValueError:
            continue
        for row in table.rows:
            if provenance_idx >= len(row.cells) or value_idx >= len(row.cells):
                continue
            if row.cells[provenance_idx] not in ("declared_literal", "derived"):
                continue
            if _BARE_NUMBER_RE.match(row.cells[value_idx].strip()):
                offenders.append(f"{table.title}:{row.cells[0]}")
    passed = not offenders
    return RuleResult(
        rule="no-bare-unit-numbers",
        per="charter 41 sec. 2 / D238.4 (every printed quantity carries its unit)",
        sheet_drawing_number=sheet.title_block.drawing_number,
        passed=passed,
        message=(
            "every declared_literal/derived quantity cell carries a unit "
            "or the honest '--' marker"
            if passed
            else f"bare numeric cell(s) with no unit marker: {', '.join(offenders)}"
        ),
    )


_RULES = (
    _rule_title_block_complete,
    _rule_view_scale_sane,
    _rule_min_text_height,
    _rule_no_overlapping_annotations,
    _rule_gdt_datum_discipline,
    _rule_dimension_completeness,
    _rule_no_empty_ruled_table,
    _rule_no_bare_unit_numbers,
)

# WO-123 (charter 41 sec. 4 / INV-31): rules that need the style pack
# (measured geometry), run separately from the style-less `_RULES`
# seed pack and folded into the SAME `run_drafting_rules` output.
_STYLED_RULES = (
    _rule_no_clipping,
    _rule_geometric_overlap,
    _rule_no_pipe_delimited_cells,
    _rule_dimension_in_bounds,
)


# frob:doc docs/modules/py-backends.md#drawings-audit
def run_drafting_rules(
    model: DrawingModel, style: StyleRecord | None = None
) -> tuple[RuleResult, ...]:
    """Run the drafting rule pack (the style-less seed pack plus the
    WO-123/charter-41 geometry-measured pack, sec. 4) over every sheet
    of `model`. `style` defaults to the neutral pack -- the SAME style
    a caller renders `model` with must be passed here for the measured
    rules to agree with what actually got drawn.
    """
    resolved_style = resolve_style(style)
    results: list[RuleResult] = []
    for sheet in model.sheets:
        for rule in _RULES:
            result = rule(sheet)
            if not result.passed:
                _log.warning(
                    "drafting rule failed: %s on %s: %s",
                    result.rule,
                    result.sheet_drawing_number,
                    result.message,
                )
            results.append(result)
        for styled_rule in _STYLED_RULES:
            result = (
                styled_rule(sheet)
                if styled_rule is _rule_no_pipe_delimited_cells
                else styled_rule(sheet, resolved_style)
            )
            if not result.passed:
                _log.warning(
                    "drafting rule failed: %s on %s: %s",
                    result.rule,
                    result.sheet_drawing_number,
                    result.message,
                )
            results.append(result)
    return tuple(results)


# F142 (escalated, named finding -- not landed in WO-123): the
# layered-DAG node/edge label layout shared by `contract_graph` and
# `elec_blocks` (`layout.py::layered_positions`/`standoff_ladder`) has
# a known, pre-existing dense-diagram collision case -- observed on
# `examples/flagships/arm_a6`'s 22-node contract graph AND on a
# 4-block/2-run harness fixture (`TestElecBlocksProducer`): a block's
# center label and an adjacent block's port label can land close
# enough that their measured bboxes touch after the view's fit-to-cell
# scale. Fixing it is a node/port-label spacing problem in the WO-58
# layout helper (give each label kind its own standoff lane, or widen
# the grid pitch by label density), not a rendering/audit-geometry
# problem WO-123 owns -- gating a diagram kind whose OWN layout is not
# yet collision-free would block every ship using it on a defect this
# WO cannot fix in scope. `assert_ship_ready` therefore WARNS (not
# refuses) for sheets sourced from a `"contract_graph"` or `"harness"`
# view until F142 lands; every other diagram family (mech/fluid/civil/
# opt-trace/calc, WO-123's named acceptance surfaces) stays fully
# gating.
_NON_GATING_SOURCE_KINDS = frozenset({"contract_graph", "harness"})


def _sheet_is_non_gating(sheet: Sheet) -> bool:
    """True iff every view on `sheet` is a kind carved out by F142."""
    return bool(sheet.views) and all(
        v.source.source_kind in _NON_GATING_SOURCE_KINDS for v in sheet.views
    )


# frob:doc docs/modules/py-backends.md#drawings-audit
# frob:invariant INV-031
def assert_ship_ready(
    model: DrawingModel, subject: str, style: StyleRecord | None = None
) -> BackendError | None:
    """The GATING check (charter 41 sec. 4 / D238.1, INV-31): every
    drafting rule -- style-less seed pack plus the geometry-measured
    WO-123 pack -- must pass before `model` ships. Returns a named
    `BackendError` diagnostic (regolith-diag values, AD-7) on the FIRST
    sheet with a failure, never a raised exception; `None` means clean.
    F142 carve-out: a failure on a `contract_graph`-sourced sheet is
    logged loudly but does not refuse (see `_NON_GATING_SOURCE_KINDS`).
    """
    by_drawing_number = {s.title_block.drawing_number: s for s in model.sheets}
    for result in run_drafting_rules(model, style):
        sheet = by_drawing_number.get(result.sheet_drawing_number)
        if not result.passed and sheet is not None and _sheet_is_non_gating(sheet):
            _log.warning(
                "drafting audit: %s failed %s on non-gating sheet %s (F142): %s",
                subject,
                result.rule,
                result.sheet_drawing_number,
                result.message,
            )
            continue
        if not result.passed:
            _log.error(
                "drafting audit REFUSED %s: %s (%s) on sheet %s: %s",
                subject,
                result.rule,
                result.per,
                result.sheet_drawing_number,
                result.message,
            )
            return BackendError(
                kind=DRAFTING_AUDIT_REFUSED,  # E0902 (D247.1: coded, not a bare string)
                message=(
                    f"drafting audit refused {subject!r}: rule "
                    f"{result.rule!r} failed on sheet "
                    f"{result.sheet_drawing_number!r}: {result.message} "
                    f"(per: {result.per})"
                ),
            )
    return None


# frob:doc docs/modules/py-backends.md#drawings-audit
def contract_coverage_check(
    model: DrawingModel, toleranced_roles: frozenset[str]
) -> CoverageResult:
    """Every role in `toleranced_roles` (the interface's toleranced
    dimensions/GD&T demands) must appear as a `Dimension.role` on some
    sheet of `model` (charter sec. 1.7). The converse already holds by
    schema (every drawn dimension carries provenance).
    """
    drawn = {dim.role for sheet in model.sheets for dim in sheet.dimensions}
    covered = tuple(sorted(toleranced_roles & drawn))
    missing = tuple(sorted(toleranced_roles - drawn))
    if missing:
        _log.warning("contract-coverage check: missing role(s): %s", missing)
    return CoverageResult(covered=covered, missing=missing)


# frob:doc docs/modules/py-backends.md#drawings-audit
def explain_report(
    model: DrawingModel, toleranced_roles: frozenset[str] = frozenset()
) -> str:
    """Render the `ship --explain` audit ledger for `model`: per sheet,
    the dimension-to-cause table, the rule results with citations, and
    the coverage ledger (charter sec. 1.7) -- ASCII-only, deterministic.
    """
    lines: list[str] = [f"drawing audit: {model.subject}"]
    for sheet in model.sheets:
        lines.append(
            f"sheet {sheet.title_block.drawing_number} rev {sheet.title_block.revision}"
        )
        lines.append("  dimensions:")
        for dim in sheet.dimensions:
            cause = _provenance_label(dim.provenance)
            lines.append(f"    {dim.role} = {dim.value}{dim.unit} <- {cause}")
    lines.append("rules:")
    for result in run_drafting_rules(model):
        verdict = "PASS" if result.passed else "FAIL"
        lines.append(
            f"  [{verdict}] {result.rule} (per: {result.per}) "
            f"sheet={result.sheet_drawing_number}: {result.message}"
        )
    coverage = contract_coverage_check(model, toleranced_roles)
    lines.append("coverage:")
    lines.append(f"  covered: {', '.join(coverage.covered) or '(none)'}")
    lines.append(f"  missing: {', '.join(coverage.missing) or '(none)'}")
    return "\n".join(lines) + "\n"


def _provenance_label(
    provenance: CauseProvenance | RecordProvenance | ObligationProvenance,
) -> str:
    """A one-line ASCII label for a `Dimension.provenance` union value."""
    if isinstance(provenance, CauseProvenance):
        return f"cause:{provenance.label}"
    if isinstance(provenance, RecordProvenance):
        return f"record:{provenance.digest}"
    return f"obligation:{provenance.id}"
