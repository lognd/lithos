"""``geometry_realizable`` post-geometry verification model (WO-22 deliverable 4).

Covers: discharged when the prediction matches the realized geometry,
VIOLATED for a deliberately-wrong prediction fixture (WO-22 acceptance),
and an honest INDETERMINATE when no realization is cached for the
request's digest (never a silent pass).
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval
from regolith.harness.registry import ModelRegistry
from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.model import (
    GeometryRealizableModel,
    clear_realized_geometry_cache,
    register_realized_geometry,
)
from regolith.realizer.mech.pack import PACK_NAME, PACK_VERSION, register

from tests.realizer.mech.fixtures import PLATE_BBOX_M, PLATE_VOLUME_M3, plate_program


def setup_function() -> None:
    """Test isolation: the realized-geometry cache is process-global."""
    clear_realized_geometry_cache()


def _registry() -> ModelRegistry:
    registry = ModelRegistry()
    register(registry)
    return registry


def _request(
    digest: str, *, volume: float, bbox: tuple[float, float, float]
) -> DischargeRequest:
    return DischargeRequest(
        claim_kind="geometry_realizable",
        limit=1e-6,
        settings_digest=digest,
        inputs={
            "volume_m3": Interval.point(volume),
            "bbox_x_m": Interval.point(bbox[0]),
            "bbox_y_m": Interval.point(bbox[1]),
            "bbox_z_m": Interval.point(bbox[2]),
        },
    )


def test_pack_registers_under_geometry_realizable() -> None:
    """`register` adds the model under its pack identity (AD-19)."""
    registry = _registry()
    candidates = registry.candidates("geometry_realizable")
    assert len(candidates) == 1
    model_id = candidates[0].model_id
    assert registry.pack_of(model_id) == (PACK_NAME, PACK_VERSION)


def test_discharged_when_prediction_matches_realized_geometry() -> None:
    """An accurate static prediction discharges cleanly."""
    realized = realize_feature_program(plate_program()).danger_ok
    register_realized_geometry(realized)
    registry = _registry()
    evidence = registry.discharge(
        _request(
            realized.geometry.feature_program_hash, volume=PLATE_VOLUME_M3, bbox=PLATE_BBOX_M
        )
    )
    assert evidence.status.value == "discharged"


def test_violated_for_deliberately_wrong_prediction() -> None:
    """A far-off predicted volume is VIOLATED evidence (release-gated)."""
    realized = realize_feature_program(plate_program()).danger_ok
    register_realized_geometry(realized)
    registry = _registry()
    wrong_volume = (
        PLATE_VOLUME_M3 * 2.0
    )  # deliberately wrong (WO-22 acceptance fixture)
    evidence = registry.discharge(
        _request(realized.geometry.feature_program_hash, volume=wrong_volume, bbox=PLATE_BBOX_M)
    )
    assert evidence.status.value == "violated"


def test_indeterminate_when_no_realization_is_cached() -> None:
    """No cached realization for the digest is an honest deferral, never a pass."""
    registry = _registry()
    evidence = registry.discharge(
        _request("sha256-of-nothing-realized", volume=1.0, bbox=(1.0, 1.0, 1.0))
    )
    assert evidence.status.value == "indeterminate"


def test_model_direct_estimate_worst_corner() -> None:
    """A wide predicted interval takes the worst (max) relative-error corner (INV-9)."""
    realized = realize_feature_program(plate_program()).danger_ok
    register_realized_geometry(realized)
    model = GeometryRealizableModel()
    request = DischargeRequest(
        claim_kind="geometry_realizable",
        limit=1e-6,
        settings_digest=realized.geometry.feature_program_hash,
        inputs={
            "volume_m3": Interval(lo=PLATE_VOLUME_M3 * 0.5, hi=PLATE_VOLUME_M3),
            "bbox_x_m": Interval.point(PLATE_BBOX_M[0]),
            "bbox_y_m": Interval.point(PLATE_BBOX_M[1]),
            "bbox_z_m": Interval.point(PLATE_BBOX_M[2]),
        },
    )
    prediction = model.estimate(request)
    assert prediction.is_ok
    # The 0.5x corner is the worst: 100% relative error vs. the realized volume.
    assert abs(prediction.danger_ok.value - 1.0) < 1e-9
