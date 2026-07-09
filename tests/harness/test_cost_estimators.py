"""WO-54 deliverable 5: the std.cost reference estimators -- BOM/fluid/
civil pricing arithmetic, quantity breaks, markup, declared exclusions,
the D95 per-profile sweep coverage, and per-basis registry selection."""

from __future__ import annotations

from pathlib import Path

from regolith._schema.models import (
    PayloadRef,
    PricingRecord,
    RateRecord,
    ScalarInterval,
    UnitCostRecord,
)
from regolith.harness import DischargeRequest, default_registry
from regolith.harness.models.cost_common import (
    COST_INPUTS_KIND,
    COST_INPUTS_PORT,
    BomLine,
    CostInputsDoc,
    CostProfileInputs,
    FlownetEdgeLine,
    FrameMemberLine,
    PricedRecord,
    RatedRecord,
    UnitCostEntry,
    bom_estimate,
    civil_takeoff_estimate,
    fluid_bom_estimate,
    price_break_at,
)
from regolith.harness.models.cost_estimators import (
    BOM_PORT,
    FLOWNET_PORT,
    FRAME_PORT,
    CostElecBomModel,
)
from regolith.orchestrator.payload_store import PayloadStore


def _iv(lo: float, hi: float, unit: str) -> ScalarInterval:
    return ScalarInterval(lo=lo, hi=hi, unit=unit)


def _pricing(
    key: str, item: str, breaks: list[tuple[float, float, float]]
) -> PricedRecord:
    return PricedRecord(
        key=key,
        digest=f"sha256:{key}",
        pricing=PricingRecord(
            item=item,
            breaks=[
                {"min_qty": q, "unit_price": _iv(lo, hi, "USD")} for q, lo, hi in breaks
            ],
            valid_until="2027-01-01",
            basis="fixture",
        ),
    )


def _profile(name: str = "proto", quantity: float = 1.0, markup: float = 1.0, **kwargs):  # type: ignore[no-untyped-def]
    return CostProfileInputs(
        name=name, quantity=quantity, markup=markup, currency="USD", **kwargs
    )


_WIDGET = _pricing("src.widget", "widget", [(1.0, 10.0, 12.0), (50.0, 8.0, 9.0)])


# --- pricing arithmetic ------------------------------------------------------


def test_price_break_selection() -> None:
    record = _WIDGET.pricing
    assert price_break_at(record, 1.0) is not None
    assert price_break_at(record, 1.0).min_qty == 1.0  # type: ignore[union-attr]
    assert price_break_at(record, 100.0).min_qty == 50.0  # type: ignore[union-attr]
    # Below every threshold: the smallest-quantity price still applies.
    assert price_break_at(record, 0.5).min_qty == 1.0  # type: ignore[union-attr]


def test_bom_estimate_prices_lines_and_declares_exclusions() -> None:
    doc = CostInputsDoc(
        subject="board",
        profiles=(),
        bom=(
            BomLine(part="w", ref="vendor(widget)"),
            BomLine(part="ghost", ref="vendor(unobtainium)"),
        ),
    )
    profile = _profile(pricing=(_WIDGET,))
    result = bom_estimate(doc, profile)
    assert result.is_ok, result
    estimate = result.danger_ok
    assert len(estimate.lines) == 1
    assert estimate.lines[0].item == "widget"
    assert estimate.total.lo == 10.0
    assert estimate.total.hi == 12.0
    assert any("unobtainium" in x for x in estimate.exclusions)


def test_bom_estimate_applies_quantity_break_and_markup() -> None:
    doc = CostInputsDoc(
        subject="board",
        profiles=(),
        bom=(BomLine(part="w", ref="vendor(widget)"),),
    )
    profile = _profile(quantity=100.0, markup=1.5, pricing=(_WIDGET,))
    result = bom_estimate(doc, profile)
    assert result.is_ok
    estimate = result.danger_ok
    # 100-off break (8..9 USD) with a 1.5x markup line appended.
    assert estimate.lines[-1].item == "overhead_markup"
    assert estimate.total.lo == 8.0 * 1.5
    assert estimate.total.hi == 9.0 * 1.5


def test_bom_estimate_with_nothing_priced_abstains() -> None:
    doc = CostInputsDoc(
        subject="board",
        profiles=(),
        bom=(BomLine(part="ghost", ref="vendor(unobtainium)"),),
    )
    result = bom_estimate(doc, _profile(pricing=(_WIDGET,)))
    assert result.is_err
    assert result.danger_err.reason == "nothing_priced"


def test_bom_estimate_rejects_line_currency_mismatched_with_profile() -> None:
    eur_widget = PricedRecord(
        key="src.eur_widget",
        digest="sha256:eur_widget",
        pricing=PricingRecord(
            item="widget",
            breaks=[{"min_qty": 1.0, "unit_price": _iv(10.0, 12.0, "EUR")}],
            valid_until="2027-01-01",
            basis="fixture",
        ),
    )
    doc = CostInputsDoc(
        subject="board",
        profiles=(),
        bom=(BomLine(part="w", ref="vendor(widget)"),),
    )
    profile = _profile(pricing=(eur_widget,))  # profile currency defaults to USD
    result = bom_estimate(doc, profile)
    assert result.is_err, result
    assert result.danger_err.reason == "currency_mismatch"
    assert "EUR" in result.danger_err.detail
    assert "USD" in result.danger_err.detail


def test_per_joint_rate_is_a_declared_exclusion() -> None:
    doc = CostInputsDoc(
        subject="board", profiles=(), bom=(BomLine(part="w", ref="vendor(widget)"),)
    )
    profile = _profile(
        pricing=(_WIDGET,),
        rates=(
            RatedRecord(
                key="rates.smt",
                digest="sha256:smt",
                rate=RateRecord(
                    name="smt", rate=_iv(0.04, 0.05, "USD/joint"), basis="fixture"
                ),
            ),
        ),
    )
    result = bom_estimate(doc, profile)
    assert result.is_ok
    assert any("per-joint assembly" in x for x in result.danger_ok.exclusions)


def test_fluid_bom_prices_component_edges_only() -> None:
    doc = CostInputsDoc(
        subject="loop",
        profiles=(),
        flownet_edges=(
            FlownetEdgeLine(id="pump", kind="pump", component="widget"),
            FlownetEdgeLine(id="supply", kind="pipe", component=""),
        ),
    )
    result = fluid_bom_estimate(doc, _profile(pricing=(_WIDGET,)))
    assert result.is_ok
    estimate = result.danger_ok
    assert len(estimate.lines) == 1
    assert any("supply" in x for x in estimate.exclusions)


def test_civil_takeoff_prices_member_lengths() -> None:
    per_meter = UnitCostEntry(
        key="src.wall_m",
        digest="sha256:wall",
        unit_cost=UnitCostRecord(
            assembly="wall_m",
            unit_basis="m",
            unit_cost=_iv(100.0, 120.0, "USD/m"),
            basis="fixture",
        ),
    )
    doc = CostInputsDoc(
        subject="frame",
        profiles=(),
        frame_members=(
            FrameMemberLine(
                id="B1",
                role="beam",
                length=_iv(3.0, 3.0, "m"),
                section="s",
                material="m",
            ),
            FrameMemberLine(
                id="C1",
                role="column",
                length=_iv(4.0, 4.0, "m"),
                section="s",
                material="m",
            ),
        ),
    )
    result = civil_takeoff_estimate(doc, _profile(unit_costs=(per_meter,)))
    assert result.is_ok
    estimate = result.danger_ok
    assert estimate.total.lo == 7.0 * 100.0
    assert estimate.total.hi == 7.0 * 120.0
    assert any("support foundations" in x for x in estimate.exclusions)


def test_civil_takeoff_normalizes_mm_authored_member_length() -> None:
    """H1/M1 regression: a member authored in mm must not be treated
    as metres (1000x over-cost)."""
    per_meter = UnitCostEntry(
        key="src.wall_m",
        digest="sha256:wall",
        unit_cost=UnitCostRecord(
            assembly="wall_m",
            unit_basis="m",
            unit_cost=_iv(100.0, 120.0, "USD/m"),
            basis="fixture",
        ),
    )
    doc = CostInputsDoc(
        subject="frame",
        profiles=(),
        frame_members=(
            FrameMemberLine(
                id="B1",
                role="beam",
                length=_iv(8000.0, 8000.0, "mm"),
                section="s",
                material="m",
            ),
        ),
    )
    result = civil_takeoff_estimate(doc, _profile(unit_costs=(per_meter,)))
    assert result.is_ok, result
    estimate = result.danger_ok
    assert estimate.total.lo == 8.0 * 100.0
    assert estimate.total.hi == 8.0 * 120.0


def test_civil_takeoff_excludes_member_with_unrecognized_length_unit() -> None:
    per_meter = UnitCostEntry(
        key="src.wall_m",
        digest="sha256:wall",
        unit_cost=UnitCostRecord(
            assembly="wall_m",
            unit_basis="m",
            unit_cost=_iv(100.0, 120.0, "USD/m"),
            basis="fixture",
        ),
    )
    doc = CostInputsDoc(
        subject="frame",
        profiles=(),
        frame_members=(
            FrameMemberLine(
                id="B1",
                role="beam",
                length=_iv(3.0, 3.0, "ft"),
                section="s",
                material="m",
            ),
        ),
    )
    result = civil_takeoff_estimate(doc, _profile(unit_costs=(per_meter,)))
    assert result.is_err, result
    assert result.danger_err.reason == "nothing_priced"


def test_civil_takeoff_rejects_line_currency_mismatched_with_profile() -> None:
    """H1 regression: a per-meter record priced in EUR must not
    silently discharge a USD profile's obligation."""
    per_meter = UnitCostEntry(
        key="src.wall_m_eur",
        digest="sha256:wall_eur",
        unit_cost=UnitCostRecord(
            assembly="wall_m",
            unit_basis="m",
            unit_cost=_iv(100.0, 120.0, "EUR/m"),
            basis="fixture",
        ),
    )
    doc = CostInputsDoc(
        subject="frame",
        profiles=(),
        frame_members=(
            FrameMemberLine(
                id="B1",
                role="beam",
                length=_iv(3.0, 3.0, "m"),
                section="s",
                material="m",
            ),
        ),
    )
    result = civil_takeoff_estimate(doc, _profile(unit_costs=(per_meter,)))
    assert result.is_err, result
    assert result.danger_err.reason == "currency_mismatch"
    assert "EUR" in result.danger_err.detail
    assert "USD" in result.danger_err.detail


# --- the model spine ---------------------------------------------------------


def _staged_request(tmp_path: Path, doc: CostInputsDoc, ports: tuple[str, ...]):  # type: ignore[no-untyped-def]
    store = PayloadStore(str(tmp_path))
    digest = store.put(doc.model_dump_json().encode("utf-8"))
    payloads = {
        port: PayloadRef(kind=COST_INPUTS_KIND, digest=digest, origin=doc.subject)
        for port in (COST_INPUTS_PORT, *ports)
    }
    request = DischargeRequest(
        claim_kind="mfg.cost", limit=100.0, inputs={}, payloads=payloads
    )
    return request, store.resolver()


def test_model_predicts_worst_profile_with_sweep_coverage(tmp_path: Path) -> None:
    doc = CostInputsDoc(
        subject="board",
        profiles=(
            _profile(name="prototype", pricing=(_WIDGET,)),
            _profile(name="production", quantity=100.0, markup=1.5, pricing=(_WIDGET,)),
        ),
        bom=(BomLine(part="w", ref="vendor(widget)"),),
    )
    request, resolver = _staged_request(tmp_path, doc, (BOM_PORT,))
    result = CostElecBomModel().estimate(request, resolver=resolver)
    assert result.is_ok, result
    prediction = result.danger_ok
    # prototype: 12.0 hi; production: 9.0 * 1.5 = 13.5 hi -- the worst wins.
    assert prediction.value == 13.5
    assert prediction.coverage == 1.0
    assert len(prediction.coverage_axes) == 1
    axis = prediction.coverage_axes[0]
    assert axis.axis == "profile"


def test_model_without_resolver_abstains(tmp_path: Path) -> None:
    doc = CostInputsDoc(
        subject="board",
        profiles=(_profile(pricing=(_WIDGET,)),),
        bom=(BomLine(part="w", ref="vendor(widget)"),),
    )
    request, _resolver = _staged_request(tmp_path, doc, (BOM_PORT,))
    result = CostElecBomModel().estimate(request, resolver=None)
    assert result.is_err


# --- registry selection ------------------------------------------------------


def test_registry_selects_by_basis_port(tmp_path: Path) -> None:
    registry = default_registry()
    doc = CostInputsDoc(
        subject="board",
        profiles=(_profile(pricing=(_WIDGET,)),),
        bom=(BomLine(part="w", ref="vendor(widget)"),),
    )
    bom_request, _ = _staged_request(tmp_path, doc, (BOM_PORT,))
    selected = registry.select(bom_request)
    assert selected.is_ok
    assert selected.danger_ok.signature.name == "cost_elec_bom"

    frame_request, _ = _staged_request(tmp_path, doc, (FRAME_PORT, FLOWNET_PORT))
    selected = registry.select(frame_request)
    assert selected.is_ok
    # Cost tie -> model-id order: the civil takeoff wins deterministically.
    assert selected.danger_ok.signature.name == "cost_civil_takeoff"


def test_no_basis_means_no_model_the_honest_gap(tmp_path: Path) -> None:
    registry = default_registry()
    doc = CostInputsDoc(subject="board", profiles=(_profile(pricing=(_WIDGET,)),))
    request, _ = _staged_request(tmp_path, doc, ())
    selected = registry.select(request)
    assert selected.is_err  # no estimator matches: the no-model indeterminate
    assert "mfg.cost" in selected.danger_err.claim_kind
