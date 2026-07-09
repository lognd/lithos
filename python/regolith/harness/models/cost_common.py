"""The shared std.cost estimator core (WO-54 deliverable 5; toolchain/27
sec. 1.4-1.5, AD-29).

ONE home for the cost-inputs document the orchestrator stages into the
payload store (``regolith.orchestrator.costing`` assembles it; the
estimator models resolve it through the ordinary D96 ``resolver``
channel) and for the itemized-estimate arithmetic every estimator and
the orchestrator's estimate-payload producer share (NO DUPLICATION:
the model computes the verdict and the orchestrator persists the
auditable payload by calling the SAME functions).

Every priced number here comes from a record body carried in the doc
(AD-29: the compiler contains no prices, rates, or currencies beyond
unit machinery -- grep-provable; this module only multiplies and sums
what the records say).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import (
    EstimateLineItem,
    ItemizedEstimate,
    PriceBreak,
    PricingRecord,
    RateRecord,
    RecordRef,
    ScalarInterval,
    UnitCostRecord,
)
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The payload port + kind the cost-inputs doc rides (D96: the kind
# vocabulary is feldspar 09 sec. 4 VERBATIM -- the doc is a `table`).
COST_INPUTS_PORT = "cost_inputs"
COST_INPUTS_KIND = "table"

# The claim kind every std.cost estimator competes under (D94 kind
# competition: one kind, per-basis signatures pick the model).
CLAIM_KIND = "mfg.cost"


class RatedRecord(BaseModel):
    """One resolved rate record: its pin digest + typed body."""

    model_config = ConfigDict(frozen=True)

    key: str
    digest: str
    rate: RateRecord


class PricedRecord(BaseModel):
    """One resolved pricing record: its pin digest + typed body."""

    model_config = ConfigDict(frozen=True)

    key: str
    digest: str
    pricing: PricingRecord


class UnitCostEntry(BaseModel):
    """One resolved unit-cost record: its pin digest + typed body."""

    model_config = ConfigDict(frozen=True)

    key: str
    digest: str
    unit_cost: UnitCostRecord


class CostProfileInputs(BaseModel):
    """One profile's resolved estimator inputs (toolchain/27 sec. 1.2):
    the quantity basis + markup + currency knobs and every record its
    manifest refs selected, in declared source order."""

    model_config = ConfigDict(frozen=True)

    name: str
    quantity: float
    markup: float
    currency: str
    rates: tuple[RatedRecord, ...] = ()
    pricing: tuple[PricedRecord, ...] = ()
    unit_costs: tuple[UnitCostEntry, ...] = ()

    def pricing_for(self, item: str) -> PricedRecord | None:
        """The FIRST source-order pricing record for ``item`` (the
        profile's declared source order is the tie-break rule)."""
        for record in self.pricing:
            if record.pricing.item == item:
                return record
        return None


class BomLine(BaseModel):
    """One `parts:` BOM entry (the Rust lowering's `cost_bom.<part>`
    given line): the part name and its raw value text."""

    model_config = ConfigDict(frozen=True)

    part: str
    ref: str

    def item_key(self) -> str:
        """The priceable item key: `vendor(<key>)`'s inner key, else
        the value's leading bare token."""
        text = self.ref.strip()
        if text.startswith("vendor(") and text.endswith(")"):
            return text[len("vendor(") : -1].strip()
        return text.split()[0] if text.split() else text


class FrameMemberLine(BaseModel):
    """One frame member's takeoff basis (the landed `FramePayload`
    surface: id/role/length; section/material refs by name)."""

    model_config = ConfigDict(frozen=True)

    id: str
    role: str
    length: ScalarInterval
    section: str
    material: str


class FlownetEdgeLine(BaseModel):
    """One flownet edge's BOM basis: id, edge kind, and the component
    record name its curve/vendor binding carries (empty when none)."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    component: str


class CostInputsDoc(BaseModel):
    """The staged estimator-inputs document (one `table` payload per
    cost obligation): the selected profile set (one entry, or every
    swept D95 axis point) plus the subject's quantity bases."""

    model_config = ConfigDict(frozen=True)

    subject: str
    profiles: tuple[CostProfileInputs, ...]
    bom: tuple[BomLine, ...] = ()
    frame_members: tuple[FrameMemberLine, ...] = ()
    flownet_edges: tuple[FlownetEdgeLine, ...] = ()


class EstimateError(BaseModel):
    """An estimate that could not be formed at all (nothing priceable):
    the honest abstain surface the models map to an indeterminate."""

    model_config = ConfigDict(frozen=True)

    reason: str
    detail: str


def _interval(lo: float, hi: float, unit: str) -> ScalarInterval:
    """A `ScalarInterval` in construction order (lo, hi, unit)."""
    return ScalarInterval(lo=lo, hi=hi, unit=unit)


def price_break_at(pricing: PricingRecord, qty: float) -> PriceBreak | None:
    """The best (highest `min_qty <=` ``qty``) quantity break, or the
    first break when ``qty`` sits below every threshold (a real order
    still pays the smallest-quantity price, never no price)."""
    applicable = [b for b in pricing.breaks if b.min_qty <= qty]
    if applicable:
        return max(applicable, key=lambda b: b.min_qty)
    return pricing.breaks[0] if pricing.breaks else None


def _markup_line(
    profile: CostProfileInputs, subtotal_lo: float, subtotal_hi: float, unit: str
) -> EstimateLineItem | None:
    """The overhead-markup line (`markup` is the ONE v1 overhead knob,
    charter sec. 3): a named line so the itemized table stays a plain
    sum, referencing the manifest knob it came from (not a registry
    record -- the profile itself is diffable project data)."""
    if profile.markup == 1.0:
        return None
    factor = profile.markup - 1.0
    return EstimateLineItem(
        item="overhead_markup",
        qty=_interval(1.0, 1.0, "each"),
        unit_cost=_interval(subtotal_lo * factor, subtotal_hi * factor, unit),
        record=RecordRef(
            digest="manifest",
            name=f"magnetite.toml [profiles.cost.{profile.name}].markup",
        ),
        extended=_interval(subtotal_lo * factor, subtotal_hi * factor, unit),
    )


def _finish(
    profile: CostProfileInputs,
    lines: list[EstimateLineItem],
    exclusions: list[str],
) -> Result[ItemizedEstimate, EstimateError]:
    """Sum ``lines``, apply the markup line, and seal the estimate.

    An empty line set is an `Err(EstimateError)` -- an estimator that
    priced NOTHING must abstain (indeterminate), never emit a zero
    total that would discharge any upper bound."""
    if not lines:
        return Err(
            EstimateError(
                reason="nothing_priced",
                detail=(
                    f"profile {profile.name!r}: no line item could be priced "
                    f"from the profile's records (exclusions: {sorted(exclusions)})"
                ),
            )
        )
    unit = profile.currency
    for line in lines:
        if line.extended.unit != unit:
            _log.error(
                "currency mismatch profile=%s line=%s record=%s "
                "line_unit=%s profile_unit=%s",
                profile.name,
                line.item,
                line.record.name,
                line.extended.unit,
                unit,
            )
            return Err(
                EstimateError(
                    reason="currency_mismatch",
                    detail=(
                        f"profile {profile.name!r}: line {line.item!r} "
                        f"(record {line.record.name!r}) is priced in "
                        f"{line.extended.unit!r}, profile currency is "
                        f"{unit!r} -- refusing to sum mismatched currencies"
                    ),
                )
            )
    subtotal_lo = sum(line.extended.lo for line in lines)
    subtotal_hi = sum(line.extended.hi for line in lines)
    markup = _markup_line(profile, subtotal_lo, subtotal_hi, unit)
    if markup is not None:
        lines = [*lines, markup]
    total_lo = sum(line.extended.lo for line in lines)
    total_hi = sum(line.extended.hi for line in lines)
    estimate = ItemizedEstimate(
        profile=profile.name,
        lines=lines,
        total=_interval(total_lo, total_hi, unit),
        exclusions=sorted(set(exclusions)),
    )
    _log.debug(
        "estimate profile=%s lines=%d total=[%g, %g] %s exclusions=%d",
        profile.name,
        len(lines),
        total_lo,
        total_hi,
        unit,
        len(estimate.exclusions),
    )
    return Ok(estimate)


def bom_estimate(
    doc: CostInputsDoc, profile: CostProfileInputs
) -> Result[ItemizedEstimate, EstimateError]:
    """The elec BOM estimate (toolchain/27 sec. 1.4): each `parts:` BOM
    line x its first-source pricing record's quantity break at the
    profile's quantity basis. An unpriced line is a DECLARED exclusion;
    per-joint assembly and the fab table are declared exclusions until
    a joint-count/fab basis exists (WO-54 close-out ledger)."""
    lines: list[EstimateLineItem] = []
    exclusions: list[str] = []
    for bom_line in doc.bom:
        item = bom_line.item_key()
        record = profile.pricing_for(item)
        if record is None:
            exclusions.append(f"unpriced part {bom_line.part} ({item})")
            continue
        chosen = price_break_at(record.pricing, profile.quantity)
        if chosen is None:
            exclusions.append(f"unpriced part {bom_line.part} ({item}: no breaks)")
            continue
        unit = chosen.unit_price.unit
        lines.append(
            EstimateLineItem(
                item=item,
                qty=_interval(1.0, 1.0, "each"),
                unit_cost=chosen.unit_price,
                record=RecordRef(digest=record.digest, name=record.key),
                extended=_interval(chosen.unit_price.lo, chosen.unit_price.hi, unit),
            )
        )
    if any(r.rate.rate.unit.endswith("/joint") for r in profile.rates):
        exclusions.append("per-joint assembly (no joint count in the v1 BOM basis)")
    return _finish(profile, lines, exclusions)


def fluid_bom_estimate(
    doc: CostInputsDoc, profile: CostProfileInputs
) -> Result[ItemizedEstimate, EstimateError]:
    """The fluid BOM estimate (toolchain/27 sec. 1.4): each flownet
    edge whose curve/vendor binding names a component record, priced
    like a BOM line. Pipe/plenum runs without a component record are
    declared exclusions (no length-based pipe pricing in v1)."""
    lines: list[EstimateLineItem] = []
    exclusions: list[str] = []
    for edge in doc.flownet_edges:
        if not edge.component:
            exclusions.append(
                f"unpriced edge {edge.id} ({edge.kind}: no component record)"
            )
            continue
        record = profile.pricing_for(edge.component)
        if record is None:
            exclusions.append(f"unpriced edge {edge.id} ({edge.component})")
            continue
        chosen = price_break_at(record.pricing, profile.quantity)
        if chosen is None:
            exclusions.append(f"unpriced edge {edge.id} ({edge.component}: no breaks)")
            continue
        lines.append(
            EstimateLineItem(
                item=edge.component,
                qty=_interval(1.0, 1.0, "each"),
                unit_cost=chosen.unit_price,
                record=RecordRef(digest=record.digest, name=record.key),
                extended=_interval(
                    chosen.unit_price.lo, chosen.unit_price.hi, chosen.unit_price.unit
                ),
            )
        )
    return _finish(profile, lines, exclusions)


def civil_takeoff_estimate(
    doc: CostInputsDoc, profile: CostProfileInputs
) -> Result[ItemizedEstimate, EstimateError]:
    """The civil takeoff estimate (toolchain/27 sec. 1.4): member-length
    takeoff x the profile's first per-meter unit-cost record -- what the
    landed `FramePayload` surface (id/role/length + name-only section/
    material refs) actually supports. Supports, deck areas, and
    connections are declared exclusions (WO-54 close-out ledger)."""
    per_meter = next(
        (e for e in profile.unit_costs if e.unit_cost.unit_basis == "m"), None
    )
    lines: list[EstimateLineItem] = []
    exclusions: list[str] = []
    for member in doc.frame_members:
        if per_meter is None:
            exclusions.append(
                f"unpriced member {member.id} (no per-meter unit-cost record)"
            )
            continue
        uc = per_meter.unit_cost.unit_cost
        lines.append(
            EstimateLineItem(
                item=f"{member.id} ({per_meter.unit_cost.assembly})",
                qty=member.length,
                unit_cost=uc,
                record=RecordRef(digest=per_meter.digest, name=per_meter.key),
                extended=_interval(
                    member.length.lo * uc.lo, member.length.hi * uc.hi, profile.currency
                ),
            )
        )
    exclusions.extend(
        (
            "support foundations (no takeoff basis in the v1 frame surface)",
            "deck/assembly areas (no area takeoff in the v1 frame surface)",
            "connections and erection labor beyond the per-meter assembly rate",
        )
    )
    return _finish(profile, lines, exclusions)
