"""WO-110 deliverable 3: `mech.twist(...)` routes from a real `.hema`
claim through `orchestrator.translate` to `ShaftTorsionModel` end to
end (the WO-109 cantilever routing test's pattern) -- discharged,
honestly violated, and inputs-missing-named, one claim each."""

from __future__ import annotations

import json
from pathlib import Path

from regolith import compiler
from regolith._schema.models import Obligation
from regolith.harness import default_registry
from regolith.harness.models.shaft_torsion import CLAIM_KIND as _TWIST_KIND
from regolith.orchestrator import discharge_all
from regolith.orchestrator.cache import EvidenceStore

_FIXTURE = Path(__file__).parent / "data" / "wo110_twist_fixture.hema"


def _discharge_by_name() -> dict[str, object]:
    result = compiler.check([str(_FIXTURE)])
    assert result.is_ok, f"check({_FIXTURE!r}) returned Err: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    obligations = [Obligation.model_validate(raw) for raw in payload["obligations"]]
    results = discharge_all(
        obligations, registry=default_registry(), store=EvidenceStore()
    )
    by_name: dict[str, object] = {}
    for obligation, res in zip(obligations, results, strict=True):
        if obligation.claim.name is not None:
            by_name[obligation.claim.name] = res
    return by_name


def test_twist_claim_discharges_end_to_end() -> None:
    """theta = 0.03288 rad <= 0.05 rad discharges."""
    results = _discharge_by_name()
    twist = results["twist"]
    assert twist.deferral is None, twist.deferral
    assert twist.evidence is not None
    assert twist.evidence.status.value == "discharged"
    assert twist.evidence.model_id == "mech_shaft_twist_uniform@1"


def test_tight_budget_is_honestly_violated() -> None:
    results = _discharge_by_name()
    stiff = results["stiff"]
    assert stiff.deferral is None, stiff.deferral
    assert stiff.evidence is not None
    assert stiff.evidence.status.value == "violated"


def test_undeclared_inputs_defer_naming_all_four() -> None:
    results = _discharge_by_name()
    undeclared = results["undeclared"]
    assert undeclared.deferral is not None
    assert undeclared.deferral.reason == f"{_TWIST_KIND}_inputs_missing"
    for name in ("torque_nm", "g_modulus_pa", "j_torsion_m4"):
        assert name in undeclared.deferral.detail
