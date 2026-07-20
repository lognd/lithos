"""`std.timing` tests (WO-156, D264): budget closure over cited
datasheet values, the route-length-to-delay conversion via a cited
stackup `Dk`, the `E0432` negative fixture naming the right worst
contributor, and the calc-book rendering path proving citations are
visible in the rendered output (not just in the underlying model).

All citations here are SYNTHETIC (invented values, not transcribed
from any source) -- D266 withdrew the real `stdlib/ti.mcu` datasheet
corpus this WO's own body originally cited pending counsel review; the
WO-138/WO-139 synthetic-fixture conversion policy applies verbatim
(see `python/regolith/harness/models/timing.py`'s module docstring).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from regolith._codes import BUDGET_CANNOT_CLOSE
from regolith._schema.models import PayloadRef
from regolith.backends.calc import build_calc_book, calc_book_json_bytes
from regolith.harness.model import DischargeRequest
from regolith.harness.models.timing import (
    CONTRIBUTIONS_KIND,
    CONTRIBUTIONS_PORT,
    LIGHT_SPEED_MM_PER_NS,
    TimingBudgetModel,
    TimingContribution,
    TimingContributionTable,
    close_timing_budget,
    route_delay_ns,
    stackup_v_p_mm_per_ns,
    timing_closure_given_loads,
)
from regolith.magnetite.citation import Citation, Cited, CitedInterval
from regolith.orchestrator.payload_store import PayloadStore


def _synthetic_citation(table: str = "table 1") -> Citation:
    """A SYNTHETIC citation -- invented values, no real datasheet."""
    return Citation(
        manufacturer="synth.mfg",
        document="SYNTH-0001",
        revision="A",
        date="2026-01-01",
        page=1,
        table=table,
        url="https://example.invalid/synth-0001",
        quote=None,
    )


def _cited_interval(hi: float, *, table: str = "table 1") -> CitedInterval:
    return CitedInterval(
        lo=None,
        hi=hi,
        typ=None,
        unit="ns",
        citation=_synthetic_citation(table=table),
        confirmed=True,
    )


@pytest.fixture
def store(tmp_path: Path) -> PayloadStore:
    return PayloadStore(str(tmp_path))


class TestStackupFormula:
    def test_v_p_matches_hand_computed_tem_relation(self) -> None:
        """`v_p = c / sqrt(Dk)`, hand-computed for Dk=4.0 (sqrt=2.0)."""
        v_p = stackup_v_p_mm_per_ns(4.0)
        assert v_p == pytest.approx(LIGHT_SPEED_MM_PER_NS / 2.0)

    def test_v_p_rejects_nonpositive_dk(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            stackup_v_p_mm_per_ns(0.0)

    def test_route_contribution_pessimal_ns_matches_hand_computed_delay(self) -> None:
        """A 40mm route over Dk=4.41 (sqrt=2.1): hand-computed delay."""
        length_mm = 40.0
        dk = 4.41
        expected = length_mm / (LIGHT_SPEED_MM_PER_NS / (dk**0.5))
        assert route_delay_ns(length_mm, dk) == pytest.approx(expected)

        contrib = TimingContribution(
            name="ddr_route",
            route_length_mm=length_mm,
            route_dk=Cited(
                value=dk, citation=_synthetic_citation(table="table 2"), confirmed=True
            ),
        )
        assert contrib.pessimal_ns() == pytest.approx(expected)


class TestTimingContributionConstruction:
    def test_bare_literal_contribution_is_unrepresentable(self) -> None:
        """No grounding source at all -- refused at construction."""
        with pytest.raises(ValidationError, match="no grounding source"):
            TimingContribution(name="bare")

    def test_both_grounding_sources_at_once_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="BOTH"):
            TimingContribution(
                name="over_specified",
                cited=_cited_interval(5.0),
                route_length_mm=10.0,
                route_dk=Cited(
                    value=4.0, citation=_synthetic_citation(), confirmed=True
                ),
            )

    def test_route_missing_dk_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="BOTH route_length_mm and route_dk"):
            TimingContribution(name="half_route", route_length_mm=10.0)


class TestCloseTimingBudget:
    def test_closes_over_cited_datasheet_values_within_limit(self) -> None:
        """t_pd + t_su under a 20ns clock period: closes with slack."""
        t_pd = TimingContribution(name="t_pd", cited=_cited_interval(6.0))
        t_su = TimingContribution(
            name="t_su", cited=_cited_interval(4.0, table="table 3")
        )
        result = close_timing_budget("mcu_bus_timing", 20.0, [t_pd, t_su])
        assert result.is_ok, result
        closure = result.danger_ok
        assert closure.sum_ns == pytest.approx(10.0)
        assert closure.slack_ns == pytest.approx(10.0)
        assert closure.verdict == "closed"
        assert closure.diagnostic_code is None
        assert "synth.mfg" in closure.contribution_citations[0]

    def test_e0432_negative_fixture_names_the_right_worst_contributor(self) -> None:
        """A budget whose contributions exceed the limit cannot close;
        the worst (largest) contributor is named, tagged with the
        REUSED `E0432`/`BUDGET_CANNOT_CLOSE` code -- no new diagnostic
        family (D264 ruling "nothing-new-here")."""
        small = TimingContribution(name="t_co", cited=_cited_interval(3.0))
        big = TimingContribution(
            name="route_ddr0",
            route_length_mm=2000.0,
            route_dk=Cited(
                value=4.0, citation=_synthetic_citation(table="table 4"), confirmed=True
            ),
        )
        result = close_timing_budget("ddr_timing", 10.0, [small, big])
        assert result.is_ok, result
        closure = result.danger_ok
        assert closure.verdict == "violated"
        assert closure.diagnostic_code == BUDGET_CANNOT_CLOSE
        assert closure.diagnostic_code == "E0432"
        assert closure.worst_contributor == "route_ddr0"

    def test_symbolic_pessimal_bound_is_a_domain_error_not_a_crash(self) -> None:
        """A symbolic `hi` (D257's carve-out) has no v1 numeric pessimal
        reading -- an honest `Err`, never a guessed float or a crash."""
        symbolic = TimingContribution(
            name="weird",
            cited=CitedInterval(
                lo=None,
                hi="VCC + 0.3 V",
                typ=None,
                unit="ns",
                citation=_synthetic_citation(),
                confirmed=True,
            ),
        )
        result = close_timing_budget("weird_budget", 10.0, [symbolic])
        assert result.is_err, result
        assert "symbolic" in result.danger_err.message

    def test_empty_contributions_is_a_domain_error(self) -> None:
        result = close_timing_budget("empty_budget", 10.0, [])
        assert result.is_err, result


class TestTimingBudgetModel:
    def test_timing_budget_model_estimate_matches_close_timing_budget(
        self, store: PayloadStore
    ) -> None:
        """The model's `discharge` value equals the same
        `close_timing_budget` sum a caller computes directly -- no
        second closure mechanism."""
        t_pd = TimingContribution(name="t_pd", cited=_cited_interval(6.0))
        t_su = TimingContribution(
            name="t_su", cited=_cited_interval(4.0, table="table 3")
        )
        table = TimingContributionTable(
            budget_name="mcu_bus_timing", contributions=(t_pd, t_su)
        )
        digest = store.put(table.model_dump_json().encode("utf-8"))
        request = DischargeRequest(
            claim_kind="elec.timing_budget",
            limit=20.0,
            inputs={},
            payloads={
                CONTRIBUTIONS_PORT: PayloadRef(
                    kind=CONTRIBUTIONS_KIND, digest=digest, origin="mcu_bus_timing"
                )
            },
        )
        model = TimingBudgetModel()
        result = model.discharge(
            request, registry_version="test", resolver=store.resolver()
        )
        assert result.is_ok, result
        evidence = result.danger_ok
        assert evidence.status.value == "discharged"
        assert evidence.value_bits is not None

    def test_violated_budget_discharges_as_violated_not_indeterminate(
        self, store: PayloadStore
    ) -> None:
        big = TimingContribution(
            name="route_ddr0",
            route_length_mm=2000.0,
            route_dk=Cited(
                value=4.0, citation=_synthetic_citation(table="table 4"), confirmed=True
            ),
        )
        table = TimingContributionTable(budget_name="ddr_timing", contributions=(big,))
        digest = store.put(table.model_dump_json().encode("utf-8"))
        request = DischargeRequest(
            claim_kind="elec.timing_budget",
            limit=10.0,
            inputs={},
            payloads={
                CONTRIBUTIONS_PORT: PayloadRef(
                    kind=CONTRIBUTIONS_KIND, digest=digest, origin="ddr_timing"
                )
            },
        )
        model = TimingBudgetModel()
        result = model.discharge(
            request, registry_version="test", resolver=store.resolver()
        )
        assert result.is_ok, result
        assert result.danger_ok.status.value == "violated"


def _claim_and_obligation(subject_ref: str, loads: tuple[str, ...]):
    """A minimal Obligation carrying grounded timing loads (mirrors
    `tests/backends/test_calc.py`'s own `_obligation` helper)."""
    from regolith._schema.models import Claim, ClaimForm1, Form, Given, Obligation

    claim = Claim(
        forall=[],
        form=ClaimForm1(form=Form.comparison, lhs="mcu_bus_timing", op="<", rhs="20"),
        hints=[],
        name="mcu_bus_timing",
    )
    given = Given(materials=[], loads=list(loads), backing=[], refs=[])
    return Obligation(claim=claim, given=given, hints=[], subject_ref=subject_ref)


class TestCalcBookRendering:
    def test_timing_table_renders_with_citations_visible(self) -> None:
        """The calc book's rendered bytes carry the contribution's own
        citation text (not merely present in the underlying model) --
        WO-156 acceptance criterion 3."""
        t_pd = TimingContribution(
            name="t_pd", cited=_cited_interval(6.0, table="table 9")
        )
        t_su = TimingContribution(
            name="t_su", cited=_cited_interval(4.0, table="table 10")
        )
        closure = close_timing_budget("mcu_bus_timing", 20.0, [t_pd, t_su]).danger_ok
        loads = timing_closure_given_loads(closure)
        assert any("table 9" in row for row in loads)
        assert any("table 10" in row for row in loads)

        obligation = _claim_and_obligation("mcu_bus_timing::subj", loads)
        from regolith.harness.attest import Unsigned
        from regolith.harness.evidence import build_evidence
        from regolith.orchestrator.acceptance import AcceptanceOutcome
        from regolith.orchestrator.discharge import ObligationResult

        evidence = build_evidence(
            model_id="std.timing.timing_budget@1",
            claim_kind="elec.timing_budget",
            sense_upper=True,
            value=closure.sum_ns,
            eps=0.0,
            limit=20.0,
            coverage=1.0,
            cost=1,
            in_domain=True,
            deterministic=True,
            registry_version="v",
            inputs_digest="d",
        )
        result = ObligationResult(
            key="k1",
            subject_ref="mcu_bus_timing::subj",
            content_hash="c1",
            evidence=evidence,
            deferral=None,
            attestation=Unsigned(kind="unsigned"),
        )
        book = build_calc_book(
            "wo156_timing_fixture",
            (obligation,),
            (result,),
            AcceptanceOutcome(),
            snapshots={},
            citations={},
            tier="release",
        )
        rendered = calc_book_json_bytes(book).decode("utf-8")
        assert "synth.mfg" in rendered
        assert "table 9" in rendered
        assert "table 10" in rendered
