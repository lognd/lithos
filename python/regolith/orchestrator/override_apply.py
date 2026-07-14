"""Value-source integration: an override enters the build as a resolved
value BEFORE lowering/discharge, with ``cause: engineer_override(author,
reason)`` (charter 42 secs. 1/3, D243.1/D243.3, WO-129A deliverable 3).

Two REAL integration points, both Python-orchestrator-level (no Rust/
lowering change -- WO-129's own escape valve was investigated and not
needed here):

1. :func:`engineer_override_lock_row` / :func:`apply_overrides_to_rows`:
   the lockfile-row surface every resolved slot already renders through
   (:mod:`regolith.orchestrator.lockfile`). An override's row REPLACES
   whatever cause a slot would otherwise carry (``optimize(...)``,
   ``planner(...)``, etc.) -- this is D243.3's "outranks `optimize(...)`
   in the provenance ladder" literally: the override row wins by
   substitution, the search's own trace is untouched (INV-30 attribution
   still holds -- the trace records the search ran, the lockfile records
   it was superseded).

2. :func:`literalize_bounded_slot`: for a bounded/minimize sketch slot
   (charter 42 sec. 1a's injectable "dimensions and bounded/minimize
   slots"), an override REPLACES the optimizer search itself with the
   engineer's literal value, fed to the SAME real discharge evaluator
   the search would have used
   (:func:`regolith.orchestrator.optimize_sketch.make_slot_evaluator`) --
   so the obligation RE-DERIVES from the injected input exactly as it
   would from a hand-authored one (charter 42 sec. 1's load-bearing
   rule), and INV-33's proof holds: nothing here can promote the
   resulting ``Evidence.status`` -- it is whatever the real model
   computes for the injected width, never touched again.
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.logging_setup import get_logger
from regolith.orchestrator.dfm_staging import parse_len_mm
from regolith.orchestrator.discharge import ObligationResult
from regolith.orchestrator.lockfile import LockRow
from regolith.orchestrator.optimize_sketch import CantileverSlot, make_slot_evaluator
from regolith.orchestrator.overrides import OverrideEntry
from regolith.orchestrator.payload_store import PayloadStore

_log = get_logger(__name__)


def engineer_override_cause(entry: OverrideEntry) -> str:
    """The rendered ``cause: engineer_override(author, reason)`` text
    (charter 42 sec. 1/3) -- ONE spelling, used by both the lockfile row
    and (WO-129B) the reporting surfaces."""
    return f"engineer_override({entry.author}, {entry.reason})"


def engineer_override_lock_row(entry: OverrideEntry) -> LockRow:
    """The :class:`LockRow` an override renders: ``entry.target`` pinned
    to ``entry.value`` with the engineer-override cause. Never fails --
    an :class:`OverrideEntry` is already validated (author/reason
    required, WO-129A deliverable 1)."""
    return LockRow(
        slot=entry.target, value=entry.value, cause=engineer_override_cause(entry)
    )


def apply_overrides_to_rows(
    rows: tuple[LockRow, ...], overrides: tuple[OverrideEntry, ...]
) -> tuple[LockRow, ...]:
    """Supersede every ``rows`` entry an override targets, and append an
    override row for any target with no prior resolution (D243.3: the
    override's cause OUTRANKS ``optimize(...)`` -- and any other cause --
    for that slot; the prior row's provenance is simply replaced, never
    merged or blended, so there is no partial-credit path from a search
    result into an evidence value)."""
    by_target = {entry.target: entry for entry in overrides}
    superseded_targets: set[str] = set()
    result: list[LockRow] = []
    for row in rows:
        override = by_target.get(row.slot)
        if override is None:
            result.append(row)
            continue
        _log.info(
            "override supersedes lockfile row: slot=%s prior_cause=%r new_cause=%r",
            row.slot,
            row.cause,
            engineer_override_cause(override),
        )
        result.append(engineer_override_lock_row(override))
        superseded_targets.add(row.slot)
    for target, override in by_target.items():
        if target not in superseded_targets and target not in {r.slot for r in rows}:
            result.append(engineer_override_lock_row(override))
    return tuple(result)


def literalize_bounded_slot(
    slot: CantileverSlot, entry: OverrideEntry, store: PayloadStore
) -> Result[tuple[float, ObligationResult], OrchestratorError]:
    """Pin ``slot`` to ``entry.value`` (an engineer override on a bounded
    slot, ``mode = "pin"`` -- "optimization removal", D243.3) and run the
    SAME real cantilever-deflection evaluator the D209 search would have
    used (:func:`make_slot_evaluator`), never a shortcut/mocked verdict.

    Returns the literalized width (metres) and a real
    :class:`ObligationResult` wrapping the model's genuine
    ``Evidence`` -- feedable straight into
    :func:`regolith.orchestrator.orchestrate.release_gate` (INV-33's
    enforcing test: a violating override yields a ``violated`` result
    and the gate refuses; nothing in this function can change that
    status once the model has spoken).

    ``Err`` (never a fabricated pin) when ``entry.value`` does not parse
    as a spelled length, or falls outside ``[slot.lo_m, slot.hi_m]`` --
    an override is a declared INPUT, not a license to defeat the slot's
    own declared bound (regolith/03's `in [lo, hi]` clause is SOURCE,
    D246's boundary in spirit: the bound itself is not an injection
    target, only the value chosen within it)."""
    mm = parse_len_mm(entry.value)
    if mm is None:
        return Err(
            OrchestratorError(
                kind="override_value_unparseable",
                message=f"override value {entry.value!r} for {entry.target!r} "
                "is not a spelled length (e.g. '24mm')",
            )
        )
    width_m = mm / 1000.0
    if not (slot.lo_m <= width_m <= slot.hi_m):
        return Err(
            OrchestratorError(
                kind="override_out_of_bound",
                message=f"override value {entry.value!r} ({width_m}m) for "
                f"{entry.target!r} falls outside the declared bound "
                f"[{slot.lo_m}m, {slot.hi_m}m]",
            )
        )

    # Run the SAME real evaluator the D209 search would have used, at the
    # engineer's literal width instead of a search candidate -- this is
    # what "the obligation re-derives exactly as it would from a hand-
    # authored input" (charter 42 sec. 1) means concretely: identical
    # geometry realization + identical discharge call, just skipping the
    # search loop (`mode = "pin"`, D243.3's "optimization removal").
    outcome = make_slot_evaluator(slot, store)((width_m,))
    _log.debug(
        "literalize_bounded_slot %s: evaluator feasible=%s digests=%s",
        slot.slot_id,
        outcome.feasible,
        outcome.evidence_digests,
    )
    # Reach the raw Evidence directly (same DischargeRequest shape the
    # evaluator built internally) so the ObligationResult carries genuine
    # schema Evidence (bit-exact margin math), never a re-derived bool.
    from regolith.harness import DischargeRequest, Interval, default_registry
    from regolith.harness.models.beam_bending import CLAIM_KIND
    from regolith.orchestrator.optimize_sketch import section_inertia_m4

    i_area = section_inertia_m4(slot.thickness_m, width_m)
    request = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=slot.limit_m,
        inputs={
            "force": Interval.point(slot.force_n),
            "length": Interval.point(slot.length_m),
            "e_modulus": Interval.point(slot.e_pa),
            "i_area": Interval.point(i_area),
        },
    )
    evidence = default_registry().discharge(request)
    result = ObligationResult(
        key=f"override:{entry.target}",
        subject_ref=slot.slot_id,
        evidence=evidence,
    )
    _log.info(
        "literalize_bounded_slot %s: width=%.5fm cause=%s verdict=%s",
        slot.slot_id,
        width_m,
        engineer_override_cause(entry),
        evidence.status.value,
    )
    return Ok((width_m, result))
