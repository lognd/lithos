"""Consume the payload's ``WaiveLedger`` at the release gate (WO-98).

The Rust core builds the todo/assume/waive ledger (INV-12 audit surface)
and puts it on ``BuildPayload.ledger``; this module turns that ledger
into the Python release gate's ACCEPTANCE decision (INV-24 completed,
D206): which otherwise-unresolved obligations are *accepted deviations*
and which remain refusing.

Load-bearing honesty rules (regolith/12 sec. 3, D206/D207):

* An evidence-carrying waiver whose evidence meets the target claim's
  trust floor (INV-14) ACCEPTS the obligations it matched: their true
  status is untouched (INV-2 -- an acceptance never forges ``discharged``),
  the release passes WITH the deviation listed.
* A bare (evidence-less) waiver and an ``assume!``/``todo!`` remain
  release-gated: durable acceptance needs evidence; per-item CLI
  acknowledgment (``--accept``) is exploration-only (rule 9) and the
  report says so.
* An expired waiver behaves as absent (its matched obligations refuse
  again) and surfaces the stale error (rule 8) -- the Rust
  ``release_blocked`` does NOT check expiry, so the gate owns it here.
* A stale waiver (``WaiverKind::Stale``) is already a Rust diagnostic
  (E0701 -> the build is not clean); the gate does not double-report it.
* A ``by doc(<ref>)`` evidence ref (D207) resolves through the record-
  path machinery to an in-project engineering memo (``memos/*.md``),
  hash-pinned; an unsigned memo confers ``community`` tier (INV-14). A
  dangling memo ref refuses loudly.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import blake3
from pydantic import BaseModel, ConfigDict

from regolith._schema.models import WaiveLedger, WaiverRecord
from regolith.logging_setup import get_logger
from regolith.magnetite.trust import TrustTier, tier_from_name
from regolith.orchestrator.discharge import ObligationResult

_log = get_logger(__name__)

# `<class>(<inner>)` shaped evidence ref, e.g. `doc(memos/x.md)` or
# `test(fai_207)`. The class selects the resolver; only `doc` resolves
# to an in-project artifact (D207), every other class is an external
# reference whose honest, unverifiable floor is `community`.
_EVIDENCE_RE = re.compile(r"^([a-z_]+)\((.*)\)$")
_DOC_CLASS = "doc"


# frob:doc docs/modules/py-orchestrator.md#acceptance
class WaiverEvidenceTier(BaseModel):
    """The trust tier a waiver's ``by <evidence>`` clause confers, plus
    the resolved provenance pin (D207).

    ``tier`` is ``None`` when the evidence ref is a dangling ``doc(<ref>)``
    (an in-project memo that does not resolve) -- a loud refusal, never a
    silent community fallback. ``digest`` is the memo's content pin when a
    ``doc`` ref resolved (empty for external classes, which pin nothing
    in-project).
    """

    model_config = ConfigDict(frozen=True)

    tier: TrustTier | None
    digest: str = ""
    detail: str = ""


# frob:doc docs/modules/py-orchestrator.md#acceptance
class Deviation(BaseModel):
    """One accepted deviation for the gate summary + acceptance ledger.

    Mirrors the source waiver's declared surface (target/scope/basis/
    evidence/kind/match set/expiry) plus the obligation content hashes it
    actually accepted this build -- the audit row `ship` writes into
    ``acceptance_ledger.json`` and `ship --explain` lists.
    """

    model_config = ConfigDict(frozen=True)

    target: str
    scope: str | None
    basis: str
    evidence: str | None
    kind: str
    accepted: tuple[str, ...]
    match_set: tuple[str, ...]
    expires: str | None
    evidence_digest: str = ""


# frob:doc docs/modules/py-orchestrator.md#acceptance
class AcceptanceOutcome(BaseModel):
    """The release gate's read of the ledger (WO-98).

    ``accepted_hashes`` are the obligation content hashes an
    evidence-carrying, trust-floor-meeting, unexpired waiver accepted --
    the gate removes them from the refusing counts (kept DISTINCT as
    ``GateCounts.accepted_deviation``, never folded into ``discharged``).
    ``ledger_blocked`` is set when the ledger itself carries a hole that
    refuses independent of the results (a ``todo!``/``assume!`` that
    emitted no obligation of its own). ``refusals``/``errors`` are the
    human-readable reasons the gate reports.
    """

    model_config = ConfigDict(frozen=True)

    accepted_hashes: tuple[str, ...] = ()
    deviations: tuple[Deviation, ...] = ()
    refusals: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    cli_accepts_used: tuple[str, ...] = ()
    ledger_blocked: bool = False

    @property
    # frob:doc docs/modules/py-orchestrator.md#acceptance
    # frob:waive TEST001 reason="acceptance helper, tested via release-gate tests"
    def accepted_set(self) -> frozenset[str]:
        """The accepted content hashes as a set (gate-side membership test)."""
        return frozenset(self.accepted_hashes)


def _expired(expires: str, as_of: date) -> bool:
    """True iff the ``expires:`` marker is a past date (regolith/12 rule 8).

    An unparseable marker is treated conservatively as NOT expired (the
    core validates the date shape upstream; a marker the gate cannot
    parse is not grounds to silently drop an otherwise-valid deviation).
    """
    try:
        return date.fromisoformat(expires.strip()) < as_of
    except ValueError:
        _log.warning(
            "waiver expiry %r is not an ISO date; treating as unexpired", expires
        )
        return False


def _resolve_memo(
    ref: str, project_root: str, record_search_paths: tuple[str, ...]
) -> WaiverEvidenceTier:
    """Resolve a ``doc(<ref>)`` engineering-memo evidence ref (D207).

    Searches the project root first, then the record search paths (the
    SAME D192/D201 roots the cost/frame/plan loaders receive), for
    ``<ref>``. A resolved memo is hash-pinned (blake3) and confers
    ``community`` tier (INV-14: unsigned in-project content). A ref that
    resolves nowhere returns ``tier=None`` -- a dangling memo the gate
    refuses loudly, never a silent pass.
    """
    roots = (project_root, *record_search_paths)
    for root in roots:
        candidate = Path(root) / ref
        if candidate.is_file():
            digest = "blake3:" + blake3.blake3(candidate.read_bytes()).hexdigest()
            _log.debug("memo evidence %s resolved at %s (%s)", ref, candidate, digest)
            return WaiverEvidenceTier(
                tier=TrustTier.COMMUNITY, digest=digest, detail=str(candidate)
            )
    _log.warning("memo evidence doc(%s) resolves to no in-project file", ref)
    return WaiverEvidenceTier(
        tier=None, detail=f"memo doc({ref}) resolves to no in-project file"
    )


def _waiver_evidence_tier(
    evidence: str, project_root: str, record_search_paths: tuple[str, ...]
) -> WaiverEvidenceTier:
    """The tier a waiver's evidence clause confers (D207).

    A ``doc(<ref>)`` ref resolves to an in-project memo (community, or a
    loud refusal when dangling). Every other evidence class (``test``,
    ``sim``, ``fea``, ...) is an external reference the toolchain cannot
    verify in-project: its honest floor is ``community`` (the design's
    author asserts the referenced artifact exists; the basis is the
    social contract). An unparenthesized ref confers ``community`` too.
    """
    match = _EVIDENCE_RE.match(evidence.strip())
    if match and match.group(1) == _DOC_CLASS:
        return _resolve_memo(match.group(2), project_root, record_search_paths)
    return WaiverEvidenceTier(tier=TrustTier.COMMUNITY)


def _tier_meets_floor(tier: TrustTier, floor: str | None) -> bool:
    """True iff ``tier`` satisfies a claim's ``trust: >= <floor>`` (INV-14).

    No floor always passes. An unparseable floor is conservatively unmet
    (a floor the gate cannot certify), matching ``_meets_trust_floor``.
    """
    if floor is None:
        return True
    parsed = tier_from_name(floor)
    if parsed.is_err:
        _log.warning("claim trust floor %r is unparseable; treating as unmet", floor)
        return False
    return tier.meets(parsed.danger_ok)


# frob:doc docs/modules/py-orchestrator.md#acceptance
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def compute_acceptance(
    ledger_raw: object,
    results: tuple[ObligationResult, ...],
    *,
    project_root: str,
    record_search_paths: tuple[str, ...] = (),
    as_of: date | None = None,
    cli_accepts: frozenset[str] = frozenset(),
) -> AcceptanceOutcome:
    """Turn a payload ``ledger`` into the release gate's acceptance read.

    ``ledger_raw`` is ``payload["ledger"]`` (the ``WaiveLedger`` wire
    shape) or ``None``/empty for a build with no ledger. ``results`` are
    the discharge results (each carrying its ``content_hash``, WO-98).
    ``cli_accepts`` are the exploration-only ``--accept <target>`` acks
    (rule 9): they let a bare waiver pass FOR THIS RUN ONLY, and the
    outcome records that they were used so the report can say so.
    """
    if not ledger_raw:
        return AcceptanceOutcome()
    ledger = WaiveLedger.model_validate(ledger_raw)
    results_by_hash = {r.content_hash: r for r in results if r.content_hash}
    as_of = as_of or date.today()

    accepted: set[str] = set()
    deviations: list[Deviation] = []
    refusals: list[str] = []
    errors: list[str] = []
    cli_used: list[str] = []
    ledger_blocked = False

    for entry in ledger.entries:
        # The pure-ledger holes: an `assume!`/`todo!`/unwaived
        # indeterminate that carries no source `waive`. These stay
        # release-gated (rung 6 or a raw hole); a `--accept` names the
        # exact text for exploration only.
        todo = getattr(entry, "todo", None)
        assume = getattr(entry, "assume", None)
        indeterminate = getattr(entry, "indeterminate", None)
        waived: WaiverRecord | None = getattr(entry, "waived", None)
        if todo is not None:
            refusals.append(f"todo!: {todo}")
            ledger_blocked = True
            continue
        if assume is not None:
            if assume in cli_accepts:
                cli_used.append(assume)
                _log.info("assume! %r accepted for exploration (--accept)", assume)
            else:
                refusals.append(f"assume!: {assume} (release-gated -- no evidence)")
                ledger_blocked = True
            continue
        if indeterminate is not None:
            # An unwaived indeterminate also surfaces as an unresolved
            # RESULT; the gate refuses it there. Nothing extra to do.
            continue
        if waived is None:
            continue

        w = waived.waiver
        scope = w.scope
        matched = tuple(waived.matched)
        match_set = tuple(waived.match_set or ())

        # Stale is already an E0701 diagnostic Rust-side (the build is not
        # clean); do not double-report -- just never accept (matched is
        # empty for a stale waiver anyway).
        if waived.kind == "stale":
            continue

        if w.expires is not None and _expired(w.expires, as_of):
            errors.append(
                f"waiver `{w.target}` expired {w.expires}; behaves as absent "
                "(regolith/12 rule 8)"
            )
            continue

        if w.evidence is None:
            if w.target in cli_accepts:
                cli_used.append(w.target)
                accepted.update(matched)
                _log.info(
                    "bare waiver `%s` accepted for exploration (--accept)", w.target
                )
            else:
                refusals.append(
                    f"bare waiver `{w.target}` (no `by` evidence; release-gated "
                    "-- regolith/12 rule 3)"
                )
                ledger_blocked = True
            continue

        # Evidence-carrying: resolve its tier, then bind trust floors.
        ev = _waiver_evidence_tier(w.evidence, project_root, record_search_paths)
        if ev.tier is None:
            errors.append(
                f"waiver `{w.target}` cites dangling evidence "
                f"`{w.evidence}`: {ev.detail}"
            )
            continue

        floor_failed = False
        this_accepted: list[str] = []
        for h in matched:
            result = results_by_hash.get(h)
            floor = result.trust_floor if result is not None else None
            if _tier_meets_floor(ev.tier, floor):
                this_accepted.append(h)
            else:
                floor_failed = True
                errors.append(
                    f"waiver `{w.target}` evidence `{w.evidence}` confers "
                    f"{ev.tier.name.lower()}, below the claim's trust floor "
                    f"`{floor}` (regolith/12 rule 7)"
                )
        accepted.update(this_accepted)
        # List the deviation whenever it contributed acceptance, or when
        # it is a rule-pack deferral the core cannot see obligations for
        # (empty match set, evidence present -- Rust's own listed-deviation
        # case). A deviation that ENTIRELY failed its trust floor is not
        # listed as accepted; the error above carries it.
        if this_accepted or (not matched and not floor_failed):
            deviations.append(
                Deviation(
                    target=w.target,
                    scope=scope,
                    basis=w.basis,
                    evidence=w.evidence,
                    kind=waived.kind,
                    accepted=tuple(this_accepted),
                    match_set=match_set,
                    expires=w.expires,
                    evidence_digest=ev.digest,
                )
            )

    outcome = AcceptanceOutcome(
        accepted_hashes=tuple(sorted(accepted)),
        deviations=tuple(deviations),
        refusals=tuple(refusals),
        errors=tuple(errors),
        cli_accepts_used=tuple(sorted(set(cli_used))),
        ledger_blocked=ledger_blocked,
    )
    if accepted or refusals or errors:
        _log.info(
            "acceptance: %d accepted, %d listed deviation(s), %d refusal(s), "
            "%d error(s)",
            len(accepted),
            len(deviations),
            len(refusals),
            len(errors),
        )
    return outcome


# frob:doc docs/modules/py-orchestrator.md#acceptance
# frob:waive TEST001 reason="acceptance helper, tested via release-gate tests"
def acceptance_ledger_bytes(outcome: AcceptanceOutcome) -> bytes:
    """The ``acceptance_ledger.json`` bytes `regolith ship` writes into a
    release package (WO-98 deliverable 3).

    Records every accepted deviation with its full declared surface
    (target, scope, basis, evidence ref + resolved pin, kind, accepted +
    authored match sets, expiry) plus any exploration acknowledgments,
    refusals, and errors -- the audit surface INV-12 requires. Emitted
    deterministically (sorted keys, sorted deviations by target then
    evidence) so two ships of the same design are byte-identical.
    """
    doc = {
        "accepted_deviations": [
            {
                "target": d.target,
                "scope": d.scope,
                "basis": d.basis,
                "evidence": d.evidence,
                "evidence_digest": d.evidence_digest,
                "kind": d.kind,
                "accepted": list(d.accepted),
                "match_set": list(d.match_set),
                "expires": d.expires,
            }
            for d in sorted(
                outcome.deviations, key=lambda d: (d.target, d.evidence or "")
            )
        ],
        "cli_accepts_used": list(outcome.cli_accepts_used),
        "refusals": list(outcome.refusals),
        "errors": list(outcome.errors),
    }
    return json.dumps(
        doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True, indent=2
    ).encode("ascii")


# frob:doc docs/modules/py-orchestrator.md#acceptance
def accepted_match_sets_by_target(
    outcome: AcceptanceOutcome,
) -> dict[str, frozenset[str]]:
    """This build's accepted obligation hashes, unioned per waiver target
    (F124.2 lockfile persistence).

    The lockfile records exactly this map so the NEXT build can diff its own
    accepted set against it (``match_set_growth_warnings``) and catch an
    unscoped waiver quietly absorbing a new obligation across builds (INV-12
    rule 5). Two deviations sharing a target (e.g. a scoped and an unscoped
    one) union -- the growth check filters scoped targets itself.
    """
    by_target: dict[str, set[str]] = {}
    for dev in outcome.deviations:
        by_target.setdefault(dev.target, set()).update(dev.accepted)
    return {target: frozenset(hashes) for target, hashes in by_target.items()}


# frob:doc docs/modules/py-orchestrator.md#acceptance
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def match_set_growth_warnings(
    outcome: AcceptanceOutcome,
    prior_match_sets: Mapping[str, frozenset[str]],
) -> tuple[str, ...]:
    """Loud warnings for each UNSCOPED accepted deviation whose match set
    grew vs the prior lockfile (regolith/12 rule 5, INV-12).

    An unscoped waiver covers its target wherever it fails; if it starts
    covering a NEW obligation the prior build did not record, the waiver
    is quietly absorbing a regression -- named here (and logged) so the
    growth is a visible build event, never silent. ``prior_match_sets``
    maps a waiver target to the content hashes it accepted previously
    (from the prior lockfile); a scoped waiver is exempt (its scope is
    the author's explicit, reviewed boundary).
    """
    warnings: list[str] = []
    for dev in outcome.deviations:
        if dev.scope is not None:
            continue
        prior = prior_match_sets.get(dev.target, frozenset())
        new_members = tuple(sorted(set(dev.accepted) - prior))
        if prior and new_members:
            msg = (
                f"unscoped waiver `{dev.target}` match set GREW: now accepts "
                f"{len(new_members)} new obligation(s) not in the prior "
                f"lockfile: {', '.join(m[:12] for m in new_members)}"
            )
            _log.warning(msg)
            warnings.append(msg)
    return tuple(warnings)
