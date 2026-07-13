"""WO-110 deliverable 4: `fluids.npsh_margin(...)` routes from a real
`.fluo` claim through `orchestrator.translate` to `NpshMarginModel`
end to end (real `compiler.check` + `orchestrator.discharge_all`, the
WO-94 fluids.dp routing test's own pattern) -- discharged, honestly
violated, and inputs-missing-named, one claim each."""

from __future__ import annotations

import json
from pathlib import Path

from regolith import compiler
from regolith._schema.models import Obligation
from regolith.harness import default_registry
from regolith.harness.models.npsh_margin import CLAIM_KIND as _NPSH_KIND
from regolith.orchestrator import discharge_all
from regolith.orchestrator.cache import EvidenceStore

_FIXTURE = Path(__file__).parent / "data" / "wo110_npsh_fixture.fluo"


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


def test_npsh_margin_claim_discharges_end_to_end() -> None:
    """`npsh: fluids.npsh_margin(...) > 1.5m` (margin 2.314 m) lowers
    through the real pipeline and discharges."""
    results = _discharge_by_name()
    npsh = results["npsh"]
    assert npsh.deferral is None, npsh.deferral
    assert npsh.evidence is not None
    assert npsh.evidence.status.value == "discharged"
    assert npsh.evidence.model_id == "fluids_npsh_margin_energy_balance@1"


def test_starved_suction_is_honestly_violated() -> None:
    """The 7 m-lift variant (margin -1.686 m) VIOLATES -- cavitation is
    a finding, never a silent pass."""
    results = _discharge_by_name()
    starved = results["starved"]
    assert starved.deferral is None, starved.deferral
    assert starved.evidence is not None
    assert starved.evidence.status.value == "violated"


def test_undeclared_inputs_defer_naming_all_six() -> None:
    results = _discharge_by_name()
    undeclared = results["undeclared"]
    assert undeclared.deferral is not None
    assert undeclared.deferral.reason == f"{_NPSH_KIND}_inputs_missing"
    for name in ("p_supply_pa", "p_vapor_pa", "npshr_m"):
        assert name in undeclared.deferral.detail
