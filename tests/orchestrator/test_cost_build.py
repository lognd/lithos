"""WO-54 end to end through `orchestrate.build`: a real project (source
+ manifest profiles + fixture records) whose mfg.cost claim discharges
via the std.cost elec BOM estimator, the expired-quote honest
indeterminate naming the record, the D95 profile sweep under ONE
obligation, and the INV-22 pin/estimate surfaces on the report."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from regolith._schema.models import ItemizedEstimate
from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.tiers import TIER_BY_VERB

_AS_OF = dt.date(2026, 7, 9)

_MANIFEST = """\
[package]
name = "costed_board"
version = "0.1.0"

[profiles.cost.prototype]
quantity = 1
pricing  = ["acme.catalog_2026"]

[profiles.cost.production]
quantity = 100
pricing  = ["acme.catalog_2026"]
markup   = 1.2

[profiles.cost.stale]
quantity = 1
pricing  = ["old.quote_2025"]

[profiles.cost.default]
profile = "prototype"
"""

_RECORDS = """\
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
"""


def _project(tmp_path: Path, claim: str) -> Path:
    (tmp_path / "magnetite.toml").write_text(_MANIFEST)
    (tmp_path / "records").mkdir()
    (tmp_path / "records" / "cost.toml").write_text(_RECORDS)
    source = tmp_path / "controller.hema"
    source.write_text(
        "part controller:\n"
        "    parts:\n"
        "        w: vendor(widget)\n"
        "    require Cost:\n"
        f"        {claim}\n"
    )
    return source


def _build(source: Path, **kwargs):  # type: ignore[no-untyped-def]
    result = build(
        (str(source),), TIER_BY_VERB["build"], cost_as_of=_AS_OF, **kwargs
    )
    assert result.is_ok, result
    return result.danger_ok


def _cost_results(report):  # type: ignore[no-untyped-def]
    return [
        r
        for r in report.results
        if r.evidence is not None and r.evidence.model_id.startswith("cost_")
    ] + [r for r in report.results if r.deferral is not None]


def test_cost_claim_discharges_end_to_end(tmp_path: Path) -> None:
    source = _project(tmp_path, "bom: mfg.cost(controller, profile=prototype) <= 100")
    report = _build(source)
    discharged = [
        r
        for r in report.results
        if r.evidence is not None
        and r.evidence.model_id.startswith("cost_elec_bom")
    ]
    assert discharged, [
        (r.evidence and r.evidence.model_id, r.deferral) for r in report.results
    ]
    assert discharged[0].is_resolved
    # INV-22: the consumed record is pinned; the estimate is persisted.
    assert dict(report.cost_record_pins).get("acme.catalog_2026.widget@1")
    estimates = dict(report.cost_estimates)
    assert "controller/prototype" in estimates
    # The persisted estimate payload is a resolvable ItemizedEstimate.
    store = PayloadStore(str(tmp_path))
    stored = store.resolve(estimates["controller/prototype"])
    assert stored.is_ok
    estimate = ItemizedEstimate.model_validate_json(stored.danger_ok)
    assert estimate.profile == "prototype"
    assert estimate.lines[0].item == "widget"
    assert estimate.total.hi == 12.0
    assert report.cost_profile == "prototype"


def test_expired_quote_is_indeterminate_naming_the_record(tmp_path: Path) -> None:
    source = _project(tmp_path, "bom: mfg.cost(controller, profile=stale) <= 100")
    report = _build(source)
    deferred = [r for r in report.results if r.deferral is not None]
    assert deferred, report.results
    deferral = deferred[0].deferral
    assert deferral is not None
    assert deferral.reason == "pricing_record_expired"
    assert "old.quote_2025.widget" in deferral.detail
    assert deferred[0].is_indeterminate  # never resolved, never violated
    assert not deferred[0].is_violated


def test_profile_sweep_is_one_obligation_with_per_profile_evidence(
    tmp_path: Path,
) -> None:
    source = _project(
        tmp_path,
        "sweep: forall profile in {prototype, production}: "
        "mfg.cost(controller) <= 100",
    )
    report = _build(source)
    discharged = [
        r
        for r in report.results
        if r.evidence is not None
        and r.evidence.model_id.startswith("cost_elec_bom")
    ]
    assert len(discharged) == 1, [
        (r.evidence and r.evidence.model_id, r.deferral) for r in report.results
    ]
    assert discharged[0].is_resolved
    # D95: per-profile axis points ride the ONE evidence's coverage.
    axes = discharged[0].evidence.coverage.axes  # type: ignore[union-attr]
    assert [a.axis for a in axes] == ["profile"]
    # Both profiles' estimates are persisted (auditable per-axis-point).
    estimates = dict(report.cost_estimates)
    assert set(estimates) == {"controller/prototype", "controller/production"}


def test_build_profile_selects_and_claims_may_omit(tmp_path: Path) -> None:
    source = _project(tmp_path, "bom: mfg.cost(controller) <= 100")
    report = _build(source, cost_profile="production")
    assert report.cost_profile == "production"
    estimates = dict(report.cost_estimates)
    assert set(estimates) == {"controller/production"}


def test_unknown_build_profile_is_a_loud_error(tmp_path: Path) -> None:
    source = _project(tmp_path, "bom: mfg.cost(controller) <= 100")
    result = build(
        (str(source),),
        TIER_BY_VERB["build"],
        cost_as_of=_AS_OF,
        cost_profile="fantasy",
    )
    assert result.is_err
    assert result.danger_err.kind == "unknown_cost_profile"


def test_costless_project_still_builds(tmp_path: Path) -> None:
    (tmp_path / "magnetite.toml").write_text('[package]\nname = "bare"\n')
    source = tmp_path / "trivial.hema"
    source.write_text("part p:\n    a: 1mm\n")
    report = _build(source)
    assert report.cost_profile is None
    assert report.cost_record_pins == ()
