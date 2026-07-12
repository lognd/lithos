"""WO-100: real projected drawing views + the 3D artifact family.

Acceptance (WO-100): a flagship part's front view is a real projected
silhouette (not a bbox rectangle); a deterministic GLB + a self-contained
offline viewer join the package; the bytes-less path degrades to a loud
annotated fallback, never a crash. Every artifact is byte-identical
across two runs (AD-6). OCP/OCCT is present on the reference host, so
these run for real; the fallback test proves the degrade path directly.
"""

from __future__ import annotations

import json
import struct
import tempfile
import xml.etree.ElementTree as ET

import pytest
from regolith._schema.models import (
    AssemblyPart,
    RealizedAssembly,
    Transform,
)
from regolith._schema.models import (
    Entity3 as PolylineEntity,
)
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.drawings.project import mech_part_projected_drawing
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.three_d.backend import (
    default_three_d_registry,
    render_assembly_3d,
    render_part_3d,
)
from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.schema import (
    ExtrudeOp,
    FeatureProgram,
    HoleOp,
    Point2,
    ResolvedParam,
    Sketch,
    Stage,
)


def _bed_plate_program() -> FeatureProgram:
    """A cnc_router_r1 BedPlate-shaped part with a real bored feature, so
    its projection is a genuine silhouette (hole circles in the plan
    view), never a plain rectangle."""
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=0.180, y=0.0),
        Point2(x=0.180, y=0.120),
        Point2(x=0.0, y=0.120),
    )
    body = ExtrudeOp(
        name="body",
        sketch=Sketch(name="blank", outline=outline),
        distance=ResolvedParam(value=0.020),
    )
    bore = HoleOp(
        name="bed_bore",
        center=Point2(x=0.090, y=0.060),
        diameter=ResolvedParam(value=0.040),
        depth=ResolvedParam(value=0.020),
    )
    stage = Stage(name="milled", process="cnc_mill", features=(body, bore))
    return FeatureProgram(part_name="BedPlate", material="AL6082_T6", stages=(stage,))


@pytest.fixture(scope="module")
def bed_plate():
    art = realize_feature_program(_bed_plate_program())
    assert art.is_ok, art
    store = NativeArtifactStore(tempfile.mkdtemp())
    store.put_at(art.danger_ok.geometry.step_content_hash, art.danger_ok.step_bytes)
    return art.danger_ok.geometry, store


class TestProjection:
    def test_front_view_is_a_real_silhouette_not_a_rectangle(self, bed_plate) -> None:
        geometry, store = bed_plate
        model = mech_part_projected_drawing("BedPlate", geometry, store)
        sheet = model.sheets[0]
        # Real multi-view sheet, not the single-view bbox stand-in.
        assert [v.name for v in sheet.views] == ["front", "top", "right", "iso"]
        # A bbox rectangle would be exactly four segments; a real
        # projection of a bored plate carries far more geometry, and
        # polyline entities (discretized edges) the stand-in never emits.
        assert len(sheet.entities) > 4
        assert any(isinstance(e, PolylineEntity) for e in sheet.entities)
        # No loud fallback annotation on the real path.
        assert not any("unavailable" in a.text for a in sheet.annotations)
        # The top view (looking down the bore axis) sees the bore: it has
        # strictly more than the 4 edges a rectangle outline would carry.
        top = next(v for v in sheet.views if v.name == "top")
        assert len(top.entity_indices) > 4

    def test_byte_identical_across_two_runs(self, bed_plate) -> None:
        geometry, store = bed_plate
        m1 = mech_part_projected_drawing("BedPlate", geometry, store)
        m2 = mech_part_projected_drawing("BedPlate", geometry, store)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        assert render_svg(m1) == render_svg(m2)

    def test_renders_to_valid_ascii_svg(self, bed_plate) -> None:
        geometry, store = bed_plate
        svg = render_svg(mech_part_projected_drawing("BedPlate", geometry, store))
        ET.fromstring(svg)
        svg.decode("ascii")


class TestFallback:
    def test_bytesless_subject_gets_loud_annotation_not_a_crash(
        self, bed_plate
    ) -> None:
        geometry, _store = bed_plate
        empty = NativeArtifactStore(tempfile.mkdtemp())
        model = mech_part_projected_drawing("BedPlate", geometry, empty)
        texts = [a.text for a in model.sheets[0].annotations]
        assert any(t.startswith("projected geometry unavailable:") for t in texts)
        # Still the honest bbox stand-in underneath (one view, renderable).
        assert render_svg(model)


class TestGlb:
    def test_glb_header_and_determinism(self, bed_plate) -> None:
        geometry, store = bed_plate
        r1 = render_part_3d("BedPlate", geometry, store)
        r2 = render_part_3d("BedPlate", geometry, store)
        assert r1.is_ok and r2.is_ok
        glb1 = next(f.content for f in r1.danger_ok if f.relpath.endswith(".glb"))
        glb2 = next(f.content for f in r2.danger_ok if f.relpath.endswith(".glb"))
        assert glb1 == glb2  # byte-identical (AD-6)
        magic, version, total = struct.unpack("<III", glb1[:12])
        assert magic == 0x46546C67  # "glTF"
        assert version == 2
        assert total == len(glb1)
        # JSON chunk parses and has exactly one node/mesh.
        jlen, jtype = struct.unpack("<II", glb1[12:20])
        assert jtype == 0x4E4F534A  # "JSON"
        gltf = json.loads(glb1[20 : 20 + jlen])
        assert len(gltf["nodes"]) == 1
        assert gltf["nodes"][0]["name"] == "BedPlate"
        assert len(gltf["meshes"]) == 1
        assert gltf["asset"]["generator"] == "regolith-3d"

    def test_assembly_glb_places_instances_by_transform(self, bed_plate) -> None:
        geometry, store = bed_plate
        asm = RealizedAssembly(
            parts=[
                AssemblyPart(
                    id="bed_left",
                    geometry_digest=geometry.step_content_hash,
                    transform=Transform(
                        rotation_deg=[0, 0, 0], translation_m=[0, 0, 0]
                    ),
                ),
                AssemblyPart(
                    id="bed_right",
                    geometry_digest=geometry.step_content_hash,
                    transform=Transform(
                        rotation_deg=[0, 0, 90], translation_m=[0.3, 0, 0]
                    ),
                ),
            ],
            dof_states={"bed_left": "fixed", "bed_right": "placed"},
            mates=[],
            mating_graph_hash="h",
            com_m=[0, 0, 0],
            mass_kg=1.0,
            interferences=[],
        )
        r1 = render_assembly_3d("router", asm, store)
        r2 = render_assembly_3d("router", asm, store)
        assert r1.is_ok
        glb1 = next(f.content for f in r1.danger_ok if f.relpath.endswith(".glb"))
        glb2 = next(f.content for f in r2.danger_ok if f.relpath.endswith(".glb"))
        assert glb1 == glb2
        jlen = struct.unpack("<I", glb1[12:16])[0]
        gltf = json.loads(glb1[20 : 20 + jlen])
        assert [n["name"] for n in gltf["nodes"]] == ["bed_left", "bed_right"]
        assert len(gltf["meshes"]) == 1  # deduped by geometry digest
        assert "matrix" in gltf["nodes"][1]


class TestViewer:
    def test_viewer_is_self_contained_ascii_offline(self, bed_plate) -> None:
        geometry, store = bed_plate
        files = render_part_3d("BedPlate", geometry, store).danger_ok
        viewer = next(f.content for f in files if f.relpath.endswith(".viewer.html"))
        # ASCII source (deliverable 4).
        viewer.decode("ascii")
        # ZERO external requests: no protocol/host reference of any kind.
        for token in (b"http://", b"https://", b"//cdn", b'src="http', b"fetch("):
            assert token not in viewer, token
        # Deterministic viewer bytes across two runs.
        again = render_part_3d("BedPlate", geometry, store).danger_ok
        v2 = next(f.content for f in again if f.relpath.endswith(".viewer.html"))
        assert viewer == v2


class TestOcpGating:
    def test_ocp_unavailable_degrades_to_annotated_fallback(
        self, bed_plate, monkeypatch
    ) -> None:
        geometry, store = bed_plate
        # Simulate a host without OCP: the projector returns None.
        import regolith.backends.drawings.project as proj

        monkeypatch.setattr(proj, "_project_views", lambda _b: None)
        model = proj.mech_part_projected_drawing("BedPlate", geometry, store)
        texts = [a.text for a in model.sheets[0].annotations]
        assert any("OCP/OCCT projection unavailable" in t for t in texts)


class TestStepViews:
    def test_place_steps_embed_a_projected_view(self, bed_plate) -> None:
        from regolith.backends.instructions import (
            render_document,
            step_view_svgs,
            steps_for_assembly,
        )

        geometry, store = bed_plate
        asm = RealizedAssembly(
            parts=[
                AssemblyPart(
                    id="base",
                    geometry_digest=geometry.step_content_hash,
                    transform=Transform(
                        rotation_deg=[0, 0, 0], translation_m=[0, 0, 0]
                    ),
                ),
                AssemblyPart(
                    id="top",
                    geometry_digest=geometry.step_content_hash,
                    transform=Transform(
                        rotation_deg=[0, 0, 0], translation_m=[0, 0, 0.05]
                    ),
                ),
            ],
            dof_states={"base": "fixed", "top": "placed"},
            mates=[],
            mating_graph_hash="h",
            com_m=[0, 0, 0],
            mass_kg=1.0,
            interferences=[],
        )
        steps = steps_for_assembly("stack", asm, {})
        views = step_view_svgs(asm, steps, store)
        assert set(views) == {1, 2}
        assert all("<svg" in v for v in views.values())
        md = render_document(steps, views)
        md.encode("ascii")
        assert md.count("<svg") == 2


class TestRegistry:
    def test_three_d_renderers_register_under_their_families(self) -> None:
        reg = default_three_d_registry()
        assert [r.format_id for r in reg.for_realized_family("3d.part")] == ["glb"]
        assert [r.format_id for r in reg.for_realized_family("3d.assembly")] == ["glb"]
        # The drawing families are untouched (WO-99 built-ins intact).
        assert "svg" in reg.formats()
