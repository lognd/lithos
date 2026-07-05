"""INV-26 Defaults-test compliance (meta-invariant) (substrate/13-invariants.md).

Ledger statement:
    **Every default behavior in either language is conservative, local in
    effect, and lockfile-materialized.**

This is an invariant *over the spec itself*: the defaults are enumerable
(free-variable resolution, implicit `by spec`, local tolerance allocation,
canonical `any`, eager candidate acceptance, derived workloads), and each
gets a "spurious-failure-not-silent-pass" test -- per default, construct
the case where the default is wrong and assert the failure mode is LOUD.

This module is part of the WO-17 invariant suite: a spec change that alters
INV-26's proof argument must change this module in the same commit.

Coverage status (honest, tracked). The candidate/discharge loop, the
canonical-`any` orbit machinery, the eager-DFM `free`-resolution path, the
local tolerance-allocation stack-up, and the implicit-`by spec` conformance
refinement are now wired through the facade, so five of the six enumerated
defaults have real, end-to-end loud-failure fixtures:

  * EAGER CANDIDATE ACCEPTANCE (build/09): the harness registry enumerates
    cost-ordered candidates and accepts a claim-satisfying one -- but every
    candidate still faces full margin verification, so an eagerly-accepted
    candidate that cannot close comes back `violated`, and an empty
    candidate set comes back `indeterminate`; both fail the release gate
    loudly, never a silent pass.
  * CANONICAL `any` (build/INV-18): the default picks the orbit's canonical
    representative, legal only on an intact orbit; over a broken or
    undeclared orbit the default is wrong and surfaces as a loud E0502.
  * FREE-VARIABLE RESOLUTION (build/09, value-sources/03): a `free`
    dimension is resolved eagerly by its DFM model (the sheet-metal
    min-bend-radius pack resolves the free bend radius to the manufacturable
    minimum). When the design's demanded window is tighter than the
    eagerly-resolved value the default is wrong -- the bend cannot be made
    -- and it surfaces as a loud `violated` + release-gate refusal, not a
    silent pass. A negative control proves an achievable window stays clean.
  * LOCAL TOLERANCE ALLOCATION (hematite/03 sec. 5): tolerances are
    allocated locally by default (loosest process-capable band, `worst_case`
    policy). The stack-up model sums the locally-allocated contributor bands
    at their worst corner; when that default allocation already overruns the
    assembly window the local default cannot close the chain (the E0432
    condition) and comes back `violated` + release-gated, never a silent
    pass. A negative control proves a closable chain discharges.

The implicit-`by spec` default now has a real fixture too: the compiler
threads the upper contract's and lower realization's comparator bounds into
the conformance obligation's `given.loads`, and the orchestrator bridge
(`orchestrator.translate`) lowers that into the harness conformance model,
so a realization that contradicts its spec discharges `violated` and is
release-gated. The remaining ONE default -- derived workloads -- depends on
derived-intent workload lowering NOT yet wired through the facade, so no
default-wrong case can be honestly constructed for it here. It is
enumerated below as an explicit `xfail` with a precise reopen criterion
rather than faked; when its machinery lands it gets a real fixture (the
meta-invariant's enumeration stays complete and honest).
"""

from __future__ import annotations

import json

import pytest
from regolith import compiler
from regolith.orchestrator.orchestrate import build, release_gate
from regolith.orchestrator.tiers import BuildTier

# INV-4/18 diagnostic: `any` over a broken/undeclared orbit (E0502).
_BROKEN_ORBIT_ANY = {"family": "instances", "offset": 2}

# A cantilever-beam claim whose subject is the shipped harness model's claim
# kind, with every model input pinned by the `loads:` block.
_BEAM_LOADS = (
    "    loads:\n"
    "        force: [10, 20]\n"
    "        length: [0.1, 0.1]\n"
    "        e_modulus: [200e9, 200e9]\n"
    "        i_area: [1e-8, 1e-8]\n"
)


def _discharge(src: str, tmp_path, name: str):  # type: ignore[no-untyped-def]
    """Discharge ``src`` at ``BuildTier.BUILD`` (candidate loop + harness)."""
    path = tmp_path / name
    path.write_text(src, encoding="ascii")
    return build((str(path),), BuildTier.BUILD).danger_ok


def _codes(payload: dict) -> list[dict]:
    return [d["code"] for d in payload["diagnostics"]]


# --------------------------------------------------------------------------
# Default 1: eager candidate acceptance -- must never silently pass.
# --------------------------------------------------------------------------


def test_inv_26_eager_candidate_that_cannot_close_is_loud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A claim whose eagerly-accepted candidate cannot close the margin must
    come back `violated` and fail the release gate -- the default (accept a
    candidate) is verdict-neutral, so a wrong default is loud, not silent."""
    src = (
        "part flange:\n"
        + _BEAM_LOADS
        + "    require Deflection:\n"
        + "        mech.beam.cantilever_deflection: <= 0.0000001\n"
    )
    report = _discharge(src, tmp_path, "tight.hem")
    statuses = [r.evidence.status.value for r in report.results if r.evidence]
    assert "violated" in statuses, (
        f"an over-tight claim must discharge violated, got {statuses}"
    )
    assert release_gate(report.results).is_err, (
        "a violated obligation must fail the release gate loudly (INV-24/26)"
    )


def test_inv_26_empty_candidate_set_defers_loud_never_passes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A claim with NO candidate model must come back `indeterminate`
    (an honest deferral), release-gated -- eager acceptance of the empty
    candidate set is impossible: the total registry refuses to invent a
    pass, so the default surfaces loudly rather than green-by-omission."""
    src = "part w:\n    require R:\n        no_such_model_claim: <= 1\n"
    report = _discharge(src, tmp_path, "nomodel.hem")
    assert report.results, "the claim must produce an obligation to discharge"
    assert all(not r.is_resolved for r in report.results), (
        "a modelless claim must never resolve to a pass"
    )
    assert any(r.is_indeterminate for r in report.results), (
        "a modelless claim must surface as an honest indeterminate/deferral"
    )
    assert release_gate(report.results).is_err, (
        "an unresolved obligation must fail the release gate loudly (INV-24/26)"
    )


# --------------------------------------------------------------------------
# Default 2: canonical `any` -- legal only on an intact orbit.
# --------------------------------------------------------------------------


def test_inv_26_canonical_any_over_a_broken_orbit_is_loud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The canonical-`any` default (pick the orbit's canonical representative)
    is legal only on an intact orbit. Over a broken orbit (`pattern` then
    `break` then `any`) the default is wrong and must surface as a loud
    E0502, not a silent extension across a collapsed orbit."""
    src = "part p:\n    pattern ring circular 4\n    break ring\n    any ring\n"
    path = tmp_path / "any.hem"
    path.write_text(src, encoding="ascii")
    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    assert _BROKEN_ORBIT_ANY in _codes(payload), (
        f"canonical `any` over a broken orbit must be loud: {payload['diagnostics']}"
    )


def test_inv_26_canonical_any_over_a_live_orbit_is_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Negative control: an intact declared orbit licenses the canonical
    representative, so the default is right and stays silent (no E0502) --
    proving the loud-failure test above is not a blanket rejection of `any`."""
    src = "part p:\n    pattern ring circular 4\n    any ring\n"
    path = tmp_path / "any_ok.hem"
    path.write_text(src, encoding="ascii")
    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    assert _BROKEN_ORBIT_ANY not in _codes(payload), payload["diagnostics"]


# --------------------------------------------------------------------------
# The four defaults whose machinery is not yet wired through the facade.
# Honest, tracked xfails with precise reopen criteria (never faked).
# --------------------------------------------------------------------------


# Inputs for the sheet-metal DFM resolver: a 1.5 mm gauge with a 1.6
# min-inside-radius ratio resolves the free bend radius to 2.4 mm.
_BEND_LOADS = (
    "    loads:\n        thickness: [0.0015, 0.0015]\n        ratio: [1.6, 1.6]\n"
)


def test_inv_26_free_variable_resolution_infeasible_is_loud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The free-variable-resolution default (resolve a `free` dimension to
    its DFM value) is wrong when the demanded window is tighter than the
    manufacturable minimum: the free bend radius resolves to 2.4 mm, so a
    design demanding <= 2.0 mm cannot be made and must come back `violated`
    + release-gated -- eager resolution is verdict-neutral, so a wrong
    default is loud, never a silent pass."""
    src = (
        "part flange:\n"
        + _BEND_LOADS
        + "    require BendRadius:\n"
        + "        mech.sheet.min_bend_radius: <= 0.002\n"
    )
    report = _discharge(src, tmp_path, "free_tight.hem")
    statuses = [r.evidence.status.value for r in report.results if r.evidence]
    assert "violated" in statuses, (
        f"an infeasible free-resolution must discharge violated, got {statuses}"
    )
    assert release_gate(report.results).is_err, (
        "a violated free resolution must fail the release gate loudly (INV-24/26)"
    )


def test_inv_26_free_variable_resolution_feasible_is_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Negative control: a window that admits the eagerly-resolved free value
    (2.4 mm <= 3.0 mm) discharges cleanly and passes the release gate --
    proving the loud case above is not a blanket rejection of `free`."""
    src = (
        "part flange:\n"
        + _BEND_LOADS
        + "    require BendRadius:\n"
        + "        mech.sheet.min_bend_radius: <= 0.003\n"
    )
    report = _discharge(src, tmp_path, "free_ok.hem")
    assert all(r.is_resolved for r in report.results), (
        "a feasible free resolution must discharge cleanly"
    )
    assert release_gate(report.results).is_ok, "a feasible free resolution passes"


# An upper contract (`interface Seat`) promising `q <= 20`, realized by an
# `impl Seat for self`. The implicit-`by spec` default trusts the impl
# refines the spec; the compiler threads both bounds into the conformance
# obligation's `given.loads`, and the harness conformance model discharges
# the refinement end-to-end through the orchestrator bridge.
def _conformance_src(impl_bound: str) -> str:
    return (
        "interface Seat:\n"
        "    q: <= 20\n"
        "part bracket:\n"
        "    impl Seat for self:\n"
        f"        q: {impl_bound}\n"
    )


def test_inv_26_implicit_by_spec_contradiction_is_loud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The implicit-`by spec` default (a realizable spec gets an implicit
    `by spec` impl, trusted to refine it) is wrong when the realization
    contradicts its upper contract: a `q <= 25` impl under a `q <= 20` spec
    promises a WIDER window than the spec, so the conformance obligation
    discharges `violated` and fails the release gate loudly -- never a
    silent pass. Reaches the harness conformance model through the real
    obligation->DischargeRequest bridge (INV-13 discharge half, AD-1)."""
    report = _discharge(_conformance_src("<= 25"), tmp_path, "conform_bad.hem")
    statuses = [r.evidence.status.value for r in report.results if r.evidence]
    assert "violated" in statuses, (
        f"a contradicting impl must discharge violated, got {statuses}"
    )
    assert release_gate(report.results).is_err, (
        "a violated conformance obligation must fail the release gate (INV-24/26)"
    )


def test_inv_26_implicit_by_spec_refinement_is_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Negative control: a realization that genuinely refines its spec
    (`q <= 14` under `q <= 20`) discharges cleanly and passes the release
    gate -- proving the loud case above is not a blanket rejection of the
    implicit-`by spec` default."""
    report = _discharge(_conformance_src("<= 14"), tmp_path, "conform_ok.hem")
    assert all(r.is_resolved for r in report.results), (
        "a conforming refinement must discharge cleanly"
    )
    assert release_gate(report.results).is_ok, "a sound refinement passes the gate"


# A three-link tolerance chain whose contributors are each allocated the
# loosest process-capable 0.1 mm band by the local default.
_STACK_LOADS = (
    "    loads:\n"
    "        contrib_a: [0.0001, 0.0001]\n"
    "        contrib_b: [0.0001, 0.0001]\n"
    "        contrib_c: [0.0001, 0.0001]\n"
)


def test_inv_26_local_tolerance_allocation_shortfall_is_loud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The local tolerance-allocation default (loosest process-capable band,
    `worst_case` policy, no cross-part flow) is wrong when the locally-
    allocated bands already sum past the assembly window: a 0.3 mm worst-case
    stack against a 0.25 mm demand cannot close the chain (the E0432
    condition) and must come back `violated` + release-gated -- the default
    allocation is loud when it cannot close, never a silent pass."""
    src = (
        "part chain:\n"
        + _STACK_LOADS
        + "    require Stack:\n"
        + "        mech.tolerance.worst_case_stack: <= 0.00025\n"
    )
    report = _discharge(src, tmp_path, "stack_tight.hem")
    statuses = [r.evidence.status.value for r in report.results if r.evidence]
    assert "violated" in statuses, (
        f"an unclosable local allocation must discharge violated, got {statuses}"
    )
    assert release_gate(report.results).is_err, (
        "an unclosable tolerance chain must fail the release gate (INV-24/26)"
    )


def test_inv_26_local_tolerance_allocation_that_closes_is_clean(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Negative control: a chain whose local allocation closes (0.3 mm stack
    <= 0.35 mm window) discharges cleanly and passes the release gate --
    proving the loud case above is not a blanket rejection of the default."""
    src = (
        "part chain:\n"
        + _STACK_LOADS
        + "    require Stack:\n"
        + "        mech.tolerance.worst_case_stack: <= 0.00035\n"
    )
    report = _discharge(src, tmp_path, "stack_ok.hem")
    assert all(r.is_resolved for r in report.results), (
        "a closable local allocation must discharge cleanly"
    )
    assert release_gate(report.results).is_ok, "a closable chain passes the gate"


@pytest.mark.xfail(
    reason=(
        "Derived-workloads default not reachable: derived-intent workload "
        "lowering (the `realizes`/derived-workload machinery) is not wired "
        "through the facade, so a derived workload whose default derivation "
        "is wrong cannot be surfaced. Reopen when derived workloads lower "
        "into obligations."
    ),
    strict=True,
)
def test_inv_26_derived_workload_wrong_default_is_loud() -> None:
    """Placeholder for the derived-workloads default's loud case."""
    raise NotImplementedError("derived-workload lowering not yet wired")
