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

from pydantic import BaseModel, ConfigDict

from regolith._schema.models import DrawingModel
from regolith._schema.models import Provenance1 as CauseProvenance
from regolith._schema.models import Provenance2 as RecordProvenance
from regolith._schema.models import Provenance3 as ObligationProvenance
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

_MIN_TEXT_HEIGHT_MM = 2.5


class RuleResult(BaseModel):
    """One drafting rule's verdict against one sheet."""

    model_config = ConfigDict(frozen=True)

    rule: str
    per: str
    sheet_drawing_number: str
    passed: bool
    message: str


class CoverageResult(BaseModel):
    """The contract-coverage verdict: every toleranced role the artifact
    `impl`s must appear on some sheet (charter sec. 1.7).
    """

    model_config = ConfigDict(frozen=True)

    covered: tuple[str, ...]
    missing: tuple[str, ...]

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


_RULES = (
    _rule_title_block_complete,
    _rule_view_scale_sane,
    _rule_min_text_height,
    _rule_no_overlapping_annotations,
    _rule_gdt_datum_discipline,
    _rule_dimension_completeness,
)


def run_drafting_rules(model: DrawingModel) -> tuple[RuleResult, ...]:
    """Run the seed drafting rule pack over every sheet of `model`."""
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
    return tuple(results)


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
