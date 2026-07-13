"""WO-110 deliverable 5: the bare `mfg.unit_cost(qty=...)` claim-facing
adapter onto the WO-54 costing surface.

End-to-end through `orchestrate.build` (which threads the staging
context): the subject derives from the enclosing part's snapshot
scope, `qty=` picks the quantity-matching declared profile, and the
remaining gaps defer NAMED -- no quantity basis (the Rust bare-form
`cost_bom` marker gap, escalated in the WO-110 close-out) or no
quantity-matching profile. Unit-level: when the derived subject DOES
carry a quantity basis (a flownet named after it), the adapter forms
a real staged `mfg.cost` request -- proving the estimator-vs-bound
comparison surface is reached (the margin rule itself is WO-54's
already-proven machinery)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from regolith import compiler
from regolith._schema.models import Obligation
from regolith.harness.models.cost_common import CLAIM_KIND as _COST_KIND
from regolith.orchestrator.costing import load_cost_context
from regolith.orchestrator.dfm_staging import load_dfm_context
from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.tiers import TIER_BY_VERB
from regolith.orchestrator.translate import translate

_AS_OF = dt.date(2026, 7, 9)

_MANIFEST = """\
[package]
name = "costed_fixture"
version = "0.1.0"

[profiles.cost.prototype]
quantity = 1
pricing  = ["acme.catalog_2026"]

[profiles.cost.production]
quantity = 100
pricing  = ["acme.catalog_2026"]

[profiles.cost.default]
profile = "prototype"
"""

_RECORDS = """\
[[pricing]]
key = "acme.catalog_2026.widget"
item = "widget"
breaks = [
    { min_qty = 1.0, unit_price = { lo = 10.0, hi = 12.0, unit = "USD" } },
]
valid_until = "2027-01-01"
basis = "test fixture"
evidence = { method = "catalog", trust_tier = "community", reference = "fixture" }
"""

_FLUO = """\
medium Water: liquid
    props: registry(potable_water_nist)

flownet CoolLoop(medium=Water):
    reference: ambient(101kPa, 293K)
    nodes: a, b
    edges:
        seg: Pipe(from=lateral.run) (a -> b)
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


def _cost_result(source: Path):  # type: ignore[no-untyped-def]
    result = build((str(source),), TIER_BY_VERB["build"], cost_as_of=_AS_OF)
    assert result.is_ok, result
    report = result.danger_ok
    for res in report.results:
        if res.deferral is not None or (
            res.evidence is not None and res.evidence.model_id.startswith("cost_")
        ):
            return res
    raise AssertionError("no cost result found")


def test_bare_qty_derives_subject_and_defers_naming_the_basis_gap(
    tmp_path: Path,
) -> None:
    """`cost: mfg.unit_cost(qty=100) <= 12` on a part: the subject
    derives ('controller'), qty picks 'production', and the deferral
    names the missing quantity basis (the Rust bare-form marker gap)
    -- never an anonymous no-model indeterminate."""
    source = _project(tmp_path, "cost: mfg.unit_cost(qty=100) <= 12")
    res = _cost_result(source)
    assert res.deferral is not None
    assert res.deferral.reason == f"{_COST_KIND}_inputs_missing"
    assert "controller" in res.deferral.detail
    assert "quantity basis" in res.deferral.detail


def test_bare_qty_with_no_matching_profile_defers_naming_quantities(
    tmp_path: Path,
) -> None:
    source = _project(tmp_path, "cost: mfg.unit_cost(qty=250) <= 4")
    res = _cost_result(source)
    assert res.deferral is not None
    assert res.deferral.reason == "cost_profile_unresolved"
    assert "250" in res.deferral.detail
    assert "production=100" in res.deferral.detail


def test_bare_qty_profile_disagreement_defers(tmp_path: Path) -> None:
    source = _project(tmp_path, "cost: mfg.unit_cost(qty=100, profile=prototype) <= 12")
    res = _cost_result(source)
    assert res.deferral is not None
    assert res.deferral.reason == "cost_profile_unresolved"
    assert "prototype" in res.deferral.detail


def test_subject_with_flownet_basis_forms_a_real_staged_request(
    tmp_path: Path,
) -> None:
    """When the derived subject names a flownet, the adapter rides
    `_translate_cost`'s real resolution + staging: the request carries
    the `cost_flownet` basis port and the parsed bound -- the
    estimator-vs-bound comparison surface, reached."""
    (tmp_path / "magnetite.toml").write_text(_MANIFEST)
    (tmp_path / "records").mkdir()
    (tmp_path / "records" / "cost.toml").write_text(_RECORDS)
    (tmp_path / "loop.fluo").write_text(_FLUO)
    checked = compiler.check([str(tmp_path / "loop.fluo")])
    assert checked.is_ok
    payload = json.loads(checked.danger_ok.payload_json)
    store = PayloadStore(str(tmp_path))
    context_result = load_cost_context(
        str(tmp_path),
        payload_store=store,
        build_payload=payload,
        as_of=_AS_OF,
    )
    assert context_result.is_ok
    cost_context = context_result.danger_ok
    assert cost_context is not None
    dfm_context = load_dfm_context(
        {"snapshots": [{"hash": "h1", "scope": "CoolLoop"}]},
        (),
        payload_store=store,
    )
    obligation = Obligation.model_validate(
        {
            "claim": {
                "name": "cost",
                "form": {
                    "form": "comparison",
                    "lhs": "mfg.unit_cost(qty=100)",
                    "op": "<=",
                    "rhs": "12 USD",
                },
                "forall": [],
                "sf": None,
                "scatter_factor": None,
                "trust_floor": None,
                "hints": [],
                "model_pin": None,
            },
            "given": {"materials": [], "loads": [], "backing": [], "refs": []},
            "hints": [],
            "payloads": [],
            "subject_ref": "h1",
        }
    )
    lowered = translate(obligation, cost_context=cost_context, dfm_context=dfm_context)
    assert lowered.is_ok, lowered
    request = lowered.danger_ok
    assert request.claim_kind == _COST_KIND
    assert request.limit == 12.0
    assert "cost_flownet" in request.payloads
