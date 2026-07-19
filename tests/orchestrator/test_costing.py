"""WO-54 deliverable 4: cost-profile resolution (profile -> record set
-> estimator inputs), the expired-pricing and missing-record honest
deferrals, the D95 profile-sweep translation, and the INV-22 consumed-
record pin ledger."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from regolith._schema.models import (
    Claim,
    ClaimForm1,
    Form,
    Given,
    Obligation,
    SweepDomain,
)
from regolith.harness import ModelRegistry
from regolith.harness.models.cost_common import (
    COST_INPUTS_PORT,
    CostInputsDoc,
    FrameMemberLine,
    ScalarInterval,
    bom_estimate,
    civil_takeoff_estimate,
)
from regolith.harness.models.cost_estimators import (
    BOM_PORT,
    CostCivilTakeoffModel,
    CostElecBomModel,
)
from regolith.orchestrator.costing import (
    CostContext,
    _estimate_fn_for,
    load_cost_context,
    load_cost_records,
    parse_profile_sweep,
    record_pins,
    resolve_profile_inputs,
)
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.translate import translate

_AS_OF = dt.date(2026, 7, 9)

_MANIFEST = """\
[package]
name = "costed"
version = "0.1.0"

[profiles.cost.prototype]
quantity = 1
labor    = "rates.bench_2026"
pricing  = ["acme.catalog_2026"]
markup   = 1.0

[profiles.cost.production]
quantity = 100
labor    = "rates.bench_2026"
pricing  = ["acme.catalog_2026"]
markup   = 1.1

[profiles.cost.stale]
quantity = 1
pricing  = ["old.quote_2025"]

[profiles.cost.default]
profile = "prototype"
"""

_RECORDS = """\
[[rate]]
key = "rates.bench_2026"
name = "bench_labor"
rate = { lo = 50.0, hi = 60.0, unit = "USD/hr" }
basis = "test fixture"
evidence = { method = "catalog", trust_tier = "community", reference = "fixture" }

[[pricing]]
key = "acme.catalog_2026.widget"
item = "widget"
breaks = [
    { min_qty = 1.0, unit_price = { lo = 10.0, hi = 12.0, unit = "USD" } },
    { min_qty = 50.0, unit_price = { lo = 8.0, hi = 9.0, unit = "USD" } },
]
valid_until = "2027-01-01"
basis = "test fixture"
evidence = { method = "catalog", trust_tier = "community", reference = "fixture" }

[[pricing]]
key = "old.quote_2025.widget"
item = "widget"
breaks = [{ min_qty = 1.0, unit_price = { lo = 7.0, hi = 7.5, unit = "USD" } }]
valid_until = "2025-12-31"
basis = "test fixture (expired)"
evidence = { method = "catalog", trust_tier = "community", reference = "fixture" }

[[unit_cost]]
key = "acme.catalog_2026.wall_m"
assembly = "wall_m"
unit_basis = "m"
unit_cost = { lo = 100.0, hi = 120.0, unit = "USD/m" }
basis = "test fixture"
evidence = { method = "catalog", trust_tier = "community", reference = "fixture" }
"""


def _project(tmp_path: Path) -> Path:
    (tmp_path / "magnetite.toml").write_text(_MANIFEST)
    (tmp_path / "records").mkdir()
    (tmp_path / "records" / "cost.toml").write_text(_RECORDS)
    return tmp_path


def _context(tmp_path: Path, **kwargs) -> CostContext:  # type: ignore[no-untyped-def]
    root = _project(tmp_path)
    result = load_cost_context(
        str(root),
        payload_store=PayloadStore(str(root)),
        as_of=_AS_OF,
        **kwargs,
    )
    assert result.is_ok, result
    context = result.danger_ok
    assert context is not None
    return context


def _cost_obligation(loads: list[str], sweep: SweepDomain | None = None) -> Obligation:
    return Obligation(
        claim=Claim(
            name="bom",
            form=ClaimForm1(
                form=Form.comparison,
                lhs="mfg.cost(widget_board)",
                op="<=",
                rhs="500USD",
            ),
            forall=[],
            hints=[],
        ),
        subject_ref="blake3:widget_board",
        given=Given(materials=[], loads=loads, backing=[]),
        hints=[],
        sweep=sweep,
    )


# --- context loading -------------------------------------------------------


def test_context_loads_profiles_and_records(tmp_path: Path) -> None:
    context = _context(tmp_path)
    assert set(context.profiles) == {"prototype", "production", "stale"}
    assert context.build_profile == "prototype"  # the manifest default
    assert "rates.bench_2026" in context.records.rates
    assert "acme.catalog_2026.widget" in context.records.pricing
    assert "acme.catalog_2026.wall_m" in context.records.unit_costs


def test_profileless_project_yields_no_context(tmp_path: Path) -> None:
    (tmp_path / "magnetite.toml").write_text('[package]\nname = "bare"\n')
    result = load_cost_context(str(tmp_path), payload_store=None, as_of=_AS_OF)
    assert result.is_ok
    assert result.danger_ok is None


def test_unknown_cli_profile_is_a_loud_error(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = load_cost_context(
        str(root), payload_store=None, cli_profile="nope", as_of=_AS_OF
    )
    assert result.is_err
    assert result.danger_err.kind == "unknown_cost_profile"
    assert "nope" in result.danger_err.message


def test_cli_profile_beats_manifest_default(tmp_path: Path) -> None:
    context = _context(tmp_path, cli_profile="production")
    assert context.build_profile == "production"


# --- record resolution -----------------------------------------------------


# frob:tests python/regolith/orchestrator/costing.py::resolve_profile_inputs
# frob:tests python/regolith/orchestrator/costing.py::record_pins
# frob:tests python/regolith/orchestrator/plan_staging.py::record_pins
def test_resolve_profile_pins_every_consumed_record(tmp_path: Path) -> None:
    context = _context(tmp_path)
    result = resolve_profile_inputs(context, context.profiles["prototype"])
    assert result.is_ok, result
    inputs = result.danger_ok
    assert [r.key for r in inputs.rates] == ["rates.bench_2026"]
    assert [p.key for p in inputs.pricing] == ["acme.catalog_2026.widget"]
    assert [u.key for u in inputs.unit_costs] == ["acme.catalog_2026.wall_m"]
    pins = dict(record_pins(context))
    assert set(pins) == {
        "rates.bench_2026@1",
        "acme.catalog_2026.widget@1",
        "acme.catalog_2026.wall_m@1",
    }
    assert all(digest.startswith("sha256:") for digest in pins.values())


def test_expired_pricing_names_the_record(tmp_path: Path) -> None:
    context = _context(tmp_path)
    result = resolve_profile_inputs(context, context.profiles["stale"])
    assert result.is_err
    failure = result.danger_err
    assert failure.reason == "pricing_record_expired"
    assert "old.quote_2025.widget" in failure.detail
    assert "2025-12-31" in failure.detail
    assert "waive with basis" in failure.detail


def test_missing_record_ref_names_the_ref(tmp_path: Path) -> None:
    context = _context(tmp_path)
    profile = context.profiles["prototype"].model_copy(
        update={"labor": ("rates.never_written",)}
    )
    result = resolve_profile_inputs(context, profile)
    assert result.is_err
    assert result.danger_err.reason == "cost_record_unresolved"
    assert "rates.never_written" in result.danger_err.detail


# --- translate: the cost path ----------------------------------------------


# frob:tests python/regolith/harness/models/cost_common.py::BomLine.item_key
def test_cost_obligation_translates_to_a_staged_request(tmp_path: Path) -> None:
    context = _context(tmp_path)
    obligation = _cost_obligation(
        ["cost_subject: widget_board", "cost_bom.w: vendor(widget)"]
    )
    result = translate(obligation, cost_context=context)
    assert result.is_ok, result
    request = result.danger_ok
    assert request.claim_kind == "mfg.cost"
    assert request.limit == 500.0
    assert COST_INPUTS_PORT in request.payloads
    assert BOM_PORT in request.payloads  # the BOM basis is populated
    assert request.settings_digest  # the doc digest rides the evidence hash
    # The staged doc is resolvable and carries the default profile.
    digest = request.payloads[COST_INPUTS_PORT].digest
    assert context.store is not None
    stored = context.store.resolve(digest)
    assert stored.is_ok
    doc = CostInputsDoc.model_validate_json(stored.danger_ok)
    assert [p.name for p in doc.profiles] == ["prototype"]
    assert doc.bom[0].item_key() == "widget"


def test_claim_profile_overrides_the_build_default(tmp_path: Path) -> None:
    context = _context(tmp_path)
    obligation = _cost_obligation(
        ["cost_subject: widget_board", "cost_profile: production"]
    )
    result = translate(obligation, cost_context=context)
    assert result.is_ok, result
    request = result.danger_ok
    digest = request.payloads[COST_INPUTS_PORT].digest
    assert context.store is not None
    doc = CostInputsDoc.model_validate_json(context.store.resolve(digest).danger_ok)
    assert [p.name for p in doc.profiles] == ["production"]


def test_profile_sweep_stages_every_axis_point(tmp_path: Path) -> None:
    context = _context(tmp_path)
    obligation = _cost_obligation(
        ["cost_subject: widget_board"],
        sweep=SweepDomain(axis="profile", domain="{prototype, production}"),
    )
    result = translate(obligation, cost_context=context)
    assert result.is_ok, result
    digest = result.danger_ok.payloads[COST_INPUTS_PORT].digest
    assert context.store is not None
    doc = CostInputsDoc.model_validate_json(context.store.resolve(digest).danger_ok)
    assert [p.name for p in doc.profiles] == ["prototype", "production"]


def test_no_context_defers_naming_the_configuration_gap(tmp_path: Path) -> None:
    obligation = _cost_obligation(["cost_subject: widget_board"])
    result = translate(obligation, cost_context=None)
    assert result.is_err
    assert result.danger_err.reason == "cost_profiles_unconfigured"


def test_unknown_claim_profile_defers_naming_it(tmp_path: Path) -> None:
    context = _context(tmp_path)
    obligation = _cost_obligation(
        ["cost_subject: widget_board", "cost_profile: fantasy"]
    )
    result = translate(obligation, cost_context=context)
    assert result.is_err
    assert result.danger_err.reason == "cost_profile_unknown"
    assert "fantasy" in result.danger_err.detail


def test_expired_profile_defers_through_translate(tmp_path: Path) -> None:
    context = _context(tmp_path)
    obligation = _cost_obligation(["cost_subject: widget_board", "cost_profile: stale"])
    result = translate(obligation, cost_context=context)
    assert result.is_err
    assert result.danger_err.reason == "pricing_record_expired"
    assert "old.quote_2025.widget" in result.danger_err.detail


# --- helpers ---------------------------------------------------------------


def test_parse_profile_sweep_accepts_only_discrete_sets() -> None:
    assert parse_profile_sweep("{a, b}") == ("a", "b")
    assert parse_profile_sweep("{ solo }") == ("solo",)
    assert parse_profile_sweep("[1, 2]") is None
    assert parse_profile_sweep("{}") is None


def test_load_cost_records_walks_package_subdirs(tmp_path: Path) -> None:
    pkg = tmp_path / "std.cost"
    (pkg / "records").mkdir(parents=True)
    (pkg / "magnetite.toml").write_text('[package]\nname = "std.cost"\n')
    (pkg / "records" / "cost.toml").write_text(_RECORDS)
    result = load_cost_records((str(tmp_path),))
    assert result.is_ok
    assert "acme.catalog_2026.widget" in result.danger_ok.pricing


# --- M6: persisted estimator matches the registry's D94 pick --------------


class _CheapBomModel(CostElecBomModel):
    """A `cost_elec_bom` twin registered at a cheaper tier than the
    built-in `cost_civil_takeoff`, so the registry's (cost, model_id)
    order picks the BOM basis even though a frame basis is ALSO
    populated -- the exact multi-basis case the old frame>bom>flownet
    cascade could not see (it never asked the registry)."""

    @property
    def cost(self) -> int:  # noqa: D102 - see class docstring
        return 0


def _multi_basis_doc() -> CostInputsDoc:
    """A subject `"all"`-shaped doc carrying BOTH a frame and a BOM
    basis (`assemble_inputs_doc` builds exactly this shape for a build
    whose subject matches every frame/flownet plus its own bom lines)."""
    from regolith.harness.models.cost_common import BomLine

    return CostInputsDoc(
        subject="all",
        profiles=(),
        bom=(BomLine(part="w", ref="vendor(widget)"),),
        frame_members=(
            FrameMemberLine(
                id="G1",
                role="beam",
                length=ScalarInterval(lo=1.0, hi=1.0, unit="m"),
                section="w8x10",
                material="steel",
            ),
        ),
    )


# frob:tests python/regolith/orchestrator/costing.py::assemble_inputs_doc
def test_estimate_fn_for_follows_default_registry_priority() -> None:
    """With the real registry, `cost_civil_takeoff` (cheapest, lowest
    model id) wins a multi-basis doc -- matching the old cascade's
    frame-first order, but now because the registry says so."""
    registry = ModelRegistry()
    registry.register(CostElecBomModel())
    registry.register(CostCivilTakeoffModel())
    doc = _multi_basis_doc()
    assert _estimate_fn_for(doc, registry) is civil_takeoff_estimate


def test_estimate_fn_for_follows_registry_when_priority_flips() -> None:
    """When a cheaper BOM-basis model is registered, the registry picks
    IT for the same multi-basis doc -- `_estimate_fn_for` must follow,
    not the hand-maintained frame-first cascade the old code used
    (which would have persisted a civil-takeoff payload here, silently
    mismatching whatever the registry actually discharged the claim
    with)."""
    registry = ModelRegistry()
    registry.register(_CheapBomModel())
    registry.register(CostCivilTakeoffModel())
    doc = _multi_basis_doc()
    assert _estimate_fn_for(doc, registry) is bom_estimate
