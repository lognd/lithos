"""Tests for the derived BOM v2 + cost join (WO-101).

Covers: real record-pinned mass with provenance, the honest-empty mass
cell + reason, the `unsourced` marker, caller-line override/augment,
determinism, and the cost join onto rows.
"""

from __future__ import annotations

from regolith._schema.models import (
    EstimateLineItem,
    ItemizedEstimate,
    RecordRef,
    ScalarInterval,
)
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.bom import (
    BomBackend,
    MaterialRecord,
    MaterialRecordSet,
    derive_bom_rows,
    load_material_records,
    render_bom_csv,
    render_bom_json,
)
from regolith.backends.framework import BackendInputs
from regolith.backends.mech import AssemblyLine
from regolith.orchestrator.lockfile import Lockfile
from regolith.realizer.mech.interpreter import realize_feature_program

from tests.realizer.mech.fixtures import plate_program


def _inputs(tmp_path):
    realized = realize_feature_program(plate_program()).danger_ok
    native = NativeArtifactStore(str(tmp_path))
    native.put_at(realized.geometry.step_content_hash, realized.step_bytes)
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={"flat_plate": realized.geometry},
        layouts={},
        native=native,
    )
    return realized, inputs


def _al_materials() -> MaterialRecordSet:
    return MaterialRecordSet(
        by_key={
            "AL6061_T6": MaterialRecord(
                key="AL6061_T6", digest="sha256:deadbeef", density_kg_m3=2700.0
            ),
            "MYSTERY": MaterialRecord(
                key="MYSTERY", digest="sha256:cafe", density_kg_m3=None
            ),
        }
    )


# frob:tests python/regolith/backends/bom.py::derive_bom_rows kind="unit"
def test_real_mass_with_material_and_geometry_provenance(tmp_path):
    realized, inputs = _inputs(tmp_path)
    line = AssemblyLine(
        subject="flat_plate",
        part_number="PN-001",
        description="Plate",
        material="AL6061_T6",
        quantity=1,
    )
    model = derive_bom_rows(inputs, assembly_lines=(line,), materials=_al_materials())
    (row,) = model.rows
    # density 2700 kg/m^3 x volume_mm3 x 1e-6 == mass in grams.
    expected = 2700.0 * realized.geometry.topology.volume_mm3 * 1e-6
    assert float(row.mass_g) == round(expected, 3)
    assert row.material_pin == "AL6061_T6@1"
    assert row.geometry_pin == realized.geometry.step_content_hash
    assert row.mass_reason == ""
    assert not row.unsourced


def test_mass_empty_with_reason_when_density_missing(tmp_path):
    _realized, inputs = _inputs(tmp_path)
    line = AssemblyLine(
        subject="flat_plate",
        part_number="PN-002",
        description="Plate",
        material="MYSTERY",
        quantity=1,
    )
    model = derive_bom_rows(inputs, assembly_lines=(line,), materials=_al_materials())
    (row,) = model.rows
    assert row.mass_g == ""
    assert "no density" in row.mass_reason
    # geometry provenance is still carried even without a density.
    assert row.geometry_pin != ""


# frob:tests python/regolith/backends/bom.py::render_bom_csv kind="unit"
def test_unsourced_marker_when_no_line_and_no_record(tmp_path):
    _realized, inputs = _inputs(tmp_path)
    model = derive_bom_rows(inputs, materials=_al_materials())
    (row,) = model.rows
    assert row.unsourced
    assert row.part_number == ""
    csv = render_bom_csv(model).decode()
    assert "UNSOURCED" in csv


def test_caller_line_augments_with_extra_subject(tmp_path):
    _realized, inputs = _inputs(tmp_path)
    lines = (
        AssemblyLine(
            subject="flat_plate",
            part_number="PN-1",
            description="",
            material="AL6061_T6",
            quantity=1,
        ),
        AssemblyLine(
            subject="fastener_kit",
            part_number="PN-9",
            description="M6 kit",
            material="",
            quantity=4,
        ),
    )
    model = derive_bom_rows(inputs, assembly_lines=lines, materials=_al_materials())
    subjects = {r.subject for r in model.rows}
    assert subjects == {"flat_plate", "fastener_kit"}
    kit = next(r for r in model.rows if r.subject == "fastener_kit")
    assert kit.part_number == "PN-9"
    assert kit.quantity == 4


# frob:tests python/regolith/backends/bom.py::render_bom_json kind="unit"
def test_determinism_stable_bytes(tmp_path):
    _realized, inputs = _inputs(tmp_path)
    line = AssemblyLine(
        subject="flat_plate",
        part_number="PN-001",
        description="Plate",
        material="AL6061_T6",
        quantity=2,
    )
    a = derive_bom_rows(inputs, assembly_lines=(line,), materials=_al_materials())
    b = derive_bom_rows(inputs, assembly_lines=(line,), materials=_al_materials())
    assert render_bom_json(a) == render_bom_json(b)
    assert render_bom_csv(a) == render_bom_csv(b)


def test_cost_join_onto_row_and_empty_reason(tmp_path):
    _realized, inputs = _inputs(tmp_path)
    line = AssemblyLine(
        subject="flat_plate",
        part_number="PN-001",
        description="Plate",
        material="AL6061_T6",
        quantity=1,
    )
    estimate = ItemizedEstimate(
        profile="shop",
        exclusions=[],
        lines=[
            EstimateLineItem(
                item="AL6061_T6",
                qty=ScalarInterval(lo=1.0, hi=1.0, unit="each"),
                unit_cost=ScalarInterval(lo=42.0, hi=42.0, unit="USD"),
                record=RecordRef(digest="sha256:price", name="metal.al"),
                extended=ScalarInterval(lo=42.0, hi=42.0, unit="USD"),
            )
        ],
        total=ScalarInterval(lo=42.0, hi=42.0, unit="USD"),
    )
    joined = derive_bom_rows(
        inputs,
        assembly_lines=(line,),
        materials=_al_materials(),
        estimates={"flat_plate": estimate},
        cost_profile="shop",
    )
    (row,) = joined.rows
    assert row.total_cost == "42.00"
    assert row.currency == "USD"
    assert row.cost_ref == "profile:shop"
    assert joined.total_cost == "42.00"

    # No estimate -> empty cost with a reason.
    unjoined = derive_bom_rows(
        inputs, assembly_lines=(line,), materials=_al_materials()
    )
    assert unjoined.rows[0].total_cost == ""
    assert "no cost estimate" in unjoined.rows[0].cost_reason


def test_backend_emits_four_formats(tmp_path):
    _realized, inputs = _inputs(tmp_path)
    line = AssemblyLine(
        subject="flat_plate",
        part_number="PN-001",
        description="Plate",
        material="AL6061_T6",
        quantity=1,
    )
    backend = BomBackend(assembly_lines=(line,), materials=_al_materials())
    produced = backend.produce(inputs)
    assert produced.is_ok
    names = {f.relpath for f in produced.danger_ok}
    assert names == {"bom.csv", "bom.json", "bom.md", "bom.pdf"}


def test_no_artifact_emits_mass_hint(tmp_path):
    """Acceptance: no BOM artifact anywhere emits `mass_hint` (the area
    landmine is gone)."""
    _realized, inputs = _inputs(tmp_path)
    line = AssemblyLine(
        subject="flat_plate",
        part_number="PN-001",
        description="Plate",
        material="AL6061_T6",
        quantity=1,
    )
    backend = BomBackend(assembly_lines=(line,), materials=_al_materials())
    for f in backend.produce(inputs).danger_ok:
        assert b"mass_hint" not in f.content


def test_load_material_records_from_stdlib():
    mats = load_material_records(("stdlib/std.materials",))
    assert "AL5083_H111" in mats.by_key
    rec = mats.by_key["AL5083_H111"]
    assert rec.density_kg_m3 is not None
    assert rec.digest.startswith("sha256:")


# --- WO-101 residual (F124 bundle): ship-time cost-estimate threading ---


def test_resolve_cost_estimates_from_store(tmp_path):
    """`resolve_cost_estimates` resolves `report.cost_estimates` digests
    from the discharge-time PayloadStore into per-subject estimates,
    preferring the build's resolved profile."""

    from regolith.backends.ship import resolve_cost_estimates
    from regolith.orchestrator.orchestrate import (
        BuildReport,
        BuildTier,
        StagedBuildReport,
    )
    from regolith.orchestrator.payload_store import PayloadStore

    store = PayloadStore(str(tmp_path))
    estimate = ItemizedEstimate(
        profile="shop",
        exclusions=[],
        lines=[],
        total=ScalarInterval(lo=42.0, hi=42.0, unit="USD"),
    )
    other = estimate.model_copy(
        update={
            "profile": "rush",
            "total": ScalarInterval(lo=99.0, hi=99.0, unit="USD"),
        }
    )
    d_shop = store.put(estimate.model_dump_json().encode("utf-8"))
    d_rush = store.put(other.model_dump_json().encode("utf-8"))
    report = StagedBuildReport(
        final=BuildReport(
            tier=BuildTier.CHECK,
            ok=True,
            cost_estimates=(("flat_plate/shop", d_shop), ("flat_plate/rush", d_rush)),
            cost_profile="shop",
        ),
        iterations=1,
    )
    resolved = resolve_cost_estimates(report, str(tmp_path))
    assert set(resolved) == {"flat_plate"}
    # The build's resolved profile ("shop") wins the per-subject pick.
    assert resolved["flat_plate"].profile == "shop"


def test_resolve_cost_estimates_empty_when_no_pairs(tmp_path):
    from regolith.backends.ship import resolve_cost_estimates
    from regolith.orchestrator.orchestrate import (
        BuildReport,
        BuildTier,
        StagedBuildReport,
    )

    report = StagedBuildReport(
        final=BuildReport(tier=BuildTier.CHECK, ok=True),
        iterations=1,
    )
    assert resolve_cost_estimates(report, str(tmp_path)) == {}


def test_bom_backend_populates_cost_from_inputs(tmp_path):
    """The BOM backend reads build-derived cost estimates off `inputs`
    (not just its constructor), so cost columns populate on a real ship."""
    realized = realize_feature_program(plate_program()).danger_ok
    native = NativeArtifactStore(str(tmp_path))
    native.put_at(realized.geometry.step_content_hash, realized.step_bytes)
    estimate = ItemizedEstimate(
        profile="shop",
        exclusions=[],
        lines=[],
        total=ScalarInterval(lo=42.0, hi=42.0, unit="USD"),
    )
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={"flat_plate": realized.geometry},
        layouts={},
        native=native,
        cost_estimates={"flat_plate": estimate},
        cost_profile="shop",
    )
    line = AssemblyLine(
        subject="flat_plate",
        part_number="PN-001",
        description="Plate",
        material="AL6061_T6",
        quantity=1,
    )
    backend = BomBackend(assembly_lines=(line,), materials=_al_materials())
    files = backend.produce(inputs).danger_ok
    json_file = next(f for f in files if f.relpath.endswith(".json"))
    assert b"42.00" in json_file.content
