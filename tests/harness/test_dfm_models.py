"""std.dfm model tests (WO-110 headline): the manufacturability
envelope checks' calibration arithmetic (hand-verifiable containment/
feasibility geometry -- the WO-67 cam-fixture posture: declared record
data in, worst excess out), the model's port/domain honesty (missing
payload -> named `DomainError`, indeterminate check -> abstained), and
the discharged/violated margin mapping."""

from __future__ import annotations

from pathlib import Path

import pytest
from regolith._schema.models import PayloadRef
from regolith.harness.model import DischargeRequest
from regolith.harness.models.cam.records import Aabb, MachineRecord, ToolRecord
from regolith.harness.models.dfm.checks import check_stock_fit, check_tool_fit
from regolith.harness.models.dfm.models import ManufacturableModel
from regolith.harness.models.dfm.records import DfmFeature, DfmPart, DfmToolSet
from regolith.harness.quantity import bits_to_f64
from regolith.orchestrator.payload_store import PayloadStore

_TRAVEL = Aabb(x_min=0, x_max=300, y_min=0, y_max=200, z_min=-50, z_max=50)
_MILL = MachineRecord(
    name="fixture_mill_3axis",
    kind="mill_3axis",
    travel=_TRAVEL,
    max_feed_mm_min=3000,
    source="WO-110 fixture (mirrors the WO-67 cam fixture record)",
)
_TOOL = ToolRecord(
    tool_id=1,
    diameter_mm=6.0,
    flutes=4,
    stickout_mm=30.0,
    source="WO-110 fixture (mirrors the WO-67 cam fixture record)",
)


def _hole(name: str, dia_mm: float, depth_mm: float | None = None) -> DfmFeature:
    return DfmFeature(
        name=name,
        count=1,
        stage="milled",
        process="cnc_mill",
        dia_mm=dia_mm,
        depth_mm=depth_mm,
        provenance="spelled",
    )


def _part(
    features: tuple[DfmFeature, ...],
    bbox: Aabb,
) -> DfmPart:
    return DfmPart(
        part_name="FixturePlate",
        claim_process="milled",
        families=("mill",),
        features=features,
        bbox_mm=bbox,
        geometry_digest="blake3:fixture",
    )


# --- check calibration (hand-verifiable arithmetic) --------------------


# frob:tests python/regolith/harness/models/dfm/checks.py::check_stock_fit
def test_stock_fit_passing_part_reports_negative_excess() -> None:
    """A 90 x 50 x 20 plate in 300 x 200 x 100 travel: the worst axis
    excess is 20 - 100 = -80 mm (z governs; x is -210, y -150)."""
    bbox = Aabb(x_min=0, x_max=90, y_min=0, y_max=50, z_min=-20, z_max=0)
    outcome = check_stock_fit(bbox, _TRAVEL)
    assert not outcome.indeterminate
    assert outcome.excess == pytest.approx(-80.0)


def test_stock_fit_oversize_part_reports_worst_axis_excess() -> None:
    """A 900 x 600 x 18 sheet in the same travel: x excess 900 - 300 =
    600 mm governs (y is 400, z -82)."""
    bbox = Aabb(x_min=0, x_max=900, y_min=0, y_max=600, z_min=-18, z_max=0)
    outcome = check_stock_fit(bbox, _TRAVEL)
    assert outcome.violated
    assert outcome.excess == pytest.approx(600.0)
    assert "x:" in outcome.note and "y:" in outcome.note


# frob:tests python/regolith/harness/models/dfm/checks.py::check_tool_fit
def test_tool_fit_feasible_hole_reports_true_margin() -> None:
    """A 12 mm dia x 17 mm deep bore vs a 6 mm dia / 30 mm stickout
    tool: infeasibility = max(6 - 12, 17 - 30) = -6 mm (dia governs)."""
    outcome = check_tool_fit((_hole("bore_b", 12.0, 17.0),), (_TOOL,))
    assert not outcome.indeterminate
    assert outcome.excess == pytest.approx(-6.0)


def test_tool_fit_hole_smaller_than_every_tool_violates() -> None:
    """A 4 mm hole vs the 6 mm tool: excess 6 - 4 = 2 mm -- the cutter
    cannot produce a feature smaller than itself."""
    outcome = check_tool_fit((_hole("pin", 4.0, 5.0),), (_TOOL,))
    assert outcome.violated
    assert outcome.excess == pytest.approx(2.0)
    assert "pin" in outcome.note


def test_tool_fit_hole_deeper_than_stickout_violates() -> None:
    """A 12 mm dia x 40 mm deep hole vs 30 mm stickout: excess
    40 - 30 = 10 mm (reach governs)."""
    outcome = check_tool_fit((_hole("deep", 12.0, 40.0),), (_TOOL,))
    assert outcome.violated
    assert outcome.excess == pytest.approx(10.0)


def test_tool_fit_best_tool_governs_per_hole() -> None:
    """With a second, smaller tool the 4 mm hole becomes feasible:
    exists-quantifier over tools, forall over holes."""
    small = _TOOL.model_copy(update={"tool_id": 2, "diameter_mm": 3.0})
    outcome = check_tool_fit(
        (_hole("pin", 4.0, 5.0), _hole("bore", 12.0, 17.0)), (_TOOL, small)
    )
    assert not outcome.violated
    # pin: min(max(6-4, 5-30), max(3-4, 5-30)) = -1; bore: -6 -> worst -1.
    assert outcome.excess == pytest.approx(-1.0)


def test_tool_fit_no_holes_is_vacuous_pass() -> None:
    outcome = check_tool_fit((), (_TOOL,))
    assert not outcome.indeterminate
    assert outcome.excess == 0.0


def test_tool_fit_no_tools_is_indeterminate() -> None:
    outcome = check_tool_fit((_hole("bore", 12.0, 17.0),), ())
    assert outcome.indeterminate


def test_tool_fit_unresolved_depth_is_indeterminate_naming_feature() -> None:
    outcome = check_tool_fit((_hole("blind", 12.0, None),), (_TOOL,))
    assert outcome.indeterminate
    assert "blind" in outcome.note


# --- model port/margin mapping -----------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> PayloadStore:
    return PayloadStore(str(tmp_path))


def _table_ref(store: PayloadStore, doc) -> PayloadRef:  # type: ignore[no-untyped-def]
    digest = store.put(doc.model_dump_json().encode())
    return PayloadRef(digest=digest, kind="table", origin=type(doc).__name__)


def _request(store: PayloadStore, part: DfmPart) -> DischargeRequest:
    model = ManufacturableModel()
    return DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={},
        payloads={
            "dfm_part": _table_ref(store, part),
            "dfm_machine": _table_ref(store, _MILL),
            "dfm_tools": _table_ref(store, DfmToolSet(tools=(_TOOL,))),
        },
        regimes=("mill",),
    )


def test_feasible_part_discharges(store: PayloadStore) -> None:
    """The idler-plate shape (90x50x20, one 12x17 bore) discharges with
    the true worst margin (-6 mm tool-dia term)."""
    part = _part(
        (_hole("bore_b", 12.0, 17.0),),
        Aabb(x_min=0, x_max=90, y_min=0, y_max=50, z_min=-20, z_max=0),
    )
    model = ManufacturableModel()
    result = model.discharge(
        _request(store, part), registry_version="test", resolver=store.resolve
    )
    assert result.is_ok
    evidence = result.danger_ok
    assert evidence.status.value == "discharged"
    assert bits_to_f64(evidence.value_bits) == pytest.approx(-6.0)


def test_oversize_part_violates(store: PayloadStore) -> None:
    """A 900 mm sheet on a 300 mm-travel machine is a genuine violation
    (the fleet Spoilboard finding's shape)."""
    part = _part(
        (_hole("insert", 7.9, 13.0),),
        Aabb(x_min=0, x_max=900, y_min=0, y_max=600, z_min=-18, z_max=0),
    )
    model = ManufacturableModel()
    result = model.discharge(
        _request(store, part), registry_version="test", resolver=store.resolve
    )
    assert result.is_ok
    evidence = result.danger_ok
    assert evidence.status.value == "violated"
    assert bits_to_f64(evidence.value_bits) == pytest.approx(600.0)


def test_missing_payload_port_abstains(store: PayloadStore) -> None:
    """A request lacking the tools port abstains (indeterminate), never
    a silent pass."""
    part = _part(
        (_hole("bore_b", 12.0, 17.0),),
        Aabb(x_min=0, x_max=90, y_min=0, y_max=50, z_min=-20, z_max=0),
    )
    model = ManufacturableModel()
    request = DischargeRequest(
        claim_kind=model.signature.claim_kind,
        limit=0.0,
        inputs={},
        payloads={
            "dfm_part": _table_ref(store, part),
            "dfm_machine": _table_ref(store, _MILL),
        },
        regimes=("mill",),
    )
    result = model.discharge(request, registry_version="test", resolver=store.resolve)
    # `Model.discharge` surfaces the gap as an error VALUE; the registry
    # maps it to `#abstained` indeterminate evidence (never a pass).
    assert result.is_err
    assert "dfm_tools" in result.danger_err.message
