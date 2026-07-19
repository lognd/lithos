"""WO-83 slice B: the five `expect:` form evaluators (charter
toolchain/37 sec. 1.3).

Each evaluator takes the REAL pipeline output for one scenario (a
:class:`~regolith.orchestrator.orchestrate.BuildReport` plus, for the
`winner` form, an optimizer trace the runner computed through the
ordinary :func:`~regolith.orchestrator.optimize.optimize_discrete`
door) and a parsed expectation tail, and returns whether the real
output matches -- never overriding, only observing (INV-2).

Two forms (`value`, `count`) hit a genuine AD-22 wall recorded here,
not hidden: `regolith_qty::Resolution` carries a value and a `Cause`
reference string, but NO slot/path field, so a scenario cannot bind a
resolution to a source path like `mount.dia` structurally -- the wire
shape does not carry it. Until a producer-side fix lands (a WO-29-
shaped follow-up naming this gap, per AD-22's escalation rule), this
runner matches `value`/`count` expectations by best-effort text
matching against the cause reference / claim name / rendered output --
the SAME documented-simplification posture `regolith.docgen.status.
claim_statuses` already uses for verdict-by-name matching (D127
precedent), not a new invention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from regolith.orchestrator.discharge import ObligationResult

_DIAG_RE = re.compile(r"^(\S+)\s+on\s+(.+)$")
# The claim-path vocabulary: dotted segments, each optionally carrying
# a forall-expansion suffix (`strength[G1]`, WO-68 section families) --
# ONE definition shared by every expectation form so the test-runner
# grammar can never lag the claim names the toolchain itself emits
# (WO115-F3: `[\w.]+` predated the expansion and made expanded claims
# unaddressable in `expect:` blocks).
_CLAIM_PATH = r"[\w.\[\]]+"
_VERDICT_RE = re.compile(
    rf"^({_CLAIM_PATH})\s*=\s*(discharged|violated|indeterminate)\s*$"
)
_VALUE_RE = re.compile(
    rf"^({_CLAIM_PATH})\s+within\s+\[([^\],]+),\s*([^\]]+)\]"
    r"(?:\s+cause\s+(\S+))?\s*$"
)
_COUNT_RE = re.compile(rf"^({_CLAIM_PATH})\s*=\s*(\d+)\s*$")
_WINNER_RE = re.compile(rf"^({_CLAIM_PATH})\s*=\s*(\S+.*)$")


@dataclass(frozen=True)
class ExpectOutcome:
    """One expectation's verdict: pass/fail plus an expected-vs-actual
    detail line, rendered through the same style as the ONE renderer
    (AD-7) so a failure reads like every other diagnostic."""

    ok: bool
    detail: str


def _mag(text: str) -> float:
    """Best-effort numeric magnitude parse off a `<num><unit>` token
    (e.g. `5mm` -> `5.0`); unit CONVERSION is not attempted (v1 cut,
    recorded in the WO close-out) -- expectations compare magnitudes
    directly, so mixed units on the same slot would false-fail loudly
    rather than silently mismatch."""
    m = re.match(r"^\s*([+-]?\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else float("nan")


def eval_diagnostic(tail: str, rendered: str) -> ExpectOutcome:
    """`diagnostic <CODE> on <subject>`: the code and subject text must
    both appear in the ONE renderer's output (reused verbatim, AD-7 --
    no second rendering of diagnostics)."""
    m = _DIAG_RE.match(tail.strip())
    if m is None:
        return ExpectOutcome(False, f"unparseable diagnostic expectation: {tail!r}")
    code, subject = m.group(1), m.group(2).strip()
    code_hit = f"[{code}]" in rendered or code in rendered
    subject_hit = subject in rendered
    ok = code_hit and subject_hit
    return ExpectOutcome(
        ok,
        f"expected diagnostic {code} on {subject}; "
        f"{'found' if ok else 'NOT found'} in rendered output",
    )


def eval_verdict(
    tail: str, named_results: list[tuple[str, ObligationResult]]
) -> ExpectOutcome:
    """`verdict <Group.claim> = <status>`: matched by the claim's own
    `name` (last path segment), the D127 best-effort convention
    `claim_statuses` already established -- a claim's declaring group
    is not separately carried in `regolith_oblig::Obligation`.

    ``named_results`` is `[(claim_name, ObligationResult), ...]` -- the
    runner zips `BuildPayload.obligations[i].claim.name` with
    `BuildReport.results[i]` (source order, INV-10) before calling.
    """
    m = _VERDICT_RE.match(tail.strip())
    if m is None:
        return ExpectOutcome(False, f"unparseable verdict expectation: {tail!r}")
    path, expected_status = m.group(1), m.group(2)
    want_name = path.rsplit(".", 1)[-1]
    for claim_name, result in named_results:
        if claim_name != want_name:
            continue
        if result.is_resolved:
            actual = "discharged"
        elif result.is_violated:
            actual = "violated"
        else:
            actual = "indeterminate"
        ok = actual == expected_status
        return ExpectOutcome(
            ok, f"expected verdict {path} = {expected_status}; actual = {actual}"
        )
    return ExpectOutcome(
        False, f"expected verdict {path} = {expected_status}; no matching claim found"
    )


# frob:waive TEST005 reason="measured 33.3% branch on 2026-07-19; backfill T-0036"
def eval_value(tail: str, resolutions: list[dict[str, object]]) -> ExpectOutcome:
    """`value <path> within [lo, hi] [cause <class>]`: the AD-22 wall
    (see module docstring) -- matched by scanning every resolution for
    one whose magnitude falls in range and (if given) whose cause
    reference text contains the expected class token."""
    m = _VALUE_RE.match(tail.strip())
    if m is None:
        return ExpectOutcome(False, f"unparseable value expectation: {tail!r}")
    path, lo_text, hi_text, cause_class = (
        m.group(1),
        m.group(2),
        m.group(3),
        m.group(4),
    )
    lo, hi = _mag(lo_text), _mag(hi_text)
    for res in resolutions:
        value = res.get("value", {})
        raw_mag = value.get("magnitude") if isinstance(value, dict) else None
        if not isinstance(raw_mag, (int, float)):
            continue
        mag: float = raw_mag
        if not (lo <= mag <= hi):
            continue
        cause = res.get("cause", {})
        cause_ref = str(cause.get("ref", "")) if isinstance(cause, dict) else ""
        cause_kind = str(cause.get("cause", "")) if isinstance(cause, dict) else ""
        if cause_class is not None and cause_class not in (cause_ref + cause_kind):
            continue
        return ExpectOutcome(
            True,
            f"expected value {path} within [{lo_text}, {hi_text}]"
            f"{f' cause {cause_class}' if cause_class else ''}; "
            f"matched magnitude={mag} cause={cause_kind}({cause_ref})",
        )
    return ExpectOutcome(
        False,
        f"expected value {path} within [{lo_text}, {hi_text}]"
        f"{f' cause {cause_class}' if cause_class else ''}; no resolution matched "
        "(AD-22 wall: Resolution carries no slot/path -- best-effort magnitude+cause "
        "scan found none)",
    )


def eval_count(tail: str, payload: dict[str, object]) -> ExpectOutcome:
    """`count <path> = <n>`: best-effort obligation-subject-prefix count
    (the same AD-22 wall as `value` -- entities are not separately
    enumerated in `BuildPayload`, so this counts obligations whose
    `subject_ref` or claim name mentions the path's leading segment)."""
    m = _COUNT_RE.match(tail.strip())
    if m is None:
        return ExpectOutcome(False, f"unparseable count expectation: {tail!r}")
    path, expected_n = m.group(1), int(m.group(2))
    prefix = path.split(".", 1)[0]
    obligations = payload.get("obligations", [])
    actual = 0
    if isinstance(obligations, list):
        for ob in obligations:
            if not isinstance(ob, dict):
                continue
            subject_ref = str(ob.get("subject_ref", ""))
            claim = ob.get("claim", {})
            name = str(claim.get("name") or "") if isinstance(claim, dict) else ""
            if prefix in subject_ref or prefix in name:
                actual += 1
    ok = actual == expected_n
    return ExpectOutcome(
        ok,
        f"expected count {path} = {expected_n}; actual (best-effort prefix match) = "
        f"{actual}",
    )


# frob:waive TEST005 reason="measured 55.6% branch on 2026-07-19; backfill T-0036"
def eval_winner(tail: str, winner_assignment: dict[str, str] | None) -> ExpectOutcome:
    """`winner <subject> = <candidate>`: matched against the real
    `optimize_discrete` winner (charter sec. 1.2's seeded-optimizer
    scenario), read off `BuildPayload.choice_points` -- never a
    second scoring path (AD-22)."""
    m = _WINNER_RE.match(tail.strip())
    if m is None:
        return ExpectOutcome(False, f"unparseable winner expectation: {tail!r}")
    subject, expected_candidate = m.group(1), m.group(2).strip()
    if winner_assignment is None:
        return ExpectOutcome(
            False,
            f"expected winner {subject} = {expected_candidate}; optimizer produced no "
            "winner (infeasible or no choice points)",
        )
    actual = winner_assignment.get(subject)
    ok = actual == expected_candidate
    return ExpectOutcome(
        ok, f"expected winner {subject} = {expected_candidate}; actual = {actual}"
    )
