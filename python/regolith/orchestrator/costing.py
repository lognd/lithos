"""Cost-profile resolution: profile -> record set -> estimator inputs
(WO-54 deliverable 4; toolchain/27 sec. 1.2-1.3, AD-29).

This module owns the orchestrator half of the costing charter: loading
a project's ``[profiles.cost.<name>]`` tables, resolving every record
ref a selected profile names (rates by exact key; pricing/unit-cost
sources by key PREFIX, first source pricing an item wins), checking
``valid_until`` expiry, staging the estimator-inputs ``table`` payload
(one per cost obligation, resolved by the std.cost models through the
ordinary D96 channel), and recording every consumed record as an
INV-22 lockfile pin. The obligation-to-request lowering itself stays
in :mod:`regolith.orchestrator.translate` (which maps this module's
error values onto its own ``Deferral`` surface).

Clock note (the expiry rule's time source): the toolchain deliberately
has NO ambient build clock -- the mech realizer NORMALIZES wall-clock
export timestamps OUT of content-addressed artifacts (AD-6/INV-10),
and the only wall-clock use anywhere is the harness adapter's
``timeout_s`` infrastructure guard. Expiry follows the same line: the
build date enters at ONE seam (:func:`load_cost_context`'s ``as_of``,
defaulting to today's UTC date exactly there and nowhere else), and an
expired record produces a DEFERRAL -- which is never cached and never
content-addressed -- so wall-clock time still never enters any hashed
artifact. Callers that need reproducibility (tests, golden fixtures)
pass ``as_of`` explicitly.
"""

from __future__ import annotations

import datetime as _dt
import json
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError
from typani.result import Err, Ok, Result

from regolith._schema.models import (
    PayloadRef,
    PricingRecord,
    RateRecord,
    ScalarInterval,
    UnitCostRecord,
)
from regolith.errors import OrchestratorError
from regolith.harness import ModelRegistry
from regolith.harness.models.cost_common import (
    CLAIM_KIND,
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
)
from regolith.harness.models.cost_estimators import BOM_PORT, FLOWNET_PORT, FRAME_PORT
from regolith.logging_setup import get_logger
from regolith.magnetite.manifest import CostProfile, load_manifest
from regolith.magnetite.stdlib_records import row_hash
from regolith.orchestrator.payload_store import PayloadStore

_log = get_logger(__name__)

# The record TOML tables this loader consumes (`[[rate]]`,
# `[[pricing]]`, `[[unit_cost]]` rows -- the stdlib/std.cost shapes).
_RATE_TABLE = "rate"
_PRICING_TABLE = "pricing"
_UNIT_COST_TABLE = "unit_cost"


# frob:doc docs/modules/py-orchestrator.md#costing
class CostResolutionError(BaseModel):
    """A named cost-resolution failure the translate layer surfaces as
    an honest deferral (never an exception, never a silent skip)."""

    model_config = ConfigDict(frozen=True)

    reason: str
    detail: str


# frob:doc docs/modules/py-orchestrator.md#costing
class CostRecordSet(BaseModel):
    """Every loaded cost record, keyed for profile-ref resolution."""

    model_config = ConfigDict(frozen=True)

    rates: dict[str, RatedRecord] = {}
    pricing: dict[str, PricedRecord] = {}
    unit_costs: dict[str, UnitCostEntry] = {}


def _interval_from(value: object) -> ScalarInterval | None:
    """A `{lo, hi, unit}` TOML table as a `ScalarInterval`, else None."""
    if not isinstance(value, dict):
        return None
    try:
        return ScalarInterval.model_validate(value)
    except ValidationError:
        return None


# frob:waive PERF003 reason="O(1) check against a fixed small set, not nested"
def _load_record_file(
    path: Path, out_rates: dict, out_pricing: dict, out_unit_costs: dict
) -> Result[None, OrchestratorError]:
    """Load one records TOML file's cost tables into the three maps.

    A malformed row is a loud error naming the file and key; a table
    this loader does not own (occupancy, sections, ...) is skipped --
    other record families have their own consumers.
    """
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Err(
            OrchestratorError(kind="cost_records_malformed", message=f"{path}: {exc}")
        )
    for table, rows in data.items():
        if table not in (_RATE_TABLE, _PRICING_TABLE, _UNIT_COST_TABLE):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or "key" not in row:
                return Err(
                    OrchestratorError(
                        kind="cost_records_malformed",
                        message=f"{path}: a {table!r} row has no 'key'",
                    )
                )
            key = str(row["key"])
            digest = row_hash(table, row)
            try:
                if table == _RATE_TABLE:
                    body_rate = RateRecord(
                        name=str(row.get("name", key)),
                        rate=ScalarInterval.model_validate(row.get("rate")),
                        basis=str(row.get("basis", "")),
                    )
                    out_rates.setdefault(
                        key, RatedRecord(key=key, digest=digest, rate=body_rate)
                    )
                elif table == _PRICING_TABLE:
                    body_pricing = PricingRecord.model_validate(
                        {
                            "item": row.get("item", ""),
                            "breaks": row.get("breaks", []),
                            "valid_until": row.get("valid_until", ""),
                            "basis": row.get("basis", ""),
                        }
                    )
                    out_pricing.setdefault(
                        key, PricedRecord(key=key, digest=digest, pricing=body_pricing)
                    )
                else:
                    body_unit = UnitCostRecord.model_validate(
                        {
                            "assembly": row.get("assembly", key),
                            "unit_basis": row.get("unit_basis", ""),
                            "unit_cost": row.get("unit_cost"),
                            "basis": row.get("basis", ""),
                        }
                    )
                    out_unit_costs.setdefault(
                        key,
                        UnitCostEntry(key=key, digest=digest, unit_cost=body_unit),
                    )
            except ValidationError as exc:
                return Err(
                    OrchestratorError(
                        kind="cost_records_malformed",
                        message=f"{path}: {table}/{key}: {exc}",
                    )
                )
    return Ok(None)


# frob:doc docs/modules/py-orchestrator.md#costing
def load_cost_records(
    search_paths: tuple[str, ...],
) -> Result[CostRecordSet, OrchestratorError]:
    """Load every cost record under ``search_paths`` (local-path only,
    the WO-16/`resolve_dependencies` posture: no network, no registry
    fetch -- charter sec. 3's live-pricing non-goal).

    Each search path contributes its own ``records/*.toml`` plus every
    package subdirectory's (``<path>/<pkg>/records/*.toml``), in sorted
    order; the FIRST loaded row for a key wins deterministically (a
    duplicate is logged, never silently merged).
    """
    rates: dict[str, RatedRecord] = {}
    pricing: dict[str, PricedRecord] = {}
    unit_costs: dict[str, UnitCostEntry] = {}
    for base_str in search_paths:
        base = Path(base_str)
        candidates = [base / "records"]
        if base.is_dir():
            candidates.extend(
                sub / "records"
                for sub in sorted(base.iterdir())
                if sub.is_dir() and (sub / "magnetite.toml").is_file()
            )
        for records_dir in candidates:
            if not records_dir.is_dir():
                continue
            for toml_file in sorted(records_dir.glob("*.toml")):
                loaded = _load_record_file(toml_file, rates, pricing, unit_costs)
                if loaded.is_err:
                    return Err(loaded.danger_err)
    _log.debug(
        "loaded cost records: %d rate(s), %d pricing, %d unit-cost from %s",
        len(rates),
        len(pricing),
        len(unit_costs),
        list(search_paths),
    )
    return Ok(CostRecordSet(rates=rates, pricing=pricing, unit_costs=unit_costs))


# frob:doc docs/modules/py-orchestrator.md#costing
class CostContext:
    """One build's cost-resolution state: profiles, records, the clock
    date, the staging store handle, and the consumed-record pin ledger
    (INV-22). Mutable on purpose -- ``consumed_pins`` accumulates as
    obligations stage; everything else is fixed at load."""

    def __init__(
        self,
        *,
        profiles: dict[str, CostProfile],
        default_profile: str | None,
        cli_profile: str | None,
        records: CostRecordSet,
        as_of: _dt.date,
        store: PayloadStore | None,
        frames: dict[str, dict],
        flownets: dict[str, dict],
    ) -> None:
        """Bind one build's fixed cost inputs (see the class docstring)."""
        self.profiles = profiles
        self.default_profile = default_profile
        self.cli_profile = cli_profile
        self.records = records
        self.as_of = as_of
        self.store = store
        self.frames = frames
        self.flownets = flownets
        # Record key -> row digest, for the lockfile's `pin` lines.
        self.consumed_pins: dict[str, str] = {}
        # Subject -> staged doc digest (observability + the estimate
        # producer's re-resolution seam).
        self.staged_docs: dict[str, str] = {}

    @property
    # frob:doc docs/modules/py-orchestrator.md#costing
    def build_profile(self) -> str | None:
        """The build-level profile pick: `--profile` beats the manifest
        default (claims may still override per-claim, charter sec. 1.2)."""
        return self.cli_profile or self.default_profile


# frob:doc docs/modules/py-orchestrator.md#costing
def load_cost_context(
    project_root: str,
    *,
    payload_store: PayloadStore | None,
    build_payload: dict[str, object] | None = None,
    cli_profile: str | None = None,
    record_search_paths: tuple[str, ...] = (),
    as_of: _dt.date | None = None,
) -> Result[CostContext | None, OrchestratorError]:
    """Load the build's cost context, or ``Ok(None)`` when the project
    declares no cost profiles (cost claims then defer honestly, naming
    the missing configuration -- never an error for a costless build).

    ``record_search_paths`` extends the default (the project root
    itself) with additional local package roots (e.g. the in-repo
    ``stdlib/`` -- the `resolve_dependencies` local-path posture).
    ``as_of`` is the ONE clock seam (module docstring); ``None`` reads
    today's UTC date here and nowhere else. An unknown ``cli_profile``
    is a loud error -- a mistyped ``--profile`` must never silently
    fall back to the default.
    """
    manifest_result = load_manifest(project_root)
    if manifest_result.is_err:
        _log.info(
            "costing: no manifest at %s (%s); cost claims will defer",
            project_root,
            manifest_result.danger_err.kind,
        )
        return Ok(None)
    manifest = manifest_result.danger_ok
    if not manifest.cost_profiles:
        _log.info(
            "costing: %s declares no [profiles.cost.*]; cost claims will defer",
            manifest.name,
        )
        return Ok(None)

    profiles = {p.name: p for p in manifest.cost_profiles}
    if cli_profile is not None and cli_profile not in profiles:
        return Err(
            OrchestratorError(
                kind="unknown_cost_profile",
                message=(
                    f"--profile {cli_profile!r} names no declared cost profile "
                    f"(declared: {sorted(profiles)})"
                ),
            )
        )

    records_result = load_cost_records((project_root, *record_search_paths))
    if records_result.is_err:
        return Err(records_result.danger_err)

    frames_raw = (build_payload or {}).get("frames", {})
    flownets_raw = (build_payload or {}).get("flownets", {})
    frames = (
        {str(k): v for k, v in frames_raw.items() if isinstance(v, dict)}
        if isinstance(frames_raw, dict)
        else {}
    )
    flownets = (
        {str(k): v for k, v in flownets_raw.items() if isinstance(v, dict)}
        if isinstance(flownets_raw, dict)
        else {}
    )
    resolved_as_of = as_of if as_of is not None else _dt.datetime.now(_dt.UTC).date()
    context = CostContext(
        profiles=profiles,
        default_profile=manifest.default_cost_profile,
        cli_profile=cli_profile,
        records=records_result.danger_ok,
        as_of=resolved_as_of,
        store=payload_store,
        frames=frames,
        flownets=flownets,
    )
    _log.info(
        "costing: context loaded (profiles=%s, default=%s, cli=%s, as_of=%s)",
        sorted(profiles),
        manifest.default_cost_profile,
        cli_profile,
        resolved_as_of,
    )
    return Ok(context)


# frob:doc docs/modules/py-orchestrator.md#costing
def parse_profile_sweep(domain: str) -> tuple[str, ...] | None:
    """The profile names of a D95 discrete sweep domain (`{a, b}`), or
    ``None`` when the domain text is not a braced discrete set."""
    text = domain.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return None
    names = tuple(n.strip() for n in text[1:-1].split(",") if n.strip())
    return names or None


def _expiry_of(record: PricedRecord) -> _dt.date | None:
    """The record's parsed `valid_until` date; ``None`` when malformed
    (the caller treats an unparseable window as expired -- honest,
    never silently perpetual)."""
    try:
        return _dt.date.fromisoformat(record.pricing.valid_until)
    except ValueError:
        return None


# frob:doc docs/modules/py-orchestrator.md#costing
def resolve_profile_inputs(
    context: CostContext, profile: CostProfile
) -> Result[CostProfileInputs, CostResolutionError]:
    """Resolve one profile's record refs into estimator inputs.

    Rates resolve by EXACT key; pricing/unit-cost sources by key
    PREFIX (`<source>.<item>`), profile source order preserved. A ref
    that resolves to NOTHING and an EXPIRED pricing record (charter
    sec. 1.3: `valid_until` before the build's `as_of` date) are named
    resolution errors -- the translate layer surfaces both as honest
    deferrals, waivable through the ordinary ladder with basis.

    Every record actually selected lands in ``context.consumed_pins``
    (INV-22: the lockfile pins every consumed record).
    """
    rates: list[RatedRecord] = []
    for ref in (*profile.labor, *profile.process_rates):
        record = context.records.rates.get(ref)
        if record is None:
            return Err(
                CostResolutionError(
                    reason="cost_record_unresolved",
                    detail=(
                        f"profile {profile.name!r} names rate record {ref!r}, "
                        "which no record search path provides"
                    ),
                )
            )
        rates.append(record)

    pricing: list[PricedRecord] = []
    unit_costs: list[UnitCostEntry] = []
    for source in profile.pricing:
        prefix = source + "."
        matched_pricing = [
            context.records.pricing[k]
            for k in sorted(context.records.pricing)
            if k.startswith(prefix)
        ]
        matched_unit_costs = [
            context.records.unit_costs[k]
            for k in sorted(context.records.unit_costs)
            if k.startswith(prefix)
        ]
        if not matched_pricing and not matched_unit_costs:
            return Err(
                CostResolutionError(
                    reason="cost_record_unresolved",
                    detail=(
                        f"profile {profile.name!r} names pricing source "
                        f"{source!r}, which no record search path provides"
                    ),
                )
            )
        pricing.extend(matched_pricing)
        unit_costs.extend(matched_unit_costs)

    expired = [
        record
        for record in pricing
        if (expiry := _expiry_of(record)) is None or expiry < context.as_of
    ]
    if expired:
        first = expired[0]
        return Err(
            CostResolutionError(
                reason="pricing_record_expired",
                detail=(
                    f"pricing record {first.key!r} expired "
                    f"{first.pricing.valid_until!r} (build date "
                    f"{context.as_of.isoformat()}; {len(expired)} expired "
                    "record(s) total); refresh the record or waive with basis"
                ),
            )
        )

    for record in rates:
        context.consumed_pins[record.key] = record.digest
    for priced in pricing:
        context.consumed_pins[priced.key] = priced.digest
    for entry in unit_costs:
        context.consumed_pins[entry.key] = entry.digest
    _log.debug(
        "costing: profile %s resolved (%d rate(s), %d pricing, %d unit-cost)",
        profile.name,
        len(rates),
        len(pricing),
        len(unit_costs),
    )
    return Ok(
        CostProfileInputs(
            name=profile.name,
            quantity=profile.quantity,
            markup=profile.markup,
            currency=profile.currency,
            rates=tuple(rates),
            pricing=tuple(pricing),
            unit_costs=tuple(unit_costs),
        )
    )


def _frame_member_lines(frame: dict) -> tuple[FrameMemberLine, ...]:
    """The takeoff lines of one raw `FramePayload` dict (source order)."""
    lines: list[FrameMemberLine] = []
    for member in frame.get("members", []) or []:
        length = _interval_from(member.get("length"))
        if length is None:
            continue
        section = member.get("section") or {}
        material = member.get("material") or {}
        lines.append(
            FrameMemberLine(
                id=str(member.get("id", "")),
                role=str(member.get("role", "")),
                length=length,
                section=str(section.get("name", "")),
                material=str(material.get("name", "")),
            )
        )
    return tuple(lines)


def _flownet_edge_lines(flownet: dict) -> tuple[FlownetEdgeLine, ...]:
    """The BOM lines of one raw `FlownetPayload` dict (source order):
    each edge's kind plus its first curve record name (the component
    binding), empty when the edge carries no component record."""
    lines: list[FlownetEdgeLine] = []
    for edge in flownet.get("edges", []) or []:
        curves = edge.get("curves") or []
        component = str(curves[0].get("name", "")) if curves else ""
        lines.append(
            FlownetEdgeLine(
                id=str(edge.get("id", "")),
                kind=str(edge.get("kind", "")),
                component=component,
            )
        )
    return tuple(lines)


# frob:doc docs/modules/py-orchestrator.md#costing
def assemble_inputs_doc(
    context: CostContext,
    subject: str,
    profiles: tuple[CostProfileInputs, ...],
    bom: tuple[BomLine, ...],
) -> CostInputsDoc:
    """Assemble one obligation's estimator-inputs doc: the resolved
    profiles plus every quantity basis the SUBJECT matches (`all`
    matches every frame/flownet in the build; a name matches its own).
    """
    frame_members: list[FrameMemberLine] = []
    for name in sorted(context.frames):
        if subject in ("all", name):
            frame = context.frames[name]
            if isinstance(frame, dict):
                frame_members.extend(_frame_member_lines(frame))
    flownet_edges: list[FlownetEdgeLine] = []
    for name in sorted(context.flownets):
        if subject in ("all", name):
            flownet = context.flownets[name]
            if isinstance(flownet, dict):
                flownet_edges.extend(_flownet_edge_lines(flownet))
    return CostInputsDoc(
        subject=subject,
        profiles=profiles,
        bom=bom,
        frame_members=tuple(frame_members),
        flownet_edges=tuple(flownet_edges),
    )


# frob:doc docs/modules/py-orchestrator.md#costing
# frob:waive TEST001 reason="costing helper, tested transitively via costing tests"
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def stage_inputs_doc(
    context: CostContext, doc: CostInputsDoc
) -> Result[tuple[dict[str, PayloadRef], str], CostResolutionError]:
    """Stage ``doc`` into the payload store; return the request's
    payload-port map plus the settings digest (INV-10: the doc digest
    folds every record body/pin and quantity basis into the evidence
    hash through the request's ``settings_digest``).

    The port map carries `cost_inputs` plus one marker port per
    non-empty quantity basis (`cost_bom`/`cost_frame`/`cost_flownet`,
    all the same digest) so estimator signatures match honestly.
    """
    if context.store is None:
        return Err(
            CostResolutionError(
                reason="cost_payload_store_missing",
                detail="no payload store is configured for this build",
            )
        )
    data = doc.model_dump_json().encode("utf-8")
    digest = context.store.put(data)
    context.staged_docs[doc.subject] = digest
    ports: dict[str, PayloadRef] = {
        COST_INPUTS_PORT: PayloadRef(
            kind=COST_INPUTS_KIND, digest=digest, origin=doc.subject
        )
    }
    for port, populated in (
        (BOM_PORT, bool(doc.bom)),
        (FRAME_PORT, bool(doc.frame_members)),
        (FLOWNET_PORT, bool(doc.flownet_edges)),
    ):
        if populated:
            ports[port] = PayloadRef(
                kind=COST_INPUTS_KIND, digest=digest, origin=doc.subject
            )
    settings_digest = json.dumps(
        {"cost_inputs": digest}, sort_keys=True, separators=(",", ":")
    )
    _log.debug(
        "costing: staged inputs doc subject=%s digest=%s ports=%s",
        doc.subject,
        digest,
        sorted(ports),
    )
    return Ok((ports, settings_digest))


# frob:doc docs/modules/py-orchestrator.md#costing
def record_pins(context: CostContext) -> tuple[tuple[str, str], ...]:
    """The INV-22 lockfile pins for every consumed record, sorted:
    ``(<key>@1, <row digest>)`` -- revision 1 is the stdlib loader's
    fixed starter revision (`magnetite.stdlib_records`)."""
    return tuple(
        (f"{key}@1", digest) for key, digest in sorted(context.consumed_pins.items())
    )


# M6 (cycle-28): a fixed frame>bom>flownet cascade duplicated the
# registry's (cost, model_id) pick order by hand -- correct only as
# long as the three built-in model ids kept sorting that way. Instead
# of maintaining a second copy of the pick order, ask the registry
# itself (D94 kind competition, `ModelRegistry.candidates`) which
# `mfg.cost` model would be selected for the SAME payload ports
# `stage_inputs_doc` publishes for this doc, and use that model's own
# basis (`_CostEstimatorModel.basis_port`) to pick the estimator
# function -- so the persisted estimate is provably the one the
# discharging model would have computed, not just coincidentally so.
_BASIS_ESTIMATORS: dict[str, object] = {}


def _basis_estimators():  # type: ignore[no-untyped-def]
    """Lazily built basis-port -> estimate-function map (avoids the
    `cost_estimators` <-> `cost_common` import at module load time)."""
    if not _BASIS_ESTIMATORS:
        from regolith.harness.models.cost_common import (
            bom_estimate,
            civil_takeoff_estimate,
            fluid_bom_estimate,
        )
        from regolith.harness.models.cost_estimators import (
            BOM_PORT,
            FLOWNET_PORT,
            FRAME_PORT,
        )

        _BASIS_ESTIMATORS[BOM_PORT] = bom_estimate
        _BASIS_ESTIMATORS[FRAME_PORT] = civil_takeoff_estimate
        _BASIS_ESTIMATORS[FLOWNET_PORT] = fluid_bom_estimate
    return _BASIS_ESTIMATORS


def _estimate_fn_for(doc: CostInputsDoc, registry: ModelRegistry):  # type: ignore[no-untyped-def]
    """The estimate function the registry would select for ``doc``'s
    populated bases, or ``None`` if no basis is populated at all."""
    available_payloads = {COST_INPUTS_PORT: COST_INPUTS_KIND}
    for port, populated in (
        (FRAME_PORT, bool(doc.frame_members)),
        (BOM_PORT, bool(doc.bom)),
        (FLOWNET_PORT, bool(doc.flownet_edges)),
    ):
        if populated:
            available_payloads[port] = COST_INPUTS_KIND
    if len(available_payloads) == 1:  # only COST_INPUTS_PORT: no basis at all
        return None
    for model in registry.candidates(CLAIM_KIND):
        basis_port = getattr(model, "basis_port", None)
        if basis_port is None:
            continue
        if model.signature.accepts_payloads(available_payloads):
            estimate_fn = _basis_estimators().get(basis_port)
            if estimate_fn is not None:
                return estimate_fn
    return None


# frob:doc docs/modules/py-orchestrator.md#costing
# frob:waive TEST001 reason="costing helper, tested transitively via costing tests"
def persist_estimates(
    context: CostContext, registry: ModelRegistry
) -> tuple[tuple[str, str], ...]:
    """Persist one itemized estimate per staged doc x profile into the
    payload store (toolchain/27 sec. 1.5: the auditable, diffable
    `table` evidence payload), returning sorted
    ``("<subject>/<profile>", <digest>)`` pairs.

    ``registry`` is the SAME registry the build discharged obligations
    against (M6 cycle-28): the estimator is picked by asking it which
    `mfg.cost` model would be selected for this doc's payload ports,
    not by a second, hand-maintained priority cascade that could drift
    from the registry's own (cost, model_id) order.

    Digesting: `PayloadStore.put` (fresh blake3 of the JSON bytes) --
    the WO-42 `put_realized_geometry` precedent for Python-produced
    payloads with no Rust-computed AD-18 digest to reproduce. A doc
    whose estimator abstained (nothing priced) is logged and skipped:
    its obligation already surfaced the honest indeterminate.
    """
    if context.store is None:
        return ()
    out: list[tuple[str, str]] = []
    for subject in sorted(context.staged_docs):
        digest = context.staged_docs[subject]
        resolved = context.store.resolve(digest)
        if resolved.is_err:  # pragma: no cover -- we just staged it
            _log.warning(
                "costing: staged doc %s for %s vanished from the store",
                digest,
                subject,
            )
            continue
        doc = CostInputsDoc.model_validate_json(resolved.danger_ok)
        estimate_fn = _estimate_fn_for(doc, registry)
        if estimate_fn is None:
            _log.info(
                "costing: subject %s has no quantity basis; no estimate persisted",
                subject,
            )
            continue
        for profile in doc.profiles:
            estimated = estimate_fn(doc, profile)
            if estimated.is_err:
                _log.info(
                    "costing: estimator abstained for %s/%s (%s)",
                    subject,
                    profile.name,
                    estimated.danger_err.reason,
                )
                continue
            data = estimated.danger_ok.model_dump_json().encode("utf-8")
            est_digest = context.store.put(data)
            out.append((f"{subject}/{profile.name}", est_digest))
            _log.debug(
                "costing: persisted estimate %s/%s -> %s",
                subject,
                profile.name,
                est_digest,
            )
    return tuple(out)
