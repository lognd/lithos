"""F152 (WO-127 finding) regression: the three registered converter
models (`elec.buck.output_voltage_ripple`, `elec.converter.efficiency`,
`elec.converter.settling_time`) were UNREACHABLE from design source --
`orchestrator.translate` had no call-form route for any of them, so a
claim spelled at the registry's OWN `CLAIM_KIND` still deferred
`unmatched_call_path` even though the model IS registered under that
exact kind string (see `harness/models/buck_ripple.py`,
`buck_efficiency.py`, `buck_transient.py`). This is a rigor-ACCOUNTING
bug, not just a routing bug: the fleet's waivers on these three claim
kinds carry the basis "no registered harness model", which is FALSE --
the model is registered, the call form was missing (D224.2).

Regression-guards: each kind now routes (never `unmatched_call_path`)
and discharges over its own declared inputs, end to end (real
`compiler.check` + `orchestrator.discharge_all`, the WO-94/WO-95
routing tests' own pattern).
"""

from __future__ import annotations

import json
from pathlib import Path

from regolith import compiler
from regolith._schema.models import Obligation
from regolith.harness import default_registry
from regolith.orchestrator import discharge_all
from regolith.orchestrator.cache import EvidenceStore
from regolith.orchestrator.translate import translate

_FIXTURE = Path(__file__).parent / "data" / "f152_converter_routing_fixture.cupr"


def _obligations() -> list[Obligation]:
    result = compiler.check([str(_FIXTURE)])
    assert result.is_ok, f"check({_FIXTURE!r}) returned Err: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    return [Obligation.model_validate(raw) for raw in payload["obligations"]]


def _discharge_by_name() -> dict[str, object]:
    obligations = _obligations()
    results = discharge_all(
        obligations, registry=default_registry(), store=EvidenceStore()
    )
    by_name: dict[str, object] = {}
    for obligation, result in zip(obligations, results, strict=True):
        name = obligation.claim.name
        if name is not None:
            by_name[name] = result
    return by_name


def test_ripple_claim_never_unmatched_call_path() -> None:
    """`elec.buck.output_voltage_ripple(...)` spelled at its own
    registered CLAIM_KIND must not defer `unmatched_call_path`."""
    obligations = _obligations()
    ripple_ob = next(o for o in obligations if o.claim.name == "ripple")
    lowered = translate(ripple_ob)
    assert lowered.is_ok, lowered
    assert lowered.danger_ok.claim_kind == "elec.buck.output_voltage_ripple"


def test_efficiency_claim_never_unmatched_call_path() -> None:
    """`elec.converter.efficiency(...)` spelled at its own registered
    CLAIM_KIND must not defer `unmatched_call_path`."""
    obligations = _obligations()
    eta_ob = next(o for o in obligations if o.claim.name == "eta")
    lowered = translate(eta_ob)
    assert lowered.is_ok, lowered
    assert lowered.danger_ok.claim_kind == "elec.converter.efficiency"


def test_settling_time_claim_never_unmatched_call_path() -> None:
    """`elec.converter.settling_time(...)` spelled at its own
    registered CLAIM_KIND must not defer `unmatched_call_path`."""
    obligations = _obligations()
    settle_ob = next(o for o in obligations if o.claim.name == "settle")
    lowered = translate(settle_ob)
    assert lowered.is_ok, lowered
    assert lowered.danger_ok.claim_kind == "elec.converter.settling_time"


def test_all_three_discharge_end_to_end() -> None:
    """All three converter claims discharge (never defer) against
    their registered models, under the models' OWN claim kinds."""
    results = _discharge_by_name()
    for name, model_id in (
        ("ripple", "buck_output_ripple_ccm@1"),
        ("eta", "buck_efficiency_loss_budget@1"),
        ("settle", "converter_settling_dominant_pole@1"),
    ):
        result = results[name]
        assert result.deferral is None, f"{name}: {result.deferral}"
        assert result.evidence is not None
        assert result.evidence.status.value == "discharged"
        assert result.evidence.model_id == model_id
