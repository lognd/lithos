"""WO-93 dispatch-note follow-up: `thermo.temperature(...)`
routes from a real `.cupr` claim through `orchestrator.translate` to
`LumpedThermalModel` and discharges, end to end (real `compiler.check`
+ `orchestrator.discharge_all`, the WO-94 `fluids.dp(...)` routing
test's own pattern -- see that test's module doc). Regression-guards
the bug the WO-93 dispatch note recorded: a label-named thermo claim
(cubesat `fpga_ceiling`/`batt_window`-style) used to translate-lower
under the claim's own label name (`obligation.claim.name`) instead of
the registered `thermo.junction_temperature` claim kind, so it never
reached `thermo_lumped_steady@1`.
"""

from __future__ import annotations

import json
from pathlib import Path

from regolith import compiler
from regolith._schema.models import Obligation
from regolith.harness import default_registry
from regolith.orchestrator import discharge_all
from regolith.orchestrator.cache import EvidenceStore

_FIXTURE = Path(__file__).parent / "data" / "wo95_thermo_routing_fixture.cupr"


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


def test_thermo_claim_discharges_end_to_end() -> None:
    """`junction: thermo.temperature(x, ambient=..., power=..., r_theta=...)
    <= 358` lowers through the real pipeline and discharges against
    `LumpedThermalModel`, under the model's OWN claim kind -- never the
    claim's label name."""
    results = _discharge_by_name()
    junction = results["junction"]
    assert junction.deferral is None, junction.deferral
    assert junction.evidence is not None
    assert junction.evidence.status.value == "discharged"
    assert junction.evidence.model_id == "thermo_lumped_steady@1"


def test_thermo_claim_missing_inputs_defers_honestly() -> None:
    """A `thermo.temperature(...)` call missing one of the model's
    required keyword arguments defers by NAME (D97), specifically
    naming the missing input -- never a silent pass or a fabricated
    request, and never the old label-name misroute."""
    from regolith.orchestrator.translate import translate

    obligations = _obligations()
    junction_ob = next(o for o in obligations if o.claim.name == "junction")
    form = junction_ob.claim.form
    patched_lhs = form.lhs.replace(", r_theta=10", "")
    patched = junction_ob.model_copy(
        update={
            "claim": junction_ob.claim.model_copy(
                update={"form": form.model_copy(update={"lhs": patched_lhs})}
            )
        }
    )
    lowered = translate(patched)
    assert lowered.is_err, lowered.danger_ok
    deferral = lowered.danger_err
    assert deferral.reason == "thermo.junction_temperature_inputs_missing"
    assert "r_theta" in deferral.detail
