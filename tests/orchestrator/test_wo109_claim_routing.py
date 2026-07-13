"""WO-109 (F130 Class B): a label-named claim whose RHS/LHS is a model
call reaches the registered model by CALL FORM regardless of the
author's label, end to end (real `compiler.check` +
`orchestrator.discharge_all`, not a model-direct request built by
hand) -- the printer_k1/arm_a6 `payload_ok`/`payload_deflection` gap
F126.1 named and this WO closes.

Covers: `mech.deflection(...)` non-frame (cantilever tip) routing to
`BeamBendingModel` (discharged + honest inputs-missing), and the bare
`mfg.unit_cost(...)` call form routing to `mfg.cost`'s claim kind with
an honest missing-`cost_subject` deferral (never "no model for label").
"""

from __future__ import annotations

import json
from pathlib import Path

from regolith import compiler
from regolith._schema.models import Obligation
from regolith.harness import default_registry
from regolith.harness.models.beam_bending import CLAIM_KIND as _CANTILEVER_KIND
from regolith.harness.models.cost_common import CLAIM_KIND as _COST_KIND
from regolith.orchestrator import discharge_all
from regolith.orchestrator.cache import EvidenceStore

_FIXTURE = Path(__file__).parent / "data" / "wo109_cantilever_deflection_fixture.hema"


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


def test_labeled_deflection_claim_discharges_by_call_form() -> None:
    """`payload_ok: mech.deflection(...)` -- a claim LABELED `payload_ok`,
    never the string `mech.deflection` -- reaches `BeamBendingModel`
    because its RHS is a call, not because of its label."""
    results = _discharge_by_name()
    payload_ok = results["payload_ok"]
    assert payload_ok.deferral is None, payload_ok.deferral
    assert payload_ok.evidence is not None
    assert payload_ok.evidence.status.value == "discharged"
    assert payload_ok.evidence.model_id == "beam_cantilever_deflection_eb@1"


def test_labeled_deflection_claim_missing_inputs_defers_honestly() -> None:
    """`payload_deflection: mech.deflection(...)` missing the `force`
    keyword defers `mech.beam.cantilever_deflection_inputs_missing`
    naming it -- NOT "no registered harness model for label kind
    'payload_deflection'"."""
    results = _discharge_by_name()
    payload_deflection = results["payload_deflection"]
    assert payload_deflection.evidence is None
    assert payload_deflection.deferral is not None
    assert payload_deflection.deferral.reason == f"{_CANTILEVER_KIND}_inputs_missing"
    assert "force" in payload_deflection.deferral.detail


def test_unmatched_call_path_defers_naming_the_dotted_path() -> None:
    """Deliverable 4(b): `crit: mech.gyroscopic_whirl(...)` -- a call
    path NO model registers -- defers `unmatched_call_path` naming the
    dotted path AND the label, never "no model for label 'crit'".
    (WO-110 swapped the exemplar: mech.critical_speed now routes
    through the feldspar-pack adapter.)"""
    results = _discharge_by_name()
    crit = results["crit"]
    assert crit.deferral is not None
    assert crit.deferral.reason == "unmatched_call_path"
    assert "mech.gyroscopic_whirl" in crit.deferral.detail
    assert "crit" in crit.deferral.detail


def test_label_only_claim_keeps_honest_no_model_deferral() -> None:
    """Deliverable 4(a): `vib_floor: cut.blank.mass < 5` -- no call form
    anywhere -- keeps the honest `no_model` deferral, annotated as
    label-only so the reader knows routing can never reach it."""
    results = _discharge_by_name()
    vib_floor = results["vib_floor"]
    assert vib_floor.deferral is not None
    assert vib_floor.deferral.reason == "no_model"
    assert "label-only" in vib_floor.deferral.detail


def test_bare_cost_call_form_defers_naming_cost_subject() -> None:
    """`cost: mfg.unit_cost(qty=25) <= 480 USD` -- no `given cost_subject=`
    clause -- routes to the REAL `mfg.cost` claim kind and defers
    naming the missing subject, never "no model for label 'cost'".
    (WO-110 deliverable 5 superseded the WO-109 stub deferral: this
    entry point threads no staging context, so the subject cannot be
    derived -- the deferral now says exactly that.)"""
    results = _discharge_by_name()
    cost = results["cost"]
    assert cost.evidence is None
    assert cost.deferral is not None
    assert cost.deferral.reason == f"{_COST_KIND}_inputs_missing"
    assert "cost subject" in cost.deferral.detail
