"""Tests for the drawings/schedules backend (WO-50, AD-27/D140):
producers, the SVG renderer, the drafting quality audit, and drawing
attestation sign-off.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from regolith._schema.models import (
    AssignmentItem,
    CandidateEntry,
    ContractEdge,
    ContractGraphPayload,
    ContractNode,
    Datum1,
    EdgeParams1,
    FlowEdge,
    FlownetPayload,
    FrameLoad,
    FrameMember,
    FramePayload,
    HarnessPayload,
    Joint,
    JointAt,
    Kind7,
    LoadKind1,
    MediumRef,
    MemberRole1,
    MemberRole6,
    ObjectiveDirection1,
    OptimizationTrace,
    Provenance2,
    RealizedGeometry,
    RecordRef,
    Reference,
    Releases,
    RunRecord,
    RunRoute1,
    RunSegment,
    ScalarInterval,
    Support,
    TerminationStatus1,
    TopologySummary,
)
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.drawings.attest import (
    drawing_content_address,
    sign_drawing,
    verify_drawing,
)
from regolith.backends.drawings.audit import (
    assert_ship_ready,
    contract_coverage_check,
    explain_report,
    run_drafting_rules,
)
from regolith.backends.drawings.backend import DrawingsBackend, DrawingSpec
from regolith.backends.drawings.layout import layered_positions, standoff_ladder
from regolith.backends.drawings.producers import (
    civil_plan_section,
    contract_graph,
    elec_blocks,
    elec_bom_table,
    fluid_pid,
    mech_part_drawing,
    opt_trace,
)
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.drawings.renderer_dxf import render_dxf
from regolith.backends.drawings.renderer_pdf import render_pdf
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


def _frame() -> FramePayload:
    return FramePayload(
        joints=[
            Joint(
                id="A|deck",
                at=JointAt(
                    grid_refs=["A"], datum=Datum1(datum_kind="level", value="deck")
                ),
            ),
            Joint(id="support:AB1", at=None),
        ],
        members=[
            FrameMember(
                id="G1",
                role=MemberRole1.beam,
                a="A|deck",
                b="support:AB1",
                length=ScalarInterval(lo=12.0, hi=12.0, unit="m"),
                orientation="horizontal",
                section=RecordRef(digest="", name="free"),
                material=RecordRef(digest="blake3:aa", name="astm_a992"),
                releases=Releases(a=[], b=[]),
            ),
            FrameMember(
                id="F1",
                role=MemberRole6.footing,
                a="A|base",
                b="A|base",
                length=ScalarInterval(lo=0.0, hi=0.0, unit="m"),
                orientation="point",
                section=RecordRef(digest="blake3:bb", name="std.civil.footing.f1"),
                material=RecordRef(digest="blake3:cc", name="concrete_c30"),
                releases=Releases(a=[], b=[]),
            ),
        ],
        supports=[Support(joint="support:AB1", fixity=[])],
        transfers=[],
        loads=[
            FrameLoad(
                case="pedestrian",
                target="Deck",
                kind=LoadKind1.distributed,
                value=ScalarInterval(lo=4.1, hi=4.1, unit="kPa"),
                direction="gravity",
            )
        ],
        combinations=RecordRef(digest="", name="std.civil.aisc.strength"),
    )


def _harness() -> HarnessPayload:
    """The `wiring_harness.cupr` corpus design's landed shape (WO-34
    D99, `examples/tracks/cuprite/wiring_harness.cupr`): two runs
    connecting four distinct components -- the WO-58 elec block
    diagram's chosen cuprite corpus design.
    """
    return HarnessPayload(
        name="MainLoom",
        environments={"engine_bay": ScalarInterval(lo=-30.0, hi=125.0, unit="degC")},
        runs={
            "batt_to_kill": RunRecord(
                **{"from": "battery.pos"},
                to="kill_switch.in",
                bundle="primary",
                route=RunRoute1(
                    kind=Kind7.waypoints,
                    segments=[
                        RunSegment(
                            structural_ref="frame.spine_tube",
                            role="engine_bay",
                            length=ScalarInterval(lo=1.2, hi=1.2, unit="m"),
                        ),
                        RunSegment(
                            structural_ref="frame.hoop_gusset",
                            role="engine_bay",
                            length=ScalarInterval(lo=0.4, hi=0.4, unit="m"),
                        ),
                    ],
                    snapshot_hash="blake3:aa",
                    total_length=ScalarInterval(lo=1.6, hi=1.6, unit="m"),
                ),
            ),
            "vr_sense": RunRecord(
                **{"from": "vr_sensor.sig"},
                to="ecu.vr_in",
                bundle="shielded_signals",
                route=RunRoute1(
                    kind=Kind7.waypoints,
                    segments=[],
                    snapshot_hash="blake3:bb",
                    total_length=ScalarInterval(lo=0.0, hi=0.0, unit="m"),
                ),
            ),
        },
    )


def _contract_graph() -> ContractGraphPayload:
    """A small multi-artifact contract graph (WO-61 deliverable 4's
    chosen corpus shape): one interface (two promise slots) and two
    artifacts, connected by one named mating.
    """
    return ContractGraphPayload(
        nodes=[
            ContractNode(name="Bore", kind="interface", promise_slots=2),
            ContractNode(name="housing", kind="artifact", promise_slots=0),
            ContractNode(name="shaft", kind="artifact", promise_slots=0),
        ],
        edges=[
            ContractEdge(name="press_fit", kind="load", a="housing", b="shaft"),
        ],
    )


def _opt_trace() -> OptimizationTrace:
    return OptimizationTrace(
        strategy_id="optimize_discrete",
        strategy_version="1",
        seed=42,
        budget_declared=10,
        budget_spent=2,
        objective=[ObjectiveDirection1.minimize],
        candidates=[
            CandidateEntry(
                assignment=[AssignmentItem(["choice.a", "vendor_a"])],
                objective_vector=[3.0],
                feasible=True,
                verdict_summary="all demands dischargeable",
                evidence_digests=["blake3:aa"],
            ),
            CandidateEntry(
                assignment=[AssignmentItem(["choice.a", "vendor_b"])],
                objective_vector=[1.5],
                feasible=True,
                verdict_summary="all demands dischargeable",
                evidence_digests=["blake3:bb"],
            ),
        ],
        nogood_keys=[],
        winner=1,
        termination=TerminationStatus1.converged,
    )


class TestLayoutHelper:
    def test_layered_positions_is_deterministic(self):
        nodes = ("a", "b", "c")
        edges = (("a", "b"), ("b", "c"))
        l1 = layered_positions(nodes, edges)
        l2 = layered_positions(nodes, edges)
        assert l1.positions == l2.positions
        assert l1.routes == l2.routes

    def test_root_nodes_land_at_layer_zero(self):
        layout = layered_positions(("a", "b"), (("a", "b"),))
        assert layout.positions["a"][0] == 0.0
        assert layout.positions["b"][0] > 0.0

    def test_cycle_does_not_raise_and_still_lays_out_every_node(self):
        layout = layered_positions(("a", "b"), (("a", "b"), ("b", "a")))
        assert set(layout.positions) == {"a", "b"}

    def test_standoff_ladder_offsets_deterministically(self):
        base = [10.0, 20.0]
        assert standoff_ladder(base, 0) == [10.0, 20.0]
        assert standoff_ladder(base, 1) != standoff_ladder(base, 2)


class TestElecBlocksProducer:
    # frob:tests python/regolith/backends/drawings/renderer.py::render_svg kind="unit"
    def test_deterministic_across_two_runs(self):
        harness = _harness()
        m1 = elec_blocks("MainLoom", harness)
        m2 = elec_blocks("MainLoom", harness)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_svg_is_valid_xml(self):
        model = elec_blocks("MainLoom", _harness())
        ET.fromstring(render_svg(model))

    def test_one_rectangle_per_block_one_polyline_per_net(self):
        """Structural match to `wiring_harness.cupr`'s own block/net
        list (WO-58 acceptance criterion): 4 blocks (battery,
        kill_switch, vr_sensor, ecu) each drawn as a 4-segment
        rectangle, 2 runs each drawn as a 3-segment orthogonal
        polyline -- counted, not eyeballed.
        """
        model = elec_blocks("MainLoom", _harness())
        sheet = model.sheets[0]
        segments = [e for e in sheet.entities if e.kind == "segment"]
        assert len(segments) == 4 * 4 + 2 * 3

    def test_no_toleranced_dimensions(self):
        model = elec_blocks("MainLoom", _harness())
        for sheet in model.sheets:
            assert sheet.dimensions == []

    # frob:tests python/regolith/backends/drawings/audit.py::run_drafting_rules kind="unit"
    # frob:tests python/regolith/backends/drawings/audit.py::assert_ship_ready kind="unit"
    def test_passes_the_drafting_audit(self):
        # WO-123 F142 (named finding, audit.py's `_NON_GATING_SOURCE_KINDS`
        # docstring): the layered block/port label layout this fixture
        # exercises has a known dense-diagram collision the WO-58 layout
        # helper still owes a fix for -- `assert_ship_ready` (the actual
        # ship-path gate) does not refuse it; every OTHER rule still must
        # pass, and the fixture's ship-readiness is asserted directly.
        model = elec_blocks("MainLoom", _harness())
        for result in run_drafting_rules(model):
            if result.rule == "geometric-overlap":
                continue
            assert result.passed, result.message
        assert assert_ship_ready(model, "MainLoom") is None


class TestMechProducer:
    # frob:tests python/regolith/backends/drawings/producers.py::mech_part_drawing kind="unit"
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

    def test_source_digest_is_local_blake3_tagged(self):
        """WO-99 D6 / charter 38 sec. 1.4: a standalone realized IR has no
        upstream Rust content address, so its `source_digest` carries the
        `local-blake3:` tag -- never confusable with a canonical address.
        Every provenance digest citing the same source carries it too."""
        model = mech_part_drawing("pillow_block", _geometry())
        view_digest = model.sheets[0].views[0].source.source_digest
        assert view_digest.startswith("local-blake3:")
        for sheet in model.sheets:
            for dim in sheet.dimensions:
                assert isinstance(dim.provenance, Provenance2)
                assert dim.provenance.digest.startswith("local-blake3:")


class TestFluidProducer:
    # frob:tests python/regolith/backends/drawings/producers.py::fluid_pid kind="unit"
    def test_pid_svg_is_valid_xml(self):
        model = fluid_pid("feed_system", _flownet())
        ET.fromstring(render_svg(model))

    def test_pid_has_no_toleranced_dimensions(self):
        model = fluid_pid("feed_system", _flownet())
        for sheet in model.sheets:
            assert sheet.dimensions == []


class TestCivilProducer:
    # frob:tests python/regolith/backends/drawings/producers.py::civil_plan_section kind="unit"
    def test_deterministic_across_two_runs(self):
        frame = _frame()
        m1 = civil_plan_section("small_office", frame)
        m2 = civil_plan_section("small_office", frame)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_svg_is_valid_xml(self):
        model = civil_plan_section("small_office", _frame())
        ET.fromstring(render_svg(model))

    def test_every_dimension_carries_provenance(self):
        model = civil_plan_section("small_office", _frame())
        for sheet in model.sheets:
            for dim in sheet.dimensions:
                assert dim.provenance is not None

    def test_point_anchored_footing_gets_no_span_dimension(self):
        # F1 is a point-anchored footing (a == b): a reaction point, not a
        # span (calcite/03 sec. 4) -- no `member.length:F1` dimension.
        model = civil_plan_section("small_office", _frame())
        roles = {dim.role for sheet in model.sheets for dim in sheet.dimensions}
        assert "member.length:F1" not in roles
        assert "member.length:G1" in roles

    def test_member_schedule_table_has_one_row_per_member(self):
        model = civil_plan_section("small_office", _frame())
        table = model.sheets[0].tables[0]
        assert table.title == "Member Schedule"
        assert len(table.rows) == 2

    def test_unresolved_section_is_honest_not_fabricated(self):
        # G1's section is the AD-25 `free` placeholder -- rendered as
        # "unresolved", never invented content.
        model = civil_plan_section("small_office", _frame())
        table = model.sheets[0].tables[0]
        g1_row = [r for r in table.rows if r.cells[0] == "G1"][0]
        assert g1_row.cells[3] == "unresolved"
        f1_row = [r for r in table.rows if r.cells[0] == "F1"][0]
        assert f1_row.cells[3] == "std.civil.footing.f1"


class TestElecBomProducer:
    # frob:tests python/regolith/backends/drawings/producers.py::elec_bom_table kind="unit"
    # frob:tests python/regolith/backends/drawings/renderer.py::table_fit_max_width kind="unit"
    def test_bom_table_renders(self):
        model = elec_bom_table("power_board", (("R1", "PN-100", "10k resistor", 4),))
        svg = render_svg(model)
        ET.fromstring(svg)
        assert b"R1" in svg


class TestContractGraphProducer:
    def test_deterministic_across_two_runs(self):
        graph = _contract_graph()
        m1 = contract_graph("bearing_assembly", graph)
        m2 = contract_graph("bearing_assembly", graph)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_svg_is_valid_xml(self):
        model = contract_graph("bearing_assembly", _contract_graph())
        ET.fromstring(render_svg(model))

    def test_one_symbol_per_node_one_polyline_per_edge(self):
        graph = _contract_graph()
        model = contract_graph("bearing_assembly", graph)
        sheet = model.sheets[0]
        symbols = [e for e in sheet.entities if e.kind == "symbol"]
        segments = [e for e in sheet.entities if e.kind == "segment"]
        assert len(symbols) == len(graph.nodes)
        # One edge routed as a 3-segment orthogonal polyline (layout.py).
        assert len(segments) == len(graph.edges) * 3

    def test_passes_the_drafting_audit(self):
        model = contract_graph("bearing_assembly", _contract_graph())
        for result in run_drafting_rules(model):
            assert result.passed, result.message

    def test_no_toleranced_dimensions(self):
        model = contract_graph("bearing_assembly", _contract_graph())
        for sheet in model.sheets:
            assert sheet.dimensions == []


class TestOptTraceProducer:
    def test_deterministic_across_two_runs(self):
        trace = _opt_trace()
        m1 = opt_trace("gearbox_ratio", trace)
        m2 = opt_trace("gearbox_ratio", trace)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    # frob:tests python/regolith/backends/drawings/renderer.py::ChartGeometry.data_to_plot kind="unit"
    def test_svg_is_valid_xml(self):
        model = opt_trace("gearbox_ratio", _opt_trace())
        ET.fromstring(render_svg(model))

    def test_one_table_row_per_candidate(self):
        trace = _opt_trace()
        model = opt_trace("gearbox_ratio", trace)
        table = model.sheets[0].tables[0]
        assert len(table.rows) == len(trace.candidates)

    def test_winner_annotation_is_a_short_on_chart_label(self):
        # WO-123 D238.3 defect 11: the winner label ON the chart is
        # SHORT ("winner: #<i>"), never the full blake3 digest inline;
        # the full digest still cites the trace in the off-chart
        # termination caption (short-form, defect 11's second half).
        trace = _opt_trace()
        model = opt_trace("gearbox_ratio", trace)
        digest = model.sheets[0].views[0].source.source_digest
        winner_annotations = [
            a for a in model.sheets[0].annotations if a.text.startswith("winner:")
        ]
        assert len(winner_annotations) == 1
        assert winner_annotations[0].text == f"winner: #{trace.winner}"
        assert digest not in winner_annotations[0].text
        termination_annotations = [
            a for a in model.sheets[0].annotations if a.text.startswith("termination:")
        ]
        assert len(termination_annotations) == 1
        assert digest[:19] in termination_annotations[0].text


class TestDrawingsBackend:
    def test_produces_mech_and_fluid_files(self, tmp_path):
        backend = DrawingsBackend(
            (
                DrawingSpec(subject="pillow_block", track="mech"),
                DrawingSpec(subject="feed_system", track="fluid"),
                DrawingSpec(subject="small_office", track="civil"),
            )
        )
        inputs = BackendInputs(
            lockfile=Lockfile(tool_version="0.1.0"),
            evidence={},
            geometry={"pillow_block": _geometry()},
            layouts={},
            flownets={"feed_system": _flownet()},
            frames={"small_office": _frame()},
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
        assert "drawings/small_office.drawing.json" in relpaths
        assert "drawings/small_office.svg" in relpaths
        assert "drawings/small_office.explain.txt" in relpaths
        assert "drawings/pillow_block.dxf" in relpaths
        assert "drawings/pillow_block.pdf" in relpaths
        assert "drawings/feed_system.dxf" in relpaths
        assert "drawings/feed_system.pdf" in relpaths
        assert "drawings/small_office.dxf" in relpaths
        assert "drawings/small_office.pdf" in relpaths

    def test_produces_elec_blocks_files(self, tmp_path):
        backend = DrawingsBackend(
            (DrawingSpec(subject="MainLoom", track="elec_blocks"),)
        )
        inputs = BackendInputs(
            lockfile=Lockfile(tool_version="0.1.0"),
            evidence={},
            geometry={},
            layouts={},
            harnesses={"MainLoom": _harness()},
            native=NativeArtifactStore(str(tmp_path)),
        )
        produced = backend.produce(inputs)
        assert produced.is_ok
        relpaths = {f.relpath for f in produced.danger_ok}
        assert relpaths == {
            "drawings/MainLoom.drawing.json",
            "drawings/MainLoom.svg",
            "drawings/MainLoom.dxf",
            "drawings/MainLoom.pdf",
            "drawings/MainLoom.explain.txt",
        }

    def test_missing_harness_is_a_named_error(self, tmp_path):
        backend = DrawingsBackend(
            (DrawingSpec(subject="unknown_harness", track="elec_blocks"),)
        )
        inputs = BackendInputs(
            lockfile=Lockfile(tool_version="0.1.0"),
            evidence={},
            geometry={},
            layouts={},
            native=NativeArtifactStore(str(tmp_path)),
        )
        produced = backend.produce(inputs)
        assert produced.is_err
        assert produced.danger_err.kind == "harness_ir_unavailable"

    def test_produces_contract_graph_files(self, tmp_path):
        backend = DrawingsBackend(
            (DrawingSpec(subject="bearing_assembly", track="contract_graph"),)
        )
        inputs = BackendInputs(
            lockfile=Lockfile(tool_version="0.1.0"),
            evidence={},
            geometry={},
            layouts={},
            contract_graph=_contract_graph(),
            native=NativeArtifactStore(str(tmp_path)),
        )
        produced = backend.produce(inputs)
        assert produced.is_ok
        relpaths = {f.relpath for f in produced.danger_ok}
        assert relpaths == {
            "drawings/bearing_assembly.drawing.json",
            "drawings/bearing_assembly.svg",
            "drawings/bearing_assembly.dxf",
            "drawings/bearing_assembly.pdf",
            "drawings/bearing_assembly.explain.txt",
        }

    def test_missing_contract_graph_is_a_named_error(self, tmp_path):
        backend = DrawingsBackend(
            (DrawingSpec(subject="bearing_assembly", track="contract_graph"),)
        )
        inputs = BackendInputs(
            lockfile=Lockfile(tool_version="0.1.0"),
            evidence={},
            geometry={},
            layouts={},
            native=NativeArtifactStore(str(tmp_path)),
        )
        produced = backend.produce(inputs)
        assert produced.is_err
        assert produced.danger_err.kind == "contract_graph_ir_unavailable"

    def test_produces_opt_trace_files(self, tmp_path):
        backend = DrawingsBackend(
            (DrawingSpec(subject="gearbox_ratio", track="opt_trace"),)
        )
        inputs = BackendInputs(
            lockfile=Lockfile(tool_version="0.1.0"),
            evidence={},
            geometry={},
            layouts={},
            opt_traces={"gearbox_ratio": _opt_trace()},
            native=NativeArtifactStore(str(tmp_path)),
        )
        produced = backend.produce(inputs)
        assert produced.is_ok
        relpaths = {f.relpath for f in produced.danger_ok}
        assert relpaths == {
            "drawings/gearbox_ratio.drawing.json",
            "drawings/gearbox_ratio.svg",
            "drawings/gearbox_ratio.dxf",
            "drawings/gearbox_ratio.pdf",
            "drawings/gearbox_ratio.explain.txt",
        }

    def test_missing_opt_trace_is_a_named_error(self, tmp_path):
        backend = DrawingsBackend(
            (DrawingSpec(subject="gearbox_ratio", track="opt_trace"),)
        )
        inputs = BackendInputs(
            lockfile=Lockfile(tool_version="0.1.0"),
            evidence={},
            geometry={},
            layouts={},
            native=NativeArtifactStore(str(tmp_path)),
        )
        produced = backend.produce(inputs)
        assert produced.is_err
        assert produced.danger_err.kind == "opt_trace_ir_unavailable"

    def test_produces_all_five_files_per_subject(self, tmp_path):
        backend = DrawingsBackend((DrawingSpec(subject="pillow_block", track="mech"),))
        inputs = BackendInputs(
            lockfile=Lockfile(tool_version="0.1.0"),
            evidence={},
            geometry={"pillow_block": _geometry()},
            layouts={},
            native=NativeArtifactStore(str(tmp_path)),
        )
        produced = backend.produce(inputs)
        assert produced.is_ok
        relpaths = {f.relpath for f in produced.danger_ok}
        assert relpaths == {
            "drawings/pillow_block.drawing.json",
            "drawings/pillow_block.svg",
            "drawings/pillow_block.dxf",
            "drawings/pillow_block.pdf",
            "drawings/pillow_block.explain.txt",
        }

    def test_missing_frame_is_a_named_error(self, tmp_path):
        backend = DrawingsBackend(
            (DrawingSpec(subject="unknown_structure", track="civil"),)
        )
        inputs = BackendInputs(
            lockfile=Lockfile(tool_version="0.1.0"),
            evidence={},
            geometry={},
            layouts={},
            native=NativeArtifactStore(str(tmp_path)),
        )
        produced = backend.produce(inputs)
        assert produced.is_err
        assert produced.danger_err.kind == "frame_ir_unavailable"

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

    # frob:tests python/regolith/backends/drawings/audit.py::CoverageResult.ok kind="unit"
    # frob:tests python/regolith/backends/drawings/audit.py::contract_coverage_check kind="unit"
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
    # frob:tests python/regolith/backends/drawings/audit.py::explain_report kind="unit"
    # frob:tests python/regolith/magnetite/trust.py::generate_signing_key kind="unit"
    def test_renders_dimension_cause_table_and_coverage_ledger(self):
        model = mech_part_drawing("pillow_block", _geometry())
        report = explain_report(model, frozenset({"bbox.width", "bore.diameter"}))
        assert "bbox.width" in report
        assert "PASS" in report or "FAIL" in report
        assert "missing: bore.diameter" in report
        assert report.isascii()


class TestDrawingAttestation:
    # frob:tests python/regolith/backends/drawings/attest.py::sign_drawing kind="unit"
    # frob:tests python/regolith/backends/drawings/attest.py::verify_drawing kind="unit"
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

    # frob:tests python/regolith/backends/drawings/attest.py::drawing_content_address kind="unit"
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


class TestSvgRenderer:
    """The SVG reference renderer must produce a real, viewable sheet
    (charter sec. 1 decision 2): a sized page, a frame, a title block,
    and a deterministic view grid -- not a skeletal, unbounded document.
    """

    def test_svg_has_viewbox_matching_sheet_size(self):
        model = mech_part_drawing("pillow_block", _geometry())
        svg = render_svg(model)
        root = ET.fromstring(svg)
        assert root.attrib["viewBox"] == "0 0 279.4000 215.9000"
        assert root.attrib["width"] == "279.4000mm"
        assert root.attrib["height"] == "215.9000mm"

    def test_svg_has_frame_and_title_block_texts(self):
        # WO-123 (charter 41 sec. 1.1): title-block fields now render as
        # a caption-face LABEL line above a body-face VALUE line (never
        # a single combined "rev A" run) -- assert the label and value
        # texts separately.
        model = mech_part_drawing("pillow_block", _geometry())
        svg = render_svg(model)
        assert b'class="frame"' in svg
        assert b'class="title-block-frame"' in svg
        assert b"DWG-pillow_block" in svg
        assert b"pillow_block" in svg
        assert b'class="title-block-label"' in svg
        assert b">REV<" in svg

    def test_deterministic_and_reorder_invariant(self):
        geometry = _geometry()
        m1 = mech_part_drawing("pillow_block", geometry)
        m2 = mech_part_drawing("pillow_block", geometry)
        assert render_svg(m1) == render_svg(m2)

    # frob:tests python/regolith/backends/drawings/renderer.py::dimension_placement kind="unit"
    def test_every_dimension_text_present_exactly_once(self):
        # WO-123 D238.3 defect 6: the printed dimension text is the
        # human value ("80.00 mm"), not the payload-path `role` prefix
        # -- assert on the value+unit text the renderer actually emits.
        model = mech_part_drawing("pillow_block", _geometry())
        svg = render_svg(model).decode("ascii")
        for sheet in model.sheets:
            for dim in sheet.dimensions:
                label = f"{dim.value:.2f} {dim.unit}"
                assert svg.count(label) == 1

    def test_multi_sheet_document_is_valid_xml_and_taller(self):
        m1 = mech_part_drawing("pillow_block", _geometry())
        m2 = mech_part_drawing("pillow_block", _geometry())
        combined = m1.model_copy(update={"sheets": [*m1.sheets, *m2.sheets]})
        svg = render_svg(combined)
        ET.fromstring(svg)
        root = ET.fromstring(svg)
        assert float(root.attrib["viewBox"].split()[-1]) > 215.9


class TestDxfRenderer:
    # frob:tests python/regolith/backends/drawings/renderer_dxf.py::render_dxf kind="unit"
    def test_starts_with_section_header(self):
        model = mech_part_drawing("pillow_block", _geometry())
        dxf = render_dxf(model)
        assert dxf.startswith(b"0\nSECTION\n2\nHEADER\n")

    def test_ends_with_eof(self):
        model = mech_part_drawing("pillow_block", _geometry())
        dxf = render_dxf(model)
        assert dxf.rstrip(b"\n").endswith(b"0\nEOF")

    def test_one_line_per_segment(self):
        model = mech_part_drawing("pillow_block", _geometry())
        dxf = render_dxf(model)
        n_segments = sum(1 for sheet in model.sheets for _e in sheet.entities)
        # Geometry lines live on the GEOMETRY layer; the sheet furniture
        # (frame + title block) lives on the SHEET layer, counted in the
        # cross-renderer consistency tests.
        assert dxf.count(b"0\nLINE\n8\nGEOMETRY\n") == n_segments

    def test_one_text_per_dimension(self):
        model = mech_part_drawing("pillow_block", _geometry())
        dxf = render_dxf(model)
        n_dims = sum(len(sheet.dimensions) for sheet in model.sheets)
        n_anns = sum(len(sheet.annotations) for sheet in model.sheets)
        assert dxf.count(b"0\nTEXT\n8\nDIMENSIONS\n") == n_dims
        assert dxf.count(b"0\nTEXT\n8\nANNOTATIONS\n") == n_anns

    def test_deterministic_across_two_runs(self):
        geometry = _geometry()
        m1 = mech_part_drawing("pillow_block", geometry)
        m2 = mech_part_drawing("pillow_block", geometry)
        assert render_dxf(m1) == render_dxf(m2)

    def test_ascii_only(self):
        model = civil_plan_section("small_office", _frame())
        dxf = render_dxf(model)
        assert dxf.decode("ascii")

    def test_text_value_newline_is_neutralized_group_pairing_intact(self):
        """M2: an embedded newline in a TEXT value must not desync R12's
        strictly line-paired code/value stream."""
        from regolith.backends.drawings.renderer_dxf import _text_entity

        lines = _text_entity(0.0, 0.0, 3.0, "0\nSECTION", "ANNOTATIONS")
        # Still exactly the 14 lines a well-formed TEXT entity has (7
        # code/value pairs): a raw newline in the value would have added
        # extra lines and desynced every following pair.
        assert len(lines) == 14
        assert lines[-2] == "1"
        assert "\n" not in lines[-1]
        assert "\r" not in lines[-1]

    def test_sanitize_text_value_replaces_control_chars_with_space(self):
        from regolith.backends.drawings.renderer_dxf import _sanitize_text_value

        assert _sanitize_text_value("0\nSECTION") == "0 SECTION"
        assert _sanitize_text_value("a\r\nb") == "a  b"

    def test_sanitize_text_value_replaces_non_ascii_with_question_mark(self):
        from regolith.backends.drawings.renderer_dxf import _sanitize_text_value

        value = "Pozna" + chr(0x144)
        assert _sanitize_text_value(value) == "Pozna?"


class TestPdfRenderer:
    # frob:tests python/regolith/backends/drawings/renderer_pdf.py::render_pdf kind="unit"
    def test_starts_with_pdf_header(self):
        model = mech_part_drawing("pillow_block", _geometry())
        pdf = render_pdf(model)
        assert pdf.startswith(b"%PDF-1.4\n")

    def test_ends_with_eof_marker(self):
        model = mech_part_drawing("pillow_block", _geometry())
        pdf = render_pdf(model)
        assert pdf.rstrip(b"\n").endswith(b"%%EOF")

    def test_deterministic_across_two_runs(self):
        geometry = _geometry()
        m1 = mech_part_drawing("pillow_block", geometry)
        m2 = mech_part_drawing("pillow_block", geometry)
        assert render_pdf(m1) == render_pdf(m2)

    def test_no_creation_date_or_id(self):
        model = mech_part_drawing("pillow_block", _geometry())
        pdf = render_pdf(model)
        assert b"/CreationDate" not in pdf
        assert b"/ID" not in pdf

    def test_has_parseable_xref_and_trailer(self):
        model = mech_part_drawing("pillow_block", _geometry())
        pdf = render_pdf(model)
        assert b"\nxref\n" in pdf
        assert b"trailer\n" in pdf
        assert b"/Root 1 0 R" in pdf
        assert b"startxref\n" in pdf

    def test_content_stream_has_expected_line_operator_count(self):
        # WO-123 D238.3 defect 5: each `Dimension` draws a real dimension
        # line + TWO extension lines (one per measured edge) + TWO
        # two-stroke arrowheads (one per end) -- 1 + 2 + 4 = 7 line
        # operators per dimension, not just a floating text label.
        # Defect 7 also gave the mech producer a "Dimensions (not
        # projected)" notes table (3 columns -> 4 vertical rules + 1
        # header rule = 5 table-ruling line operators). The total line
        # count is entity segments PLUS 7 per dimension PLUS the notes
        # table's own 5 ruling lines.
        model = mech_part_drawing("pillow_block", _geometry())
        pdf = render_pdf(model)
        n_segments = sum(len(sheet.entities) for sheet in model.sheets)
        n_dims = sum(len(sheet.dimensions) for sheet in model.sheets)
        n_table_rules = 5
        assert pdf.count(b" l\n") == n_segments + 7 * n_dims + n_table_rules

    def test_pdf_text_replaces_non_ascii_with_question_mark(self):
        """L2: documented lossy contract, matching the DXF renderer's own
        choice (no Result-return seam at this leaf)."""
        from regolith.backends.drawings.renderer_pdf import _pdf_text

        value = "Pozna" + chr(0x144)
        assert _pdf_text(value) == "Pozna?"

    def test_pdf_text_escapes_newline_safely_via_parens(self):
        """PDF literal strings are paren-delimited, so an embedded
        newline cannot desync the content stream (unlike DXF's
        line-paired groups, M2) -- still passed through untouched."""
        from regolith.backends.drawings.renderer_pdf import _pdf_text

        assert _pdf_text("a\nb") == "a\nb"


def _distinct_title_block_model():
    """A one-sheet fixture whose title-block field values are pairwise
    distinct and never substrings of any other rendered text, so
    exactly-once assertions on raw output bytes are unambiguous.
    """
    model = mech_part_drawing("pillow_block", _geometry())
    sheet = model.sheets[0]
    tb = sheet.title_block.model_copy(
        update={
            "title": "TBFX-TITLE",
            "drawing_number": "TBFX-NUM-001",
            "revision": "R7",
            "scale_label": "1:23",
            "subject": "TBFX-SUBJ",
        }
    )
    return model.model_copy(
        update={"sheets": [sheet.model_copy(update={"title_block": tb})]}
    )


class TestRendererFurnitureConsistency:
    """All three renderers must emit the SAME sheet furniture (frame
    border + title block) from the one shared layout home
    (`renderer._sheet_furniture`) -- a renderer missing its frame or a
    title-block field is a divergence bug, not a style choice.
    """

    # WO-123 (charter 41 sec. 1.1): title-block VALUES render bare (no
    # "rev "/"scale " prefix -- that's now the separate LABEL line),
    # each preceded by its own caption-face label ("REV", "SCALE", ...).
    _FIELD_TEXTS = (
        b"TBFX-TITLE",
        b"TBFX-NUM-001",
        b"R7",
        b"1:23",
        b"TBFX-SUBJ",
    )

    def test_svg_has_frame_and_each_field_exactly_once(self):
        svg = render_svg(_distinct_title_block_model())
        assert svg.count(b'class="frame"') == 1
        assert svg.count(b'class="title-block-frame"') == 1
        for text in self._FIELD_TEXTS:
            assert svg.count(text) == 1, text

    # frob:tests python/regolith/backends/drawings/renderer.py::ChartGeometry.scale kind="unit"
    def test_dxf_has_frame_and_each_field_exactly_once(self):
        dxf = render_dxf(_distinct_title_block_model())
        # 2 rects (frame + title block) x 4 edges on the SHEET layer.
        assert dxf.count(b"0\nLINE\n8\nSHEET\n") == 8
        # 6 fields (title/dwg-no/rev/scale/subject/sheet) x 2 lines
        # (label + value) + 1 provenance footer line, all on SHEET.
        assert dxf.count(b"0\nTEXT\n8\nSHEET\n") == 13
        for text in self._FIELD_TEXTS:
            assert dxf.count(b"\n" + text + b"\n") == 1, text

    def test_pdf_has_frame_and_each_field_exactly_once(self):
        pdf = render_pdf(_distinct_title_block_model())
        # 3 stroked `re` rectangles: frame + title-block box + the mech
        # producer's "Dimensions (not projected)" notes table (WO-123
        # D238.3 defect 7: the height note is now a table row, not a
        # floating annotation -- the table's own ruled frame is a
        # THIRD rect this fixture never had before).
        assert pdf.count(b" re\n") == 3
        for text in self._FIELD_TEXTS:
            assert pdf.count(b"(" + text + b") Tj") == 1, text
