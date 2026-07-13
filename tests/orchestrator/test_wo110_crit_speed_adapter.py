"""WO-110 scope item 2: the `mech.critical_speed(...)` call form
routes through the adapter onto the FELDSPAR pack's registered model
(adapter only -- the pack owns the physics, charter 39 sec. 4's
one-home rule), end to end. Also pins the adapter's verbatim
pack-port strings against the installed pack's signature (the WO-78
SI posture), and proves the `rms(...)` waveform-statistic exclusion
(scope item 5, the F131 2(c) style)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from regolith import compiler
from regolith._schema.models import Obligation
from regolith.harness import default_registry
from regolith.orchestrator import discharge_all
from regolith.orchestrator.cache import EvidenceStore
from regolith.orchestrator.translate import (
    _CRIT_SPEED_KIND,
    _CRIT_SPEED_PORTS,
    translate,
)

_FIXTURE = Path(__file__).parent / "data" / "wo110_crit_speed_fixture.hema"

_PACK_LOADED = _CRIT_SPEED_KIND in default_registry()._by_kind


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


@pytest.mark.skipif(not _PACK_LOADED, reason="feldspar pack not installed")
def test_adapter_ports_pin_the_installed_pack_signature() -> None:
    """The adapter's verbatim port strings match the pack's registered
    `ModelSignature.inputs` exactly -- a pack rename fails HERE, not as
    a silent fleet-wide inputs-missing regression."""
    models = default_registry()._by_kind[_CRIT_SPEED_KIND]
    assert any(set(m.signature.inputs) == set(_CRIT_SPEED_PORTS) for m in models)


@pytest.mark.skipif(not _PACK_LOADED, reason="feldspar pack not installed")
def test_crit_speed_discharges_through_the_pack_end_to_end() -> None:
    """k = 1.2e7 N/m, m = 3 kg -> 19098.6 rpm > 12000 rpm discharges
    THROUGH the pack model (no lithos-side physics)."""
    results = _discharge_by_name()
    crit = results["crit"]
    assert crit.deferral is None, crit.deferral
    assert crit.evidence is not None
    assert crit.evidence.status.value == "discharged"
    assert crit.evidence.model_id.startswith("mech_shaft_critical_speed")


@pytest.mark.skipif(not _PACK_LOADED, reason="feldspar pack not installed")
def test_undercritical_floor_is_honestly_violated() -> None:
    results = _discharge_by_name()
    slow = results["slow"]
    assert slow.deferral is None, slow.deferral
    assert slow.evidence is not None
    assert slow.evidence.status.value == "violated"


@pytest.mark.skipif(not _PACK_LOADED, reason="feldspar pack not installed")
def test_expression_bound_resolves_the_full_product_never_truncated() -> None:
    """`> 1.4 * 9200rpm` (the exact WO110-F1 evidence shape) must NOT
    parse as limit 1.4: WO-122's bound resolver evaluates the full
    scalar product in the pack's own rpm port unit (1.4 * 9200 =
    12880 rpm -- the route declares `rpm` native because the pack's
    output port is `mech.critical_speed.rpm`, so an SI conversion
    would mis-compare against the model's rpm output), and the claim
    discharges through the pack at that limit (19098.6 rpm >
    12880 rpm). The pre-WO-122 posture (guarded refusal,
    `unresolved_limit`) is superseded: the truncation hazard now
    resolves correctly instead of merely being refused."""
    results = _discharge_by_name()
    expr = results["expr"]
    assert expr.deferral is None, expr.deferral
    assert expr.evidence is not None
    assert expr.evidence.status.value == "discharged"


def test_missing_inputs_defer_naming_the_pack_ports() -> None:
    results = _discharge_by_name()
    undeclared = results["undeclared"]
    assert undeclared.deferral is not None
    assert undeclared.deferral.reason == f"{_CRIT_SPEED_KIND}_inputs_missing"
    for port in _CRIT_SPEED_PORTS:
        assert port in undeclared.deferral.detail


def test_rms_waveform_statistic_is_excluded_by_name() -> None:
    """scope item 5: `jitter: rms(x_step, band=[0Hz, 1kHz]) < 2us`
    defers `excluded_call_form` naming the form and the WO-111 route
    -- never an anonymous label-only no_model."""
    obligation = Obligation.model_validate(
        {
            "claim": {
                "name": "jitter",
                "form": {
                    "form": "comparison",
                    "lhs": "rms(x_step, band=[0Hz, 1kHz])",
                    "op": "<",
                    "rhs": "2us",
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
    lowered = translate(obligation)
    assert lowered.is_err
    deferral = lowered.danger_err
    assert deferral.reason == "excluded_call_form"
    assert "rms(...)" in deferral.detail
    assert "WO-111" in deferral.detail
