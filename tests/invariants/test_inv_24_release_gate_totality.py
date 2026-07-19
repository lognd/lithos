"""INV-24 Release-gate totality (regolith/13-invariants.md).

Ledger statement:
    **A `--release` build's report contains zero unaccepted violated or
    indeterminate obligations, and every acceptance is listed.**

Mechanism provided by: WO-13 (obligations) + the orchestrator release
gate. The orchestrator routes every obligation through the total harness
path and enforces the gate: any ``violated``/``indeterminate``/deferred
obligation that is not accepted fails ``--release`` (there is no
waiver/assume ledger yet, so nothing is accepted -- strictly conservative).
This is the deliberate-violation fixture the ledger statement requires.
"""

from __future__ import annotations

from pathlib import Path

from regolith.harness.evidence import build_evidence
from regolith.orchestrator import ObligationResult, release_gate
from regolith.orchestrator.acceptance import (
    AcceptanceOutcome,
    Deviation,
    compute_acceptance,
    match_set_growth_warnings,
)
from regolith.orchestrator.orchestrate import build, gate_summary_for
from regolith.orchestrator.tiers import BuildTier
from regolith.orchestrator.translate import Deferral

# A minimal design whose one claim has no harness model, so it stays
# genuinely indeterminate -- exactly the shape a `waive` exists for
# (D206/D207). The scoped waiver carries `by doc(<memo>)` evidence.
_DEVIATION_DESIGN = """part widget:
    require Strength:
        fatigue_life: >= 1e6
    waive Strength.fatigue_life on self:
        basis: "no fatigue model landed; accepted, see memo"
        by doc(memos/fatigue.md)
"""

_BARE_DESIGN = """part widget:
    require Strength:
        fatigue_life: >= 1e6
    waive Strength.fatigue_life on self:
        basis: "accepted; no evidence"
"""

_EXPIRED_DESIGN = """part widget:
    require Strength:
        fatigue_life: >= 1e6
    waive Strength.fatigue_life on self:
        basis: "accepted; concession lapsed"
        by doc(memos/fatigue.md)
        expires: 2020-01-01
"""

_MEMO = """# Fatigue acceptance memo

widget.Strength.fatigue_life has no landed model (WO wall). Discharge
path: a fatigue model in std.mech retires this waiver.
"""


def _write_design(tmp_path: Path, source: str, *, with_memo: bool) -> tuple[str, ...]:
    """Write a one-file design (and optionally its memo) under ``tmp_path``."""
    design = tmp_path / "widget.hema"
    design.write_text(source, encoding="ascii")
    if with_memo:
        memos = tmp_path / "memos"
        memos.mkdir(exist_ok=True)
        (memos / "fatigue.md").write_text(_MEMO, encoding="ascii")
    return (str(design),)


def _result(*, value: float, limit: float, subject: str) -> ObligationResult:
    """An upper-bound obligation result with honest margin math."""
    evidence = build_evidence(
        model_id="test.model@1",
        claim_kind="stress",
        sense_upper=True,
        value=value,
        eps=0.0,
        limit=limit,
        coverage=1.0,
        cost=1,
        in_domain=True,
        deterministic=True,
        registry_version="test-1",
        inputs_digest="d",
    )
    return ObligationResult(key=f"k:{subject}", subject_ref=subject, evidence=evidence)


# frob:tests python/regolith/orchestrator/discharge.py::ObligationResult.is_resolved
def test_inv_24_all_discharged_passes_release() -> None:
    """A report where every obligation discharged clears the gate."""
    results = (_result(value=50.0, limit=100.0, subject="a"),)
    assert results[0].is_resolved
    assert release_gate(results).is_ok


def test_inv_24_unaccepted_violation_fails_release() -> None:
    """A single unaccepted violated obligation refuses the release build."""
    results = (
        _result(value=50.0, limit=100.0, subject="ok"),
        _result(value=150.0, limit=100.0, subject="bad"),  # violated
    )
    assert results[1].is_violated
    gate = release_gate(results)
    assert gate.is_err
    assert gate.danger_err.kind == "release_gate_failed"


def test_inv_24_deferred_obligation_fails_release() -> None:
    """A deferral (no verdict formed) is not proven, so it gates release."""
    deferred = ObligationResult(
        key="k:deferred",
        subject_ref="deferred",
        deferral=Deferral(reason="no_model", detail="no harness model"),
    )
    assert deferred.is_indeterminate
    assert release_gate((deferred,)).is_err


# --- WO-98: the release gate consumes the waiver ledger (D206/D207) ---


# frob:tests python/regolith/orchestrator/orchestrate.py::GateSummary.stamp_text
# frob:tests python/regolith/orchestrator/orchestrate.py::gate_summary_for
def test_inv_24_evidence_deviation_passes_and_is_listed(tmp_path) -> None:
    """An indeterminate obligation + evidence-carrying scoped waive whose
    memo resolves builds ``--release`` green, with the deviation LISTED
    and counted distinctly (never folded into discharged)."""
    paths = _write_design(tmp_path, _DEVIATION_DESIGN, with_memo=True)
    report = build(paths, BuildTier.RELEASE).danger_ok
    assert report.ok
    assert report.release_ok
    counts = gate_summary_for(report).counts
    assert counts.accepted_deviation == 1
    assert counts.indeterminate == 0 and counts.violated == 0
    assert counts.clean
    dev = report.acceptance.deviations
    assert len(dev) == 1
    assert dev[0].target == "Strength.fatigue_life"
    assert dev[0].evidence == "doc(memos/fatigue.md)"
    assert dev[0].evidence_digest.startswith("blake3:")
    # The stamp names the acceptance -- never a bare "RELEASE-CLEAN".
    assert gate_summary_for(report).stamp_text == "RELEASE-CLEAN (1 accepted deviation)"


def test_inv_24_same_design_without_evidence_refuses(tmp_path) -> None:
    """The SAME design with the evidence ref removed (a bare waiver)
    refuses the release build (regolith/12 rule 3)."""
    paths = _write_design(tmp_path, _BARE_DESIGN, with_memo=False)
    report = build(paths, BuildTier.RELEASE).danger_ok
    assert not report.release_ok
    assert report.acceptance.accepted_hashes == ()
    assert report.acceptance.ledger_blocked
    assert any("bare waiver" in r for r in report.acceptance.refusals)


def test_inv_24_dangling_memo_ref_refuses(tmp_path) -> None:
    """A `by doc(<memo>)` ref that resolves to no in-project file refuses
    loudly (D207) -- never a silent community-tier fallback."""
    paths = _write_design(tmp_path, _DEVIATION_DESIGN, with_memo=False)
    report = build(paths, BuildTier.RELEASE).danger_ok
    assert not report.release_ok
    assert report.acceptance.accepted_hashes == ()
    assert any("dangling evidence" in e for e in report.acceptance.errors)


def test_inv_24_expired_waiver_refuses_and_errors(tmp_path) -> None:
    """An expired waiver behaves as absent (its obligation refuses again)
    AND surfaces the stale/expiry error (regolith/12 rule 8)."""
    paths = _write_design(tmp_path, _EXPIRED_DESIGN, with_memo=True)
    report = build(paths, BuildTier.RELEASE).danger_ok
    assert not report.release_ok
    assert report.acceptance.accepted_hashes == ()
    assert any("expired" in e for e in report.acceptance.errors)


# frob:tests python/regolith/orchestrator/acceptance.py::compute_acceptance
def test_inv_24_trust_floor_exceeding_claim_cannot_be_memo_waived() -> None:
    """A community memo cannot waive a claim whose trust floor exceeds
    community (regolith/12 rule 7, INV-14). Unit-level: the floor is
    asserted on the result directly -- the gate's binding of the DESIGNED
    channel. The SOURCE half (a `trust:` group directive populating
    `claim.trust_floor`) is proven end-to-end by
    `test_inv_24_source_trust_floor_blocks_community_memo` (F124.1)."""
    result = ObligationResult(
        key="k",
        content_hash="h1",
        subject_ref="widget.body",
        deferral=Deferral(reason="no_model", detail="no fatigue model"),
        trust_floor="certified",
    )
    ledger = {
        "entries": [
            {
                "waived": {
                    "kind": "matched",
                    "matched": ["h1"],
                    "match_set": ["h1"],
                    "waiver": {
                        "target": "Strength.fatigue_life",
                        "scope": "self",
                        "basis": "community memo only",
                        "evidence": "test(fai)",
                    },
                }
            }
        ]
    }
    outcome = compute_acceptance(
        ledger, (result,), project_root=".", record_search_paths=()
    )
    # The memo (community) does not meet a `certified` floor: not accepted.
    assert outcome.accepted_hashes == ()
    assert any("below the claim's trust floor" in e for e in outcome.errors)
    assert not release_gate((result,), outcome).is_ok


# A design whose group carries a `trust: >= certified` floor directive on
# a genuinely-indeterminate claim, waived by a COMMUNITY memo. Before
# F124.1 the source directive never reached `claim.trust_floor`, so the
# community memo silently accepted it; now the floor is populated at
# lowering time and the gate refuses the under-tier waiver end-to-end.
_TRUST_FLOOR_DESIGN = """part widget:
    require Strength:
        trust: >= certified
        fatigue_life: >= 1e6
    waive Strength.fatigue_life on self:
        basis: "no fatigue model landed; accepted, see memo"
        by doc(memos/fatigue.md)
"""


def test_inv_24_source_trust_floor_populates_claim() -> None:
    """F124.1: a group `trust: >= <tier>` directive populates the sibling
    claim's `trust_floor` at lowering time (from SOURCE, not just unit
    level), and does NOT emit a standalone `trust` claim obligation."""
    import json

    from regolith import compiler
    from regolith._schema.models import Obligation

    design = Path(__file__).parent / "_wo_f124_scratch.hema"
    design.write_text(_TRUST_FLOOR_DESIGN, encoding="ascii")
    try:
        result = compiler.check((str(design),))
        assert result.is_ok, result
        payload = json.loads(result.danger_ok.payload_json)
        obligations = [Obligation.model_validate(o) for o in payload["obligations"]]
        # The `trust:` directive is folded, never lowered as its own claim.
        assert all(o.claim.name != "trust" for o in obligations)
        fatigue = [o for o in obligations if o.claim.name == "fatigue_life"]
        assert fatigue, "fatigue_life obligation present"
        assert all(o.claim.trust_floor == "certified" for o in fatigue)
    finally:
        design.unlink()


def test_inv_24_source_trust_floor_blocks_community_memo(tmp_path) -> None:
    """F124.1 end-to-end: the SAME community-memo waiver that would accept a
    floorless indeterminate claim is REFUSED once the source `trust: >=
    certified` directive populates the floor -- the memo (community) is
    below the floor (regolith/12 rule 7, INV-14)."""
    paths = _write_design(tmp_path, _TRUST_FLOOR_DESIGN, with_memo=True)
    report = build(paths, BuildTier.RELEASE).danger_ok
    assert not report.release_ok
    assert report.acceptance.accepted_hashes == ()
    assert any("below the claim's trust floor" in e for e in report.acceptance.errors)


# frob:tests python/regolith/orchestrator/acceptance.py::match_set_growth_warnings
def test_inv_24_match_set_growth_warns() -> None:
    """An unscoped deviation whose accepted set grew vs the prior lockfile
    emits a loud warning naming the new members (regolith/12 rule 5)."""
    outcome = AcceptanceOutcome(
        accepted_hashes=("h1", "h2"),
        deviations=(
            Deviation(
                target="Manufacture.makeable",
                scope=None,
                basis="b",
                evidence="test(fai)",
                kind="matched",
                accepted=("h1", "h2"),
                match_set=("h1",),
                expires=None,
            ),
        ),
    )
    warnings = match_set_growth_warnings(
        outcome, {"Manufacture.makeable": frozenset({"h1"})}
    )
    assert len(warnings) == 1
    assert "GREW" in warnings[0] and "h2" in warnings[0]
    # A scoped deviation is exempt (its scope is the reviewed boundary).
    scoped = outcome.model_copy(
        update={
            "deviations": (outcome.deviations[0].model_copy(update={"scope": "s"}),)
        }
    )
    assert (
        match_set_growth_warnings(scoped, {"Manufacture.makeable": frozenset({"h1"})})
        == ()
    )


def test_inv_24_cli_accept_is_exploration_only(tmp_path) -> None:
    """`--accept <target>` lets a bare waiver pass FOR THIS RUN, and the
    outcome records it was used (regolith/12 rule 9)."""
    paths = _write_design(tmp_path, _BARE_DESIGN, with_memo=False)
    report = build(
        paths, BuildTier.RELEASE, accept=frozenset({"Strength.fatigue_life"})
    ).danger_ok
    assert report.release_ok
    assert report.acceptance.cli_accepts_used == ("Strength.fatigue_life",)


def test_inv_24_ship_package_contains_acceptance_ledger(tmp_path) -> None:
    """`regolith ship` writes acceptance_ledger.json recording the
    accepted deviation, content-addressed in the manifest (D206)."""
    import json

    from regolith.backends.ship import ship
    from regolith.orchestrator.lockfile import Lockfile

    paths = _write_design(tmp_path, _DEVIATION_DESIGN, with_memo=True)
    out = tmp_path / "out"
    result = ship(paths, {}, str(out), lockfile=Lockfile(tool_version="0.1.0"))
    assert result.is_ok, result.danger_err if result.is_err else ""
    ledger_path = out / "acceptance_ledger.json"
    assert ledger_path.is_file()
    doc = json.loads(ledger_path.read_text())
    targets = [d["target"] for d in doc["accepted_deviations"]]
    assert "Strength.fatigue_life" in targets
    assert "acceptance_ledger.json" in [f.relpath for f in result.danger_ok.files]


def test_inv_24_stale_waiver_example_still_fails() -> None:
    """The encoded negative fixture (a waiver matching nothing) still
    fails exactly as encoded (INV-12 stale-waiver error E0701)."""
    report = build(
        ("examples/negative/30_stale_waiver.hema",), BuildTier.RELEASE
    ).danger_ok
    assert not report.ok
