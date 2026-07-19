"""WO-86: the uav_talon CG/moment-budget claim (F112) forms a real
obligation and defers HONESTLY, naming both missing inputs -- never a
silent pass. See `orchestrator/translate.py::_translate_cg_moment`'s
docstring for the deliverable-1 keystone finding this claim shape
records: `mech.mass(all)` (the "landed" budget-arithmetic precedent
WO-86 was dispatched to extend) has no numeric contribution wiring
either (`close_budget` always runs against an empty contributions
slice, `regolith-lower/src/contracts.rs`), and no `.hema` mount in this
corpus declares a scalar part position -- so a weighted-sum CG closure
(sum(m_i * x_i)) has neither half of its sum available from declared
data. Reopens per WO-70's W2 criterion once a location/moment
budget-math `kind=` lands (D49 extension) AND declared part-position
data exists.
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

_UAV_TALON = Path("examples/flagships/uav_talon")


def _obligations() -> list[Obligation]:
    result = compiler.check((str(_UAV_TALON),))
    assert result.is_ok, f"check(uav_talon) returned Err: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    return [Obligation.model_validate(raw) for raw in payload["obligations"]]


def test_cg_claim_forms_a_real_obligation() -> None:
    """`cg_ok: mech.cg(members=[...]) in [0.40m, 0.55m]` in
    `uav_talon.cupr`'s `require CGEnvelope:` group lowers to a real,
    named obligation -- the claim is present in the payload, not
    silently dropped by the core lowering (INV-24 totality)."""
    obligations = _obligations()
    names = [o.claim.name for o in obligations]
    assert "cg_ok" in names, names


def test_cg_claim_defers_with_named_input_reason() -> None:
    """The CG obligation defers through `orchestrator.translate` with a
    specific, greppable reason naming BOTH missing inputs (no wired
    `mech.mass(...)` contribution and no declared part position) --
    never a generic `unsupported_op` deferral, and never a silent
    discharge over undeclared data."""
    obligations = _obligations()
    cg_ob = next(o for o in obligations if o.claim.name == "cg_ok")

    lowered = translate(cg_ob)
    assert lowered.is_err, lowered.danger_ok
    deferral = lowered.danger_err
    assert deferral.reason == "cg_moment_no_declared_position_data"
    assert "mech.mass" in deferral.detail
    assert "position" in deferral.detail


def test_cg_claim_defers_end_to_end_through_discharge_all() -> None:
    """The same claim, run through the real `discharge_all` orchestrator
    path (not just the unit-level `translate` call above), reports an
    INDETERMINATE deferral -- never `discharged`, never a fabricated
    passing verdict over data the corpus does not declare."""
    obligations = _obligations()
    results = discharge_all(
        obligations, registry=default_registry(), store=EvidenceStore()
    )
    by_name = {
        o.claim.name: r
        for o, r in zip(obligations, results, strict=True)
        if o.claim.name is not None
    }
    cg_result = by_name["cg_ok"]
    assert cg_result.evidence is None
    assert cg_result.deferral is not None
    assert cg_result.deferral.reason == "cg_moment_no_declared_position_data"


def test_uav_talon_check_stays_clean() -> None:
    """Adding the CG claim does not regress `regolith check` over
    uav_talon: the WO's zero-fleet-regression acceptance criterion for
    this flagship specifically -- structural check stays `Ok`."""
    result = compiler.check((str(_UAV_TALON),))
    assert result.is_ok, result
