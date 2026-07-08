"""INV-3 Hint droppability (regolith/13-invariants.md).

Ledger statement:
    **For a fixed resolved design, verdicts are invariant under removal of
    all `@hint`s; `policy: prefer` only reorders exploration among
    claim-satisfying candidates.**

Mechanism (now end-to-end): WO-05 types `@hint(...)` as a verdict-inert
`HintStmt` (grammar, alongside the OwnershipStmt/QueryStmt precedent) and
`policy: prefer` as a `PolicyBlock`/`PolicyRule`; neither is read by any
`regolith-lower` pass, so an obligation's content hash -- and therefore the
`compiler.check` payload and the harness discharge verdict -- is BYTE
INVARIANT under their presence. The orchestrator candidate/discharge loop
(`orchestrator.build` at `BuildTier.BUILD`) drives the harness registry's
cost-ordered candidate enumeration to a real verdict, so the invariant is
exercised on a genuinely *resolved* design, not an empty one.

This module is part of the WO-17 invariant suite: the implementation's
contract with the spec. A spec change that alters INV-3's proof argument
must change this module in the same commit.

The proof reduces to construction: anything load-bearing must arrive as a
checked fact, a registry record, or an `assume!`; the hint channel emits
no CST node any lowering pass consumes, so it structurally cannot carry a
fact. The tests diff the verdict SET with and without the hints -- a hint
that changed a verdict would break the diff and fail loudly.
"""

from __future__ import annotations

import json

from regolith import compiler
from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.tiers import BuildTier

# A resolved cantilever-beam design: the `require` subject is exactly the
# shipped harness model's claim kind (`mech.beam.cantilever_deflection`),
# and the `loads:` block pins every model input, so the obligation
# discharges to a real `discharged` verdict through the candidate loop.
_BEAM_BODY = (
    "    loads:\n"
    "        force: [10, 20]\n"
    "        length: [0.1, 0.1]\n"
    "        e_modulus: [200e9, 200e9]\n"
    "        i_area: [1e-8, 1e-8]\n"
    "    require Deflection:\n"
    "        mech.beam.cantilever_deflection: <= 0.001\n"
)

# The same design carrying rung-3 redirects: an `@hint(...)` annotation and
# a `policy: prefer` block. By INV-3 both are droppable.
_HINTS = (
    "    @hint(regime=small_deflection)\n"
    "    policy:\n"
    "        prefer vendor(ti) over vendor(onsemi)\n"
)


def _verdict_set(src: str, tmp_path, name: str) -> frozenset[tuple[str, str]]:  # type: ignore[no-untyped-def]
    """Discharge ``src`` through the orchestrator and return its verdict set.

    Each element is ``(obligation subject_ref, status)`` -- the identity the
    invariant demands be invariant. Discharge runs at ``BuildTier.BUILD``
    (candidate enumeration + harness verdict, no lazy loop)."""
    path = tmp_path / name
    path.write_text(src, encoding="ascii")
    report = build((str(path),), BuildTier.BUILD).danger_ok
    verdicts: set[tuple[str, str]] = set()
    for result in report.results:
        status = (
            result.evidence.status.value if result.evidence is not None else "deferred"
        )
        verdicts.add((result.subject_ref, status))
    return frozenset(verdicts)


def _obligation_hashes(src: str, tmp_path, name: str) -> list[str]:  # type: ignore[no-untyped-def]
    """The core-emitted obligation subject refs for ``src`` (content ids)."""
    path = tmp_path / name
    path.write_text(src, encoding="ascii")
    payload = json.loads(compiler.check((str(path),)).danger_ok.payload_json)
    return sorted(o["subject_ref"] for o in payload["obligations"])


def test_inv_03_hints_and_policy_prefer_are_droppable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The primary INV-3 fixture: one resolved design, discharged twice --
    once with `@hint`/`policy: prefer` present, once with them removed --
    must yield the identical verdict set. A hint that changed a verdict
    would break this diff (that is the invariant's whole point)."""
    with_hints = "part flange:\n" + _HINTS + _BEAM_BODY
    without = "part flange:\n" + _BEAM_BODY

    hinted = _verdict_set(with_hints, tmp_path, "hinted.hema")
    plain = _verdict_set(without, tmp_path, "plain.hema")

    # Non-vacuity: the design is genuinely resolved (a real obligation that
    # a model discharged), not an empty verdict set that is trivially equal.
    assert plain, "the beam design must produce at least one obligation"
    assert any(status == "discharged" for _ref, status in plain), (
        f"the design must discharge a real verdict, got {plain}"
    )

    # The invariant: verdicts are invariant under hint removal.
    assert hinted == plain, (
        "dropping @hint/policy:prefer changed the verdict set (INV-3 violated): "
        f"with-hints={hinted} without={plain}"
    )


def test_inv_03_hints_do_not_perturb_obligation_identity(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The structural half of the proof: a hint emits no CST node any
    lowering pass reads, so the obligation content hashes are byte-identical
    with and without the hint channel -- the verdict invariance above is a
    corollary of this content-address invariance (INV-1)."""
    with_hints = "part flange:\n" + _HINTS + _BEAM_BODY
    without = "part flange:\n" + _BEAM_BODY
    assert _obligation_hashes(with_hints, tmp_path, "h.hema") == _obligation_hashes(
        without, tmp_path, "p.hema"
    ), "an @hint/policy:prefer perturbed obligation identity"


def test_inv_03_the_verdict_diff_has_teeth(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A negative control proving the droppability assertion is not vacuous:
    a change to the *checked* content (the limit, a rung-1 assert -- NOT a
    hint) flips the verdict, so the diff the primary test relies on would
    indeed catch a hint that illegitimately altered a verdict."""
    passing = "part flange:\n" + _BEAM_BODY
    failing = passing.replace("<= 0.001", "<= 0.0000001")
    assert _verdict_set(passing, tmp_path, "ok.hema") != _verdict_set(
        failing, tmp_path, "bad.hema"
    ), "a real content change must move the verdict set (else the diff is blind)"
