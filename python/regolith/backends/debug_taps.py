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

The DERIVER (:func:`derive_taps`) is PURE (no IO, no compiler/
orchestrator calls) so it is independently unit-testable on fixtures.
This module also owns the tap surface's sources and its INV-32 check
(WO-125 continuation, deliverables 3-7):

- :func:`load_tap_header_record` -- the ONE published header pinout
  record (charter 40 sec. 4; `stdlib/std.elec/records/dft.toml`,
  ``class = "tap_header"``), loaded through the same records walk
  `regolith.orchestrator.si_stackups.load_si_context` uses.
- :func:`tap_candidates_from_payload` -- derived candidates from the
  build payload's own claim-named nets/signals (the census truth).
- :func:`explicit_taps_from_debug_spec` /
  :func:`hdl_debug_pins_from_debug_spec` -- the ship spec's
  ``"debug"`` block (the WO-102 spec-block idiom; no grammar change,
  charter 40 sec. 6).
- :func:`check_tap_agreement` -- INV-32: every tap-map row exists in
  the emitted artifacts and vice versa, re-parsed from the EMITTED
  bytes (never the in-memory objects that produced them).
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from typani.result import Err, Ok, Result

from regolith.errors import BackendError
from regolith.logging_setup import get_logger

if TYPE_CHECKING:
    from regolith.backends.framework import OutputFile

_log = get_logger(__name__)

#: The stable marker every debug artifact embeds per carried tap and
#: :func:`check_tap_agreement` re-parses (INV-32's one grep surface).
#: Format: ``REGOLITH-TAP ch=<channel> target=<target_path>``.
TAP_MARKER_PREFIX = "REGOLITH-TAP"

# `target=` never contains whitespace or a double quote, so the marker
# is greppable verbatim inside JSON string values, C comments, and
# Verilog comments alike.
_TAP_MARKER_RE = re.compile(r'REGOLITH-TAP ch=(\d+) target=([^\s"]+)')

#: The record class the tap-header loader consumes (dft.toml, AD-37:
#: one home for the pinout both the board placement and the WO-127 jig
#: reference).
_TAP_HEADER_CLASS = "tap_header"

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


class TapHeaderRecord(BaseModel):
    """The published tap-header pinout record (charter 40 sec. 4, AD-37).

    ONE home: `stdlib/std.elec/records/dft.toml`'s ``class =
    "tap_header"`` row -- the debug profile places it, the WO-127 jig
    mates it. ``channels`` is the deriver's capacity; ``ordering``/
    ``ground``/``keying``/``connector`` are carried verbatim onto the
    tap map so the shipped record is self-describing.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    channels: int
    positions: int
    pitch_mm: float
    connector: str
    ordering: str
    ground: str
    keying: str
    reference: str
    source_file: str

    def connector_pin(self, channel: int) -> int:
        """The connector pin carrying ``channel`` (signal-on-odd
        ordering: channel N rides pin 2N+1; grounds ride the evens)."""
        return 2 * channel + 1


def load_tap_header_record(
    project_root: str,
    record_search_paths: tuple[str, ...] = (),
) -> Result[TapHeaderRecord | None, BackendError]:
    """Load THE tap-header pinout record from the record search roots.

    Walks ``<root>/records/*.toml`` plus every package subdirectory's
    ``records/*.toml`` (the exact walk
    `regolith.orchestrator.si_stackups.load_si_context` established)
    looking for ``class = "tap_header"`` component rows. ``Ok(None)``
    is the honest absence (a project with no resolvable stdlib root:
    no channels can be allocated, named as such in the tap map --
    charter 40 sec. 5). TWO records is a loud error (the single-home
    rule, AD-37): a second pinout would let the board and the jig
    drift apart.
    """
    found: TapHeaderRecord | None = None
    for search_path in (project_root, *record_search_paths):
        base = Path(search_path)
        candidates = [base / "records"]
        if base.is_dir():
            candidates.extend(
                sub / "records"
                for sub in sorted(base.iterdir())
                if sub.is_dir() and (sub / "magnetite.toml").is_file()
            )
        for records_dir in candidates:
            if not records_dir.is_dir():
                continue
            for toml_file in sorted(records_dir.glob("*.toml")):
                try:
                    with toml_file.open("rb") as f:
                        data = tomllib.load(f)
                except (OSError, tomllib.TOMLDecodeError) as exc:
                    return Err(
                        BackendError(
                            kind="tap_header_record_malformed",
                            message=f"{toml_file}: {exc}",
                        )
                    )
                for row in data.get("component", ()):
                    if (
                        not isinstance(row, dict)
                        or row.get("class") != _TAP_HEADER_CLASS
                    ):
                        continue
                    evidence = row.get("evidence")
                    reference = (
                        str(evidence.get("reference", ""))
                        if isinstance(evidence, dict)
                        else ""
                    )
                    try:
                        record = TapHeaderRecord(
                            key=str(row.get("key", "")),
                            channels=int(row.get("channels", 0)),
                            positions=int(row.get("positions", 0)),
                            pitch_mm=float(row.get("pitch_mm", 0.0)),
                            connector=str(row.get("connector", "")),
                            ordering=str(row.get("ordering", "")),
                            ground=str(row.get("ground", "")),
                            keying=str(row.get("keying", "")),
                            reference=reference,
                            source_file=str(toml_file),
                        )
                    except (TypeError, ValueError, ValidationError) as exc:
                        return Err(
                            BackendError(
                                kind="tap_header_record_malformed",
                                message=f"{toml_file}: tap_header row "
                                f"{row.get('key')!r}: {exc}",
                            )
                        )
                    if found is not None and found.key != record.key:
                        return Err(
                            BackendError(
                                kind="tap_header_record_duplicate",
                                message=(
                                    f"two tap_header records ({found.key!r} in "
                                    f"{found.source_file}, {record.key!r} in "
                                    f"{record.source_file}) -- the pinout has "
                                    "ONE home (charter 40 sec. 4)"
                                ),
                            )
                        )
                    if found is None:
                        found = record
    if found is None:
        _log.info(
            "load_tap_header_record: no tap_header record under %s -- "
            "honest absence, zero channels allocatable",
            (project_root, *record_search_paths),
        )
    else:
        _log.info(
            "load_tap_header_record: %s (%d channels) from %s",
            found.key,
            found.channels,
            found.source_file,
        )
    return Ok(found)


# The signal-expression shape D102's temporal claim forms carry
# (`v(out)`, `i(load)`); nothing else in the repo parses the INNER
# name today (translate.py keeps `form.signal` opaque), so this tiny
# grammar is the tap deriver's own, documented here.
_SIGNAL_EXPR_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(([A-Za-z0-9_.]+)\)$")

_CLOCKISH = ("clk", "clock")


def _kind_for_net(net: str) -> TapKind:
    """Family for a claim-named NET (SI claims): a clock-named net is a
    `clock`, everything else on the SI surface is a `bus` (charter 40
    sec. 2's ranking families)."""
    lowered = net.lower()
    return "clock" if any(tok in lowered for tok in _CLOCKISH) else "bus"


def _kind_for_signal(quantity: str, inner: str) -> TapKind:
    """Family for a temporal-claim SIGNAL expression: `v(x)` is a rail,
    a clock-named target is a clock, anything else is a plain signal."""
    lowered = inner.lower()
    if any(tok in lowered for tok in _CLOCKISH):
        return "clock"
    return "rail" if quantity == "v" else "signal"


def tap_candidates_from_payload(payload: dict) -> tuple[TapCandidate, ...]:
    """Derive tap candidates from a build payload's own obligations --
    the SAME claim surface the census reads (D237.2).

    Two claim shapes name a physical net/signal today:

    1. SI claims (`elec.impedance`/`elec.termination`, ClaimForm1) --
       parsed through `translate.si_sheet_fields`, the ONE home for SI
       claim text (NO DUPLICATION); the net is scope-qualified into
       ``<scope>.<net>``.
    2. Typed temporal forms (ClaimForm2..6) -- their ``signal``
       expression (`v(out)`, `i(load)`); `v(...)` targets are rails.

    Deterministic: candidates are deduplicated by ``target_path``
    (first family rank wins) and sorted by (family rank, target_path).
    A claim naming nothing physical contributes nothing -- never a
    guessed net (D224).
    """
    from regolith._schema.models import Obligation
    from regolith.orchestrator.translate import si_sheet_fields

    scope_of = {snap["hash"]: snap["scope"] for snap in payload.get("snapshots", ())}
    by_path: dict[str, TapCandidate] = {}

    def offer(target_path: str, kind: TapKind, why: str) -> None:
        existing = by_path.get(target_path)
        if existing is None or _FAMILY_RANK[kind] < _FAMILY_RANK[existing.kind]:
            by_path[target_path] = TapCandidate(
                target_path=target_path, kind=kind, why=why
            )

    for raw in payload.get("obligations", ()):
        try:
            obligation = Obligation.model_validate(raw)
        except ValidationError:
            _log.warning(
                "tap_candidates_from_payload: unparseable obligation row "
                "skipped (no candidate derived)"
            )
            continue
        scope = scope_of.get(obligation.subject_ref, obligation.subject_ref[:12])
        claim_name = obligation.claim.name or ""
        fields = si_sheet_fields(obligation)
        if fields is not None and fields["net"]:
            net = fields["net"]
            offer(
                f"{scope}.{net}",
                _kind_for_net(net),
                f"claim {fields['claim']}",
            )
            continue
        signal = getattr(obligation.claim.form, "signal", None)
        if isinstance(signal, str):
            match = _SIGNAL_EXPR_RE.match(signal.strip())
            if match is None:
                continue
            quantity, inner = match.group(1), match.group(2)
            offer(
                f"{scope}.{inner}",
                _kind_for_signal(quantity, inner),
                f"claim {claim_name or signal}",
            )

    candidates = tuple(
        sorted(
            by_path.values(),
            key=lambda c: (_FAMILY_RANK[c.kind], c.target_path),
        )
    )
    _log.info(
        "tap_candidates_from_payload: %d candidate(s) from %d obligation(s)",
        len(candidates),
        len(payload.get("obligations", ())),
    )
    return candidates


def explicit_taps_from_debug_spec(
    block: dict,
) -> Result[tuple[ExplicitTap, ...], BackendError]:
    """Parse the ship spec's ``"debug"`` block ``taps`` list (the WO-102
    spec-block idiom): each entry a bare net-path string or a
    ``{"target_path": ..., "why": ...}`` object. A non-list/non-string
    entry is a named diagnostic, never a silent skip."""
    raw = block.get("taps", [])
    if not isinstance(raw, list):
        return Err(
            BackendError(
                kind="debug_spec_malformed",
                message=f'"debug".taps must be a list, got {type(raw).__name__}',
            )
        )
    taps: list[ExplicitTap] = []
    for entry in raw:
        if isinstance(entry, str):
            taps.append(ExplicitTap(target_path=entry))
        elif isinstance(entry, dict) and isinstance(entry.get("target_path"), str):
            taps.append(
                ExplicitTap(
                    target_path=entry["target_path"],
                    why=str(entry.get("why", "explicit (debug spec block)")),
                )
            )
        else:
            return Err(
                BackendError(
                    kind="debug_spec_malformed",
                    message=f'"debug".taps entry {entry!r} is neither a net-path '
                    'string nor a {"target_path": ...} object',
                )
            )
    return Ok(tuple(taps))


def hdl_debug_pins_from_debug_spec(block: dict) -> dict[str, tuple[str, ...]]:
    """Parse the ``"debug"`` block's ``hdl_debug_pins`` map:
    ``{"<subject>": ["dbg0", ...]}`` -- the DECLARED spare pins the HDL
    tap module may route to (charter 40 sec. 1: no declaration means an
    honest named absence, never an invented pin)."""
    raw = block.get("hdl_debug_pins", {})
    if not isinstance(raw, dict):
        return {}
    pins: dict[str, tuple[str, ...]] = {}
    for subject, names in raw.items():
        if isinstance(names, list):
            pins[str(subject)] = tuple(str(n) for n in names)
    return pins


def resolve_explicit_taps(
    explicit: tuple[ExplicitTap, ...],
    candidates: tuple[TapCandidate, ...],
) -> Result[tuple[ExplicitTap, ...], BackendError]:
    """Resolve each explicit tap's path against the candidate universe:
    exact ``target_path`` match wins; else a UNIQUE bare-net suffix
    match (``refclk`` -> ``CarrierSi.refclk``) is rewritten to the full
    path; an unknown or ambiguous name is a named diagnostic (charter
    40 sec. 2), never a guess."""
    by_path = {c.target_path for c in candidates}
    resolved: list[ExplicitTap] = []
    for tap in explicit:
        if tap.target_path in by_path:
            resolved.append(tap)
            continue
        suffix_hits = sorted(p for p in by_path if p.endswith(f".{tap.target_path}"))
        if len(suffix_hits) == 1:
            _log.debug(
                "resolve_explicit_taps: %r resolved to %r by unique suffix",
                tap.target_path,
                suffix_hits[0],
            )
            resolved.append(tap.model_copy(update={"target_path": suffix_hits[0]}))
        elif len(suffix_hits) > 1:
            return Err(
                BackendError(
                    kind="ambiguous_explicit_tap",
                    message=f"explicit debug tap {tap.target_path!r} matches "
                    f"multiple claim-named nets: {suffix_hits}",
                )
            )
        else:
            return Err(
                BackendError(
                    kind="unknown_explicit_tap",
                    message=f"explicit debug tap {tap.target_path!r} names no "
                    "claim-named net/signal in this design (the census truth "
                    "surface, D237.2)",
                )
            )
    return Ok(tuple(resolved))


def tap_marker(channel: int, target_path: str) -> str:
    """The INV-32 marker line for one tap (embedded verbatim by every
    emitting family; re-parsed by :func:`check_tap_agreement`)."""
    return f"{TAP_MARKER_PREFIX} ch={channel} target={target_path}"


def check_tap_agreement(
    tap_map_bytes: bytes,
    files: tuple[OutputFile, ...],
) -> Result[None, BackendError]:
    """INV-32 (tap-map/artifact agreement, charter 40 sec. 3).

    Re-parses the EMITTED bytes on both sides: the tap map's allocated
    rows (``taps[].channel``/``target_path``) and every ``REGOLITH-TAP``
    marker in every other emitted file. Both inclusions must hold:

    - every map row's ``(channel, target_path)`` appears as a marker in
      at least one emitted artifact (the map never overstates the
      hardware);
    - every marker found in an artifact is a map row (no unmapped tap
      ships).

    A mismatch is a named ``tap_map_artifact_mismatch`` diagnostic and
    the ship path refuses -- never a silently inconsistent package.
    """
    try:
        tap_map = json.loads(tap_map_bytes.decode("ascii"))
    except (ValueError, UnicodeDecodeError) as exc:
        return Err(
            BackendError(
                kind="tap_map_malformed", message=f"tap map is not JSON: {exc}"
            )
        )
    map_rows = {
        (int(row["channel"]), str(row["target_path"]))
        for row in tap_map.get("taps", ())
    }
    found: set[tuple[int, str]] = set()
    for f in files:
        try:
            text = f.content.decode("utf-8")
        except UnicodeDecodeError:
            continue  # binary artifact: never carries a marker
        for match in _TAP_MARKER_RE.finditer(text):
            found.add((int(match.group(1)), match.group(2)))
    missing = sorted(map_rows - found)
    unmapped = sorted(found - map_rows)
    if missing or unmapped:
        _log.error(
            "check_tap_agreement: INV-32 violated: %d map row(s) absent from "
            "artifacts %s; %d artifact tap(s) absent from map %s",
            len(missing),
            missing,
            len(unmapped),
            unmapped,
        )
        return Err(
            BackendError(
                kind="tap_map_artifact_mismatch",
                message="INV-32 tap agreement failed: map rows with no emitted "
                f"artifact: {missing}; emitted taps not in the map: {unmapped}",
            )
        )
    _log.info(
        "check_tap_agreement: INV-32 holds (%d tap(s) agree across %d file(s))",
        len(map_rows),
        len(files),
    )
    return Ok(None)
