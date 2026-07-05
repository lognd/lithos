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

Coverage status (honest, tracked). The candidate/discharge loop and the
canonical-`any` orbit machinery are now wired through the facade, so two of
the six enumerated defaults have real, end-to-end loud-failure fixtures:

  * EAGER CANDIDATE ACCEPTANCE (build/09): the harness registry enumerates
    cost-ordered candidates and accepts a claim-satisfying one -- but every
    candidate still faces full margin verification, so an eagerly-accepted
    candidate that cannot close comes back `violated`, and an empty
    candidate set comes back `indeterminate`; both fail the release gate
    loudly, never a silent pass.
  * CANONICAL `any` (build/INV-18): the default picks the orbit's canonical
    representative, legal only on an intact orbit; over a broken or
    undeclared orbit the default is wrong and surfaces as a loud E0502.

The remaining four defaults -- free-variable resolution, implicit `by
spec`, local tolerance allocation, derived workloads -- depend on resolver
provenance (WO-04), conformance/tolerance allocation (WO-12), and
derived-intent workload lowering that are NOT yet wired through the facade,
so no default-wrong case can be honestly constructed for them here. They
are enumerated below as explicit `xfail`s with precise reopen criteria
rather than faked; when their machinery lands, each gets a real fixture in
this module (the meta-invariant's enumeration stays complete and honest).
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


@pytest.mark.xfail(
    reason=(
        "Free-variable resolution default not reachable: the resolver "
        "(WO-04) does not run through the facade, so a `free` variable with "
        "no resolving Cause cannot be constructed to surface loudly (INV-21 "
        "makes a causeless value unrepresentable in the type, but no facade "
        "path emits a resolved value yet). Reopen when regolith-lower feeds "
        "resolved values with their Cause through compiler.compile."
    ),
    strict=True,
)
def test_inv_26_free_variable_without_a_cause_is_loud() -> None:
    """Placeholder for the free-variable-resolution default's loud case."""
    raise NotImplementedError("WO-04 resolver wiring not yet through the facade")


@pytest.mark.xfail(
    reason=(
        "Implicit `by spec` default not reachable end-to-end: WO-12 collects "
        "conformance edges and claims.rs emits a conformance obligation per "
        "impl/extern/import binding (BE-6), but no harness model discharges a "
        "conformance claim to a real verdict, so a lower realization that "
        "contradicts its implicit-by-spec upper contract cannot be shown to "
        "fail loudly. Reopen when a conformance model discharges the "
        "conformance obligation kind."
    ),
    strict=True,
)
def test_inv_26_implicit_by_spec_contradiction_is_loud() -> None:
    """Placeholder for the implicit-`by spec` default's loud case."""
    raise NotImplementedError("conformance discharge not yet wired")


@pytest.mark.xfail(
    reason=(
        "Local tolerance-allocation default not reachable: tolerance "
        "allocation (WO-12) is not lowered through the facade, so a case "
        "where the local default under-allocates a stack-up cannot be "
        "constructed. Reopen when tolerance allocation lowers into "
        "obligations the harness discharges."
    ),
    strict=True,
)
def test_inv_26_local_tolerance_allocation_shortfall_is_loud() -> None:
    """Placeholder for the local-tolerance-allocation default's loud case."""
    raise NotImplementedError("tolerance allocation not yet lowered")


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
