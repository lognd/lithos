"""WO-166 slice (b): the wire-EDM profile-cut program kind
(`regolith.realizer.mech.wire_edm`) -- realize gating and DXF
emission via the existing `DrawingModel` -> `render_dxf` path."""

from __future__ import annotations

from regolith.backends.drawings.renderer_dxf import render_dxf
from regolith.realizer.mech.wire_edm import (
    LeadIn,
    ProfileVertex,
    WireEdmProfile,
    profile_drawing_model,
    realize_wire_edm_profile,
)


def _square_profile(
    *, corner_radius_mm: float = 0.5, closed: bool = True, has_start_hole: bool = True
) -> WireEdmProfile:
    return WireEdmProfile(
        profile_ref="demo_punch_profile",
        material_ref="std.materials/tool_steel_d2",
        vertices=(
            ProfileVertex(x_mm=0.0, y_mm=0.0, corner_radius_mm=corner_radius_mm),
            ProfileVertex(x_mm=20.0, y_mm=0.0, corner_radius_mm=corner_radius_mm),
            ProfileVertex(x_mm=20.0, y_mm=10.0, corner_radius_mm=corner_radius_mm),
            ProfileVertex(x_mm=0.0, y_mm=10.0, corner_radius_mm=corner_radius_mm),
        ),
        closed=closed,
        kerf_mm=0.25,
        spark_gap_mm=0.02,
        lead_in=LeadIn(start_x_mm=10.0, start_y_mm=5.0, has_start_hole=has_start_hole),
    )


def test_realize_passes_for_a_well_formed_profile() -> None:
    result = realize_wire_edm_profile(_square_profile())
    assert result.is_ok
    realized = result.danger_ok
    assert len(realized.corner_radius_outcomes) == 4
    assert not realized.start_hole_outcome.violated


def test_realize_refuses_a_too_sharp_corner() -> None:
    result = realize_wire_edm_profile(_square_profile(corner_radius_mm=0.001))
    assert result.is_err
    assert result.danger_err.kind == "corner_radius_violation"


def test_realize_refuses_a_closed_profile_with_no_start_hole() -> None:
    result = realize_wire_edm_profile(_square_profile(has_start_hole=False))
    assert result.is_err
    assert result.danger_err.kind == "start_hole_violation"


def test_open_profile_needs_no_start_hole() -> None:
    result = realize_wire_edm_profile(_square_profile(closed=False, has_start_hole=False))
    assert result.is_ok


def test_profile_drawing_model_renders_to_nonempty_dxf() -> None:
    realized = realize_wire_edm_profile(_square_profile()).danger_ok
    model = profile_drawing_model(realized)
    dxf_bytes = render_dxf(model)
    assert len(dxf_bytes) > 0
    assert b"SECTION" in dxf_bytes


def test_profile_drawing_model_is_deterministic() -> None:
    realized = realize_wire_edm_profile(_square_profile()).danger_ok
    first = render_dxf(profile_drawing_model(realized))
    second = render_dxf(profile_drawing_model(realized))
    assert first == second
