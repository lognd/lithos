"""Unit tests for `regolith.backends.harness_pack` (WO-126, D224).

Exercises the pure formatting/provenance-resolution functions directly
against small synthetic payloads/results/calc-books -- the heavier
real-CLI acceptance runs live in `tests/test_wo126_bringup_harness.py`
(mirrors `tests/backends/test_debug_emission.py`'s own split against
`tests/test_wo125_debug_profile.py`).
"""

from __future__ import annotations

from regolith._codes import EXPECTATION_PROVENANCE_UNRESOLVED
from regolith._schema.models import (
    Claim,
    ClaimForm1,
    ClaimForm2,
    Coverage,
    Evidence,
    Form,
    Form1,
    Given,
    Obligation,
    Status1,
    Window1,
)
from regolith.backends.calc import (
    AuditIndex,
    AuditSummary,
    CalcBook,
    build_calc_book,
)
from regolith.backends.debug_taps import Tap, TapSet
from regolith.backends.framework import OutputFile
from regolith.backends.harness_pack import (
    build_expected_signals,
    check_expectation_provenance,
    expected_signals_bytes,
    harness_files,
    render_bringup,
)
from regolith.harness.quantity import f64_to_bits
from regolith.orchestrator.discharge import ObligationResult


def _rail_obligation(claim_name: str, subject_ref: str) -> Obligation:
    return Obligation(
        claim=Claim(
            forall=[],
            form=ClaimForm2(
                form=Form1.peak,
                op="<=",
                rhs="3.465V",
                signal="v(out)",
                window=Window1(during="startup"),
            ),
            hints=[],
            name=claim_name,
        ),
        given=Given(backing=[], loads=[], materials=[], refs=[]),
        hints=[],
        payloads=[],
        subject_ref=subject_ref,
    )


def _impedance_obligation(claim_name: str, subject_ref: str) -> Obligation:
    """A `refclk_z0.lo`-shaped SI claim: the DSL's `within [45ohm,
    55ohm]` interval lowers to two scalar comparisons, each carrying
    its SI-reduced unit token on `rhs` (D256: Rust's
    `resolve_unit_suffix` re-attaches the canonical base unit instead
    of discarding it -- the real mainboard_mx channel-0 shape)."""
    return Obligation(
        claim=Claim(
            forall=[],
            form=ClaimForm1(
                form=Form.comparison,
                lhs="elec.impedance(refclk, role=microstrip, "
                "stackup=jlc04161h_7628, layer=outer, w=0.00036)",
                op=">=",
                rhs="45ohm",
            ),
            hints=[],
            name=claim_name,
        ),
        given=Given(backing=[], loads=[], materials=[], refs=[]),
        hints=[],
        payloads=[],
        subject_ref=subject_ref,
    )


def _discharged_result(index: int, subject_ref: str) -> ObligationResult:
    evidence = Evidence(
        cost=1,
        coverage=Coverage(axes=[], fraction_bits=f64_to_bits(1.0)),
        eps_bits=f64_to_bits(0.0),
        hash=f"evidence-hash-{index}",
        margin_bits=f64_to_bits(0.1),
        model_id="voltage_rail_ripple@1",
        status=Status1.discharged,
        value_bits=f64_to_bits(3.3),
    )
    return ObligationResult(
        key=f"k{index}",
        subject_ref=subject_ref,
        content_hash=f"ch{index}",
        evidence=evidence,
    )


def _payload(obligations: list[Obligation]) -> dict:
    return {
        "snapshots": [
            {"hash": o.subject_ref, "scope": f"Scope{i}"}
            for i, o in enumerate(obligations)
        ],
        "obligations": [o.model_dump(mode="json") for o in obligations],
    }


def _tap_set(target_path: str, channel: int = 0) -> TapSet:
    return TapSet(
        taps=(
            Tap(
                channel=channel,
                kind="rail",
                target_path=target_path,
                why="claim rail_ripple",
                source="derived",
            ),
        )
    )


class TestBuildExpectedSignals:
    # frob:tests python/regolith/harness/quantity.py::f64_to_bits
    # frob:tests python/regolith/backends/harness_pack.py::build_expected_signals
    def test_discharged_obligation_cites_calc_sheet(self) -> None:
        obligation = _rail_obligation("rail_ripple", "sub-hash-0")
        payload = _payload([obligation])
        results = (_discharged_result(0, "sub-hash-0"),)
        book = build_calc_book(
            "proj",
            (obligation,),
            results,
            acceptance=_empty_acceptance(),
            snapshots={"sub-hash-0": "Scope0"},
            citations={},
            tier="release",
        )
        tap_set = _tap_set("Scope0.out")
        rows = build_expected_signals(tap_set, payload, results, book)
        assert len(rows) == 1
        row = rows[0]
        assert row.provenance.kind == "calc_sheet"
        assert row.provenance.ref == book.sheets[0].chain.sheet_digest
        # D256: `expected` is the bare magnitude (unit split into
        # `units`), so `_tap_line`'s "expect {expected} {units}" render
        # never duplicates the unit token.
        assert row.expected == "3.465"
        assert row.units == "V"

    def test_undischarged_claim_emits_no_number(self) -> None:
        obligation = _rail_obligation("rail_ripple", "sub-hash-0")
        payload = _payload([obligation])
        result = ObligationResult(
            key="k0",
            subject_ref="sub-hash-0",
            content_hash="ch0",
            evidence=None,
            deferral=None,
        )
        rows = build_expected_signals(_tap_set("Scope0.out"), payload, (result,), None)
        assert len(rows) == 1
        row = rows[0]
        assert row.expected is None
        assert row.provenance.kind == "claim"
        assert row.provenance.ref == "rail_ripple"
        assert row.note == "no_verified_expectation"

    def test_tap_with_no_traceable_obligation_is_named_absence(self) -> None:
        rows = build_expected_signals(
            _tap_set("Nowhere.out"), {"obligations": []}, (), None
        )
        assert rows[0].provenance.kind == "none"
        assert "no obligation" in rows[0].provenance.reason

    def test_discharged_si_claim_prints_real_value_with_units(self) -> None:
        """D256 (closes WO-128/F144 via the Rust root fix, not the
        interim closed-SI-vocabulary channel WO-128 landed and D256.4
        deletes): a discharged, calc-sheet-backed row whose claim's own
        `rhs` now carries its unit token directly (`elec.impedance(...)
        >= 45ohm`, `resolve_unit_suffix` preserves it) ships a REAL
        populated expected value read straight off the claim text --
        no closed-vocabulary fallback needed. The quantity label still
        comes from the claim's own SI call name (`impedance`), never
        the tap-kind family bucket (`refclk`'s net name lands it in the
        `clock` family purely by name -- charter 40 sec. 2 -- which is
        not the claim's actual quantity)."""
        obligation = _impedance_obligation("refclk_z0.lo", "sub-hash-0")
        payload = _payload([obligation])
        results = (_discharged_result(0, "sub-hash-0"),)
        book = build_calc_book(
            "proj",
            (obligation,),
            results,
            acceptance=_empty_acceptance(),
            snapshots={"sub-hash-0": "Scope0"},
            citations={},
            tier="release",
        )
        tap_set = TapSet(
            taps=(
                Tap(
                    channel=0,
                    kind="clock",
                    target_path="Scope0.refclk",
                    why="claim refclk_z0.lo",
                    source="derived",
                ),
            )
        )
        rows = build_expected_signals(tap_set, payload, results, book)
        assert len(rows) == 1
        row = rows[0]
        assert row.expected == "45"
        assert row.units == "ohm"
        assert row.note == ""
        assert row.provenance.kind == "calc_sheet"
        assert row.provenance.ref == book.sheets[0].chain.sheet_digest
        assert row.quantity == "impedance"
        assert book.sheets[0].unit == "ohm"


class TestCheckExpectationProvenance:
    # frob:tests python/regolith/backends/calc.py::calc_book_json_bytes
    # frob:tests python/regolith/backends/calc.py::audit_index_json_bytes
    # frob:tests python/regolith/backends/harness_pack.py::expected_signals_bytes
    # frob:tests python/regolith/backends/harness_pack.py::check_expectation_provenance
    def test_resolves_calc_sheet_ref(self) -> None:
        obligation = _rail_obligation("rail_ripple", "sub-hash-0")
        results = (_discharged_result(0, "sub-hash-0"),)
        book = build_calc_book(
            "proj",
            (obligation,),
            results,
            acceptance=_empty_acceptance(),
            snapshots={"sub-hash-0": "Scope0"},
            citations={},
            tier="release",
        )
        rows = build_expected_signals(
            _tap_set("Scope0.out"), _payload([obligation]), results, book
        )
        from regolith.backends.calc import audit_index_json_bytes, calc_book_json_bytes

        calc_files = (
            OutputFile.of("calc/calc_book.json", calc_book_json_bytes(book)),
            OutputFile.of("calc/audit_index.json", audit_index_json_bytes(book)),
        )
        result = check_expectation_provenance(expected_signals_bytes(rows), calc_files)
        assert result.is_ok

    def test_unresolved_ref_refuses(self) -> None:
        from regolith.backends.harness_pack import ExpectedSignal, Provenance

        rows = (
            ExpectedSignal(
                channel=0,
                target_path="x.y",
                kind="rail",
                quantity="voltage",
                expected=None,
                units="",
                provenance=Provenance(
                    kind="calc_sheet", ref="local-blake3:doesnotexist"
                ),
            ),
        )
        empty_book = CalcBook(
            sheets=(),
            index=AuditIndex(
                project="p",
                summary=AuditSummary(
                    obligations=0,
                    discharged=0,
                    accepted_deviation=0,
                    accepted_rows=0,
                    deferred=0,
                    violated=0,
                ),
                rows=(),
            ),
        )
        from regolith.backends.calc import audit_index_json_bytes, calc_book_json_bytes

        calc_files = (
            OutputFile.of("calc/calc_book.json", calc_book_json_bytes(empty_book)),
            OutputFile.of("calc/audit_index.json", audit_index_json_bytes(empty_book)),
        )
        result = check_expectation_provenance(expected_signals_bytes(rows), calc_files)
        assert result.is_err
        assert result.danger_err.kind == EXPECTATION_PROVENANCE_UNRESOLVED

    def test_populated_value_with_no_units_refuses_the_ship(self) -> None:
        """D224 invariant (this WO's item 3): `expected is not None`
        implies `units != ""` -- a row that violates it (a naked number
        with an empty units field, the exact shape the coordinator
        flagged on mainboard_mx channel 0 before this fix) REFUSES the
        ship with a named error, exactly like an unresolved provenance
        ref, never a silent pass."""
        from regolith.backends.harness_pack import ExpectedSignal, Provenance

        obligation = _rail_obligation("rail_ripple", "sub-hash-0")
        results = (_discharged_result(0, "sub-hash-0"),)
        book = build_calc_book(
            "proj",
            (obligation,),
            results,
            acceptance=_empty_acceptance(),
            snapshots={"sub-hash-0": "Scope0"},
            citations={},
            tier="release",
        )
        rows = (
            ExpectedSignal(
                channel=0,
                target_path="x.y",
                kind="clock",
                quantity="impedance",
                expected="45",
                units="",
                provenance=Provenance(
                    kind="calc_sheet", ref=book.sheets[0].chain.sheet_digest
                ),
            ),
        )
        from regolith.backends.calc import audit_index_json_bytes, calc_book_json_bytes

        calc_files = (
            OutputFile.of("calc/calc_book.json", calc_book_json_bytes(book)),
            OutputFile.of("calc/audit_index.json", audit_index_json_bytes(book)),
        )
        result = check_expectation_provenance(expected_signals_bytes(rows), calc_files)
        assert result.is_err
        assert result.danger_err.kind == EXPECTATION_PROVENANCE_UNRESOLVED
        assert "no units" in result.danger_err.message


class TestRenderBringup:
    # frob:tests python/regolith/backends/harness_pack.py::render_bringup
    def test_no_header_states_named_absence(self) -> None:
        text = render_bringup("proj", TapSet(), None, ())
        assert "No tap header record resolved" in text

    def test_orders_rails_before_signals(self) -> None:
        tap_set = TapSet(
            taps=(
                Tap(
                    channel=0,
                    kind="signal",
                    target_path="a.sig",
                    why="w",
                    source="derived",
                ),
                Tap(
                    channel=1,
                    kind="rail",
                    target_path="a.rail",
                    why="w",
                    source="derived",
                ),
            )
        )
        text = render_bringup("proj", tap_set, None, ())
        assert text.index("a.rail") < text.index("a.sig")


# frob:tests python/regolith/backends/calc.py::build_calc_book
def test_harness_files_are_deterministic() -> None:
    obligation = _rail_obligation("rail_ripple", "sub-hash-0")
    payload = _payload([obligation])
    results = (_discharged_result(0, "sub-hash-0"),)
    book = build_calc_book(
        "proj",
        (obligation,),
        results,
        acceptance=_empty_acceptance(),
        snapshots={"sub-hash-0": "Scope0"},
        citations={},
        tier="release",
    )
    tap_set = _tap_set("Scope0.out")
    a = harness_files("proj", b'{"schema":"x"}', tap_set, None, payload, results, book)
    b = harness_files("proj", b'{"schema":"x"}', tap_set, None, payload, results, book)
    assert tuple((f.relpath, f.content) for f in a) == tuple(
        (f.relpath, f.content) for f in b
    )


# frob:tests python/regolith/backends/calc.py::AuditSummary.balanced
# frob:tests python/regolith/backends/manifest.py::FileHash.of
# frob:tests python/regolith/backends/quantity.py::DimensionedValue.of
# frob:tests python/regolith/backends/framework.py::OutputFile.of
def test_units_on_the_evidence_surface_move_no_verdict() -> None:
    """WO-128 deliverable 6 (D206/D220.1): resolving a claim's unit adds
    NO discharge and moves NO verdict. The SI unit fallback changes only
    the PRESENTATION of an already-discharged obligation, so the calc
    book's census-shape summary over an SI-claim build is byte-identical
    to the same summary computed with the unit surface unreachable (an
    obligation whose claim is outside the SI vocabulary entirely) -- the
    denominators, the discharged count, and the verdict all stand."""
    si = _impedance_obligation("refclk_z0.lo", "sub-hash-0")
    rail = _rail_obligation("rail_ripple", "sub-hash-1")
    obligations = (si, rail)
    results = (
        _discharged_result(0, "sub-hash-0"),
        _discharged_result(1, "sub-hash-1"),
    )
    book = build_calc_book(
        "proj",
        obligations,
        results,
        acceptance=_empty_acceptance(),
        snapshots={"sub-hash-0": "Scope0", "sub-hash-1": "Scope1"},
        citations={},
        tier="release",
    )
    # The SI sheet now carries its unit (the WO-128 fix) ...
    si_sheet = next(s for s in book.sheets if s.claim_name == "refclk_z0.lo")
    assert si_sheet.unit == "ohm"
    # ... and the census math is exactly what it was: both obligations
    # discharged, nothing accepted/deferred/violated, denominators intact.
    assert book.index.summary.census_row() == {
        "obligations": 2,
        "discharged": 2,
        "accepted_deviation": 0,
        "violated": 0,
    }
    assert book.index.summary.balanced()
    assert {s.verdict for s in book.sheets} == {"discharged"}


def _empty_acceptance():
    from regolith.orchestrator.acceptance import AcceptanceOutcome

    return AcceptanceOutcome(accepted_hashes=frozenset(), deviations=())


# frob:tests python/regolith/backends/harness_pack.py::check_bringup_expectation_authored_posture
def test_check_bringup_expectation_authored_posture_refuses_authored_record_cited_as_expectation() -> (
    None
):
    """WO-151 deliverable 4/D263.1: a fixture `expected_signals.json` row
    citing `examples/tracks/cuprite/records/masks.toml`'s real
    `monotonic_rise` record (posture `authored`) as a `record`-kind
    provenance ref refuses with `BRINGUP_EXPECTATION_AUTHORED_POSTURE`,
    naming the ref and its posture directly (not a placeholder)."""
    import json

    from regolith.backends.harness_pack import (
        BRINGUP_EXPECTATION_AUTHORED_POSTURE,
        check_bringup_expectation_authored_posture,
    )

    doc = {
        "schema": "regolith.expected_signals.v1",
        "signals": [
            {
                "channel": 0,
                "target_path": "v(out)",
                "kind": "rail",
                "quantity": "voltage",
                "expected": "1.0",
                "units": "V",
                "provenance": {
                    "kind": "record",
                    "ref": "monotonic_rise(5ms)",
                    "reason": "",
                },
                "note": "",
            }
        ],
    }
    expected_bytes = json.dumps(doc).encode("ascii")
    result = check_bringup_expectation_authored_posture(
        expected_bytes,
        ("examples/tracks/cuprite/records",),
        package="examples.tracks.cuprite",
    )
    assert result.is_err
    assert result.danger_err.kind == BRINGUP_EXPECTATION_AUTHORED_POSTURE
    assert "monotonic_rise(5ms)" in result.danger_err.message
    assert "authored" in result.danger_err.message


# frob:tests python/regolith/backends/harness_pack.py::check_bringup_expectation_authored_posture
def test_check_bringup_expectation_authored_posture_passes_when_no_record_refs_present() -> (
    None
):
    """A row set with no `record`-kind provenance ref at all (the
    ordinary calc_sheet/claim/none shapes every other test in this
    file exercises) never trips this check."""
    import json

    from regolith.backends.harness_pack import check_bringup_expectation_authored_posture

    doc = {
        "schema": "regolith.expected_signals.v1",
        "signals": [
            {
                "channel": 0,
                "target_path": "v(out)",
                "kind": "rail",
                "quantity": "voltage",
                "expected": None,
                "units": "",
                "provenance": {"kind": "none", "ref": "", "reason": "no obligation"},
                "note": "no_verified_expectation",
            }
        ],
    }
    expected_bytes = json.dumps(doc).encode("ascii")
    result = check_bringup_expectation_authored_posture(
        expected_bytes, ("examples/tracks/cuprite/records",), package="examples.tracks.cuprite"
    )
    assert result.is_ok
