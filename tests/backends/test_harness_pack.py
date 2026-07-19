"""Unit tests for `regolith.backends.harness_pack` (WO-126, D224).

Exercises the pure formatting/provenance-resolution functions directly
against small synthetic payloads/results/calc-books -- the heavier
real-CLI acceptance runs live in `tests/test_wo126_bringup_harness.py`
(mirrors `tests/backends/test_debug_emission.py`'s own split against
`tests/test_wo125_debug_profile.py`).
"""

from __future__ import annotations

import json

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
from regolith.backends.debug_taps import Tap, TapHeaderRecord, TapSet, UnallocatedTap
from regolith.backends.framework import OutputFile
from regolith.backends.harness_pack import (
    ExpectedSignal,
    Provenance,
    _expected_magnitude_and_units,
    _sources_from_payload,
    _split_expected_magnitude_and_unit,
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


class TestPrivateHelpers:
    # frob:tests python/regolith/backends/harness_pack.py::_split_expected_magnitude_and_unit
    def test_no_recognizable_unit_token_returns_text_unchanged(self) -> None:
        assert _split_expected_magnitude_and_unit("no_unit_here") == (
            "no_unit_here",
            "",
        )

    # frob:tests python/regolith/backends/harness_pack.py::_sources_from_payload
    def test_unparseable_obligation_row_is_skipped(self) -> None:
        sources = _sources_from_payload(
            {"snapshots": [], "obligations": [{"not": "an obligation"}]}
        )
        assert sources == {}

    # frob:tests python/regolith/backends/harness_pack.py::_sources_from_payload
    # frob:tests python/regolith/backends/harness_pack.py::_expected_magnitude_and_units
    def test_empty_rhs_is_a_named_absence(self) -> None:
        obligation = _rail_obligation("rail_ripple", "sub-hash-0")
        object.__setattr__(obligation.claim.form, "rhs", "")
        assert _expected_magnitude_and_units(obligation) == (None, "")

    # frob:tests python/regolith/backends/harness_pack.py::_sources_from_payload
    def test_no_si_fields_and_no_signal_attr_is_skipped(self) -> None:
        obligation = Obligation(
            claim=Claim(
                forall=[],
                form=ClaimForm1(form=Form.comparison, lhs="k", op="<", rhs="10"),
                hints=[],
                name="c",
            ),
            given=Given(backing=[], loads=[], materials=[], refs=[]),
            hints=[],
            payloads=[],
            subject_ref="sub-hash-0",
        )
        sources = _sources_from_payload(_payload([obligation]))
        assert sources == {}

    def test_non_call_signal_expression_is_skipped(self) -> None:
        obligation = Obligation(
            claim=Claim(
                forall=[],
                form=ClaimForm2(
                    form=Form1.peak,
                    op="<=",
                    rhs="1V",
                    signal="not a call expr",
                    window=Window1(during="startup"),
                ),
                hints=[],
                name="c",
            ),
            given=Given(backing=[], loads=[], materials=[], refs=[]),
            hints=[],
            payloads=[],
            subject_ref="sub-hash-0",
        )
        sources = _sources_from_payload(_payload([obligation]))
        assert sources == {}

    def test_unit_unresolved_calc_sheet_row_degrades_to_named_absence(self) -> None:
        """A discharged, calc-sheet-backed obligation whose declared
        threshold carries no recognizable unit token degrades to the
        honest no_verified_expectation absence (WO117-F2), never a
        bare unitless number."""
        obligation = _rail_obligation("rail_ripple", "sub-hash-0")
        object.__setattr__(obligation.claim.form, "rhs", "3.465")
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
        rows = build_expected_signals(_tap_set("Scope0.out"), payload, results, book)
        assert len(rows) == 1
        row = rows[0]
        assert row.expected is None
        assert row.units == ""
        assert row.provenance.kind == "calc_sheet"
        assert row.note == "no_verified_expectation"
        assert "unit_unresolved" in row.provenance.reason


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

    # frob:tests python/regolith/backends/harness_pack.py::check_expectation_provenance
    def test_no_calc_package_skips_resolution(self) -> None:
        """No `calc/audit_index.json` among the shipped files (the calc
        package build already logged why, e.g. an obligation/result
        count mismatch) -- nothing to resolve any ref against, so the
        check is skipped rather than refusing the ship a second time."""
        rows = (
            ExpectedSignal(
                channel=0,
                target_path="x.y",
                kind="rail",
                quantity="voltage",
                expected=None,
                units="",
                provenance=Provenance(kind="none", ref=""),
            ),
        )
        result = check_expectation_provenance(expected_signals_bytes(rows), ())
        assert result.is_ok

    # frob:tests python/regolith/backends/harness_pack.py::check_expectation_provenance
    def test_malformed_expected_signals_json_refuses(self) -> None:
        calc_files = (OutputFile.of("calc/audit_index.json", b"{}"),)
        result = check_expectation_provenance(b"not json", calc_files)
        assert result.is_err
        assert result.danger_err.kind == "expected_signals_malformed"

    # frob:tests python/regolith/backends/harness_pack.py::check_expectation_provenance
    def test_malformed_shipped_calc_files_are_skipped_not_crashed(self) -> None:
        """A shipped ``calc/calc_book.json``/``calc/audit_index.json``
        that fails to decode as JSON (a genuinely corrupt package,
        never produced by this toolchain's own writers) is skipped
        rather than crashing the ship-path check -- any ref against it
        then correctly reports unresolved."""
        rows = (
            ExpectedSignal(
                channel=0,
                target_path="x.y",
                kind="rail",
                quantity="voltage",
                expected=None,
                units="",
                provenance=Provenance(kind="calc_sheet", ref="local-blake3:x"),
            ),
        )
        calc_files = (
            OutputFile.of("calc/calc_book.json", b"not json"),
            OutputFile.of("calc/audit_index.json", b"not json either"),
        )
        result = check_expectation_provenance(expected_signals_bytes(rows), calc_files)
        assert result.is_err
        assert result.danger_err.kind == EXPECTATION_PROVENANCE_UNRESOLVED

    # frob:tests python/regolith/backends/harness_pack.py::check_expectation_provenance
    def test_sheet_with_no_digest_and_row_with_no_claim_name_are_not_indexed(
        self,
    ) -> None:
        """A sheet dict with no ``chain.sheet_digest`` and an audit row
        with no ``claim_name`` contribute nothing to the resolution
        sets (the honest degenerate case), never a spurious match."""
        rows = (
            ExpectedSignal(
                channel=0,
                target_path="x.y",
                kind="claim",
                quantity="voltage",
                expected=None,
                units="",
                provenance=Provenance(kind="claim", ref="some_claim"),
            ),
        )
        calc_files = (
            OutputFile.of(
                "calc/calc_book.json",
                json.dumps({"sheets": [{"chain": {}}]}).encode("ascii"),
            ),
            OutputFile.of(
                "calc/audit_index.json",
                json.dumps({"rows": [{"claim_name": None}]}).encode("ascii"),
            ),
        )
        result = check_expectation_provenance(expected_signals_bytes(rows), calc_files)
        assert result.is_err
        assert result.danger_err.kind == EXPECTATION_PROVENANCE_UNRESOLVED
        assert "claim ref" in result.danger_err.message


class TestCheckBringupExpectationAuthoredPostureExtra:
    # frob:tests python/regolith/backends/harness_pack.py::check_bringup_expectation_authored_posture
    def test_malformed_expected_signals_json_refuses(self) -> None:
        from regolith.backends.harness_pack import (
            check_bringup_expectation_authored_posture,
        )

        result = check_bringup_expectation_authored_posture(b"not json", ())
        assert result.is_err
        assert result.danger_err.kind == "expected_signals_malformed"

    # frob:tests python/regolith/backends/harness_pack.py::check_bringup_expectation_authored_posture
    def test_unresolvable_record_ref_is_left_to_the_other_check(self) -> None:
        """A `record`-kind ref that does not resolve at all is
        `check_expectation_provenance`'s job (E1101); this check only
        judges POSTURE on a ref that DID resolve, so an unresolvable
        ref here is skipped, never a crash or a false posture refusal."""
        import json

        from regolith.backends.harness_pack import (
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
                        "ref": "does_not_exist(5ms)",
                        "reason": "",
                    },
                    "note": "",
                }
            ],
        }
        result = check_bringup_expectation_authored_posture(
            json.dumps(doc).encode("ascii"),
            ("examples/tracks/cuprite/records",),
            package="examples.tracks.cuprite",
        )
        assert result.is_ok


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

    def test_header_present_prints_connector_details(self) -> None:
        header = TapHeaderRecord(
            key="dft_hdr",
            channels=8,
            positions=16,
            pitch_mm=2.54,
            connector="idc",
            ordering="signal_on_odd",
            ground="even",
            keying="pin1",
            reference="std.elec/records/dft.toml",
            source_file="dft.toml",
        )
        tap_set = _tap_set("Scope0.out")
        text = render_bringup("proj", tap_set, header, ())
        assert "Tap header: `dft_hdr`" in text
        assert "connector pin 1" in text

    def test_degraded_calc_sheet_row_names_the_reason(self) -> None:
        tap_set = _tap_set("Scope0.out")
        expected = (
            ExpectedSignal(
                channel=0,
                target_path="Scope0.out",
                kind="rail",
                quantity="voltage",
                expected=None,
                units="",
                provenance=Provenance(
                    kind="calc_sheet", ref="local-blake3:abc", reason="unit_unresolved"
                ),
                note="no_verified_expectation",
            ),
        )
        text = render_bringup("proj", tap_set, None, expected)
        assert "no printed value -- discharged" in text
        assert "unit_unresolved" in text

    def test_claim_row_names_the_claim(self) -> None:
        tap_set = _tap_set("Scope0.out")
        expected = (
            ExpectedSignal(
                channel=0,
                target_path="Scope0.out",
                kind="rail",
                quantity="voltage",
                expected=None,
                units="",
                provenance=Provenance(
                    kind="claim", ref="rail_ripple", reason="claim status=deferred"
                ),
                note="no_verified_expectation",
            ),
        )
        text = render_bringup("proj", tap_set, None, expected)
        assert "claim `rail_ripple` declared but not discharged" in text

    def test_none_provenance_row_names_the_reason(self) -> None:
        tap_set = _tap_set("Scope0.out")
        expected = (
            ExpectedSignal(
                channel=0,
                target_path="Scope0.out",
                kind="rail",
                quantity="voltage",
                expected=None,
                units="",
                provenance=Provenance(
                    kind="none", ref="", reason="no obligation traces this"
                ),
                note="no_verified_expectation",
            ),
        )
        text = render_bringup("proj", tap_set, None, expected)
        assert "no verified expectation (no obligation traces this)" in text

    def test_unallocated_candidates_are_named(self) -> None:
        tap_set = TapSet(
            unallocated=(
                UnallocatedTap(
                    target_path="over.flow",
                    kind="signal",
                    why="claim x",
                    reason="header capacity exceeded",
                ),
            )
        )
        text = render_bringup("proj", tap_set, None, ())
        assert "over.flow" in text
        assert "header capacity exceeded" in text


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

    from regolith.backends.harness_pack import (
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
                "expected": None,
                "units": "",
                "provenance": {"kind": "none", "ref": "", "reason": "no obligation"},
                "note": "no_verified_expectation",
            }
        ],
    }
    expected_bytes = json.dumps(doc).encode("ascii")
    result = check_bringup_expectation_authored_posture(
        expected_bytes,
        ("examples/tracks/cuprite/records",),
        package="examples.tracks.cuprite",
    )
    assert result.is_ok
