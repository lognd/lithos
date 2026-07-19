"""Unit-test coverage closing frob's TEST001 gate for
`python/regolith/backends` (wave-agent frob-adoption pass, W2b).

Each test below targets one flagged, previously-untested public symbol
directly; the `frob:tests` binding comment sits immediately above the
test function that covers it. Additive-only: this file does not modify
any existing test.
"""

from __future__ import annotations

import json

from regolith._schema.models import (
    Claim,
    ClaimForm1,
    DrawingModel,
    Form,
    Given,
    Obligation,
    RealizedAssembly,
    RealizedGeometry,
)
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.bom import BomModel, BomRow, MaterialRecord, MaterialRecordSet
from regolith.backends.calc import (
    build_calc_book,
    calc_package_files,
    calc_sheet_drawing,
    inputs_from_claim_kwargs,
    unit_from_claim,
)
from regolith.backends.debug_taps import (
    explicit_taps_from_debug_spec,
    hdl_debug_pins_from_debug_spec,
)
from regolith.backends.drawings.renderer import (
    TitleBlockField,
    fit_text,
    measure_text_width_mm,
    wrap_to_width,
)
from regolith.backends.drawings.style import NEUTRAL_STYLE
from regolith.backends.elec_fabset import _GerberWriter, kicad_layers_arg
from regolith.backends.framework import BackendInputs, OutputFile
from regolith.backends.package import acceptance_ledger_placeholder
from regolith.backends.parity import assumed_waived_rows, classify_lockfile
from regolith.backends.registry import (
    ProducerRegistration,
    ProducerRegistry,
    RendererRegistration,
    RendererRegistry,
)
from regolith.errors import BackendError
from regolith.orchestrator.lockfile import Lockfile, LockRow, LockSection
from typani.result import Result


# frob:tests python/regolith/backends/calc.py::inputs_from_claim_kwargs kind="unit"
def test_inputs_from_claim_kwargs_reads_numeric_kwargs_with_units() -> None:
    inputs = inputs_from_claim_kwargs("bolted_joint(under=9.4N*m, pair=dgb_6006)")
    assert len(inputs) == 1
    assert inputs[0].name == "under"
    assert inputs[0].value == "9.4"
    assert inputs[0].unit == "N*m"
    assert inputs[0].provenance == "declared_literal"


# frob:tests python/regolith/backends/calc.py::unit_from_claim kind="unit"
def test_unit_from_claim_reads_the_rhs_literal_suffix() -> None:
    claim = Claim(
        forall=[], form=ClaimForm1(form=Form.comparison, lhs="life", op=">=", rhs="20000hr"), hints=[], name="c"
    )
    assert unit_from_claim(claim) == "hr"

    unitless = Claim(
        forall=[],
        form=ClaimForm1(form=Form.comparison, lhs="life", op=">=", rhs="other_symbol"),
        hints=[],
        name="c",
    )
    assert unit_from_claim(unitless) == ""


def _calc_book():
    from regolith.harness.attest import Unsigned
    from regolith.harness.evidence import build_evidence
    from regolith.orchestrator.acceptance import AcceptanceOutcome
    from regolith.orchestrator.discharge import ObligationResult

    claim = Claim(
        forall=[],
        form=ClaimForm1(form=Form.comparison, lhs="stress", op="<", rhs="limit"),
        hints=[],
        name="stress_ok",
    )
    ob = Obligation(
        claim=claim,
        given=Given(materials=[], loads=[], backing=[], refs=[]),
        hints=[],
        subject_ref="s1",
    )
    evidence = build_evidence(
        model_id="mech.deflection@2",
        claim_kind="mech.deflection",
        sense_upper=True,
        value=1.0,
        eps=0.0,
        limit=3.0,
        coverage=1.0,
        cost=1,
        in_domain=True,
        deterministic=True,
        registry_version="v",
        inputs_digest="d",
    )
    res = ObligationResult(
        key="k1",
        subject_ref="s1",
        content_hash="c1",
        evidence=evidence,
        deferral=None,
        attestation=Unsigned(kind="unsigned"),
    )
    return build_calc_book(
        "p",
        (ob,),
        (res,),
        AcceptanceOutcome(),
        snapshots={"s1": "Beam.deflect"},
        citations={},
        tier="release",
    )


# frob:tests python/regolith/backends/calc.py::calc_sheet_drawing kind="unit"
def test_calc_sheet_drawing_projects_the_four_sections() -> None:
    book = _calc_book()
    model = calc_sheet_drawing(book.sheets[0])
    tables = {t.title for t in model.sheets[0].tables}
    assert tables == {"Claim / Model", "Inputs", "Result", "Evidence chain"}


# frob:tests python/regolith/backends/calc.py::calc_package_files kind="unit"
def test_calc_package_files_emits_book_index_and_one_pdf_per_sheet() -> None:
    book = _calc_book()
    files = calc_package_files(book)
    relpaths = {f.relpath for f in files}
    assert "calc/calc_book.json" in relpaths
    assert "calc/audit_index.json" in relpaths
    assert sum(1 for p in relpaths if p.endswith(".pdf")) == len(book.sheets)


# frob:tests python/regolith/backends/package.py::acceptance_ledger_placeholder kind="unit"
def test_acceptance_ledger_placeholder_is_a_schema_stable_empty_ledger() -> None:
    payload = json.loads(acceptance_ledger_placeholder())
    assert payload["entries"] == []
    assert "placeholder" in payload["note"]


# frob:tests python/regolith/backends/bom.py::MaterialRecordSet.density_of kind="unit"
def test_material_record_set_density_of_looks_up_by_key() -> None:
    record = MaterialRecord(key="al6061", digest="sha256:aaaa", density_kg_m3=2700.0)
    records = MaterialRecordSet(by_key={"al6061": record})
    assert records.density_of("al6061") is record
    assert records.density_of("no_such_key") is None


def _bom_model() -> BomModel:
    return BomModel(
        rows=(
            BomRow(subject="bracket", kind="part", quantity=2, part_number="P-1"),
        ),
        currency="USD",
    )


# frob:tests python/regolith/backends/bom.py::render_bom_md kind="unit"
def test_render_bom_md_includes_every_row_and_totals() -> None:
    from regolith.backends.bom import render_bom_md

    text = render_bom_md(_bom_model()).decode("ascii")
    assert "bracket" in text
    assert "P-1" in text
    assert "Total mass" in text


# frob:tests python/regolith/backends/bom.py::bom_drawing_model kind="unit"
def test_bom_drawing_model_projects_rows_into_a_table_sheet() -> None:
    from regolith.backends.bom import bom_drawing_model

    model = bom_drawing_model(_bom_model())
    assert model.sheets
    table = model.sheets[0].tables[0]
    assert any("bracket" in cell for row in table.rows for cell in row.cells)


# frob:tests python/regolith/backends/bom.py::render_bom_pdf kind="unit"
# frob:tests python/regolith/backends/drawings/renderer_pdf.py::_ContentBuilder.to_bytes kind="unit"
def test_render_bom_pdf_produces_pdf_bytes() -> None:
    from regolith.backends.bom import render_bom_pdf

    pdf_bytes = render_bom_pdf(_bom_model())
    assert pdf_bytes.startswith(b"%PDF")


# frob:tests python/regolith/backends/bom.py::register_bom_renderers kind="unit"
def test_register_bom_renderers_registers_all_four_formats() -> None:
    from regolith.backends.bom import register_bom_renderers

    registry = RendererRegistry()
    result = register_bom_renderers(registry)
    assert result.is_ok
    assert set(registry.formats("bom")) == {"csv", "json", "md", "pdf"}


# frob:tests python/regolith/backends/registry.py::ProducerRegistry.registrations kind="unit"
def test_producer_registry_registrations_lists_in_registration_order() -> None:
    def _unused_produce(
        subject: str, inputs: BackendInputs
    ) -> Result[DrawingModel, BackendError]:
        raise NotImplementedError("never invoked; registration order only")

    def _no_subjects(inputs: BackendInputs) -> tuple[str, ...]:
        return ()

    registry = ProducerRegistry()
    reg_a = ProducerRegistration(
        kind="mech", produce=_unused_produce, subjects=_no_subjects
    )
    reg_b = ProducerRegistration(
        kind="fluid", produce=_unused_produce, subjects=_no_subjects
    )
    assert registry.register(reg_a).is_ok
    assert registry.register(reg_b).is_ok
    assert registry.registrations() == (reg_a, reg_b)


# frob:tests python/regolith/backends/registry.py::RendererRegistry.for_family kind="unit"
def test_renderer_registry_for_family_lists_only_that_family() -> None:
    registry = RendererRegistry()
    reg = RendererRegistration("svg", "svg", "drawing", lambda m: b"")
    assert registry.register(reg).is_ok
    assert registry.for_family("drawing") == (reg,)
    assert registry.for_family("bom") == ()


# frob:tests python/regolith/backends/registry.py::RendererRegistry.register_realized kind="unit"
def test_renderer_registry_register_realized_is_keyed_by_family() -> None:
    from regolith.backends.registry import RealizedRendererRegistration

    def _unused_render(
        subject: str,
        geometry: RealizedGeometry | RealizedAssembly,
        store: NativeArtifactStore,
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        raise NotImplementedError("never invoked; registration keying only")

    registry = RendererRegistry()
    reg = RealizedRendererRegistration(
        format_id="glb", over="3d.part", render=_unused_render
    )
    assert registry.register_realized(reg).is_ok
    # A duplicate id in the same realized family is a loud Err, never a
    # silent shadow (the same discipline the drawing renderers hold).
    assert registry.register_realized(reg).is_err


# frob:tests python/regolith/backends/debug_taps.py::explicit_taps_from_debug_spec kind="unit"
def test_explicit_taps_from_debug_spec_parses_strings_and_objects() -> None:
    result = explicit_taps_from_debug_spec(
        {"taps": ["refclk", {"target_path": "ripple", "why": "power rail"}]}
    )
    assert result.is_ok
    taps = result.danger_ok
    assert taps[0].target_path == "refclk"
    assert taps[1].target_path == "ripple"
    assert taps[1].why == "power rail"


def test_explicit_taps_from_debug_spec_bad_entry_is_a_diagnostic() -> None:
    result = explicit_taps_from_debug_spec({"taps": [123]})
    assert result.is_err
    assert result.danger_err.kind == "debug_spec_malformed"


# frob:tests python/regolith/backends/debug_taps.py::hdl_debug_pins_from_debug_spec kind="unit"
def test_hdl_debug_pins_from_debug_spec_reads_the_declared_map() -> None:
    pins = hdl_debug_pins_from_debug_spec(
        {"hdl_debug_pins": {"mainboard_mx": ["dbg0", "dbg1"]}}
    )
    assert pins == {"mainboard_mx": ("dbg0", "dbg1")}
    assert hdl_debug_pins_from_debug_spec({}) == {}


# frob:tests python/regolith/backends/elec_fabset.py::kicad_layers_arg kind="unit"
def test_kicad_layers_arg_names_edge_cuts_and_copper_layers() -> None:
    layers = kicad_layers_arg()
    assert "F.Cu" in layers
    assert "Edge.Cuts" in layers


# frob:tests python/regolith/backends/elec_fabset.py::_GerberWriter.flash_pixel kind="unit"
# frob:tests python/regolith/backends/elec_fabset.py::_GerberWriter.rect_outline kind="unit"
def test_gerber_writer_flash_pixel_and_rect_outline_emit_valid_commands() -> None:
    writer = _GerberWriter("Legend,Top")
    writer.flash_pixel(1.0, 2.0)
    writer.rect_outline(10.0, 5.0)
    body = "\n".join(writer._body)
    assert body.count("D02*") == 5  # one pixel move + 4 rect-outline moves
    assert body.count("D01*") == 5


# frob:tests python/regolith/backends/parity.py::classify_lockfile kind="unit"
def test_classify_lockfile_sorts_by_subject_and_slot() -> None:
    lockfile = Lockfile(
        tool_version="0.1.0",
        sections=(
            LockSection(
                name="",
                rows=(
                    LockRow(slot="b.x", value="1mm", cause="dfm(rule)"),
                    LockRow(slot="a.y", value="2mm", cause="mystery(rule)"),
                ),
            ),
        ),
    )
    rows = classify_lockfile(lockfile)
    assert [r.subject for r in rows] == ["a", "b"]


# frob:tests python/regolith/backends/drawings/renderer.py::measure_text_width_mm kind="unit"
def test_measure_text_width_mm_scales_with_length_and_height() -> None:
    short = measure_text_width_mm("ab", 2.5, NEUTRAL_STYLE)
    long = measure_text_width_mm("abcd", 2.5, NEUTRAL_STYLE)
    assert long == 2 * short
    assert measure_text_width_mm("", 2.5, NEUTRAL_STYLE) == 0.0


# frob:tests python/regolith/backends/drawings/renderer.py::wrap_to_width kind="unit"
def test_wrap_to_width_greedily_wraps_and_hard_splits_long_words() -> None:
    lines = wrap_to_width("one two three", 2.5, 40.0, NEUTRAL_STYLE)
    assert len(lines) >= 1
    assert " ".join(lines).replace(" ", "") == "onetwothree"

    # A single token wider than the column hard-splits (no hyphen invented).
    long_token = "x" * 100
    split_lines = wrap_to_width(long_token, 2.5, 10.0, NEUTRAL_STYLE)
    assert len(split_lines) > 1
    assert "".join(split_lines) == long_token


# frob:tests python/regolith/backends/drawings/renderer.py::fit_text kind="unit"
def test_fit_text_shrinks_when_the_wrapped_block_overflows() -> None:
    height, lines = fit_text("a normal short caption", 100.0, 100.0, 2.5, NEUTRAL_STYLE)
    assert height == 2.5
    assert lines

    shrunk_height, shrunk_lines = fit_text(
        "a very long caption that will not fit in a tiny box at all",
        15.0,
        3.0,
        2.5,
        NEUTRAL_STYLE,
    )
    assert shrunk_height <= 2.5
    assert shrunk_lines


# frob:tests python/regolith/backends/drawings/renderer.py::TitleBlockField.row_height kind="unit"
def test_title_block_field_row_height_scales_with_wrapped_line_count() -> None:
    field = TitleBlockField("NAME", "a very long value that wraps", 0.0, 0.0, 30.0, NEUTRAL_STYLE)
    assert field.row_height == len(field.value_lines) * field.value_line_h


# frob:tests python/regolith/backends/parity.py::assumed_waived_rows kind="unit"
def test_assumed_waived_rows_covers_assume_and_waived_entries() -> None:
    from regolith._schema.models import WaiveLedger, Waiver, WaiverKind1, WaiverRecord

    ledger = WaiveLedger(
        entries=[
            {"assume": "vendor_confirmed"},
            {
                "waived": WaiverRecord(
                    kind=WaiverKind1.matched,
                    matched=["h.deviated"],
                    waiver=Waiver(
                        basis="vendor-confirmed, quote Q-1",
                        evidence="test(first_article)",
                        target="Manufacture.makeable",
                    ),
                ).model_dump(mode="json")
            },
        ]
    )
    rows = assumed_waived_rows(ledger)
    assert {r.kind for r in rows} == {"assume", "waived"}
    assert any(r.target == "vendor_confirmed" for r in rows)
    assert any(r.target == "Manufacture.makeable" for r in rows)
