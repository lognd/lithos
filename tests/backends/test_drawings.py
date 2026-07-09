"""Tests for the drawings/schedules backend (WO-50, AD-27/D140):
producers, the SVG renderer, the drafting quality audit, and drawing
attestation sign-off.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from regolith._schema.models import (
    EdgeParams1,
    FlowEdge,
    FlownetPayload,
    MediumRef,
    RealizedGeometry,
    Reference,
    ScalarInterval,
    TopologySummary,
)
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.drawings.attest import (
    drawing_content_address,
    sign_drawing,
    verify_drawing,
)
from regolith.backends.drawings.audit import (
    contract_coverage_check,
    explain_report,
    run_drafting_rules,
)
from regolith.backends.drawings.backend import DrawingsBackend, DrawingSpec
from regolith.backends.drawings.producers import (
    elec_bom_table,
    fluid_pid,
    mech_part_drawing,
)
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.framework import BackendInputs
from regolith.magnetite import (
    KeyDesignation,
    TrustKeySet,
    TrustTier,
    generate_signing_key,
)
from regolith.orchestrator.lockfile import Lockfile


def _geometry() -> RealizedGeometry:
    return RealizedGeometry(
        feature_program_hash="blake3:aa",
        step_content_hash="sha256:bb",
        topology=TopologySummary(
            num_solids=1,
            num_faces=6,
            num_edges=12,
            num_vertices=8,
            volume_mm3=1000.0,
            area_mm2=600.0,
            bbox_min_mm=[0.0, 0.0, 0.0],
            bbox_max_mm=[10.0, 20.0, 30.0],
            center_of_mass_mm=[5.0, 10.0, 15.0],
        ),
        paths={},
    )


def _flownet() -> FlownetPayload:
    return FlownetPayload(
        edges=[
            FlowEdge(
                a="n1",
                b="n2",
                compliance=None,
                curves=[],
                id="e1",
                kind="pipe",
                params=EdgeParams1(source="scalars", values={}),
            )
        ],
        medium=MediumRef(records=[]),
        nodes=["n1", "n2"],
        reference=Reference(
            node="n1",
            p=ScalarInterval(lo=0.0, hi=0.0, unit="Pa"),
            t=ScalarInterval(lo=293.0, hi=293.0, unit="K"),
        ),
        states=[],
    )


class TestMechProducer:
    def test_deterministic_across_two_runs(self):
        geometry = _geometry()
        m1 = mech_part_drawing("pillow_block", geometry)
        m2 = mech_part_drawing("pillow_block", geometry)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_every_dimension_carries_provenance(self):
        model = mech_part_drawing("pillow_block", _geometry())
        for sheet in model.sheets:
            for dim in sheet.dimensions:
                assert dim.provenance is not None


class TestFluidProducer:
    def test_pid_svg_is_valid_xml(self):
        model = fluid_pid("feed_system", _flownet())
        ET.fromstring(render_svg(model))

    def test_pid_has_no_toleranced_dimensions(self):
        model = fluid_pid("feed_system", _flownet())
        for sheet in model.sheets:
            assert sheet.dimensions == []


class TestElecBomProducer:
    def test_bom_table_renders(self):
        model = elec_bom_table("power_board", (("R1", "PN-100", "10k resistor", 4),))
        svg = render_svg(model)
        ET.fromstring(svg)
        assert b"R1" in svg


class TestDrawingsBackend:
    def test_produces_mech_and_fluid_files(self, tmp_path):
        backend = DrawingsBackend(
            (
                DrawingSpec(subject="pillow_block", track="mech"),
                DrawingSpec(subject="feed_system", track="fluid"),
            )
        )
        inputs = BackendInputs(
            lockfile=Lockfile(tool_version="0.1.0"),
            evidence={},
            geometry={"pillow_block": _geometry()},
            layouts={},
            flownets={"feed_system": _flownet()},
            native=NativeArtifactStore(str(tmp_path)),
        )
        produced = backend.produce(inputs)
        assert produced.is_ok
        relpaths = {f.relpath for f in produced.danger_ok}
        assert "drawings/pillow_block.drawing.json" in relpaths
        assert "drawings/pillow_block.svg" in relpaths
        assert "drawings/pillow_block.explain.txt" in relpaths
        assert "drawings/feed_system.drawing.json" in relpaths
        assert "drawings/feed_system.svg" in relpaths

    def test_missing_geometry_is_a_named_error(self, tmp_path):
        backend = DrawingsBackend((DrawingSpec(subject="unknown_part", track="mech"),))
        inputs = BackendInputs(
            lockfile=Lockfile(tool_version="0.1.0"),
            evidence={},
            geometry={},
            layouts={},
            native=NativeArtifactStore(str(tmp_path)),
        )
        produced = backend.produce(inputs)
        assert produced.is_err
        assert produced.danger_err.kind == "geometry_ir_unavailable"


class TestDraftingRules:
    """The seed pack (>= 5 rules, per: citations) catches deliberate
    over-/under-dimensioning fixtures 60/61 (negative-corpus reservation,
    docs/workflow/README.md's fixture ledger).
    """

    def test_seed_pack_has_at_least_five_rules_with_citations(self):
        model = mech_part_drawing("pillow_block", _geometry())
        results = run_drafting_rules(model)
        rule_names = {r.rule for r in results}
        assert len(rule_names) >= 5
        assert all(r.per for r in results)

    def test_fixture_60_over_dimensioned_fails_dimension_completeness(self):
        # Fixture 60: the SAME role dimensioned twice on the SAME view --
        # a deliberately over-dimensioned sheet.
        model = mech_part_drawing("pillow_block", _geometry())
        sheet = model.sheets[0]
        duplicate = sheet.dimensions[0]
        bad_sheet = sheet.model_copy(
            update={"dimensions": [*sheet.dimensions, duplicate]}
        )
        bad_model = model.model_copy(update={"sheets": [bad_sheet]})
        results = run_drafting_rules(bad_model)
        completeness = [r for r in results if r.rule == "dimension-completeness"][0]
        assert not completeness.passed

    def test_fixture_61_under_dimensioned_fails_coverage_check(self):
        # Fixture 61: a toleranced contract role never appears on any
        # sheet -- the contract-coverage check's named diagnostic.
        model = mech_part_drawing("pillow_block", _geometry())
        coverage = contract_coverage_check(
            model, frozenset({"bbox.width", "bore.diameter"})
        )
        assert not coverage.ok
        assert "bore.diameter" in coverage.missing
        assert "bbox.width" in coverage.covered

    def test_title_block_completeness_catches_blank_field(self):
        model = mech_part_drawing("pillow_block", _geometry())
        sheet = model.sheets[0]
        blank_tb = sheet.title_block.model_copy(update={"revision": ""})
        bad_sheet = sheet.model_copy(update={"title_block": blank_tb})
        bad_model = model.model_copy(update={"sheets": [bad_sheet]})
        results = run_drafting_rules(bad_model)
        tb_rule = [r for r in results if r.rule == "title-block-completeness"][0]
        assert not tb_rule.passed


class TestExplainReport:
    def test_renders_dimension_cause_table_and_coverage_ledger(self):
        model = mech_part_drawing("pillow_block", _geometry())
        report = explain_report(model, frozenset({"bbox.width", "bore.diameter"}))
        assert "bbox.width" in report
        assert "PASS" in report or "FAIL" in report
        assert "missing: bore.diameter" in report
        assert report.isascii()


class TestDrawingAttestation:
    def test_signature_verifies_over_unchanged_drawing(self, tmp_path):
        model = mech_part_drawing("pillow_block", _geometry())
        key = generate_signing_key(str(tmp_path), "project-1").danger_ok
        keys = TrustKeySet(
            designations=(
                KeyDesignation(
                    key_id=key.key_id,
                    public_key_base64=key.public_key_base64(),
                    confers=TrustTier.TESTED,
                ),
            )
        )
        att = sign_drawing(model, key, pack_name="reviewer", pack_version="1.0.0")
        assert verify_drawing(model, att, keys)

    def test_signature_dies_on_regeneration(self, tmp_path):
        model = mech_part_drawing("pillow_block", _geometry())
        key = generate_signing_key(str(tmp_path), "project-1").danger_ok
        keys = TrustKeySet(
            designations=(
                KeyDesignation(
                    key_id=key.key_id,
                    public_key_base64=key.public_key_base64(),
                    confers=TrustTier.TESTED,
                ),
            )
        )
        att = sign_drawing(model, key, pack_name="reviewer", pack_version="1.0.0")

        regenerated_geometry = _geometry().model_copy(
            update={
                "topology": _geometry().topology.model_copy(
                    update={"bbox_max_mm": [11.0, 20.0, 30.0]}
                )
            }
        )
        regenerated_model = mech_part_drawing("pillow_block", regenerated_geometry)
        assert drawing_content_address(regenerated_model) != drawing_content_address(
            model
        )
        assert not verify_drawing(regenerated_model, att, keys)
