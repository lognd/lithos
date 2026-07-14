"""Tests for the WO-130 edit models (D244.2, charter 42 sec. 7)."""

from __future__ import annotations

from regolith._schema.models import (
    AssemblyPart,
    CopperSummary,
    Placement,
    RealizedAssembly,
    RealizedLayout,
    Transform,
)
from regolith.backends.edit_models import (
    assembly_edit_model,
    board_edit_model,
    drawing_edit_model,
)

_EMPTY_COPPER = CopperSummary(copper_areas_mm2=[], net_lengths_mm=[])


def _layout(placements: tuple[Placement, ...]) -> RealizedLayout:
    return RealizedLayout(
        board_outline_ref="ref",
        copper=_EMPTY_COPPER,
        kicad_pcb_content_hash="deadbeef" * 8,
        netlist_hash="",
        parasitics=[],
        placements=list(placements),
        routed_segments=[],
    )


def test_board_edit_model_component_target_and_pose():
    layout = _layout(
        (
            Placement(
                footprint="R0805",
                position_mm=[1.0, 2.0],
                reference="R1",
                rotation_deg=90.0,
                side="top",
            ),
        )
    )
    model = board_edit_model("mainboard_mx", "MainboardMcu", layout)
    assert len(model.entities) == 1
    entity = model.entities[0]
    assert entity.kind == "component"
    assert entity.entity_id == "R1"
    assert entity.pose == {"x_mm": 1.0, "y_mm": 2.0, "rot_deg": 90.0, "side": "top"}
    assert entity.override_target == "mainboard_mx.MainboardMcu.placements.R1.pose"
    assert entity.read_only is False
    assert model.keepouts_absent_reason


def test_board_edit_model_tap_header_and_test_points():
    from regolith.realizer.elec.debug_placement import TapPlacementPlan, TapTestPoint

    header_placement = Placement(
        footprint="conn",
        position_mm=[5.0, 7.5],
        reference="J_DBG1",
        rotation_deg=0.0,
        side="top",
    )
    tp_placement = Placement(
        footprint="tp",
        position_mm=[5.0, 2.5],
        reference="TP_DBG0",
        rotation_deg=0.0,
        side="top",
    )
    plan = TapPlacementPlan(
        subject="MainboardMcu",
        header_record="std.debug.tap_header",
        header_placement=header_placement,
        test_points=(
            TapTestPoint(
                channel=0,
                target_path="x.y",
                kind="rail",
                why="probe",
                placement=tp_placement,
                label="CH0",
                marker="m",
            ),
        ),
        silkscreen_labels=(),
    )
    layout = _layout(())
    model = board_edit_model("mainboard_mx", "MainboardMcu", layout, tap_plan=plan)
    kinds = {e.entity_id: e.kind for e in model.entities}
    assert kinds == {"J_DBG1": "tap_header", "TP_DBG0": "test_point"}
    targets = {e.entity_id: e.override_target for e in model.entities}
    assert targets["J_DBG1"] == "mainboard_mx.MainboardMcu.placements.J_DBG1.pose"


def test_drawing_edit_model_annotation_movable_view_read_only():
    from regolith._schema.models import (
        Annotation,
        DrawingModel,
        Sheet,
        SheetSize1,
        TitleBlock,
        View,
        ViewSource,
    )

    annotation = Annotation(anchor=[10.0, 20.0], text="note", text_height_mm=2.0)
    view = View(
        entity_indices=[],
        name="front",
        plane="XY",
        scale=1.0,
        source=ViewSource(source_digest="digest", source_kind="geometry.realized"),
    )
    sheet = Sheet(
        annotations=[annotation],
        dimensions=[],
        entities=[],
        size=SheetSize1.ansi_a,
        tables=[],
        title_block=TitleBlock(
            drawing_number="1", revision="A", scale_label="1:1", subject="s", title="t"
        ),
        views=[view],
    )
    model = DrawingModel(sheets=[sheet], subject="CarrierSi")
    edit_model = drawing_edit_model("mainboard_mx", "CarrierSi", model.sheets)
    kinds = {e.kind for e in edit_model.entities}
    assert kinds == {"annotation", "view"}
    annotation_row = next(e for e in edit_model.entities if e.kind == "annotation")
    assert annotation_row.read_only is False
    assert annotation_row.pose == {"x_mm": 10.0, "y_mm": 20.0}
    assert (
        annotation_row.override_target == "mainboard_mx.CarrierSi.annotations.0.anchor"
    )
    view_row = next(e for e in edit_model.entities if e.kind == "view")
    assert view_row.read_only is True
    assert view_row.read_only_reason is not None


def test_assembly_edit_model_fixed_and_placed_are_read_only_underconstrained_is_not():
    def part(id_: str) -> AssemblyPart:
        return AssemblyPart(
            geometry_digest="digest",
            id=id_,
            transform=Transform(rotation_deg=[0.0, 0.0, 0.0], translation_m=[0, 0, 0]),
        )

    assembly = RealizedAssembly(
        com_m=[0.0, 0.0, 0.0],
        dof_states={"root": "fixed", "arm": "placed", "loose": "underconstrained"},
        interferences=[],
        mass_kg=1.0,
        mates=[],
        mating_graph_hash="hash",
        parts=[part("root"), part("arm"), part("loose")],
    )
    model = assembly_edit_model("mainboard_mx", "Gantry", assembly)
    by_id = {e.entity_id: e for e in model.entities}
    assert by_id["root"].read_only is True
    assert "mate solve" in by_id["root"].read_only_reason
    assert by_id["arm"].read_only is True
    assert by_id["loose"].read_only is False
    assert by_id["loose"].override_target == "mainboard_mx.Gantry.parts.loose.pose"
