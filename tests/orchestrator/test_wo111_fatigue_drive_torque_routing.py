"""WO-111 (D223) coordinator wiring dispatch: `mech.fatigue.damage` and
`mech.drive_torque` route from a real `.hema` claim through
`orchestrator.translate` to their harness models and discharge, end to
end (real `compiler.check` + `orchestrator.discharge_all`), the same
shape `test_wo72_bolted_joint_bearing_routing.py` already proves for
the bolt/bearing pair.

Both `FatigueDamageModel` (`regolith.harness.models.fatigue_damage`)
and `DriveTorqueModel` (`regolith.harness.models.drive_torque`) already
had passing model-direct unit tests before this WO; the gap this test
closes is `orchestrator.translate` having NO dispatch entry that could
ever route a claim to them -- see `translate.py`'s
`_FATIGUE_DAMAGE_FORM_NAMES`/`_DRIVE_TORQUE_FORM_NAMES`,
`_translate_fatigue_damage`/`_translate_drive_torque`, and the
fixture's own module doc for the literal-kwarg shape and the `N*m`
native-unit bound.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from regolith import compiler
from regolith._schema.models import ClaimForm1, Obligation
from regolith.harness import default_registry
from regolith.orchestrator import discharge_all
from regolith.orchestrator.cache import EvidenceStore
from regolith.orchestrator.discharge import ObligationResult

_FIXTURE = Path(__file__).parent / "data" / "wo111_fatigue_drive_torque_fixture.hema"


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


def test_fatigue_damage_claim_discharges_end_to_end() -> None:
    """`spindle: mech.fatigue.damage(...) < 1.0` lowers through the
    real pipeline and discharges against `FatigueDamageModel`."""
    results = _discharge_by_name()
    spindle = results["spindle"]
    assert spindle.deferral is None, spindle.deferral
    assert spindle.evidence is not None
    assert spindle.evidence.status.value == "discharged"
    assert spindle.evidence.model_id == "fatigue_goodman_marin_basquin_damage@1"


def test_drive_torque_claim_discharges_end_to_end() -> None:
    """`drive: mech.drive_torque(...) <= 1.2 N*m` lowers through the
    real pipeline (the `N*m` native-unit bound) and discharges against
    `DriveTorqueModel`."""
    results = _discharge_by_name()
    drive = results["drive"]
    assert drive.deferral is None, drive.deferral
    assert drive.evidence is not None
    assert drive.evidence.status.value == "discharged"
    assert drive.evidence.model_id == "ballscrew_drive_torque@1"


def test_fatigue_damage_claim_missing_inputs_defers_honestly() -> None:
    """A `mech.fatigue.damage(...)` call missing one of the model's
    required keyword arguments defers by NAME (D97), never a silent
    pass or a fabricated request."""
    from regolith.orchestrator.translate import translate

    obligations = _obligations()
    spindle_ob = next(o for o in obligations if o.claim.name == "spindle")
    form = spindle_ob.claim.form
    assert isinstance(form, ClaimForm1), (
        f"expected a scalar-comparison form, got {form!r}"
    )
    patched_lhs = re.sub(r",\s*cycles_applied=5e5", "", form.lhs)
    patched = spindle_ob.model_copy(
        update={
            "claim": spindle_ob.claim.model_copy(
                update={"form": form.model_copy(update={"lhs": patched_lhs})}
            )
        }
    )
    lowered = translate(patched)
    assert lowered.is_err, lowered.danger_ok
    deferral = lowered.danger_err
    assert deferral.reason == "mech.fatigue.damage_inputs_missing"
    assert "cycles_applied" in deferral.detail


def test_drive_torque_claim_missing_inputs_defers_honestly() -> None:
    """A `mech.drive_torque(...)` call missing one of the model's
    required keyword arguments defers by NAME (D97), never a silent
    pass or a fabricated request."""
    from regolith.orchestrator.translate import translate

    obligations = _obligations()
    drive_ob = next(o for o in obligations if o.claim.name == "drive")
    form = drive_ob.claim.form
    assert isinstance(form, ClaimForm1), (
        f"expected a scalar-comparison form, got {form!r}"
    )
    patched_lhs = re.sub(r",\s*efficiency=0\.90", "", form.lhs)
    patched = drive_ob.model_copy(
        update={
            "claim": drive_ob.claim.model_copy(
                update={"form": form.model_copy(update={"lhs": patched_lhs})}
            )
        }
    )
    lowered = translate(patched)
    assert lowered.is_err, lowered.danger_ok
    deferral = lowered.danger_err
    assert deferral.reason == "mech.drive_torque_inputs_missing"
    assert "efficiency" in deferral.detail
