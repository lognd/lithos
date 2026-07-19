"""WO-94 (D196.1): `fluids.dp(...)` routes from a real `.fluo` claim
through `orchestrator.translate` to `FluidPressureDropModel` and
discharges, end to end (real `compiler.check` + `orchestrator.
discharge_all`, the WO-72 bolted-joint/bearing-life routing test's
own pattern -- see that test's module doc for why the model's inputs
are literal call keyword arguments rather than `given.loads`: a
fluorite `require` claim's obligation is built by `push_fluid_
obligation` in `crates/regolith-lower/src/claims.rs`, which hardcodes
`given: Given { loads: Vec::new(), .. }` -- the inline `given <ident>
= <expr>` suffix syntax elsewhere in this corpus (`given T_group =
90degC`) is parsed but never threaded into any obligation for a fluid
claim, a genuine toolchain gap this WO's ledger escalates rather than
works around).
"""

from __future__ import annotations

import json
from pathlib import Path

from regolith import compiler
from regolith._schema.models import ClaimForm1, Obligation
from regolith.harness import default_registry
from regolith.orchestrator import discharge_all
from regolith.orchestrator.cache import EvidenceStore
from regolith.orchestrator.discharge import ObligationResult

_FIXTURE = Path(__file__).parent / "data" / "wo94_fluid_dp_fixture.fluo"


def _obligations() -> list[Obligation]:
    result = compiler.check((str(_FIXTURE),))
    assert result.is_ok, f"check({_FIXTURE!r}) returned Err: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    return [Obligation.model_validate(raw) for raw in payload["obligations"]]


def _discharge_by_name() -> dict[str, ObligationResult]:
    obligations = _obligations()
    results = discharge_all(
        obligations, registry=default_registry(), store=EvidenceStore()
    )
    by_name: dict[str, ObligationResult] = {}
    for obligation, result in zip(obligations, results, strict=True):
        name = obligation.claim.name
        if name is not None:
            by_name[name] = result
    return by_name


def test_fluid_dp_claim_discharges_end_to_end() -> None:
    """`dp: fluids.dp(a -> b, ...) <= 2Pa` lowers through the real
    pipeline and discharges against `FluidPressureDropModel`."""
    results = _discharge_by_name()
    dp = results["dp"]
    assert dp.deferral is None, dp.deferral
    assert dp.evidence is not None
    assert dp.evidence.status.value == "discharged"
    assert dp.evidence.model_id == "fluid_darcy_weisbach_dp@1"


def test_fluid_dp_claim_missing_inputs_defers_honestly() -> None:
    """A `fluids.dp(...)` call missing one of the model's required
    keyword arguments defers by NAME (D97), never a silent pass or a
    fabricated request."""
    from regolith.orchestrator.translate import translate

    obligations = _obligations()
    dp_ob = next(o for o in obligations if o.claim.name == "dp")
    form = dp_ob.claim.form
    assert isinstance(form, ClaimForm1), (
        f"expected a scalar-comparison form, got {form!r}"
    )
    patched_lhs = form.lhs.replace(", density_kgm3=965", "")
    patched = dp_ob.model_copy(
        update={
            "claim": dp_ob.claim.model_copy(
                update={"form": form.model_copy(update={"lhs": patched_lhs})}
            )
        }
    )
    lowered = translate(patched)
    assert lowered.is_err, lowered.danger_ok
    deferral = lowered.danger_err
    assert deferral.reason == "fluids.dp_inputs_missing"
    assert "density_kgm3" in deferral.detail
