"""WO-72 coordinator wiring dispatch: `mech.bolt.joint_separation` and
`mech.bearing.l10_hours` route from a real `.hema` claim through
`orchestrator.translate` to their harness models and discharge, end to
end (real `compiler.check` + `orchestrator.discharge_all`, not a
model-direct request built by hand).

Both `BoltedJointModel` (`regolith.harness.models.bolted_joint`) and
`BearingL10HoursModel` (`regolith.harness.models.bearing_life`) already
had passing model-direct unit tests before this WO; the gap this test
closes is `orchestrator.translate` having NO dispatch entry that could
ever route a claim to them -- see `translate.py`'s
`_split_named_call_predicate`/`_match_call_lhs`/`_translate_bolted_
joint`/`_translate_bearing_l10`, and the fixture's own module doc for
why the four scalar inputs are literal call keyword arguments (not
`given.loads`) and why the call carries an `under=` keyword arg (a
bare single-positional-arg call lowers through a different, ordinary
comparison shape this routing does not target).
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

_FIXTURE = Path(__file__).parent / "data" / "wo72_bolted_joint_bearing_fixture.hema"


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
    # Obligations do not carry their own `claim.name` back on
    # `ObligationResult` (keyed by `subject_ref`/content hash instead),
    # so pair each result up with its source obligation by list order
    # (`discharge_all` discharges in source order, INV-10).
    by_name: dict[str, ObligationResult] = {}
    for obligation, result in zip(obligations, results, strict=True):
        name = obligation.claim.name
        if name is not None:
            by_name[name] = result
    return by_name


def test_bolted_joint_claim_discharges_end_to_end() -> None:
    """`clamp: mech.bolt.joint_separation(...) >= 2000` lowers through
    the real pipeline and discharges against `BoltedJointModel`."""
    results = _discharge_by_name()
    clamp = results["clamp"]
    assert clamp.deferral is None, clamp.deferral
    assert clamp.evidence is not None
    assert clamp.evidence.status.value == "discharged"
    assert clamp.evidence.model_id == "bolted_joint_separation_vdi2230@1"


def test_bearing_l10_claim_discharges_end_to_end() -> None:
    """`b10: mech.bearing.l10_hours(...) >= 4000` lowers through the
    real pipeline and discharges against `BearingL10HoursModel`."""
    results = _discharge_by_name()
    b10 = results["b10"]
    assert b10.deferral is None, b10.deferral
    assert b10.evidence is not None
    assert b10.evidence.status.value == "discharged"
    assert b10.evidence.model_id == "bearing_basic_rating_life_l10h@1"


def test_bolted_joint_claim_missing_inputs_defers_honestly() -> None:
    """A `mech.bolt.joint_separation(...)` call missing one of the
    model's required keyword arguments defers by NAME (D97), never a
    silent pass or a fabricated request."""
    from regolith.orchestrator.translate import translate

    obligations = _obligations()
    clamp_ob = next(o for o in obligations if o.claim.name == "clamp")
    # Drop `k_clamp` from the call text the same way the source would
    # if a caller forgot it -- rebuild the obligation's form with one
    # fewer keyword argument, reusing the real predicate text otherwise.
    form = clamp_ob.claim.form
    assert isinstance(form, ClaimForm1), (
        f"expected a scalar-comparison form, got {form!r}"
    )
    stripped_rhs = form.rhs
    patched_lhs = form.lhs.replace(", k_clamp=1.1e9", "")
    patched = clamp_ob.model_copy(
        update={
            "claim": clamp_ob.claim.model_copy(
                update={
                    "form": form.model_copy(
                        update={"lhs": patched_lhs, "rhs": stripped_rhs}
                    )
                }
            )
        }
    )
    lowered = translate(patched)
    assert lowered.is_err, lowered.danger_ok
    deferral = lowered.danger_err
    assert deferral.reason == "mech.bolt.joint_separation_inputs_missing"
    assert "k_clamp" in deferral.detail
