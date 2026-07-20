"""WO-157 (T-0027, D264): `_translate_timing_budget` forms a real
`elec.timing_budget` `DischargeRequest` -- a `timing_contributions`
payload resolved from a project-relative `timing_contributions_ref` --
from an obligation carrying the `timing_budget_name`/`timing_limit_ns`/
`timing_contributions_ref` given-fields. Closes the gap this ticket's
own recon found: `std.timing`'s `TimingBudgetModel` (WO-156) was
defined but never registered (`harness/models/__init__.py::
register_all`), and `translate.py`'s dispatch table had no
`elec.timing_budget` route at all -- so `sdr_transceiver`'s existing
`budget ddr_timing: kind=timing` clause could never discharge
regardless of corpus authoring.

BLOCKER (recorded here, not worked around): no Rust-side lowering
pass emits an `elec.timing_budget` obligation from a real `.cupr`
`budget kind=timing:` clause today -- confirmed empirically (see
`translate.py`'s `_TIMING_BUDGET_NAME_FIELD` block comment) --
`BudgetStmt` (`regolith-syntax/src/ast.rs`) exposes only `name()`/
`value()` and `decl.claims()` only walks a decl's DIRECT `RequireClaim`
children, so a `require:` line nested inside a `budget kind=timing:`
body never reaches obligation formation. A true WO-72-style test
(compiling a real `.cupr` fixture via `compiler.check()` then
`discharge_all`) is therefore not achievable without Rust changes in
`crates/regolith-syntax`/`crates/regolith-lower`, outside this
ticket's scope; this suite proves the translate+discharge HALF is
real and correct (hand-built `Obligation`, exactly `test_translate_
hdl.py`'s and `test_hdl_sim_gate_cache.py`'s own precedented testing
level for the WO-155 sim gate) so the remaining gap is purely the
Rust-side emission pass named above (tracked in T-0072).

All citations are SYNTHETIC (D266 policy, `test_std_timing.py`'s own
note) -- invented values, not transcribed from any datasheet.
"""

from __future__ import annotations

from regolith._schema.models import Claim, ClaimForm1, Form, Given, Obligation
from regolith.harness import ModelRegistry
from regolith.harness.models.timing import CLAIM_KIND as _TIMING_BUDGET_KIND
from regolith.harness.models.timing import (
    TimingBudgetModel,
    TimingContribution,
    TimingContributionTable,
)
from regolith.magnetite.citation import Citation, Cited
from regolith.orchestrator.cache import EvidenceStore
from regolith.orchestrator.discharge import discharge_one
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.plan_staging import PlanContext
from regolith.orchestrator.translate import _translate_timing_budget


def _synthetic_citation() -> Citation:
    """A SYNTHETIC datasheet-style citation (D266 policy)."""
    return Citation(
        manufacturer="synth.mfg",
        document="SYNTH-0157",
        revision="A",
        date="2026-01-01",
        page=1,
        table="table 1",
        url="https://example.invalid/synth-0157",
        quote=None,
    )


def _contributions_table() -> TimingContributionTable:
    return TimingContributionTable(
        budget_name="ddr_timing",
        contributions=(
            TimingContribution(
                name="route_dq",
                route_length_mm=25.0,
                route_dk=Cited(
                    value=4.2, citation=_synthetic_citation(), confirmed=True
                ),
            ),
        ),
    )


# frob:ticket T-0027
def _obligation(*loads: str) -> Obligation:
    return Obligation(
        claim=Claim(
            name=_TIMING_BUDGET_KIND,
            form=ClaimForm1(
                form=Form.comparison, lhs=_TIMING_BUDGET_KIND, op="<=", rhs="0"
            ),
            forall=[],
            hints=[],
        ),
        subject_ref="blake3:deadbeef",
        given=Given(materials=[], loads=list(loads), backing=[]),
        hints=[],
    )


# frob:ticket T-0027
def _plan_context(tmp_path) -> PlanContext:
    return PlanContext(
        project_root=str(tmp_path), records={}, store=PayloadStore(str(tmp_path))
    )


# frob:ticket T-0027
def test_translate_timing_budget_forms_a_request_with_contributions_payload(
    tmp_path,
) -> None:
    (tmp_path / "ddr_timing_contributions").write_text(
        _contributions_table().model_dump_json()
    )
    ob = _obligation(
        "timing_budget_name: ddr_timing",
        "timing_limit_ns: 2.5",
        "timing_contributions_ref: ddr_timing_contributions",
    )
    ctx = _plan_context(tmp_path)
    result = _translate_timing_budget(ob, ctx)
    assert result.is_ok, result
    req = result.danger_ok
    assert req.claim_kind == _TIMING_BUDGET_KIND
    assert req.limit == 2.5
    assert "timing_contributions" in req.payloads
    assert req.payloads["timing_contributions"].kind == "timing_contribution_table"


# frob:ticket T-0027
def test_translate_timing_budget_defers_on_unresolvable_contributions_ref(
    tmp_path,
) -> None:
    """A named datum missing (D250.3): the contributions ref names no
    file in the build -- a named Deferral, never a silent skip or a
    fabricated closure."""
    ob = _obligation(
        "timing_budget_name: ddr_timing",
        "timing_limit_ns: 2.5",
        "timing_contributions_ref: does_not_exist",
    )
    ctx = _plan_context(tmp_path)
    result = _translate_timing_budget(ob, ctx)
    assert result.is_err
    assert result.danger_err.reason == "timing_contributions_ref_unresolved"


# frob:ticket T-0027
def test_translate_timing_budget_defers_on_incomplete_clause(tmp_path) -> None:
    """No `timing_budget_name`/`timing_limit_ns`/`timing_contributions_ref`
    given at all -- honest deferral, matching `_translate_hdl`'s own
    `hdl_clause_incomplete` posture."""
    ob = _obligation()
    ctx = _plan_context(tmp_path)
    result = _translate_timing_budget(ob, ctx)
    assert result.is_err
    assert result.danger_err.reason == "timing_budget_clause_incomplete"


# frob:ticket T-0027
def test_translate_timing_budget_discharges_end_to_end_against_the_real_model(
    tmp_path,
) -> None:
    """Real, non-mocked discharge: `_translate_timing_budget`'s request
    resolves through `TimingBudgetModel.discharge` (registered per this
    ticket's `harness/models/__init__.py::register_all` fix) and closes
    for real against the synthetic route contribution (route delay
    25.0mm / v_p(Dk=4.2) ~= 0.162ns, well inside the 2.5ns limit)."""
    (tmp_path / "ddr_timing_contributions").write_text(
        _contributions_table().model_dump_json()
    )
    ob = _obligation(
        "timing_budget_name: ddr_timing",
        "timing_limit_ns: 2.5",
        "timing_contributions_ref: ddr_timing_contributions",
    )
    ctx = _plan_context(tmp_path)
    translated = _translate_timing_budget(ob, ctx)
    assert translated.is_ok, translated

    registry = ModelRegistry(version="test-registry")
    registry.register(TimingBudgetModel())
    evidence_store = EvidenceStore()
    result = discharge_one(
        ob,
        registry=registry,
        store=evidence_store,
        payload_store=ctx.store,
        plan_context=ctx,
    )
    assert result.evidence is not None, result
    assert result.evidence.status.value == "discharged"
    assert result.evidence.model_id == "timing_budget@1"
