"""Tests for `regolith.orchestrator.test_expect` (T-0036 phase 2): the
five `expect:` form evaluators (WO-83 slice B). Despite living beside
`test_runner.py`, `test_expect.py` is production code (the module
docstring's own AD-22 wall notes); these tests cover each evaluator's
parse-failure branch, match branch, and no-match branch directly with
small hand-built fixtures -- no real pipeline run needed since every
evaluator is a pure function over already-produced pipeline output.
"""

from __future__ import annotations

from regolith._schema.models import Coverage, Evidence, Status1, Status2
from regolith.harness.quantity import f64_to_bits
from regolith.orchestrator.discharge import ObligationResult
from regolith.orchestrator.test_expect import (
    eval_count,
    eval_diagnostic,
    eval_value,
    eval_verdict,
    eval_winner,
)


# frob:ticket T-0036
def _evidence(status: object) -> Evidence:
    """A minimal, otherwise-inert `Evidence` row for `ObligationResult` fixtures."""
    return Evidence(
        cost=0,
        coverage=Coverage(fraction_bits=f64_to_bits(1.0), axes=[]),
        eps_bits=0,
        hash="blake3:test-evidence",
        margin_bits=f64_to_bits(1.0),
        model_id="test.model",
        status=status,
        value_bits=0,
    )


# --- eval_diagnostic ---------------------------------------------------


# frob:ticket T-0036
def test_eval_diagnostic_unparseable_tail_fails_with_message() -> None:
    """A tail with no ` on ` separator is an unparseable-expectation fail."""
    outcome = eval_diagnostic("garbage tail with no separator", "anything")
    assert outcome.ok is False
    assert "unparseable diagnostic expectation" in outcome.detail


# frob:ticket T-0036
def test_eval_diagnostic_matches_code_and_subject_present() -> None:
    """Both the bracketed code and the subject text present -> pass."""
    outcome = eval_diagnostic("DIAG001 on mount.dia", "[DIAG001] failed on mount.dia")
    assert outcome.ok is True
    assert "found" in outcome.detail


# frob:ticket T-0036
def test_eval_diagnostic_subject_missing_fails() -> None:
    """The code appears but the subject text does not -> fail."""
    outcome = eval_diagnostic("DIAG001 on mount.dia", "[DIAG001] failed on other.part")
    assert outcome.ok is False
    assert "NOT found" in outcome.detail


# --- eval_verdict --------------------------------------------------------


# frob:ticket T-0036
def test_eval_verdict_unparseable_tail_fails() -> None:
    """A tail with no `=` status assignment is unparseable."""
    outcome = eval_verdict("not a valid tail", [])
    assert outcome.ok is False
    assert "unparseable verdict expectation" in outcome.detail


# frob:ticket T-0036
def test_eval_verdict_no_matching_claim_fails() -> None:
    """No claim in `named_results` has the wanted name -> fail, named as such."""
    outcome = eval_verdict("Group.rail_stress = discharged", [])
    assert outcome.ok is False
    assert "no matching claim found" in outcome.detail


# frob:ticket T-0036
def test_eval_verdict_discharged_matches() -> None:
    """A resolved result's actual status is `discharged`."""
    result = ObligationResult(
        key="k", subject_ref="blake3:aaa", evidence=_evidence(Status1.discharged)
    )
    outcome = eval_verdict(
        "Group.rail_stress = discharged", [("rail_stress", result)]
    )
    assert outcome.ok is True
    assert "actual = discharged" in outcome.detail


# frob:ticket T-0036
def test_eval_verdict_violated_actual_mismatches_expected_discharged() -> None:
    """A violated result's actual status is `violated`, mismatching a
    `discharged` expectation -> fail with both sides in the detail."""
    result = ObligationResult(
        key="k", subject_ref="blake3:bbb", evidence=_evidence(Status2.violated)
    )
    outcome = eval_verdict(
        "Group.rail_stress = discharged", [("rail_stress", result)]
    )
    assert outcome.ok is False
    assert "actual = violated" in outcome.detail


# frob:ticket T-0036
def test_eval_verdict_indeterminate_when_neither_resolved_nor_violated() -> None:
    """A bare deferral/no-evidence result reads as `indeterminate`."""
    result = ObligationResult(key="k", subject_ref="blake3:ccc")
    outcome = eval_verdict(
        "Group.rail_stress = indeterminate", [("rail_stress", result)]
    )
    assert outcome.ok is True
    assert "actual = indeterminate" in outcome.detail


# --- eval_value ------------------------------------------------------


# frob:ticket T-0036
def test_eval_value_unparseable_tail_fails() -> None:
    """A tail missing the `within [lo, hi]` shape is unparseable."""
    outcome = eval_value("garbage", [])
    assert outcome.ok is False
    assert "unparseable value expectation" in outcome.detail


# frob:ticket T-0036
def test_eval_value_no_resolution_in_range_fails_naming_the_ad22_wall() -> None:
    """No resolution's magnitude falls in range -> fail, naming AD-22."""
    resolutions = [{"value": {"magnitude": 99.0}, "cause": {"ref": "x", "cause": "y"}}]
    outcome = eval_value("mount.dia within [1, 5]", resolutions)
    assert outcome.ok is False
    assert "AD-22 wall" in outcome.detail


# frob:ticket T-0036
def test_eval_value_non_numeric_magnitude_is_skipped() -> None:
    """A resolution whose magnitude is not int/float is skipped, not crashed on."""
    resolutions = [
        {"value": {"magnitude": "not-a-number"}},
        {"value": {"magnitude": 3.0}, "cause": {"ref": "backing", "cause": "load"}},
    ]
    outcome = eval_value("mount.dia within [1, 5]", resolutions)
    assert outcome.ok is True
    assert "matched magnitude=3.0" in outcome.detail


# frob:ticket T-0036
def test_eval_value_in_range_with_matching_cause_class_passes() -> None:
    """An in-range magnitude whose cause text contains the requested
    class token passes; the cause_class filter is a substring match."""
    resolutions = [
        {"value": {"magnitude": 2.5}, "cause": {"ref": "backing_ref", "cause": "load"}}
    ]
    outcome = eval_value("mount.dia within [1, 5] cause backing", resolutions)
    assert outcome.ok is True


# frob:ticket T-0036
def test_eval_value_in_range_but_wrong_cause_class_is_skipped() -> None:
    """An in-range magnitude whose cause text does NOT contain the
    requested class token is skipped (continue branch), not a false pass."""
    resolutions = [
        {"value": {"magnitude": 2.5}, "cause": {"ref": "unrelated", "cause": "other"}}
    ]
    outcome = eval_value("mount.dia within [1, 5] cause backing", resolutions)
    assert outcome.ok is False


# --- eval_count ------------------------------------------------------


# frob:ticket T-0036
def test_eval_count_unparseable_tail_fails() -> None:
    """A tail with no `= <n>` count assignment is unparseable."""
    outcome = eval_count("garbage tail", {})
    assert outcome.ok is False
    assert "unparseable count expectation" in outcome.detail


# frob:ticket T-0036
def test_eval_count_matches_prefix_in_subject_ref_and_name() -> None:
    """Obligations whose `subject_ref` or claim `name` mentions the
    path's leading segment are counted; a non-list `obligations` value
    and a non-dict obligation row are both silently skipped."""
    payload = {
        "obligations": [
            {"subject_ref": "mount.dia:blake3:x", "claim": {"name": "other"}},
            {"subject_ref": "blake3:y", "claim": {"name": "mount_check"}},
            {"subject_ref": "blake3:z", "claim": {}},
            "not-a-dict",
        ]
    }
    outcome = eval_count("mount = 2", payload)
    assert outcome.ok is True
    assert "actual (best-effort prefix match) = 2" in outcome.detail


# frob:ticket T-0036
def test_eval_count_non_list_obligations_counts_zero() -> None:
    """A payload whose `obligations` is not a list counts zero, not raised."""
    outcome = eval_count("mount = 0", {"obligations": "not-a-list"})
    assert outcome.ok is True


# --- eval_winner ------------------------------------------------------


# frob:ticket T-0036
def test_eval_winner_unparseable_tail_fails() -> None:
    """A tail missing the `= <candidate>` shape is unparseable."""
    outcome = eval_winner("garbage", {})
    assert outcome.ok is False
    assert "unparseable winner expectation" in outcome.detail


# frob:ticket T-0036
def test_eval_winner_no_assignment_fails_naming_no_winner() -> None:
    """`winner_assignment is None` (infeasible/no choice points) -> fail."""
    outcome = eval_winner("gearbox = ratio_a", None)
    assert outcome.ok is False
    assert "optimizer produced no winner" in outcome.detail


# frob:ticket T-0036
def test_eval_winner_matches_expected_candidate() -> None:
    """The real winner assignment for the subject equals the expected candidate."""
    outcome = eval_winner("gearbox = ratio_a", {"gearbox": "ratio_a"})
    assert outcome.ok is True
    assert "actual = ratio_a" in outcome.detail


# frob:ticket T-0036
def test_eval_winner_mismatched_candidate_fails() -> None:
    """A different real winner for the same subject -> fail, both named."""
    outcome = eval_winner("gearbox = ratio_a", {"gearbox": "ratio_b"})
    assert outcome.ok is False
    assert "actual = ratio_b" in outcome.detail
