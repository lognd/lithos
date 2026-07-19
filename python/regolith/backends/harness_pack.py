"""The bring-up harness pack -- `harness/` family (WO-126, D237.3).

A debug-profile ship emits everything a technician with the target
board, the jig, and a logic analyzer needs to physically verify a
design: the tap map (WO-125's own emission, moved INTO this family --
no second copy), an ordered bring-up procedure (the WO-96 instructions
idiom), an expected-signal manifest where EVERY row traces to a
discharged claim, a calc-sheet hash, or a declared record (D224 --
fabricating a number is the one unforgivable failure mode here), and
sigrok-compatible capture configs per tap-kind group.

Layering (regolith/07 sec. 6, "backends never decide"): this module
only FORMATS data `regolith.backends.ship` already resolved --
`debug_taps.TapSet` (WO-125's pure deriver), the release report's own
obligations/results, and the calc book (WO-114) `regolith.backends.
calc.build_calc_book` already built for the SAME ship. It invents
nothing: an expectation with no discharged evidence and no calc sheet
behind it is emitted as a named `no_verified_expectation` absence with
a reason, never a fabricated number (D224, charter 40 sec. 5).
"""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._codes import EXPECTATION_PROVENANCE_UNRESOLVED
from regolith._schema.models import Obligation
from regolith.backends.calc import CalcBook, CalcSheet, claim_text
from regolith.backends.debug_taps import Tap, TapHeaderRecord, TapSet, tap_marker
from regolith.backends.framework import OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger
from regolith.magnetite.waveform import resolve_mask_ref
from regolith.orchestrator.discharge import ObligationResult
from regolith.orchestrator.translate import si_sheet_fields

_log = get_logger(__name__)

# `E1104` -- WO-151/D263.1: `bringup_expectation_authored_posture`.
# PENDING-CODEGEN (this WO's implementer is scoped to the
# `comparison.rs` Rust residual only, per dispatch; minting the real
# `regolith-diag::code::BringUp` slot -- confirmed free at E1104 as of
# this WO, `crates/regolith-diag/src/code.rs:620-640` shows E1101-
# E1103 assigned -- and its `explain.rs` entry is escalated to a
# follow-up so `make codes` can regenerate `regolith._codes` from a
# single Rust source, per the WO-131/D247.1 house mechanism). Bare
# string now, backfilled to the real `DiagCode` later with NO
# grandfathering, exactly like `EXPECTATION_PROVENANCE_UNRESOLVED`'s
# own pre-D247.2 history above.
BRINGUP_EXPECTATION_AUTHORED_POSTURE = "bringup_expectation_authored_posture"

# charter 40 sec. 2 ranking, reused for bring-up ordering (safety-relevant
# rails first, then clocks, buses, everything else) -- the SAME family
# rank `debug_taps._FAMILY_RANK` uses, kept in sync by hand since that
# dict is module-private (no second public constant to drift).
_KIND_RANK: dict[str, int] = {"rail": 0, "clock": 1, "bus": 2, "signal": 3}

# The unit token trailing a declared threshold expression (`3.465 V`,
# `50 ohm`, `100 mA`) -- honest best-effort extraction of what the
# author already wrote; a threshold with no recognizable trailing unit
# keeps an empty `units` field rather than a guessed one.
_UNIT_RE = re.compile(r"([-+]?[0-9][0-9.eE+-]*)\s*([A-Za-z%]+)\s*$")

# The sigrok-cli capture groups this WO emits (charter 40 sec. 3): one
# config per tap kind that actually has allocated channels.
_CAPTURE_GROUPS: tuple[str, ...] = ("rail", "clock", "bus", "signal")
_CAPTURE_GROUP_LABEL = {
    "rail": "rails",
    "clock": "clocks",
    "bus": "buses",
    "signal": "signals",
}

ProvenanceKind = Literal["calc_sheet", "claim", "record", "none"]


# frob:doc docs/modules/py-backends.md#backends-harness-pack
class Provenance(BaseModel):
    """D224's provenance pin for one expected signal: a discharged calc
    sheet's digest, a claim id (declared but not model-backed numeric),
    a declared record, or `none` (the honest, reasoned absence).

    `posture` is populated ONLY for `kind == "record"` (WO-151,
    D263.1): the record class's own evidence-posture tag
    (`authored`/`measured`/`model_derived`), carried here so
    `check_bringup_expectation_authored_posture` can refuse an
    `authored` record cited as a verified expectation without a
    second resolution pass."""

    model_config = ConfigDict(frozen=True)

    kind: ProvenanceKind
    ref: str
    reason: str = ""
    posture: str | None = None


# frob:doc docs/modules/py-backends.md#backends-harness-pack
class ExpectedSignal(BaseModel):
    """One tap's expected-signal row (charter 40 sec. 3)."""

    model_config = ConfigDict(frozen=True)

    channel: int
    target_path: str
    kind: str
    quantity: str
    expected: str | None
    units: str
    provenance: Provenance
    note: str = ""


def _split_expected_magnitude_and_unit(text: str) -> tuple[str, str]:
    """Split a claim's declared threshold text into (bare magnitude,
    unit), the ONE home for this shape (D256 supersedes WO-128/F144's
    closed-SI-vocabulary fallback: `resolve_unit_suffix` now preserves
    every claim's unit token directly on `lhs`/`rhs`, so the evidence
    surface reads it straight off the claim text -- never a per-call-
    name lookup table). Returns ``(text, "")`` when `text` carries no
    recognizable trailing unit token -- never a guess (D224)."""
    match = _UNIT_RE.search(text.strip())
    if match is None:
        return text, ""
    magnitude, unit = match.groups()
    return magnitude, unit


def _quantity_for(tap: Tap, obligation: Obligation | None) -> str:
    """A human label for a tap's physical quantity.

    When the obligation is a real SI claim (`elec.impedance`/`elec.
    termination`), the quantity comes from the claim's OWN call name
    (`translate.si_sheet_fields`'s ``call_name``, e.g. `elec.impedance`
    -> `impedance`) -- the honest quantity the claim actually measures,
    not a guess off the tap's family bucket (a `refclk` net lands in
    the `clock` tap-kind family purely because its NAME contains
    "clk" -- charter 40 sec. 2's placement heuristic -- even when the
    claim behind it is an impedance bound, WO117-F2/D224). Falls back
    to the tap-kind family label ONLY when no structured SI call name
    is reachable (a temporal claim, an unclaimed candidate, or no
    obligation at all) -- never a per-quantity guess table beyond this
    one SI vocabulary `translate.si_sheet_fields` already owns."""
    if obligation is not None:
        fields = si_sheet_fields(obligation)
        if fields is not None:
            return fields["call_name"].rsplit(".", 1)[-1]
    return {
        "rail": "voltage",
        "clock": "clock presence",
        "bus": "impedance",
        "signal": "signal level",
    }.get(tap.kind, "signal level")


class _Source(BaseModel):
    """One target-path's originating obligation (index into the report's
    own obligation/result lists) -- the SAME claim surface
    `debug_taps.tap_candidates_from_payload` derived candidates from,
    walked again here to trace a tap BACK to its claim for provenance
    (a different task than allocation: no dedup-by-capacity, every
    matching obligation index is kept so the FIRST one -- declaration
    order, deterministic -- is used, mirroring the candidate walk's own
    "first family rank wins" tie discipline via insertion order)."""

    model_config = ConfigDict(frozen=True)

    obligation_index: int
    claim_name: str


_SIGNAL_EXPR_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(([A-Za-z0-9_.]+)\)$")


def _sources_from_payload(payload: dict) -> dict[str, _Source]:
    """Rebuild `target_path -> _Source` from a build payload's own
    obligations -- the exact net/signal parsing
    `debug_taps.tap_candidates_from_payload` uses (SI claims via
    `si_sheet_fields`, typed temporal claims via their `signal`
    expression), kept here as its own small walk (NO import of a
    private candidate-ranking helper) since this walk answers a
    different question: which OBLIGATION named this path, not which
    candidate wins a channel."""
    scope_of = {snap["hash"]: snap["scope"] for snap in payload.get("snapshots", ())}
    sources: dict[str, _Source] = {}
    for index, raw in enumerate(payload.get("obligations", ())):
        try:
            obligation = Obligation.model_validate(raw)
        except Exception:  # noqa: BLE001 -- unparseable row: no source derived
            continue
        scope = scope_of.get(obligation.subject_ref, obligation.subject_ref[:12])
        claim_name = obligation.claim.name or ""
        fields = si_sheet_fields(obligation)
        if fields is not None and fields["net"]:
            path = f"{scope}.{fields['net']}"
            sources.setdefault(
                path, _Source(obligation_index=index, claim_name=claim_name)
            )
            continue
        signal = getattr(obligation.claim.form, "signal", None)
        if isinstance(signal, str):
            match = _SIGNAL_EXPR_RE.match(signal.strip())
            if match is None:
                continue
            path = f"{scope}.{match.group(2)}"
            sources.setdefault(
                path, _Source(obligation_index=index, claim_name=claim_name)
            )
    return sources


def _expected_magnitude_and_units(obligation: Obligation) -> tuple[str | None, str]:
    """The claim's own declared threshold (`form.rhs`), split into its
    bare magnitude (the `expected` field) and unit (`units`) -- the
    honest DECLARED value, never a computed number (the computed
    number, when discharged, rides the calc sheet reference instead).
    ``(None, "")`` when the form carries no `rhs`."""
    rhs = getattr(obligation.claim.form, "rhs", None)
    if not isinstance(rhs, str) or not rhs:
        return None, ""
    magnitude, unit = _split_expected_magnitude_and_unit(rhs)
    return magnitude, unit


# frob:doc docs/modules/py-backends.md#backends-harness-pack
def build_expected_signals(
    tap_set: TapSet,
    payload: dict,
    results: tuple[ObligationResult, ...],
    calc_book: CalcBook | None,
) -> tuple[ExpectedSignal, ...]:
    """Build the per-tap expected-signal rows (charter 40 sec. 3, D224).

    For each allocated tap: trace it back to the obligation that named
    its target path, then:

    - a DISCHARGED obligation with a calc sheet in `calc_book` (matched
      by `(claim_name, subject_ref)`, exact -- no anchor ambiguity)
      cites that sheet's digest as the provenance ref, `expected` is the
      claim's declared threshold text;
    - a claim-covered obligation with NO calc sheet (deferred, violated,
      indeterminate, or a discharge with no calc book entry) emits the
      claim-ref expectation WITHOUT a number (WO117-F2 territory, per
      this WO's escalation clause) -- `expected`/`units` stay empty,
      `provenance.kind == "claim"`, a named `note`;
    - a DISCHARGED obligation with a calc sheet but NO unit reachable
      on this obligation's provenance surface (the claim's declared
      threshold text carries no trailing unit token this module's
      `_UNIT_RE` recognizes -- a rare claim shape whose bound is
      genuinely dimensionless or spells a unit `regolith-qty` does not
      know) DEGRADES to the honest `no_verified_expectation` absence
      too:
      `expected`/`units` stay empty, `provenance.kind` stays
      `calc_sheet` (the sheet IS real evidence, still cited for audit),
      reason `unit_unresolved (WO117-F2)` (D224: an honest absence beats
      a number a technician
      could misread; charter 40 sec. 3 requires quantity + value/window
      + UNITS + provenance on every POPULATED row, so an unresolved
      unit means the row is not populated);
    - a tap with no traceable obligation (should not happen -- every
      allocated tap derives FROM an obligation, `debug_taps.
      tap_candidates_from_payload`'s own contract) is the honest
      `no_verified_expectation` absence, never invented.
    """
    sources = _sources_from_payload(payload)
    obligations = tuple(
        Obligation.model_validate(raw) for raw in payload.get("obligations", ())
    )
    results_by_index = {i: r for i, r in enumerate(results)}
    sheets_by_key: dict[tuple[str, str], CalcSheet] = {}
    if calc_book is not None:
        for sheet in calc_book.sheets:
            sheets_by_key[(sheet.claim_name, sheet.subject_ref)] = sheet

    rows: list[ExpectedSignal] = []
    for tap in tap_set.taps:
        source = sources.get(tap.target_path)
        if source is None:
            rows.append(
                ExpectedSignal(
                    channel=tap.channel,
                    target_path=tap.target_path,
                    kind=tap.kind,
                    quantity=_quantity_for(tap, None),
                    expected=None,
                    units="",
                    provenance=Provenance(
                        kind="none",
                        ref="",
                        reason="no obligation traces this tap's target path "
                        "(unexpected -- every allocated tap derives from a "
                        "claim, debug_taps.tap_candidates_from_payload)",
                    ),
                    note="no_verified_expectation",
                )
            )
            continue
        obligation = obligations[source.obligation_index]
        result = results_by_index.get(source.obligation_index)
        expected, units = _expected_magnitude_and_units(obligation)
        quantity = _quantity_for(tap, obligation)
        evidence = result.evidence if result is not None else None
        sheet = sheets_by_key.get((source.claim_name, obligation.subject_ref))
        if (
            evidence is not None
            and evidence.status.value == "discharged"
            and sheet is not None
        ):
            if expected is not None and units:
                rows.append(
                    ExpectedSignal(
                        channel=tap.channel,
                        target_path=tap.target_path,
                        kind=tap.kind,
                        quantity=quantity,
                        expected=expected,
                        units=units,
                        provenance=Provenance(
                            kind="calc_sheet",
                            ref=sheet.chain.sheet_digest,
                        ),
                    )
                )
                continue
            # Discharged, calc-sheet-backed, but NO unit reachable from
            # this obligation's provenance surface (D224/WO117-F2): the
            # sheet is real evidence, still cited, but the row degrades
            # to the honest absence rather than ship a bare number a
            # technician could misread (charter 40 sec. 3).
            _log.warning(
                "build_expected_signals: channel %d (%s) discharged with a "
                "calc sheet but no unit reachable on the claim's provenance "
                "surface -- degrading to no_verified_expectation "
                "(unit_unresolved, WO117-F2)",
                tap.channel,
                tap.target_path,
            )
            rows.append(
                ExpectedSignal(
                    channel=tap.channel,
                    target_path=tap.target_path,
                    kind=tap.kind,
                    quantity=quantity,
                    expected=None,
                    units="",
                    provenance=Provenance(
                        kind="calc_sheet",
                        ref=sheet.chain.sheet_digest,
                        reason="unit_unresolved (WO117-F2): the claim's "
                        "declared threshold carries no unit token and no "
                        "other Python-visible field (evidence, calc sheet, "
                        "calc input) carries one for this claim shape -- "
                        "an honest absence beats a number a technician "
                        "could misread (D224)",
                    ),
                    note="no_verified_expectation",
                )
            )
            continue
        status = (
            evidence.status.value
            if evidence is not None
            else (
                "deferred"
                if result is not None and result.deferral is not None
                else "unresolved"
            )
        )
        rows.append(
            ExpectedSignal(
                channel=tap.channel,
                target_path=tap.target_path,
                kind=tap.kind,
                quantity=quantity,
                expected=None,
                units="",
                provenance=Provenance(
                    kind="claim",
                    ref=source.claim_name or claim_text(obligation.claim),
                    reason=f"claim status={status}: not model-backed discharged "
                    "(calc book carries no resolved numeric for this tap -- "
                    "WO117-F2 territory) -- emitted without a fabricated number",
                ),
                note="no_verified_expectation",
            )
        )
    _log.info(
        "build_expected_signals: %d row(s), %d provenance-backed",
        len(rows),
        sum(1 for r in rows if r.provenance.kind == "calc_sheet"),
    )
    return tuple(rows)


# frob:doc docs/modules/py-backends.md#backends-harness-pack
def expected_signals_bytes(rows: tuple[ExpectedSignal, ...]) -> bytes:
    """Canonical, deterministic `harness/expected_signals.json` bytes."""
    doc = {
        "schema": "regolith.expected_signals.v1",
        "signals": [r.model_dump(mode="json") for r in rows],
    }
    return json.dumps(
        doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True, indent=2
    ).encode("ascii")


# frob:doc docs/modules/py-backends.md#backends-harness-pack
def check_expectation_provenance(
    expected_bytes: bytes, calc_files: tuple[OutputFile, ...]
) -> Result[None, BackendError]:
    """Ship-path check (deliverable 6): every `calc_sheet` provenance ref
    resolves to a real sheet digest inside the SAME package's `calc/`
    family, and every `claim` provenance ref resolves to a claim name
    the `calc/audit_index.json` row set actually carries (the same
    "zero unexplained rows" surface the calc audit index already
    provides -- no second resolution index invented for this WO).

    When the `calc/` family itself did not ship at all (no
    `calc/audit_index.json` among ``calc_files`` -- `_build_calc_book`
    already logged WHY, e.g. an obligation/result count mismatch on a
    degenerate/test report), there is nothing in the package to resolve
    ANY provenance ref against; this is a calc-package-build condition
    already surfaced elsewhere, not a WO-126 fabrication, so the check
    is skipped (logged) rather than refusing the ship a second time for
    the same root cause."""
    has_audit_index = any(f.relpath == "calc/audit_index.json" for f in calc_files)
    if not has_audit_index:
        _log.warning(
            "check_expectation_provenance: no calc/audit_index.json in this "
            "package -- provenance resolution skipped (the calc package "
            "build already logged why)"
        )
        return Ok(None)
    try:
        doc = json.loads(expected_bytes.decode("ascii"))
    except (ValueError, UnicodeDecodeError) as exc:
        return Err(
            BackendError(
                kind="expected_signals_malformed",
                message=f"expected_signals.json is not JSON: {exc}",
            )
        )
    sheet_digests: set[str] = set()
    audit_claim_names: set[str] = set()
    for f in calc_files:
        if f.relpath == "calc/calc_book.json":
            try:
                book = json.loads(f.content.decode("ascii"))
            except (ValueError, UnicodeDecodeError):
                continue
            for sheet in book.get("sheets", ()):
                chain = sheet.get("chain", {})
                digest = chain.get("sheet_digest")
                if digest:
                    sheet_digests.add(digest)
        if f.relpath == "calc/audit_index.json":
            try:
                index = json.loads(f.content.decode("ascii"))
            except (ValueError, UnicodeDecodeError):
                continue
            for row in index.get("rows", ()):
                name = row.get("claim_name")
                if name:
                    audit_claim_names.add(name)

    unresolved: list[str] = []
    unitless: list[str] = []
    for row in doc.get("signals", ()):
        provenance = row.get("provenance", {})
        kind = provenance.get("kind")
        ref = provenance.get("ref", "")
        if kind == "calc_sheet" and ref not in sheet_digests:
            unresolved.append(f"channel {row.get('channel')}: calc_sheet ref {ref!r}")
        elif kind == "claim" and ref and ref not in audit_claim_names:
            unresolved.append(f"channel {row.get('channel')}: claim ref {ref!r}")
        # D224 units invariant (charter 40 sec. 3): a POPULATED expected
        # value never ships without its units -- an empty units string
        # beside a real number is neither a value-with-units nor an
        # honest named absence, so this is refused exactly like an
        # unresolved provenance ref rather than silently shipped.
        if row.get("expected") is not None and not row.get("units"):
            unitless.append(
                f"channel {row.get('channel')}: expected value with no units"
            )
    if unresolved or unitless:
        _log.error(
            "check_expectation_provenance: %d unresolved provenance ref(s), "
            "%d unitless expected value(s): %s",
            len(unresolved),
            len(unitless),
            unresolved + unitless,
        )
        return Err(
            BackendError(
                kind=EXPECTATION_PROVENANCE_UNRESOLVED,  # E1101 (D247.1)
                message="expected_signals.json carries provenance ref(s) that do "
                "not resolve inside the package, or a populated expected value "
                f"with no units (D224): {unresolved + unitless}",
            )
        )
    _log.info(
        "check_expectation_provenance: %d signal row(s), all provenance refs "
        "resolve, every populated value carries units",
        len(doc.get("signals", ())),
    )
    return Ok(None)


# frob:doc docs/modules/py-backends.md#backends-harness-pack
def check_bringup_expectation_authored_posture(
    expected_bytes: bytes,
    records_dirs: tuple[str, ...],
    package: str = "",
) -> Result[None, BackendError]:
    """WO-151 deliverable 4: refuse an `expected_signals.json` row whose
    `provenance.kind == "record"` cites a `posture = "authored"`
    waveform/mask record -- an authored (hand-drawn) record is design
    intent (D260 ruling 3), never a verified numeric expectation. The
    record remains perfectly usable as a mask/stimulus profile
    (`stays_within`, `structure: transient`); it is only refused HERE,
    at the point it is cited as a `expected_signals`/`model=` verified
    pin.

    Every `record`-kind ref is resolved fresh against `records_dirs`
    (WO-151 deliverable 3's `resolve_mask_ref`) rather than trusting
    the row's own `posture` field, so a row that lies about its cited
    record's posture cannot forge a pass (D246's unreachability
    doctrine, the same one this record class's constructors follow)."""
    try:
        doc = json.loads(expected_bytes.decode("ascii"))
    except (ValueError, UnicodeDecodeError) as exc:
        return Err(
            BackendError(
                kind="expected_signals_malformed",
                message=f"expected_signals.json is not JSON: {exc}",
            )
        )
    refused: list[str] = []
    for row in doc.get("signals", ()):
        provenance = row.get("provenance", {})
        if provenance.get("kind") != "record":
            continue
        ref = provenance.get("ref", "")
        resolved = resolve_mask_ref(ref, records_dirs, package=package)
        if resolved.is_err:
            # A record ref that does not resolve at all is
            # `check_expectation_provenance`'s job (an unresolved
            # provenance ref, E1101); this check only judges POSTURE
            # on a ref that DID resolve.
            continue
        posture = resolved.danger_ok.provenance.posture
        if posture == "authored":
            refused.append(
                f"channel {row.get('channel')}: record ref {ref!r} is "
                f"posture={posture!r}"
            )
    if refused:
        _log.error(
            "check_bringup_expectation_authored_posture: %d authored-posture "
            "record(s) cited as a verified expectation: %s",
            len(refused),
            refused,
        )
        return Err(
            BackendError(
                kind=BRINGUP_EXPECTATION_AUTHORED_POSTURE,  # E1104 (pending codegen)
                message=(
                    "expected_signals.json cites an authored-posture "
                    "waveform/mask record where a verified expectation is "
                    "required (D263.1: authored is design intent, never a "
                    "model-backed or measured value); the record stays "
                    "usable as a mask/stimulus profile (stays_within, "
                    f"structure: transient), never as a verified pin: "
                    f"{refused}"
                ),
            )
        )
    _log.info(
        "check_bringup_expectation_authored_posture: no authored-posture "
        "record cited as a verified expectation"
    )
    return Ok(None)


def _tap_line(
    tap: Tap, header: TapHeaderRecord | None, expected: ExpectedSignal | None
) -> str:
    """One `bringup.md` probe-procedure line for an allocated tap."""
    pin = header.connector_pin(tap.channel) if header is not None else None
    where = (
        f"connector pin {pin}" if pin is not None else "no connector (named absence)"
    )
    if expected is None:
        verdict = "no expected-signal row (unexpected)"
    elif expected.provenance.kind == "calc_sheet" and expected.expected is not None:
        verdict = (
            f"expect {expected.expected} {expected.units} "
            f"(calc sheet `{expected.provenance.ref}`)"
        )
    elif expected.provenance.kind == "calc_sheet":
        # Discharged, calc-sheet-backed, but the row degraded (D224/
        # WO117-F2, `build_expected_signals`): no bare number is
        # printed, the sheet is still cited so a technician can look
        # the real discharge up by hand.
        verdict = (
            "no printed value -- discharged (see calc sheet "
            f"`{expected.provenance.ref}`) but {expected.provenance.reason}"
        )
    elif expected.provenance.kind == "claim":
        verdict = (
            f"no verified expectation -- claim `{expected.provenance.ref}` declared "
            f"but not discharged ({expected.provenance.reason})"
        )
    else:
        verdict = f"no verified expectation ({expected.provenance.reason})"
    marker = tap_marker(tap.channel, tap.target_path)
    return (
        f"- Probe TP{tap.channel} / channel {tap.channel} ({where}), "
        f"target `{tap.target_path}` ({tap.kind}): {verdict}. [{marker}]"
    )


# frob:doc docs/modules/py-backends.md#backends-harness-pack
def render_bringup(
    project: str,
    tap_set: TapSet,
    header: TapHeaderRecord | None,
    expected: tuple[ExpectedSignal, ...],
) -> str:
    """The ordered bring-up procedure (WO-96 instructions idiom): power-on
    order safety-first (rails, then clocks, buses, the rest), per-channel
    probe steps with claim/calc-sheet cross-references, and the honest
    unallocated/absence callouts (charter 40 sec. 5)."""
    by_channel = {e.channel: e for e in expected}
    ordered = sorted(tap_set.taps, key=lambda t: (_KIND_RANK.get(t.kind, 9), t.channel))

    lines: list[str] = [f"# Bring-up procedure: {project}", ""]
    if header is not None:
        lines.append(
            f"Tap header: `{header.key}` ({header.connector}, {header.channels} "
            f"channel(s), {header.ordering}, ground {header.ground}, keying "
            f"{header.keying}). Reference: {header.reference}."
        )
    else:
        lines.append(
            "No tap header record resolved for this project -- no physical "
            "connector to probe (charter 40 sec. 4/5 named absence)."
        )
    lines.append("")
    lines.append(
        "## Power-on order (safety-relevant first: rails, then clocks, "
        "buses, other signals)"
    )
    lines.append("")
    if not ordered:
        lines.append("(no taps allocated)")
    for tap in ordered:
        lines.append(_tap_line(tap, header, by_channel.get(tap.channel)))
    lines.append("")

    lines.append("## Unallocated candidates")
    lines.append("")
    if tap_set.unallocated:
        for row in tap_set.unallocated:
            lines.append(
                f"- `{row.target_path}` ({row.kind}): {row.reason} -- {row.why}"
            )
    else:
        lines.append("(none -- every claim-named candidate was allocated a channel)")
    lines.append("")
    return "\n".join(lines)


def _capture_config(kind: str, taps: tuple[Tap, ...]) -> str:
    """One sigrok-cli command file for a capture group (config-only tier:
    the driver line is a template a technician swaps for their actual
    analyzer -- `sigrok-cli --scan` names it -- never a claimed physical
    fact). Deterministic text, channel list sorted by channel number."""
    ordered = sorted(taps, key=lambda t: t.channel)
    channel_list = ",".join(f"{t.channel}={t.target_path}" for t in ordered)
    lines = [
        f"# sigrok-cli capture config -- {_CAPTURE_GROUP_LABEL[kind]} group",
        "# Replace --driver with your analyzer (see `sigrok-cli --scan`).",
        f"# Channels ({len(ordered)}): {channel_list}",
        "sigrok-cli \\",
        "  --driver fx2lafw \\",
        f"  --channels {','.join(str(t.channel) for t in ordered)} \\",
        "  --config samplerate=1MHz \\",
        "  --time 10ms \\",
        f"  -o {_CAPTURE_GROUP_LABEL[kind]}.sr",
        "",
    ]
    return "\n".join(lines)


# frob:doc docs/modules/py-backends.md#backends-harness-pack
def harness_files(
    project: str,
    tap_map_bytes: bytes,
    tap_set: TapSet,
    header: TapHeaderRecord | None,
    payload: dict,
    results: tuple[ObligationResult, ...],
    calc_book: CalcBook | None,
) -> tuple[OutputFile, ...]:
    """Every `harness/` family file for a debug ship (charter 40 sec. 3):
    the canonical tap map (WO-125's own bytes, unmodified -- one truth),
    `expected_signals.json`, `bringup.md`, and per-kind sigrok-cli
    capture configs (only for kinds that actually have allocated taps --
    an empty group is a named absence in `bringup.md`'s unallocated
    section, never an empty capture file)."""
    expected = build_expected_signals(tap_set, payload, results, calc_book)
    files: list[OutputFile] = [
        OutputFile.of("harness/tap_map.json", tap_map_bytes),
        OutputFile.of(
            "harness/expected_signals.json", expected_signals_bytes(expected)
        ),
        OutputFile.of(
            "harness/bringup.md",
            render_bringup(project, tap_set, header, expected).encode("ascii"),
        ),
    ]
    by_kind: dict[str, list[Tap]] = {}
    for tap in tap_set.taps:
        by_kind.setdefault(tap.kind, []).append(tap)
    for kind in _CAPTURE_GROUPS:
        taps = tuple(by_kind.get(kind, ()))
        if not taps:
            continue
        config = _capture_config(kind, taps)
        files.append(
            OutputFile.of(
                f"harness/capture_{_CAPTURE_GROUP_LABEL[kind]}.sigrok-cli",
                config.encode("ascii"),
            )
        )
    _log.info("harness_files: %d file(s) for %s", len(files), project)
    return tuple(files)
