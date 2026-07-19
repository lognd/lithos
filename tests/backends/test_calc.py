"""Unit tests for the calc package + audit index (WO-114, D221).

Fast, fixture-driven tests over the pure calc builders -- claim-text
reconstruction, per-input provenance pinning, the citation marker, the
disposition routing, and the census/row accounting -- with no build.
"""

from __future__ import annotations

from regolith._schema.models import (
    Claim,
    ClaimForm1,
    ClaimForm3,
    Form,
    Form2,
    Given,
    Material,
    Obligation,
    Ref,
    Window1,
)
from regolith.backends.calc import (
    UNCITED,
    _deviation_for_hash,
    _quantity_cell,
    _safe_name,
    _split_value_unit,
    build_calc_book,
    claim_text,
    inputs_from_claim_kwargs,
    inputs_from_given,
    subject_anchor,
    unit_from_claim,
)
from regolith.harness.attest import Unsigned
from regolith.harness.evidence import build_evidence
from regolith.orchestrator.acceptance import AcceptanceOutcome, Deviation
from regolith.orchestrator.discharge import Deferral, ObligationResult


def _claim(name: str = "stress_ok", lhs: str = "stress", rhs: str = "limit") -> Claim:
    return Claim(
        forall=[],
        form=ClaimForm1(form=Form.comparison, lhs=lhs, op="<", rhs=rhs),
        hints=[],
        name=name,
    )


def _obligation(
    subject_ref: str,
    *,
    materials: list[Material] | None = None,
    loads: list[str] | None = None,
    refs: list[Ref] | None = None,
    claim: Claim | None = None,
) -> Obligation:
    return Obligation(
        claim=claim or _claim(),
        given=Given(
            materials=materials or [],
            loads=loads or [],
            backing=[],
            refs=refs or [],
        ),
        hints=[],
        subject_ref=subject_ref,
    )


def _discharged_evidence(margin: float = 2.0) -> object:
    return build_evidence(
        model_id="mech.deflection@2",
        claim_kind="mech.deflection",
        sense_upper=True,
        value=1.0,
        eps=0.0,
        limit=3.0,
        coverage=1.0,
        cost=1,
        in_domain=True,
        deterministic=True,
        registry_version="v",
        inputs_digest="d",
    )


class TestClaimText:
    # frob:tests python/regolith/harness/evidence.py::build_evidence
    # frob:tests python/regolith/harness/model.py::DischargeRequest.inputs_digest
    # frob:tests python/regolith/backends/calc.py::claim_text
    def test_comparison_renders_lhs_op_rhs(self) -> None:
        assert claim_text(_claim(lhs="k", rhs="10")) == "k < 10"

    def test_never_blank(self) -> None:
        assert claim_text(_claim(name="x")).strip()


class TestInputsProvenance:
    # frob:tests python/regolith/backends/calc.py::inputs_from_given
    def test_material_is_record_ref_with_pin(self) -> None:
        inputs = inputs_from_given(
            Given(
                materials=[Material(root=["steel_a36", "blake3:abc123"])],
                loads=[],
                backing=[],
                refs=[],
            )
        )
        assert len(inputs) == 1
        assert inputs[0].provenance == "record_ref"
        assert inputs[0].pin == "blake3:abc123"
        assert inputs[0].name == "steel_a36"

    def test_load_is_declared_literal(self) -> None:
        inputs = inputs_from_given(
            Given(materials=[], loads=["speed_rpm: 1500"], backing=[], refs=[])
        )
        assert inputs[0].provenance == "declared_literal"
        assert inputs[0].name == "speed_rpm"
        assert inputs[0].value == "1500"

    def test_ref_is_derived(self) -> None:
        inputs = inputs_from_given(
            Given(
                materials=[],
                loads=[],
                backing=[],
                refs=[Ref(root=["comms.pa_out", "30 dBm"])],
            )
        )
        assert inputs[0].provenance == "derived"
        assert inputs[0].name == "comms.pa_out"

    def test_empty_given_is_honest_gap(self) -> None:
        assert (
            inputs_from_given(Given(materials=[], loads=[], backing=[], refs=[])) == ()
        )


class TestHelpers:
    def test_subject_anchor_prefers_scope(self) -> None:
        assert (
            subject_anchor("h" * 40, {"h" * 40: "BaseFrame.beam"}) == "BaseFrame.beam"
        )

    def test_subject_anchor_falls_back_to_hash(self) -> None:
        assert subject_anchor("abcdef1234567890", {}) == "abcdef123456"

    def test_safe_name_escapes(self) -> None:
        assert "/" not in _safe_name("a/b::c d")
        assert _safe_name("a/b::c d") == "a_b__c_d"


class TestBuildCalcBook:
    def test_discharged_obligation_gets_a_calc_sheet(self) -> None:
        ob = _obligation("s1", loads=["speed_rpm: 100"])
        res = ObligationResult(
            key="k1",
            subject_ref="s1",
            content_hash="c1",
            evidence=_discharged_evidence(),
            deferral=None,
            attestation=Unsigned(kind="unsigned"),
        )
        book = build_calc_book(
            "p",
            (ob,),
            (res,),
            AcceptanceOutcome(),
            snapshots={"s1": "Beam.deflect"},
            citations={},
            tier="release",
        )
        assert len(book.sheets) == 1
        sheet = book.sheets[0]
        assert sheet.subject_anchor == "Beam.deflect"
        assert sheet.citation == UNCITED  # no citation registered
        assert sheet.chain.sheet_digest.startswith("local-blake3:")
        assert sheet.chain.evidence_hash  # a canonical address, untagged
        assert book.index.summary.discharged == 1
        assert book.index.rows[0].disposition == "calc_sheet"

    def test_citation_renders_when_present(self) -> None:
        ob = _obligation("s1")
        res = ObligationResult(
            key="k",
            subject_ref="s1",
            content_hash="c1",
            evidence=_discharged_evidence(),
            deferral=None,
            attestation=Unsigned(kind="unsigned"),
        )
        book = build_calc_book(
            "p",
            (ob,),
            (res,),
            AcceptanceOutcome(),
            snapshots={},
            citations={"mech.deflection@2": "Roark 7th ed. Table 8.1"},
            tier="release",
        )
        assert book.sheets[0].citation == "Roark 7th ed. Table 8.1"

    def test_accepted_deviation_cross_links_the_waiver(self) -> None:
        ob = _obligation("s1")
        res = ObligationResult(
            key="k",
            subject_ref="s1",
            content_hash="cAcc",
            evidence=None,
            deferral=Deferral(reason="no_model", detail=""),
            attestation=Unsigned(kind="unsigned"),
        )
        acc = AcceptanceOutcome(
            accepted_hashes=("cAcc",),
            deviations=(
                Deviation(
                    target="pilot_perp",
                    scope=None,
                    basis="model gap",
                    evidence="doc(memos/x.md)",
                    kind="matched",
                    accepted=("cAcc",),
                    match_set=("cAcc",),
                    expires=None,
                    evidence_digest="blake3:memo",
                ),
            ),
        )
        book = build_calc_book(
            "p", (ob,), (res,), acc, snapshots={}, citations={}, tier="release"
        )
        assert not book.sheets
        row = book.index.rows[0]
        assert row.disposition == "accepted_deviation"
        assert "pilot_perp" in row.detail
        assert "blake3:memo" in row.detail
        assert book.index.summary.accepted_deviation == 1
        assert book.index.summary.accepted_rows == 1

    def test_named_deferral_and_violation(self) -> None:
        obs = (
            _obligation("s1", claim=_claim("a")),
            _obligation("s2", claim=_claim("b")),
        )
        res = (
            ObligationResult(
                key="k1",
                subject_ref="s1",
                content_hash="c1",
                evidence=None,
                deferral=Deferral(reason="no_model", detail="kind x"),
                attestation=Unsigned(kind="unsigned"),
            ),
            ObligationResult(
                key="k2",
                subject_ref="s2",
                content_hash="c2",
                evidence=None,
                deferral=Deferral(reason="violated", detail=""),
                attestation=Unsigned(kind="unsigned"),
            ),
        )
        book = build_calc_book(
            "p",
            obs,
            res,
            AcceptanceOutcome(),
            snapshots={},
            citations={},
            tier="release",
        )
        summary = book.index.summary
        assert summary.deferred == 1
        assert summary.violated == 1
        assert summary.balanced()
        dispositions = {r.claim_name: r.disposition for r in book.index.rows}
        assert dispositions["a"] == "deferred"
        assert dispositions["b"] == "violated"

    def test_zero_unexplained_and_census_row(self) -> None:
        obs = tuple(_obligation(f"s{i}", claim=_claim(f"c{i}")) for i in range(3))
        res = tuple(
            ObligationResult(
                key=f"k{i}",
                subject_ref=f"s{i}",
                content_hash=f"c{i}",
                evidence=_discharged_evidence() if i == 0 else None,
                deferral=None if i == 0 else Deferral(reason="no_model", detail=""),
                attestation=Unsigned(kind="unsigned"),
            )
            for i in range(3)
        )
        book = build_calc_book(
            "p",
            obs,
            res,
            AcceptanceOutcome(),
            snapshots={},
            citations={},
            tier="release",
        )
        assert len(book.index.rows) == 3
        assert book.index.summary.balanced()
        assert book.index.summary.census_row() == {
            "obligations": 3,
            "discharged": 1,
            "accepted_deviation": 0,
            "violated": 0,
        }

    def test_deferral_free_indeterminate_evidence_is_a_named_deferral(self) -> None:
        """No deferral, no accepted waiver, evidence not discharged
        (an unmatched model pin on a non-release build): a deferred row,
        never a fabricated calc sheet (TEST005 backfill T-0036)."""
        ob = _obligation("s1")
        res = ObligationResult(
            key="k",
            subject_ref="s1",
            content_hash="cX",
            evidence=None,
            deferral=None,
            attestation=Unsigned(kind="unsigned"),
        )
        book = build_calc_book(
            "p",
            (ob,),
            (res,),
            AcceptanceOutcome(),
            snapshots={},
            citations={},
            tier="release",
        )
        assert not book.sheets
        row = book.index.rows[0]
        assert row.disposition == "deferred"
        assert "indeterminate evidence" in row.detail
        assert book.index.summary.deferred == 1


class TestQuantityCellAndUnits:
    # frob:tests python/regolith/backends/calc.py::_quantity_cell
    def test_non_quantity_cell_renders_unchanged(self) -> None:
        assert _quantity_cell("dgb_6006", "N", is_quantity=False) == "dgb_6006"

    # frob:tests python/regolith/backends/calc.py::inputs_from_claim_kwargs
    def test_duplicate_kwarg_name_keeps_first_occurrence_only(self) -> None:
        inputs = inputs_from_claim_kwargs("f(c_rating=13200, c_rating=9400)")
        assert len(inputs) == 1
        assert inputs[0].source == "c_rating=13200"

    # frob:tests python/regolith/backends/calc.py::unit_from_claim
    def test_unit_from_claim_is_empty_for_a_non_comparison_form(self) -> None:
        claim = Claim(
            forall=[],
            form=ClaimForm3(
                form=Form2.settles,
                signal="x",
                tol="0.1",
                window=Window1(during="startup"),
            ),
            hints=[],
            name="settle",
        )
        assert unit_from_claim(claim) == ""

    # frob:tests python/regolith/backends/calc.py::_split_value_unit
    def test_lone_star_unit_factor_strips_its_leading_star(self) -> None:
        """``"9.4*m"`` -> ``("9.4", "m")`` -- a lone ``*<unit>`` factor with
        no attached prefix unit names one unit, not a product of two."""
        assert _split_value_unit("9.4*m") == ("9.4", "m")

    # frob:tests python/regolith/backends/calc.py::_deviation_for_hash
    def test_deviation_for_hash_absent_falls_back_to_ledger_note(self) -> None:
        """A hash the ledger's ``accepted_hashes`` names but no listed
        deviation actually claims (a stale/summary-only ledger entry):
        the cross-link degrades to the honest ledger pointer, never a
        crash or a fabricated deviation."""
        assert _deviation_for_hash("cAcc", AcceptanceOutcome()) is None
