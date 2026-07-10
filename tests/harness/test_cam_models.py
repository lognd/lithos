"""std.cam model tests (WO-67 deliverables 3-7): a good pillow_block
plan discharges every check-mode model Valid, one broken variant per
failure class yields the named violated/indeterminate result with a
line citation, the conservative-honesty removal test, and the
flagship-1 Marlin envelope fixture."""

from __future__ import annotations

from pathlib import Path

import pytest
from regolith._schema.models import PayloadRef
from regolith.harness.errors import DomainError
from regolith.harness.model import DischargeRequest
from regolith.harness.models.cam.ir import Dialect
from regolith.harness.models.cam.models import (
    CamCollisionCoarseModel,
    CamCoverageModel,
    CamEnvelopeModel,
    CamRemovalModel,
)
from regolith.harness.models.cam.records import (
    Aabb,
    FeatureTarget,
    MachineRecord,
    StockTarget,
    ToolRecord,
)
from regolith.harness.quantity import Interval
from regolith.orchestrator.payload_store import PayloadStore

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cam"

_MILL = MachineRecord(
    name="fixture_mill_3axis",
    kind="mill_3axis",
    travel=Aabb(x_min=0, x_max=300, y_min=0, y_max=200, z_min=-50, z_max=50),
    max_feed_mm_min=3000,
    source="WO-67 fixture (WO-66 std.machines not landed; swap-to-ref follow-up)",
)
_TOOL = ToolRecord(
    tool_id=1,
    diameter_mm=6.0,
    flutes=4,
    stickout_mm=30.0,
    source="WO-67 fixture (WO-66 std.tooling not landed; swap-to-stdlib-ref follow-up)",
)
_TARGET = StockTarget(
    geometry_digest="fixture:pillow_block:v1",
    stock=Aabb(x_min=0, x_max=90, y_min=0, y_max=50, z_min=-20, z_max=0),
    finished=Aabb(x_min=0, x_max=90, y_min=0, y_max=50, z_min=-18, z_max=-0.1),
    margin_mm=0.5,
    features=(
        FeatureTarget(
            name="pocket_a",
            kind="pocket",
            touch_zone=Aabb(x_min=9, x_max=41, y_min=9, y_max=41, z_min=-18, z_max=-1),
        ),
        FeatureTarget(
            name="bore_b",
            kind="bore",
            touch_zone=Aabb(
                x_min=69, x_max=81, y_min=29, y_max=41, z_min=-18, z_max=-1
            ),
        ),
    ),
)
_PRINTER = MachineRecord(
    name="fixture_fdm_printer",
    kind="fdm_printer",
    travel=Aabb(x_min=0, x_max=220, y_min=0, y_max=220, z_min=0, z_max=250),
    max_feed_mm_min=6000,
    source="WO-67 fixture (WO-66 std.machines not landed; swap-to-ref follow-up)",
)


@pytest.fixture
def store(tmp_path: Path) -> PayloadStore:
    return PayloadStore(str(tmp_path))


def _plan_ref(store: PayloadStore, name: str) -> PayloadRef:
    digest = store.put((_FIXTURES / name).read_bytes())
    return PayloadRef(digest=digest, kind="plan", origin=name)


def _table_ref(store: PayloadStore, doc) -> PayloadRef:  # type: ignore[no-untyped-def]
    digest = store.put(doc.model_dump_json().encode())
    return PayloadRef(digest=digest, kind="table", origin=type(doc).__name__)


def _resolver(store: PayloadStore):  # type: ignore[no-untyped-def]
    return store.resolve


def test_good_plan_envelope_valid(store: PayloadStore) -> None:
    model = CamEnvelopeModel(Dialect.fanuc)
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={},
        payloads={
            "plan": _plan_ref(store, "good.nc"),
            "cam_machine": _table_ref(store, _MILL),
            "cam_tooling": _table_ref(store, _TOOL),
        },
        regimes=(Dialect.fanuc.value,),
    )
    result = model.discharge(
        request, registry_version="test", resolver=_resolver(store)
    )
    assert result.is_ok, result.danger_err if result.is_err else None
    evidence = result.danger_ok
    assert evidence.status.value == "discharged"


def test_out_of_travel_envelope_violated(store: PayloadStore) -> None:
    model = CamEnvelopeModel(Dialect.fanuc)
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={},
        payloads={
            "plan": _plan_ref(store, "out_of_travel.nc"),
            "cam_machine": _table_ref(store, _MILL),
            "cam_tooling": _table_ref(store, _TOOL),
        },
        regimes=(Dialect.fanuc.value,),
    )
    result = model.discharge(
        request, registry_version="test", resolver=_resolver(store)
    )
    assert result.is_ok
    # Excess > 0 pushes the margin negative -- a violated discharge.
    from regolith.harness.quantity import bits_to_f64

    evidence = result.danger_ok
    assert bits_to_f64(evidence.value_bits) > 0.0


def test_rapid_through_stock_collision_flagged(store: PayloadStore) -> None:
    model = CamCollisionCoarseModel(Dialect.fanuc)
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={},
        payloads={
            "plan": _plan_ref(store, "rapid_through_stock.nc"),
            "cam_target": _table_ref(store, _TARGET),
        },
        regimes=(Dialect.fanuc.value,),
    )
    result = model.discharge(
        request, registry_version="test", resolver=_resolver(store)
    )
    assert result.is_ok
    from regolith.harness.quantity import bits_to_f64

    assert bits_to_f64(result.danger_ok.value_bits) > 0.0


def test_good_plan_collision_clear(store: PayloadStore) -> None:
    model = CamCollisionCoarseModel(Dialect.fanuc)
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={},
        payloads={
            "plan": _plan_ref(store, "good.nc"),
            "cam_target": _table_ref(store, _TARGET),
        },
        regimes=(Dialect.fanuc.value,),
    )
    result = model.discharge(
        request, registry_version="test", resolver=_resolver(store)
    )
    assert result.is_ok
    from regolith.harness.quantity import bits_to_f64

    assert bits_to_f64(result.danger_ok.value_bits) == 0.0


@pytest.mark.parametrize(
    ("fixture", "expect_kind"),
    [("undercut.nc", "undercut"), ("overcut.nc", "overcut")],
)
def test_removal_broken_variants_named_violation(
    store: PayloadStore, fixture: str, expect_kind: str
) -> None:
    model = CamRemovalModel(Dialect.fanuc)
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={"resolution_mm": Interval(lo=0.05, hi=0.05)},
        payloads={
            "plan": _plan_ref(store, fixture),
            "cam_target": _table_ref(store, _TARGET),
        },
        regimes=(Dialect.fanuc.value,),
    )
    outcome_note = _removal_note(store, model, request)
    assert expect_kind in outcome_note


def _removal_note(
    store: PayloadStore, model: CamRemovalModel, request: DischargeRequest
) -> str:
    # Re-derive the raw `CamOutcome.note` for the assertion (the model
    # itself only carries value/eps in Evidence -- the note is the
    # check function's own diagnostic, exercised directly here to
    # assert the NAMED failure class per the acceptance shape).
    from regolith.harness.models.cam.checks import check_removal
    from regolith.harness.models.cam.ir import parse_plan

    raw = store.resolve(request.payloads["plan"].digest).danger_ok
    toolpath = parse_plan(raw, Dialect.fanuc)
    target_raw = store.resolve(request.payloads["cam_target"].digest).danger_ok
    target = StockTarget.model_validate_json(target_raw)
    outcome = check_removal(toolpath, target, request.inputs["resolution_mm"].hi)
    return outcome.note


def test_removal_good_plan_valid(store: PayloadStore) -> None:
    model = CamRemovalModel(Dialect.fanuc)
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={"resolution_mm": Interval(lo=0.05, hi=0.05)},
        payloads={
            "plan": _plan_ref(store, "good.nc"),
            "cam_target": _table_ref(store, _TARGET),
        },
        regimes=(Dialect.fanuc.value,),
    )
    result = model.discharge(
        request, registry_version="test", resolver=_resolver(store)
    )
    assert result.is_ok
    from regolith.harness.quantity import bits_to_f64

    assert bits_to_f64(result.danger_ok.value_bits) == 0.0


def test_removal_conservative_honesty_thin_margin_indeterminate(
    store: PayloadStore,
) -> None:
    """charter D3 acceptance shape: a coarse resolution whose margin is
    thinner than the voxel error stays INDETERMINATE, never an
    optimistic pass."""
    model = CamRemovalModel(Dialect.fanuc)
    # `_TARGET.margin_mm` is 0.5mm; a 1.0mm-resolution pass cannot
    # honestly claim anything at that margin.
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={"resolution_mm": Interval(lo=1.0, hi=1.0)},
        payloads={
            "plan": _plan_ref(store, "good.nc"),
            "cam_target": _table_ref(store, _TARGET),
        },
        regimes=(Dialect.fanuc.value,),
    )
    result = model.discharge(
        request, registry_version="test", resolver=_resolver(store)
    )
    assert result.is_err
    assert isinstance(result.danger_err, DomainError)
    assert "indeterminate" in result.danger_err.message


def test_coverage_good_plan_valid(store: PayloadStore) -> None:
    model = CamCoverageModel(Dialect.fanuc)
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={},
        payloads={
            "plan": _plan_ref(store, "good.nc"),
            "cam_target": _table_ref(store, _TARGET),
        },
        regimes=(Dialect.fanuc.value,),
    )
    result = model.discharge(
        request, registry_version="test", resolver=_resolver(store)
    )
    assert result.is_ok
    from regolith.harness.quantity import bits_to_f64

    assert bits_to_f64(result.danger_ok.value_bits) == 0.0


def test_coverage_missing_feature_violated(store: PayloadStore) -> None:
    model = CamCoverageModel(Dialect.fanuc)
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={},
        payloads={
            "plan": _plan_ref(store, "missing_feature.nc"),
            "cam_target": _table_ref(store, _TARGET),
        },
        regimes=(Dialect.fanuc.value,),
    )
    result = model.discharge(
        request, registry_version="test", resolver=_resolver(store)
    )
    assert result.is_ok
    from regolith.harness.quantity import bits_to_f64

    assert bits_to_f64(result.danger_ok.value_bits) > 0.0


def test_marlin_flagship1_envelope_valid(store: PayloadStore) -> None:
    model = CamEnvelopeModel(Dialect.marlin)
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={},
        payloads={
            "plan": _plan_ref(store, "flagship1_print.gcode"),
            "cam_machine": _table_ref(store, _PRINTER),
        },
        regimes=(Dialect.marlin.value,),
    )
    result = model.discharge(
        request, registry_version="test", resolver=_resolver(store)
    )
    assert result.is_ok, result.danger_err if result.is_err else None
    from regolith.harness.quantity import bits_to_f64

    assert bits_to_f64(result.danger_ok.value_bits) == 0.0


def test_evidence_is_cached_by_content_address(store: PayloadStore) -> None:
    """charter acceptance shape: cached (second run = cache hits) --
    proven here as byte-identical evidence hashes for identical inputs
    (the orchestrator's `EvidenceStore` keys on exactly this hash)."""
    model = CamEnvelopeModel(Dialect.fanuc)
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={},
        payloads={
            "plan": _plan_ref(store, "good.nc"),
            "cam_machine": _table_ref(store, _MILL),
            "cam_tooling": _table_ref(store, _TOOL),
        },
        regimes=(Dialect.fanuc.value,),
    )
    first = model.discharge(request, registry_version="test", resolver=_resolver(store))
    second = model.discharge(
        request, registry_version="test", resolver=_resolver(store)
    )
    assert first.is_ok and second.is_ok
    assert first.danger_ok.hash == second.danger_ok.hash
