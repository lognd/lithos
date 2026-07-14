"""The debug-profile tap model + deriver (WO-125 deliverable 2, D237.2).

A tap is ``(channel, kind, target_path, why)``: one signal a debug
build exposes for physical probing. Two sources feed one merged,
deduplicated, deterministically ordered :class:`TapSet`:

1. DERIVED -- every net/signal named by a claim in the design (the
   same routing truth the census reads) is a candidate, ranked by
   claim family (power rails, clocks, buses, then everything else)
   and truncated to header capacity; overflow is recorded as named
   ``unallocated`` rows, never silently dropped.
2. EXPLICIT -- the ship spec block's ``"debug"`` entry (the WO-102
   spec-block idiom, no grammar change per charter 40 sec. 6) lists
   taps by net path. Explicit taps win channels before derived ones;
   an explicit tap naming a path absent from the candidate universe is
   a diagnostic (``Err``), never a silent skip.

This module is PURE (no IO, no compiler/orchestrator calls) so it is
independently unit-testable on fixtures; wiring a real project's
claim-named nets into :func:`derive_taps` (deliverables 3-6: board/
firmware/HDL augmentation reading the resulting :class:`TapSet`) is
cut from this pass -- see WO-125's plan/close-out for the escalation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

TapKind = Literal["rail", "clock", "bus", "signal"]
TapSource = Literal["derived", "explicit"]

# charter 40 sec. 2 ranking: rails, clocks, buses, then the rest.
_FAMILY_RANK: dict[TapKind, int] = {"rail": 0, "clock": 1, "bus": 2, "signal": 3}


class TapCandidate(BaseModel):
    """One claim-named net/signal eligible to become a derived tap.

    ``target_path`` is the net/signal path a claim names (the same
    identifier space the census reads); ``kind`` is the claim family
    used for ranking (charter 40 sec. 2); ``why`` is a short human-
    readable citation (claim id or family description) carried onto
    the resulting :class:`Tap` unchanged.
    """

    model_config = ConfigDict(frozen=True)

    target_path: str
    kind: TapKind
    why: str


class ExplicitTap(BaseModel):
    """One ``"debug"`` spec-block entry naming a tap by net path."""

    model_config = ConfigDict(frozen=True)

    target_path: str
    why: str = "explicit (debug spec block)"


class Tap(BaseModel):
    """One allocated debug-profile channel."""

    model_config = ConfigDict(frozen=True)

    channel: int
    kind: TapKind
    target_path: str
    why: str
    source: TapSource


class UnallocatedTap(BaseModel):
    """A candidate that lost to header capacity -- a named absence,
    never a silent drop (charter 40 sec. 5's honesty rule)."""

    model_config = ConfigDict(frozen=True)

    target_path: str
    kind: TapKind
    why: str
    reason: str = "header capacity exceeded"


class TapSet(BaseModel):
    """The full deterministic result: allocated channels + named
    overflow, sorted by ``channel`` / ``target_path`` respectively."""

    model_config = ConfigDict(frozen=True)

    taps: tuple[Tap, ...] = ()
    unallocated: tuple[UnallocatedTap, ...] = ()


def derive_taps(
    candidates: tuple[TapCandidate, ...],
    explicit: tuple[ExplicitTap, ...],
    capacity: int,
) -> Result[TapSet, BackendError]:
    """Merge derived candidates + explicit spec-block taps into one
    deterministic, capacity-limited :class:`TapSet`.

    Explicit taps win channels first (charter 40 sec. 2), in the order
    given (spec-block declaration order is the author's own ranking);
    an explicit ``target_path`` absent from ``candidates`` is a named
    diagnostic (``Err``, kind ``unknown_explicit_tap``) -- never a
    silent skip. Remaining capacity is filled by derived candidates,
    ranked by claim family (rail < clock < bus < signal) then by
    ``target_path`` (the deterministic AD-6 tiebreak), deduplicated by
    ``target_path`` (an explicit tap suppresses its own derived
    duplicate, never double-allocates a channel to the same net).
    Overflow candidates become named :class:`UnallocatedTap` rows,
    sorted by ``target_path``.
    """
    if capacity < 0:
        return Err(
            BackendError(
                kind="invalid_tap_capacity",
                message=f"tap header capacity must be >= 0, got {capacity}",
            )
        )

    candidates_by_path = {c.target_path: c for c in candidates}
    unknown = [
        e.target_path for e in explicit if e.target_path not in candidates_by_path
    ]
    if unknown:
        _log.warning(
            "derive_taps: %d explicit tap(s) name unknown net path(s): %s",
            len(unknown),
            sorted(unknown),
        )
        return Err(
            BackendError(
                kind="unknown_explicit_tap",
                message="explicit debug tap(s) name net path(s) absent from "
                f"the design: {sorted(unknown)}",
            )
        )

    allocated: list[Tap] = []
    used_paths: set[str] = set()
    channel = 0
    for e in explicit:
        if e.target_path in used_paths:
            _log.debug(
                "derive_taps: duplicate explicit tap for %s, skipping repeat",
                e.target_path,
            )
            continue
        if channel >= capacity:
            break
        candidate = candidates_by_path[e.target_path]
        allocated.append(
            Tap(
                channel=channel,
                kind=candidate.kind,
                target_path=e.target_path,
                why=e.why,
                source="explicit",
            )
        )
        used_paths.add(e.target_path)
        channel += 1

    remaining = sorted(
        (c for c in candidates if c.target_path not in used_paths),
        key=lambda c: (_FAMILY_RANK[c.kind], c.target_path),
    )
    overflow: list[TapCandidate] = []
    for c in remaining:
        if channel >= capacity:
            overflow.append(c)
            continue
        allocated.append(
            Tap(
                channel=channel,
                kind=c.kind,
                target_path=c.target_path,
                why=c.why,
                source="derived",
            )
        )
        used_paths.add(c.target_path)
        channel += 1

    # Explicit taps beyond capacity (the `break` above) also overflow,
    # named the same honest way as a derived overflow.
    explicit_overflow = [
        candidates_by_path[e.target_path]
        for e in explicit
        if e.target_path not in used_paths
        and e.target_path not in {o.target_path for o in overflow}
    ]

    unallocated = tuple(
        UnallocatedTap(target_path=c.target_path, kind=c.kind, why=c.why)
        for c in sorted(
            (*overflow, *explicit_overflow),
            key=lambda c: c.target_path,
        )
    )

    tap_set = TapSet(taps=tuple(allocated), unallocated=unallocated)
    _log.info(
        "derive_taps: %d channel(s) allocated (%d explicit, %d derived), "
        "%d unallocated",
        len(tap_set.taps),
        sum(1 for t in tap_set.taps if t.source == "explicit"),
        sum(1 for t in tap_set.taps if t.source == "derived"),
        len(tap_set.unallocated),
    )
    return Ok(tap_set)
