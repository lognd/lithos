"""The parity ledger: ``regolith ship --explain``'s attribution report
(WO-63; charter ``31-flagships.md`` sec. 1 NORMATIVE, D170; AD-33).

Classifies every resolved value the build already emitted (lockfile
rows), every demand's discharge state (the release-gate's
``ObligationResult`` list), and every assume/waive ledger entry into
the provenance classes D170 names -- ``optimize(trace)``,
``dfm/drc/rule``, ``budget``, ``planner``, ``derived``, ``process``,
``asserted(literal, source position)``, ``assumed/waived(basis)`` --
ASCII tables plus a ``--json`` structured form, exactly like the WO-50
drawing audit's ``explain_report`` (one report mechanism, no new
renderer, AD-7).

Artifact-only (AD-22): this module reads ONLY the
:class:`~regolith.orchestrator.lockfile.Lockfile`,
:class:`~regolith.orchestrator.discharge.ObligationResult` list, and
``WaiveLedger`` a build already produced -- never the CST, never
``EntityDb``, never a second read path into compiler state.

Escalated gap (recorded per the dispatch instruction's AD-22 posture,
the F96 pattern): ``asserted(literal, source position)`` is NOT
reachable from any artifact this toolchain emits today. Every
non-literal value resolves into the lockfile carrying a ``Cause``
(``regolith_qty::Cause``, INV-21); a LITERAL value carries no
``Cause`` and produces no ``Diagnostic`` in the clean-build case (the
only diagnostics channel with source spans), so its source position is
invisible past the FFI boundary. Rather than invent a private read
into the entity DB (the exact side channel AD-22 forbids), this module
renders the attention list with an explicit, loud caveat instead of a
silently-empty (falsely "clean") list -- see
``docs/workflow/design-log/2026-07-09-cycle-31.md`` addendum D170-a
for the escalation record.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from regolith._schema.models import WaiveLedger
from regolith.logging_setup import get_logger
from regolith.orchestrator.discharge import ObligationResult
from regolith.orchestrator.lockfile import Lockfile

_log = get_logger(__name__)


# frob:doc docs/modules/py-backends.md#backends-parity
class ProvenanceClass(StrEnum):
    """The D170 provenance classes a resolved lockfile row falls into."""

    optimize = "optimize"
    rule = "dfm_drc_rule"
    budget = "budget"
    planner = "planner"
    derived = "derived"
    process = "process"
    report_error = "report_error"


# Lockfile cause-string prefix -> class (`lockfile.py`'s documented
# rendering, mirroring `regolith_qty::Cause`'s nine variants plus the
# two Python-authored cause families: `optimize(...)` (WO-55/56's
# `winner_lock_row`) and `realizer(...)` (WO-42's
# `realized_lock_rows`). Order matters only for readability; prefixes
# are disjoint by construction (each cause kind's opening token is
# unique).
_CAUSE_PREFIX_CLASS: tuple[tuple[str, ProvenanceClass], ...] = (
    ("optimize(", ProvenanceClass.optimize),
    ("dfm(", ProvenanceClass.rule),
    ("drc(", ProvenanceClass.rule),
    ("erc(", ProvenanceClass.rule),
    ("rule(", ProvenanceClass.rule),
    ("budget(", ProvenanceClass.budget),
    ("planner(", ProvenanceClass.planner),
    ("policy(", ProvenanceClass.planner),
    ("obligation(", ProvenanceClass.derived),
    ("derived(", ProvenanceClass.derived),
    ("derived_intent(", ProvenanceClass.derived),
    ("topology(", ProvenanceClass.derived),
    ("process(", ProvenanceClass.process),
    ("realizer(", ProvenanceClass.process),
    ("extern(", ProvenanceClass.process),
    # `regolith build`'s own cost-profile pin (WO-54/AD-29, `cli/app.py`
    # `build()`): a tooling/config decision, not a physics resolution --
    # grouped with the other manufacturing/process-shaped causes.
    ("cost_profile(", ProvenanceClass.process),
)

# The provenance classes the D170 bar treats as DECISION-shaped (free/
# select/allocated values resolved by an engine, per
# `03-value-sources.md` sec. 1's table): everything an optimizer, a
# rule-pack eager resolver, a budget allocator, or a planner pinned.
# `derived`/`process` are CONSEQUENCE-shaped (a system-analysis or
# manufacturing-process fact, never a free choice) and stay out of the
# decision table -- the WO-63 deliverable 2 distinction.
_DECISION_CLASSES = frozenset(
    {
        ProvenanceClass.optimize,
        ProvenanceClass.rule,
        ProvenanceClass.budget,
        ProvenanceClass.planner,
    }
)

# The honest caveat rendered in place of a per-literal attention list
# (module docstring; the escalated AD-22 gap). A single, loud, always-
# present note rather than a silently-empty list that could be misread
# as "this design has zero literals."
# frob:doc docs/modules/py-backends.md#backends-parity
LITERAL_ATTRIBUTION_CAVEAT = (
    "literal source-position attribution: UNAVAILABLE from current "
    "build artifacts (AD-22 gap -- no Cause/Resolution variant or "
    "clean-build diagnostic names an asserted literal's source "
    "position today; escalated, design-log "
    "2026-07-09-cycle-31.md addendum D170-a)"
)


# frob:doc docs/modules/py-backends.md#backends-parity
class ClassifiedRow(BaseModel):
    """One lockfile row, classified: its subject, slot, value, cause,
    and D170 provenance class."""

    model_config = ConfigDict(frozen=True)

    subject: str
    slot: str
    value: str
    cause: str
    provenance_class: ProvenanceClass


# frob:doc docs/modules/py-backends.md#backends-parity
def classify_cause(cause: str) -> ProvenanceClass:
    """Classify one rendered lockfile cause string by its prefix.

    An unrecognized prefix is ``report_error`` -- the bar's own honesty
    check (deliverable 1): never silently bucketed, always loudly
    listed by :func:`build_parity_report`.
    """
    for prefix, cls in _CAUSE_PREFIX_CLASS:
        if cause.startswith(prefix):
            return cls
    _log.warning("parity: unclassifiable lockfile cause: %r", cause)
    return ProvenanceClass.report_error


def _subject_of(slot: str) -> str:
    """The subject a slot belongs to: the entity name before its first
    ``.`` (``flange.radius`` -> ``flange``), or the whole slot if bare.
    """
    return slot.split(".", 1)[0] if "." in slot else slot


# frob:doc docs/modules/py-backends.md#backends-parity
def classify_lockfile(lockfile: Lockfile) -> tuple[ClassifiedRow, ...]:
    """Classify every row of every section of ``lockfile``, sorted by
    ``(subject, slot)`` (AD-6 determinism)."""
    rows = [
        ClassifiedRow(
            subject=_subject_of(row.slot),
            slot=row.slot,
            value=row.value,
            cause=row.cause,
            provenance_class=classify_cause(row.cause),
        )
        for section in lockfile.sections
        for row in section.rows
    ]
    return tuple(sorted(rows, key=lambda r: (r.subject, r.slot)))


# frob:doc docs/modules/py-backends.md#backends-parity
class DemandStatus(StrEnum):
    """A demand's discharge state (deliverable 2's demand table)."""

    discharged = "discharged"
    indeterminate = "indeterminate"
    violated = "violated"
    deviation = "deviation"


# frob:doc docs/modules/py-backends.md#backends-parity
class DemandRow(BaseModel):
    """One obligation's demand-table row: its subject/key, discharge
    state, and (for a deviation) the accepted basis."""

    model_config = ConfigDict(frozen=True)

    subject_ref: str
    key: str
    status: DemandStatus
    basis: str | None = None


def _deviation_bases(ledger: WaiveLedger) -> dict[str, str]:
    """Obligation content-hash -> accepted basis, for every waiver in
    ``ledger`` that carries evidence (regolith/12 sec. 3 rule 3: a
    waiver WITH a ``by`` clause is a deviation, not a bare waiver)."""
    bases: dict[str, str] = {}
    for entry in ledger.entries:
        waived = getattr(entry, "waived", None)
        if waived is None or waived.waiver.evidence is None:
            continue
        for obligation_hash in waived.matched:
            bases[obligation_hash] = waived.waiver.basis
    return bases


# frob:doc docs/modules/py-backends.md#backends-parity
def demand_table(
    results: Sequence[ObligationResult], ledger: WaiveLedger
) -> tuple[DemandRow, ...]:
    """The demand table: every obligation result's discharge state,
    sorted by ``(subject_ref, key)`` (AD-6). A result whose obligation
    key is covered by an evidence-carrying waiver renders as
    ``deviation`` (permitted in ``--release``, still listed) rather
    than its raw indeterminate/violated status -- regolith/12 sec. 6's
    audit-surface trail made concrete here.
    """
    deviations = _deviation_bases(ledger)
    rows = []
    for result in results:
        # WO-98: match on the obligation CONTENT hash the ledger records
        # (`WaiverRecord.matched`), not the registry-version-folded cache
        # key -- the two are different addresses, so keying on `key` never
        # matched a deviation (the demand table silently showed every
        # deviation as raw indeterminate/violated).
        basis = deviations.get(result.content_hash)
        if basis is not None:
            status = DemandStatus.deviation
        elif result.is_resolved:
            status = DemandStatus.discharged
        elif result.is_violated:
            status = DemandStatus.violated
        else:
            status = DemandStatus.indeterminate
        rows.append(
            DemandRow(
                subject_ref=result.subject_ref,
                key=result.key,
                status=status,
                basis=basis,
            )
        )
    return tuple(sorted(rows, key=lambda r: (r.subject_ref, r.key)))


# frob:doc docs/modules/py-backends.md#backends-parity
class AssumedWaivedRow(BaseModel):
    """One ``assume!``/bare-``waive`` ledger entry: kind, target, basis."""

    model_config = ConfigDict(frozen=True)

    kind: str  # "assume" | "waived"
    target: str
    basis: str


# frob:doc docs/modules/py-backends.md#backends-parity
def assumed_waived_rows(ledger: WaiveLedger) -> tuple[AssumedWaivedRow, ...]:
    """Every ``assume!``/``waived`` ledger entry (regolith/12 rungs 6-7),
    sorted by ``(kind, target)``. Evidence-carrying waivers (deviations)
    still appear here too -- they are counted in BOTH the demand table
    (as ``deviation``) and here (an accepted-risk record is always
    visible on its own ladder-rung trail, regolith/12 sec. 6).
    """
    rows = []
    for entry in ledger.entries:
        assume = getattr(entry, "assume", None)
        if assume is not None:
            rows.append(AssumedWaivedRow(kind="assume", target=assume, basis=assume))
            continue
        waived = getattr(entry, "waived", None)
        if waived is not None:
            rows.append(
                AssumedWaivedRow(
                    kind="waived",
                    target=waived.waiver.target,
                    basis=waived.waiver.basis,
                )
            )
    return tuple(sorted(rows, key=lambda r: (r.kind, r.target)))


# frob:doc docs/modules/py-backends.md#backends-parity
class ParityReport(BaseModel):
    """The full D170 parity ledger for one build: classified lockfile
    rows, the demand table, the assumed/waived ledger, and the
    report-error list (deliverable 1's own honesty path)."""

    model_config = ConfigDict(frozen=True)

    subjects: tuple[str, ...]
    rows: tuple[ClassifiedRow, ...]
    demands: tuple[DemandRow, ...]
    assumed_waived: tuple[AssumedWaivedRow, ...]
    report_errors: tuple[str, ...]

    # frob:doc docs/modules/py-backends.md#backends-parity
    @property
    def decisions(self) -> tuple[ClassifiedRow, ...]:
        """The decision table: rows whose class is DECISION-shaped
        (deliverable 2's free/select/allocated-with-pins subset)."""
        return tuple(r for r in self.rows if r.provenance_class in _DECISION_CLASSES)


# frob:doc docs/modules/py-backends.md#backends-parity
def build_parity_report(
    lockfile: Lockfile,
    results: Sequence[ObligationResult],
    ledger: WaiveLedger,
) -> ParityReport:
    """Assemble the parity report from the three artifact-only inputs
    AD-22 permits: the lockfile, the release gate's obligation results,
    and the waive ledger.
    """
    rows = classify_lockfile(lockfile)
    report_errors = tuple(
        f"{r.slot} = {r.value}  cause={r.cause!r} (unrecognized cause prefix)"
        for r in rows
        if r.provenance_class is ProvenanceClass.report_error
    )
    demands = demand_table(results, ledger)
    assumed_waived = assumed_waived_rows(ledger)
    subjects = tuple(
        sorted({r.subject for r in rows} | {d.subject_ref for d in demands})
    )
    _log.info(
        "parity report: %d subject(s), %d row(s), %d demand(s), %d assumed/"
        "waived, %d report error(s)",
        len(subjects),
        len(rows),
        len(demands),
        len(assumed_waived),
        len(report_errors),
    )
    return ParityReport(
        subjects=subjects,
        rows=rows,
        demands=demands,
        assumed_waived=assumed_waived,
        report_errors=report_errors,
    )


# frob:doc docs/modules/py-backends.md#backends-parity
def gate_summary_line(report: ParityReport) -> str:
    """The one-line parity gate summary (deliverable 3): ``clean`` /
    ``attention(n)`` / ``failing(n)``. Summarizes only -- never relabels
    a demand's verdict (INV-2): a violated demand or a report error
    makes the build ``failing``; an indeterminate demand or an
    accepted assume/waive makes it ``attention`` (nothing worse, but
    worth a human look); otherwise ``clean``.
    """
    failing = sum(1 for d in report.demands if d.status is DemandStatus.violated) + len(
        report.report_errors
    )
    if failing:
        return f"parity: failing({failing})"
    attention = sum(
        1 for d in report.demands if d.status is DemandStatus.indeterminate
    ) + len(report.assumed_waived)
    if attention:
        return f"parity: attention({attention})"
    return "parity: clean"


def _class_counts_by_subject(
    rows: tuple[ClassifiedRow, ...],
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        subject_counts = counts.setdefault(row.subject, {})
        subject_counts[row.provenance_class.value] = (
            subject_counts.get(row.provenance_class.value, 0) + 1
        )
    return counts


# frob:doc docs/modules/py-backends.md#backends-parity
def render_parity_report(report: ParityReport) -> str:
    """Render the ASCII parity ledger (deliverable 2): per-subject class
    counts, the decision table, the demand table, the assumed/waived
    ledger, the attention-list caveat, report errors, and the gate
    summary line -- deterministic, ASCII-only (AD-6).
    """
    lines: list[str] = ["parity report"]

    lines.append("class counts by subject:")
    counts = _class_counts_by_subject(report.rows)
    if not counts:
        lines.append("  (no resolved lockfile rows)")
    for subject in sorted(counts):
        parts = ", ".join(f"{cls}={n}" for cls, n in sorted(counts[subject].items()))
        lines.append(f"  {subject}: {parts}")

    lines.append("decision table (free/select/allocated values, engine-pinned):")
    if not report.decisions:
        lines.append("  (none)")
    for row in report.decisions:
        lines.append(
            f"  {row.slot} = {row.value}  [{row.provenance_class.value}] <- {row.cause}"
        )

    lines.append("derived/process values (consequence-shaped, not decisions):")
    consequences = tuple(
        r
        for r in report.rows
        if r.provenance_class in (ProvenanceClass.derived, ProvenanceClass.process)
    )
    if not consequences:
        lines.append("  (none)")
    for row in consequences:
        lines.append(
            f"  {row.slot} = {row.value}  [{row.provenance_class.value}] <- {row.cause}"
        )

    lines.append("demand table:")
    if not report.demands:
        lines.append("  (no obligations)")
    for demand in report.demands:
        basis = f"  basis={demand.basis}" if demand.basis is not None else ""
        status = demand.status.value
        lines.append(f"  {demand.subject_ref} {demand.key}: {status}{basis}")

    lines.append("assumed/waived:")
    if not report.assumed_waived:
        lines.append("  (none)")
    for entry in report.assumed_waived:
        lines.append(f"  [{entry.kind}] {entry.target}: {entry.basis}")

    lines.append("attention list (asserted literals, sorted by subject):")
    lines.append(f"  {LITERAL_ATTRIBUTION_CAVEAT}")

    lines.append("report errors:")
    if not report.report_errors:
        lines.append("  (none)")
    for error in report.report_errors:
        lines.append(f"  {error}")

    lines.append(gate_summary_line(report))
    return "\n".join(lines) + "\n"
