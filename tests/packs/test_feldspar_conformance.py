"""WO-27 lithos-side conformance run: the real `feldspar` distribution
run from OUTSIDE the regolith package (the design doc's "outside-
consumer proof" of the whole WO-20/21/30 plugin contract).

This is the SCALAR conformance half named in the WO file (parametric
ports, corner sweep, signing) -- dispatchable once WO-20/21/22's engine
half and WO-30's pack contract v2 are in place, all true in this repo.
The PAYLOAD half (WO-22 end-to-end `geometry.realized` emission from a
real `.hema` lowering) stays honestly out of scope: WO-22 status is
still "engine half only" here (feature-program emission from
`regolith-lower` is blocked upstream), so no test in this module routes
a payload-ref through the discharge channel -- every request below
carries only the SCALAR named-port inputs feldspar's models declare.

Skips whole-module if `feldspar` is not installed in this environment
(``pip install`` it non-editable per the dispatch instructions to run
this suite for real). Does not require `ccx`/`gmsh` on PATH: at the
eps budget these requests carry, feldspar's own internal planner
always finds its cheaper closed-form direction sufficient (proven
live below), so no discretized solve is invoked; this mirrors
feldspar's own "FEA-marked tests ... run the first time the
environment has the tools" posture -- nothing here claims to exercise
the discretized ccx/gmsh path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("feldspar")

from feldspar import __version__ as feldspar_version  # noqa: E402
from feldspar.pack.models import (  # noqa: E402
    DEFAULT_STRESS_CLAIM_KIND,
    FeaStaticStressModel,
)
from regolith.harness import (  # noqa: E402
    DischargeRequest,
    Interval,
    ModelRegistry,
    default_registry,
)
from regolith.harness.models import register_all  # noqa: E402
from regolith.harness.models.lame_cylinder import (  # noqa: E402
    CLAIM_KIND as LAME_CLAIM_KIND,
)
from regolith.harness.quantity import bits_to_f64  # noqa: E402
from regolith.magnetite import KeyDesignation, TrustKeySet, TrustTier  # noqa: E402
from regolith.magnetite.trust import generate_signing_key  # noqa: E402
from regolith.orchestrator.orchestrate import build  # noqa: E402
from regolith.orchestrator.tiers import BuildTier  # noqa: E402

# The five scalar ports both feldspar models under test require, at a
# fixed thin-wall-cylinder corner (SI base units): pressure 5 MPa,
# 20/21 mm bore/OD, steel modulus/Poisson. feldspar's own bore-stress
# direction evaluates this to ~105.15 MPa (checked live, not hand-
# derived) -- so a 110 MPa limit is a THIN margin discharge (~4.6%)
# and a 100 MPa limit is a violation, both exercised below.
_STRESS_INPUTS = {
    "mech.load.internal_pressure": Interval(lo=5e6, hi=5e6),
    "mech.geom.cylinder.inner_radius": Interval(lo=0.02, hi=0.02),
    "mech.geom.cylinder.outer_radius": Interval(lo=0.021, hi=0.021),
    "mech.material.youngs_modulus": Interval(lo=200e9, hi=200e9),
    "mech.material.poisson": Interval(lo=0.3, hi=0.3),
}
_THIN_MARGIN_LIMIT = 110e6

# A `.hema` fixture in the fixture-pack style (WO-20 `test_pack_protocol.
# py`'s `_FIXTURE_SOURCE`): named `loads:` pin the scalar ports directly,
# and `require` states the claim kind verbatim (lowering's `translate.py`
# takes `claim_kind = obligation.claim.name or form.lhs` -- no vocabulary
# gate blocks an unregistered-in-this-repo kind string at parse time).
_FEA_SOURCE = f"""\
part cylinder_shell:
    loads:
        mech.load.internal_pressure: [5e6, 5e6]
        mech.geom.cylinder.inner_radius: [0.02, 0.02]
        mech.geom.cylinder.outer_radius: [0.021, 0.021]
        mech.material.youngs_modulus: [200e9, 200e9]
        mech.material.poisson: [0.3, 0.3]
    require Structural:
        {DEFAULT_STRESS_CLAIM_KIND}: <= {_THIN_MARGIN_LIMIT:g}
"""


def _stress_request(limit: float) -> DischargeRequest:
    """A `mech.static_stress` request over the fixed cylinder corner."""
    return DischargeRequest(
        claim_kind=DEFAULT_STRESS_CLAIM_KIND,
        limit=limit,
        inputs=dict(_STRESS_INPUTS),
    )


def _registry_without_feldspar() -> ModelRegistry:
    """Built-ins only -- the pack "uninstalled" (no entry point composed).

    Simulates uninstalling feldspar without any regolith code change:
    the caller simply does not run `load_packs`, exactly what happens
    when the distribution is absent from the environment.
    """
    registry = ModelRegistry()
    register_all(registry)
    return registry


# -- acceptance 1: real-pack discovery + protocol conformance ---------------


def test_feldspar_registers_via_entry_point() -> None:
    """`default_registry()` discovers the installed feldspar distribution
    and merges its two models after the built-ins (D-B composition)."""
    registry = default_registry()
    pack_names = [p.name for p in registry.packs]
    assert "feldspar" in pack_names
    stress_models = [
        m.model_id
        for m in registry.candidates(DEFAULT_STRESS_CLAIM_KIND)
        if registry.pack_of(m.model_id)[0] == "feldspar"
    ]
    assert stress_models, "feldspar must register a mech.static_stress model"


def test_feldspar_pack_selection_and_discharge_and_determinism() -> None:
    """The REAL installed feldspar distribution, discovered exactly as
    `default_registry()` discovers it (no fake entry point -- this pack
    IS installed in the environment, so the WO-20 fake-entry-point
    conformance helper in `conformance.py` does not apply: composing
    it a second time would double-register and trip the loud
    duplicate-id guard, which is the correct behavior, not a bug).

    Exercises the same protocol surface that helper checks: selection
    picks a feldspar model for its own claim kind, discharge is total
    (a value, never an exception), and repeat discharge is
    byte-identical (INV-10) -- the outside-consumer proof WO-27 asks
    for, run against the real distribution rather than a synthetic
    fixture pack."""
    # Compare against feldspar's own `__version__` (the string `pack_of`
    # actually registers under), not `importlib.metadata` -- the wheel's
    # packaging metadata is sourced from a separate Cargo workspace
    # version field that can lag `__version__` across a bump, which is
    # not this test's concern (it only asserts the attestation names the
    # feldspar pack, not that upstream packaging metadata is in sync).
    registry = default_registry()
    request = _stress_request(_THIN_MARGIN_LIMIT)

    selected = registry.select(request)
    assert selected.is_ok
    assert registry.pack_of(selected.danger_ok.model_id) == (
        "feldspar",
        feldspar_version,
    )

    evidence = registry.discharge(request)
    assert evidence.status.value == "discharged"
    again = registry.discharge(request)
    assert again == evidence, "repeat discharge must be byte-identical"


# -- acceptance: thin-margin discharge through orchestrator.build ----------


def test_thin_margin_stress_claim_discharged_by_fea_pack_via_build(
    tmp_path: Path,
) -> None:
    """A thin-margin `mech.static_stress` claim that no closed-form model
    in this repo even registers for (an honest, total no-model absence,
    the strongest form of "the closed-form tier leaves it
    indeterminate") is DISCHARGED by the real feldspar pack through
    `orchestrator.build`, with signed evidence and coverage stated."""
    source_path = tmp_path / "cylinder_shell.hema"
    source_path.write_text(_FEA_SOURCE, encoding="ascii")

    key = generate_signing_key(str(tmp_path), "conformance-key")
    assert key.is_ok
    signer = key.danger_ok
    trust_keys = TrustKeySet().designate(
        KeyDesignation(
            key_id=signer.key_id,
            public_key_base64=signer.public_key_base64(),
            confers=TrustTier.CERTIFIED,
        )
    )

    report = build(
        (str(source_path),),
        BuildTier.BUILD,
        signer=signer,
        trust_keys=trust_keys,
    )
    report_ok = report.danger_ok
    assert report_ok.obligations_discharged >= 1

    fea_results = [
        r
        for r in report_ok.results
        if r.evidence is not None
        and r.evidence.model_id.startswith("fea_static_stress")
    ]
    assert fea_results, "the feldspar model must have discharged the claim"
    result = fea_results[0]
    assert result.evidence.status.value == "discharged"
    assert result.evidence.coverage is not None
    # Signed AND verified against the designated key set: `Valid(tier)`,
    # never the bare `Unsigned` default arm or a present-but-unverifiable
    # `Invalid` (the WO text's "verifies Valid(tier) under a designated
    # key set").
    assert result.attestation.kind == "valid"
    assert result.attestation.tier == TrustTier.CERTIFIED


def test_uninstalling_the_pack_reverts_to_honest_indeterminate(
    tmp_path: Path,
) -> None:
    """Acceptance 2: the SAME `.hema` source, run with the pack absent
    (no `load_packs` composition -- exactly what "uninstalled" means),
    reverts the claim to `harness.no_model` -- no regolith code change,
    only which packs happen to be on the machine."""
    source_path = tmp_path / "cylinder_shell.hema"
    source_path.write_text(_FEA_SOURCE, encoding="ascii")

    report = build(
        (str(source_path),),
        BuildTier.BUILD,
        registry=_registry_without_feldspar(),
    )
    report_ok = report.danger_ok
    no_model_results = [
        r
        for r in report_ok.results
        if r.evidence is not None and r.evidence.status.value == "indeterminate"
    ]
    assert no_model_results, "absent the pack, the claim must be honest-indeterminate"
    assert report_ok.obligations_discharged == 0


# -- acceptance 3: determinism ----------------------------------------------


def test_same_request_twice_is_byte_identical_evidence() -> None:
    """Acceptance 3: discharging the same request twice through two
    independently constructed (but identically composed) registries
    produces a byte-identical evidence hash -- determinism through the
    pack's own settings digest (INV-10), not incidental process state."""
    first = default_registry().discharge(_stress_request(_THIN_MARGIN_LIMIT))
    second = default_registry().discharge(_stress_request(_THIN_MARGIN_LIMIT))
    assert first.hash == second.hash
    assert first == second


# -- best-path ordering: cost still decides model selection -----------------


def test_cheaper_closed_form_model_is_selected_over_the_fea_pack() -> None:
    """`ModelRegistry.select` is a pure (cost, model id) order (`registry.
    py`): registering feldspar's real model under the SAME claim kind a
    cheap closed-form model already owns (the OPEN-6 `claim_kind=`
    override interim feldspar's own model constructors document)
    proves the cheaper tier wins the registry's one shared graph,
    exactly D-A's "one best-path graph" design decision -- regardless
    of how fat or thin the margin is, since selection has no
    margin-conditioned fallback today (a residual worth naming, not
    invented here)."""
    registry = ModelRegistry()
    register_all(registry)  # includes LameCylinderModel, cost=1
    registry.register(FeaStaticStressModel(claim_kind=LAME_CLAIM_KIND))  # cost=10

    request = DischargeRequest(
        claim_kind=LAME_CLAIM_KIND,
        limit=200e6,
        inputs={
            # lame_cylinder's own port names ...
            "pressure": Interval(lo=5e6, hi=5e6),
            "r_inner": Interval(lo=0.02, hi=0.02),
            "r_outer": Interval(lo=0.021, hi=0.021),
            # ... union'd with feldspar's, so BOTH candidates match.
            **_STRESS_INPUTS,
        },
    )
    selected = registry.select(request)
    assert selected.is_ok
    assert registry.pack_of(selected.danger_ok.model_id)[0] != "feldspar"
    assert selected.danger_ok.cost == 1


def test_value_at_the_fixed_corner_is_the_thin_margin_it_claims_to_be() -> None:
    """Documents the live number the fixture's `_THIN_MARGIN_LIMIT` is
    pinned against, so a future eps/physics change in feldspar cannot
    silently turn this from a thin-margin discharge into a violation
    without the fixture's own assertion catching it first."""
    evidence = default_registry().discharge(_stress_request(_THIN_MARGIN_LIMIT))
    assert evidence.status.value == "discharged"
    value = bits_to_f64(evidence.value_bits)
    margin = (_THIN_MARGIN_LIMIT - value) / _THIN_MARGIN_LIMIT
    assert 0.0 < margin < 0.10, f"fixture drifted off its thin-margin corner: {margin}"
