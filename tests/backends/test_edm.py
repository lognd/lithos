"""WO-166 slice (b): the wire-EDM manufacturing backend
(`regolith.backends.edm.WireEdmBackend`)."""

from __future__ import annotations

import json

from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.edm import WireEdmBackend
from regolith.backends.framework import BackendInputs
from regolith.orchestrator.lockfile import Lockfile
from regolith.realizer.mech.wire_edm import (
    LeadIn,
    ProfileVertex,
    WireEdmProfile,
    realize_wire_edm_profile,
)


def _inputs(subject: str = "demo_punch_profile") -> BackendInputs:
    profile = WireEdmProfile(
        profile_ref=subject,
        material_ref="std.materials/tool_steel_d2",
        vertices=(
            ProfileVertex(x_mm=0.0, y_mm=0.0, corner_radius_mm=0.5),
            ProfileVertex(x_mm=20.0, y_mm=0.0, corner_radius_mm=0.5),
            ProfileVertex(x_mm=20.0, y_mm=10.0, corner_radius_mm=0.5),
            ProfileVertex(x_mm=0.0, y_mm=10.0, corner_radius_mm=0.5),
        ),
        closed=True,
        kerf_mm=0.25,
        spark_gap_mm=0.02,
        lead_in=LeadIn(start_x_mm=10.0, start_y_mm=5.0, has_start_hole=True),
    )
    realized = realize_wire_edm_profile(profile).danger_ok
    return BackendInputs(
        lockfile=Lockfile(tool_version="test"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore("."),
        edm_profiles={subject: realized},
    )


def test_produce_emits_dxf_and_setup_sheet() -> None:
    result = WireEdmBackend("demo_punch_profile").produce(_inputs())
    assert result.is_ok
    paths = {f.relpath for f in result.danger_ok}
    assert paths == {"edm_profile/profile.dxf", "edm_profile/setup_sheet.json"}
    for f in result.danger_ok:
        assert len(f.content) > 0
        assert f.provenance is not None
        assert f.provenance.tier == "deterministic"


def test_setup_sheet_carries_the_real_dfm_outcomes() -> None:
    result = WireEdmBackend("demo_punch_profile").produce(_inputs())
    setup_sheet = next(
        f for f in result.danger_ok if f.relpath == "edm_profile/setup_sheet.json"
    )
    payload = json.loads(setup_sheet.content)
    assert payload["kerf_mm"] == 0.25
    assert len(payload["dfm_outcomes"]["corner_radius"]) == 4
    assert payload["dfm_outcomes"]["start_hole"]["violated"] is False
    assert payload["provenance_tier"] == "deterministic"


def test_produce_refuses_an_unknown_subject() -> None:
    result = WireEdmBackend("nonexistent").produce(_inputs())
    assert result.is_err
    assert result.danger_err.kind == "edm_profile_ir_unavailable"


def test_produce_is_deterministic_across_calls() -> None:
    first = WireEdmBackend("demo_punch_profile").produce(_inputs())
    second = WireEdmBackend("demo_punch_profile").produce(_inputs())
    first_bytes = {f.relpath: f.content for f in first.danger_ok}
    second_bytes = {f.relpath: f.content for f in second.danger_ok}
    assert first_bytes == second_bytes
