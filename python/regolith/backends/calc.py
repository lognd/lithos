"""The calc package + audit index -- the audit trail (WO-114, D221).

Every shipped ``dist/<project>/`` release package gains a CALCULATION
REPORT family (``calc/``) -- what an engineering firm calls the calc
book -- produced beside the other artifact families in
:mod:`regolith.backends.ship`:

1. One calc SHEET per DISCHARGED obligation (a result with no deferral
   AND ``discharged`` evidence status -- model-backed resolved, census
   v2/D220.3, the same set the fleet census counts as ``discharged``):
   the claim
   (source text + subject anchor), the model (id, version, citation),
   every ``given`` input with its provenance pin (record ref / declared
   literal / derived), the solver + tier + attestation, the computed
   margin, and the verdict -- with a content-hash CHAIN linking the
   sheet -> its evidence -> its payload refs -> the source content
   addresses (subject + pinned material records).
2. One package-level AUDIT INDEX mapping EVERY obligation in the design
   to exactly one disposition -- a calc sheet (discharged), an accepted
   deviation (cross-linking the WO-98 ``acceptance_ledger.json`` waiver
   target + its memo digest), a named deferral, or a violated verdict --
   so a reviewer walks the complete obligation set with ZERO unexplained
   rows. Its summary counts use the SAME definitions as
   ``tools.health.fleet._census_from_report`` (discharged = no deferral;
   accepted = the acceptance ledger's accepted hashes; violated =
   ``violated`` deferrals), so the audit index and the census can never
   disagree.

Forms (D221.3): canonical JSON (deterministic, sorted, ASCII) for the
book and the index, plus a rendered PDF per sheet through the EXISTING
`DrawingModel` renderer registry (the style-pack seam,
:func:`regolith.backends.registry.render_files_for_model`) -- no second
renderer, no second encoder. Every file is an
:class:`~regolith.backends.framework.OutputFile`, so it is
content-addressed in the ship manifest and re-verified by
``ship --verify`` exactly like any artifact.

Determinism (AD-6/INV-10): the canonical addresses this book CITES
(``subject_ref``, ``evidence.hash``, material record hashes) are the
Rust content addresses already on the payload; the sheet's OWN digest is
a producer-local blake3, PREFIX-TAGGED ``local-blake3:`` per charter 38
sec. 1.4 so a local digest is never confusable with a canonical one.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Literal

import blake3
from pydantic import BaseModel, ConfigDict

from regolith._schema.models import Claim, Given, Obligation
from regolith.backends.framework import OutputFile
from regolith.harness.quantity import bits_to_f64
from regolith.logging_setup import get_logger
from regolith.orchestrator.acceptance import AcceptanceOutcome, Deviation
from regolith.orchestrator.discharge import ObligationResult

_log = get_logger(__name__)

# The honest marker a model with no citation renders as (D221 d4 /
# WO-114 deliverable 4): the sheet never fabricates a reference.
UNCITED = "uncited built-in"

# WO-123 (D238.4 defect 1): a printed calc quantity NEVER ships bare --
# a numeric declared_literal/derived row that carries no reachable unit
# renders this explicit marker instead (never a guessed unit, D224); a
# reviewer reading `k_bolt -- 6.3e8` knows immediately the unit is an
# honest gap, not an omission.
UNIT_UNREACHABLE = "--"


def _looks_numeric(value: str) -> bool:
    """True iff ``value`` is a bare numeric literal (a real quantity).

    Used to gate the unit/marker suffix (WO-123 D238.4): a non-numeric
    cell (a record-ref hash pin, a verdict word, ``"-"`` for an
    unresolved obligation) is not a quantity and never grows a unit
    marker it has no business carrying.
    """
    stripped = value.strip()
    return bool(stripped) and stripped not in ("-",) and stripped[0] in "+-0123456789"


def _quantity_cell(value: str, unit: str, *, is_quantity: bool) -> str:
    """Render one quantity's table cell: value + unit, or the honest marker.

    A non-quantity cell (``is_quantity=False``) renders unchanged --
    this only ever adds a unit or :data:`UNIT_UNREACHABLE`, never
    invents one (D224)."""
    if not is_quantity:
        return value
    return f"{value} {unit}" if unit else f"{value} {UNIT_UNREACHABLE}"


# The provenance pin classes for a calc input (D221.1). ``record_ref``:
# a pinned std.*/registry record (its content hash is the pin);
# ``declared_literal``: a value written directly in the design source
# (a `given:` load expression); ``derived``: a value resolved from other
# declared design data (a D103 entity-field reference); ``unresolved``:
# no provenance is reachable from the payload surface for this datum
# (never invented -- the honest gap, ledgered per model family).
ProvenanceKind = Literal["record_ref", "declared_literal", "derived", "unresolved"]

# The disposition every obligation maps to in the audit index (D221.2).
Disposition = Literal["calc_sheet", "accepted_deviation", "deferred", "violated"]


class CalcInput(BaseModel):
    """One input to a calc sheet's obligation, with its provenance pin.

    ``value`` is the datum as written (unit-carrying text is kept
    verbatim -- the source is the truth, never re-normalized); ``pin`` is
    the content address for a ``record_ref`` (else empty). ``source`` is
    the human-readable origin (the record name, the literal expression,
    or the derived value-source text).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    value: str
    provenance: ProvenanceKind
    pin: str = ""
    source: str = ""
    unit: str = ""


class EvidenceChain(BaseModel):
    """The content-hash chain proving a calc sheet's derivation (D221.1).

    ``sheet_digest`` is the producer-local blake3 of the sheet's own
    canonical bytes (``local-blake3:`` tagged, charter 38 sec. 1.4);
    ``evidence_hash`` / ``subject_ref`` / ``record_pins`` are the
    CANONICAL Rust content addresses off the payload (untagged). A
    reviewer follows sheet -> evidence -> payload -> sources without
    trusting anything but the shipped bytes.
    """

    model_config = ConfigDict(frozen=True)

    sheet_digest: str
    evidence_hash: str
    subject_ref: str
    payload_refs: tuple[str, ...] = ()
    record_pins: tuple[str, ...] = ()


class CalcSheet(BaseModel):
    """One discharged obligation's calc sheet (D221.1)."""

    model_config = ConfigDict(frozen=True)

    sheet_id: str
    claim_name: str
    claim_text: str
    subject_anchor: str
    subject_ref: str
    model_id: str
    model_version: str
    citation: str
    solver: str
    tier: str
    attestation: str
    inputs: tuple[CalcInput, ...]
    value: str
    margin: str
    unit: str = ""
    verdict: str
    chain: EvidenceChain


class AuditRow(BaseModel):
    """One obligation's disposition in the audit index (D221.2).

    ``detail`` names the exact evidence: for a ``calc_sheet`` the sheet
    id; for an ``accepted_deviation`` the waiver target + its memo digest
    (cross-linking ``acceptance_ledger.json``, never duplicating it); for
    a ``deferred``/``violated`` row the named reason.
    """

    model_config = ConfigDict(frozen=True)

    claim_name: str
    subject_anchor: str
    content_hash: str
    disposition: Disposition
    detail: str


class AuditSummary(BaseModel):
    """The audit index's obligation accounting (D221.2).

    TWO honest denominators, both reported so they can never be confused:

    * the CENSUS-shape counts (``discharged`` = model-backed resolved:
      no deferral AND ``discharged`` evidence status, census v2/D220.3;
      ``accepted_deviation`` = the number of UNIQUE accepted obligation
      content addresses -- exactly ``len(acceptance.accepted_hashes)``,
      the same value ``fleet._census_from_report`` records; ``violated``)
      so the audit index reconciles with ``fleet_census.json`` field for
      field via :meth:`census_row`;
    * the ROW partition (``discharged`` + ``accepted_rows`` + ``deferred``
      + ``violated`` == ``obligations``), because a calc sheet and an
      audit row are PER OBLIGATION and forall-expanded obligation
      instances legitimately share one content address -- so the number
      of accepted ROWS (:attr:`accepted_rows`) can exceed the number of
      unique accepted addresses (:attr:`accepted_deviation`). The row
      partition is the zero-unexplained property (:meth:`balanced`).
    """

    model_config = ConfigDict(frozen=True)

    obligations: int
    discharged: int
    accepted_deviation: int
    accepted_rows: int
    deferred: int
    violated: int

    def balanced(self) -> bool:
        """True iff every obligation row is accounted for exactly once."""
        return (
            self.discharged + self.accepted_rows + self.deferred + self.violated
            == self.obligations
        )

    def census_row(self) -> dict[str, int]:
        """The census-shape projection (matches ``fleet_census.json``)."""
        return {
            "obligations": self.obligations,
            "discharged": self.discharged,
            "accepted_deviation": self.accepted_deviation,
            "violated": self.violated,
        }


class AuditIndex(BaseModel):
    """The package-level audit index: total accounting + per-obligation rows."""

    model_config = ConfigDict(frozen=True)

    project: str
    summary: AuditSummary
    rows: tuple[AuditRow, ...]


class CalcBook(BaseModel):
    """The whole calc package: every calc sheet plus the audit index."""

    model_config = ConfigDict(frozen=True)

    sheets: tuple[CalcSheet, ...]
    index: AuditIndex


def claim_text(claim: Claim) -> str:
    """Reconstruct one claim's source text from its typed form.

    A scalar comparison renders ``<lhs> <op> <rhs>``; every other typed
    form renders through its own fields (the form's ``op`` when it
    carries one, else its class name) so no claim ever renders blank.
    """
    form = claim.form
    lhs = getattr(form, "lhs", None)
    op = getattr(form, "op", None)
    rhs = getattr(form, "rhs", None)
    if lhs is not None and op is not None and rhs is not None:
        return f"{lhs} {op} {rhs}"
    if lhs is not None and op is not None:
        return f"{lhs} {op}"
    # Non-comparison forms (temporal/containment): name + any op.
    label = getattr(form, "signal", None) or getattr(form, "lhs", None) or ""
    return (
        f"{label} {op}".strip() if op is not None else str(label) or claim.name or "-"
    )


def subject_anchor(subject_ref: str, snapshots: dict[str, str]) -> str:
    """The obligation's human-readable source anchor.

    The snapshot ``scope`` for the subject (the declaration the
    obligation is rooted at) when known, else the truncated content
    address -- never blank, never fabricated.
    """
    return snapshots.get(subject_ref, subject_ref[:12])


# The trailing unit suffix directly attached to a numeric literal,
# including a one-`*` compound unit (`9.4N*m` -> unit `N*m`, matching
# how the corpus spells a moment as force-times-lever-arm inline; D224:
# read verbatim off the source text, never re-derived).
_VALUE_UNIT_RE = re.compile(
    r"^([+-]?[0-9][0-9.eE+_]*)\s*((?:[A-Za-z%]+)?(?:\*[A-Za-z]+)?)$"
)


def _split_value_unit(text: str) -> tuple[str, str]:
    """Split a literal's numeric magnitude from its inline unit suffix.

    ``"9.4N*m"`` -> ``("9.4", "N*m")``; ``"9.4*m"`` -> ``("9.4", "m")``
    (a lone ``*<unit>`` factor with no attached prefix unit strips its
    leading ``*`` -- it names one unit, not a product of two); ``"14900"``
    -> ``("14900", "")`` (no inline unit -- the caller falls back to the
    model's declared port unit, else the honest :data:`UNIT_UNREACHABLE`
    marker). Text that is not a bare numeric literal (a record name, a
    reference path) returns unchanged with an empty unit -- never
    misparsed.
    """
    match = _VALUE_UNIT_RE.match(text.strip())
    if match is None:
        return text, ""
    value, unit = match.groups()
    unit = unit or ""
    if unit.startswith("*") and unit.count("*") == 1:
        unit = unit[1:]
    return value, unit


def inputs_from_given(
    given: Given, *, input_units: Mapping[str, str] | None = None
) -> tuple[CalcInput, ...]:
    """Every input the obligation's ``given:`` context pins, with provenance.

    ``materials`` are pinned records (``record_ref``, the record hash is
    the pin); ``loads`` are declared source expressions
    (``declared_literal``); ``refs`` are D103 entity-field references
    resolved from other declared data (``derived``). An obligation whose
    given carries none of these yields an empty tuple -- the honest
    "no reachable provenance" signal a per-family gap ledger reads, never
    an invented input.

    WO-123 D238.4: ``input_units`` (the discharging model's own
    declared port units, when known) fills a numeric row's unit when
    the literal text carries none of its own -- the same fallback
    order :func:`inputs_from_claim_kwargs` uses.
    """
    units = input_units or {}
    inputs: list[CalcInput] = []
    for material in given.materials:
        parts = list(material.root)
        name = parts[0] if parts else "?"
        pin = parts[1] if len(parts) > 1 else ""
        inputs.append(
            CalcInput(
                name=name,
                value=pin[:12] if pin else "",
                provenance="record_ref",
                pin=pin,
                source=name,
            )
        )
    for load in given.loads:
        key, sep, val = load.partition(":")
        name = key.strip() if sep else load
        raw_value = val.strip() if sep else ""
        value, unit = _split_value_unit(raw_value)
        inputs.append(
            CalcInput(
                name=name,
                value=value,
                provenance="declared_literal",
                source=load,
                unit=unit or units.get(name, ""),
            )
        )
    for ref in given.refs or ():
        parts = list(ref.root)
        path = parts[0] if parts else "?"
        value_src = parts[1] if len(parts) > 1 else ""
        value, unit = _split_value_unit(value_src)
        inputs.append(
            CalcInput(
                name=path,
                value=value,
                provenance="derived",
                source=value_src or path,
                unit=unit or units.get(path, ""),
            )
        )
    return tuple(inputs)


# WO-123 (D238.3 defect 1): a `given:` context is not the only place a
# claim's own literal data lives -- a call-form claim (e.g.
# `mech.bearing.l10_hours(c_rating=13200, p_load=500, ...)`) carries its
# numeric arguments INLINE, in the claim's own source text. Those are
# just as real and just as provenance-pinnable (the claim text IS the
# declared source) as a `given:` load, so they render as `declared_literal`
# rows too -- read from the claim's own text, never computed (D224).
# WO-123 D238.4: the value group also captures a directly-attached unit
# suffix (`9.4N*m`, one `*`-compound at most) so a kwarg that spells its
# own unit inline is never truncated to a bare number.
_KWARG_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([0-9][0-9.eE+_-]*[A-Za-z%]*(?:\*[A-Za-z]+)?)"
)


def inputs_from_claim_kwargs(
    text: str, *, input_units: Mapping[str, str] | None = None
) -> tuple[CalcInput, ...]:
    """Numeric ``name=value`` keyword arguments inline in a claim's own
    call-form source text, as ``declared_literal`` inputs.

    Only numeric-literal kwargs match (``c_rating=13200``, not
    ``pair=dgb_6006`` -- a symbol reference has no scalar value to
    print); each becomes a row citing the exact source text as its
    provenance, so a reviewer can trace the printed row back to the
    claim line it came from.

    WO-123 D238.4: the unit is read off the literal itself when it
    carries one inline (``under=9.4N*m`` -> unit ``N*m``); otherwise it
    falls back to ``input_units[name]`` -- the discharging model's own
    declared port unit (never guessed, D224) -- else stays unreachable.
    """
    units = input_units or {}
    inputs: list[CalcInput] = []
    seen: set[str] = set()
    for match in _KWARG_RE.finditer(text):
        name, raw_value = match.group(1), match.group(2)
        if name in seen:
            continue
        seen.add(name)
        value, unit = _split_value_unit(raw_value)
        inputs.append(
            CalcInput(
                name=name,
                value=value,
                provenance="declared_literal",
                source=f"{name}={raw_value}",
                unit=unit or units.get(name, ""),
            )
        )
    return tuple(inputs)


# The trailing unit suffix of a numeric literal (`"20000hr"` -> `"hr"`,
# `"13200N"` -> `"N"`); a claim's own comparison rhs is the ONE place a
# discharged claim's result unit is declared (D224: the renderer never
# invents a unit, it reads the one the claim's own source text carries).
_UNIT_SUFFIX_RE = re.compile(r"^[+-]?[0-9][0-9.eE+_]*\s*([A-Za-z%/*]+)?$")


def unit_from_claim(claim: Claim) -> str:
    """The claim's own result unit, read from its comparison rhs literal
    (e.g. ``>= 20000hr`` -> ``"hr"``); empty when the rhs carries no unit
    suffix or the claim has no scalar rhs -- never fabricated.
    """
    rhs = getattr(claim.form, "rhs", None)
    if not isinstance(rhs, str):
        return ""
    match = _UNIT_SUFFIX_RE.match(rhs.strip())
    if match is None:
        return ""
    return match.group(1) or ""


def _si_unit_from_obligation(obligation: Obligation) -> str:
    """WO-128/F144 deliverable 1's Rust-lowering fallback: the closed
    `elec.impedance`/`elec.termination` SI vocabulary's own known output
    unit (`translate.si_output_unit`), for an obligation whose claim rhs
    carries no unit token of its own post SI-normalization. Import kept
    local (not top-level) to avoid a module-load cycle: `orchestrator.
    translate` is the higher-level lowering module, `backends.calc` a
    lower one it does not itself import."""
    from regolith.orchestrator.translate import si_sheet_fields

    fields = si_sheet_fields(obligation)
    return fields["unit"] if fields is not None else ""


def _canonical_bytes(doc: object) -> bytes:
    """Deterministic, sorted, ASCII JSON bytes (the calc-book encoder).

    The same discipline ``acceptance_ledger_bytes`` uses -- one home for
    the calc family's canonical serialization, byte-identical across
    runs (no wall-clock, no absolute paths, sorted keys)."""
    return json.dumps(
        doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True, indent=2
    ).encode("ascii")


def _sheet_digest(sheet_without_chain: dict[str, object]) -> str:
    """The producer-local blake3 of a sheet's canonical bytes (tagged).

    Tagged ``local-blake3:`` (charter 38 sec. 1.4) because a calc sheet
    has no upstream Rust content address of its own -- the tag keeps a
    producer-local digest from ever being confused with a canonical one.
    """
    digest = blake3.blake3(_canonical_bytes(sheet_without_chain)).hexdigest()
    return f"local-blake3:{digest}"


def _model_version(model_id: str) -> str:
    """The version suffix of a ``name@version`` model id (empty if none)."""
    _, sep, version = model_id.rpartition("@")
    return version if sep else ""


def _build_sheet(
    obligation: Obligation,
    result: ObligationResult,
    *,
    snapshots: dict[str, str],
    citations: dict[str, str | None],
    input_units: dict[str, Mapping[str, str]] | None = None,
    output_units: dict[str, str | None] | None = None,
    tier: str,
) -> CalcSheet:
    """Assemble one discharged obligation's calc sheet."""
    evidence = result.evidence
    claim = obligation.claim
    anchor = subject_anchor(obligation.subject_ref, snapshots)
    model_id = evidence.model_id if evidence is not None else "-"
    model_units = (input_units or {}).get(model_id, {})
    given_inputs = inputs_from_given(obligation.given, input_units=model_units)
    given_names = {i.name for i in given_inputs}
    kwarg_inputs = tuple(
        i
        for i in inputs_from_claim_kwargs(claim_text(claim), input_units=model_units)
        if i.name not in given_names
    )
    inputs = given_inputs + kwarg_inputs
    # WO-123 D238.4: the model's own declared output unit is the primary
    # source for the Result value/margin unit; the claim rhs suffix
    # (`unit_from_claim`) is the fallback for claim kinds that compare
    # directly against a unit-bearing literal. WO-128/F144 deliverable 1
    # adds a THIRD fallback: `elec.impedance`/`elec.termination` window
    # halves lose their rhs unit token in Rust's `resolve_unit_suffix`
    # SI-normalization (the trace this WO recorded), so
    # `translate.si_output_unit`'s closed SI vocabulary is read last --
    # never a guess beyond that fixed, physically-known set (D224).
    unit = (
        (output_units or {}).get(model_id)
        or unit_from_claim(claim)
        or _si_unit_from_obligation(obligation)
    )
    for row in inputs:
        if (
            row.provenance in ("declared_literal", "derived")
            and not row.unit
            and row.value[:1] in "+-0123456789"
        ):
            _log.warning(
                "calc sheet %s: input %r has no reachable unit -- "
                "rendering the honest %r marker (D224, never guessed)",
                claim.name or claim_text(claim),
                row.name,
                UNIT_UNREACHABLE,
            )
    citation = citations.get(model_id) or UNCITED
    value = f"{bits_to_f64(evidence.value_bits):g}" if evidence is not None else "-"
    margin = f"{bits_to_f64(evidence.margin_bits):g}" if evidence is not None else "-"
    verdict = evidence.status.value if evidence is not None else "unresolved"
    payload_refs = tuple(
        f"{ref.kind}:{ref.origin}@{ref.digest}"
        if ref.digest
        else f"{ref.kind}:{ref.origin}"
        for ref in (obligation.payloads or ())
    )
    record_pins = tuple(
        m.root[1] for m in obligation.given.materials if len(m.root) > 1
    )
    sheet_id = f"{claim.name or claim_text(claim)}::{obligation.subject_ref[:12]}"
    # The sheet's own body (everything but its chain digest) hashes into
    # that digest -- the chain closes over the sheet, not vice versa.
    body: dict[str, object] = {
        "sheet_id": sheet_id,
        "claim_name": claim.name or "",
        "claim_text": claim_text(claim),
        "subject_anchor": anchor,
        "subject_ref": obligation.subject_ref,
        "model_id": model_id,
        "model_version": _model_version(model_id),
        "citation": citation,
        "inputs": [i.model_dump() for i in inputs],
        "value": value,
        "margin": margin,
        "verdict": verdict,
        "evidence_hash": evidence.hash if evidence is not None else "",
    }
    chain = EvidenceChain(
        sheet_digest=_sheet_digest(body),
        evidence_hash=evidence.hash if evidence is not None else "",
        subject_ref=obligation.subject_ref,
        payload_refs=payload_refs,
        record_pins=record_pins,
    )
    return CalcSheet(
        sheet_id=sheet_id,
        claim_name=claim.name or "",
        claim_text=claim_text(claim),
        subject_anchor=anchor,
        subject_ref=obligation.subject_ref,
        model_id=model_id,
        model_version=_model_version(model_id),
        citation=citation,
        solver=model_id.partition("@")[0],
        tier=tier,
        attestation=getattr(result.attestation, "kind", "unknown"),
        inputs=inputs,
        value=value,
        margin=margin,
        unit=unit,
        verdict=verdict,
        chain=chain,
    )


def _deviation_for_hash(
    content_hash: str, acceptance: AcceptanceOutcome
) -> Deviation | None:
    """The accepted deviation (waiver) that accepted ``content_hash``.

    The first deviation, in the acceptance outcome's own order, whose
    ``accepted`` set contains the hash -- the cross-link into
    ``acceptance_ledger.json`` (never a re-derivation of the ledger)."""
    for dev in acceptance.deviations:
        if content_hash in dev.accepted:
            return dev
    return None


def build_calc_book(
    project: str,
    obligations: tuple[Obligation, ...],
    results: tuple[ObligationResult, ...],
    acceptance: AcceptanceOutcome,
    *,
    snapshots: dict[str, str],
    citations: dict[str, str | None],
    input_units: dict[str, Mapping[str, str]] | None = None,
    output_units: dict[str, str | None] | None = None,
    tier: str,
) -> CalcBook:
    """Build the whole calc book from a build's obligations + results.

    ``obligations`` and ``results`` are index-aligned (the payload's
    obligation list and ``final.results``). Every obligation maps to
    exactly one audit row; a discharged one emits a calc sheet. The
    summary uses the census definitions so it reconciles with
    ``fleet_census.json`` by construction.

    "Discharged" (census v2, D220.3/WO117-F1, LOCKSTEP with
    ``tools.health.fleet._census_from_report``): no deferral AND the
    evidence status is ``discharged`` -- a model-backed resolve. A
    deferral-free INDETERMINATE (the pin-unmatched marker: an author
    pinned a model the probe environment does not register) is NOT a
    calc sheet; it flows to its true disposition (its waiver's
    accepted-deviation row, or an honest named deferral).
    """
    accepted = acceptance.accepted_set
    sheets: list[CalcSheet] = []
    rows: list[AuditRow] = []
    discharged = deferred = violated = 0
    accepted_count = 0
    for obligation, result in zip(obligations, results, strict=True):
        anchor = subject_anchor(obligation.subject_ref, snapshots)
        name = obligation.claim.name or claim_text(obligation.claim)
        evidence = result.evidence
        resolved = (
            result.deferral is None
            and evidence is not None
            and evidence.status == "discharged"
        )
        if resolved:
            sheet = _build_sheet(
                obligation,
                result,
                snapshots=snapshots,
                citations=citations,
                input_units=input_units,
                output_units=output_units,
                tier=tier,
            )
            sheets.append(sheet)
            discharged += 1
            rows.append(
                AuditRow(
                    claim_name=name,
                    subject_anchor=anchor,
                    content_hash=result.content_hash,
                    disposition="calc_sheet",
                    detail=sheet.sheet_id,
                )
            )
            continue
        if result.content_hash and result.content_hash in accepted:
            dev = _deviation_for_hash(result.content_hash, acceptance)
            accepted_count += 1
            detail = (
                f"waiver {dev.target} by {dev.evidence} memo={dev.evidence_digest}"
                if dev is not None
                else "accepted deviation (see acceptance_ledger.json)"
            )
            rows.append(
                AuditRow(
                    claim_name=name,
                    subject_anchor=anchor,
                    content_hash=result.content_hash,
                    disposition="accepted_deviation",
                    detail=detail,
                )
            )
            continue
        if result.deferral is None:
            # Deferral-free but NOT resolved (unaccepted indeterminate
            # evidence, e.g. an unmatched model pin on a non-release
            # build): an honest named deferral row, never a sheet.
            deferred += 1
            model = evidence.model_id if evidence is not None else "-"
            rows.append(
                AuditRow(
                    claim_name=name,
                    subject_anchor=anchor,
                    content_hash=result.content_hash,
                    disposition="deferred",
                    detail=f"indeterminate evidence ({model})",
                )
            )
            continue
        reason = result.deferral.reason
        if reason == "violated":
            violated += 1
            disposition: Disposition = "violated"
        else:
            deferred += 1
            disposition = "deferred"
        detail = reason
        if result.deferral.detail:
            detail = f"{reason}: {result.deferral.detail}"
        rows.append(
            AuditRow(
                claim_name=name,
                subject_anchor=anchor,
                content_hash=result.content_hash,
                disposition=disposition,
                detail=detail,
            )
        )
    summary = AuditSummary(
        obligations=len(results),
        discharged=discharged,
        accepted_deviation=len(accepted),
        accepted_rows=accepted_count,
        deferred=deferred,
        violated=violated,
    )
    rows.sort(key=lambda r: (r.claim_name, r.subject_anchor, r.content_hash))
    sheets.sort(key=lambda s: s.sheet_id)
    _log.info(
        "calc book: %s -- %d sheet(s); index %d obligation(s) "
        "(%d discharged, %d accepted, %d deferred, %d violated)",
        project,
        len(sheets),
        summary.obligations,
        summary.discharged,
        summary.accepted_deviation,
        summary.deferred,
        summary.violated,
    )
    if not summary.balanced():
        _log.error(
            "calc book: %s audit index does NOT balance (%d != %d) -- "
            "an obligation is unaccounted for",
            project,
            summary.discharged
            + summary.accepted_rows
            + summary.deferred
            + summary.violated,
            summary.obligations,
        )
    return CalcBook(
        sheets=tuple(sheets),
        index=AuditIndex(project=project, summary=summary, rows=tuple(rows)),
    )


def calc_book_json_bytes(book: CalcBook) -> bytes:
    """The canonical ``calc/calc_book.json`` bytes (every sheet, sorted)."""
    return _canonical_bytes(book.model_dump(mode="json"))


def audit_index_json_bytes(book: CalcBook) -> bytes:
    """The canonical ``calc/audit_index.json`` bytes (total accounting)."""
    return _canonical_bytes(book.index.model_dump(mode="json"))


def _safe_name(sheet_id: str) -> str:
    """A deterministic, filesystem-safe base name for a sheet id.

    Every character outside ``[A-Za-z0-9._-]`` collapses to ``_`` so a
    claim/subject id with ``:``/``/``/spaces cannot escape the ``calc/``
    directory or drift the manifest across platforms.
    """
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in sheet_id)


def calc_sheet_drawing(sheet: CalcSheet):  # noqa: ANN201 -- DrawingModel (avoid import cycle at top)
    """Project one calc sheet into a `DrawingModel` for the PDF renderer.

    A single-sheet table (metadata rows then one row per input with its
    provenance) so the PDF renders through the EXISTING style-pack
    renderer seam -- no calc-specific renderer, no second encoder.
    """
    from regolith._schema.models import (
        DrawingModel,
        Sheet,
        SheetSize1,
        Table,
        TableRow,
        TitleBlock,
    )

    # Charter 41 sec. 2: Claim / Model, Inputs, Result, Evidence chain --
    # FOUR sections, not one undifferentiated key-value dump (the D238.3
    # defect this WO's iteration pass fixes: Result gets its own value/
    # margin/verdict section instead of rows buried in a generic table).
    #
    # WO-123 D238.4 (defect 1): every printed quantity carries its unit
    # or the explicit UNIT_UNREACHABLE marker -- never a bare number.
    claim_columns = ["field", "value"]
    claim_rows = [
        TableRow(cells=["claim", sheet.claim_text]),
        TableRow(cells=["subject", sheet.subject_anchor]),
        TableRow(cells=["model", sheet.model_id]),
        TableRow(cells=["model version", sheet.model_version]),
        TableRow(cells=["citation", sheet.citation]),
        TableRow(cells=["solver", sheet.solver]),
        TableRow(cells=["tier", sheet.tier]),
        TableRow(cells=["attestation", sheet.attestation]),
    ]
    input_columns = ["input", "value", "provenance", "pin"]
    input_rows = [
        TableRow(
            cells=[
                i.name,
                _quantity_cell(i.value, i.unit, is_quantity=_looks_numeric(i.value)),
                i.provenance,
                i.pin,
            ]
        )
        for i in sheet.inputs
    ]
    result_columns = ["field", "value"]
    result_rows = [
        TableRow(
            cells=[
                "value",
                _quantity_cell(
                    sheet.value, sheet.unit, is_quantity=_looks_numeric(sheet.value)
                ),
            ]
        ),
        TableRow(
            cells=[
                "margin",
                _quantity_cell(
                    sheet.margin, sheet.unit, is_quantity=_looks_numeric(sheet.margin)
                ),
            ]
        ),
        TableRow(cells=["verdict", sheet.verdict.upper()]),
    ]
    evidence_columns = ["field", "value"]
    evidence_rows = [
        TableRow(cells=["evidence hash", sheet.chain.evidence_hash]),
        TableRow(cells=["sheet digest", sheet.chain.sheet_digest]),
        TableRow(cells=["subject ref", sheet.chain.subject_ref]),
    ]
    drawing_sheet = Sheet(
        size=SheetSize1.ansi_a,
        title_block=TitleBlock(
            title=f"Calc: {sheet.claim_name or sheet.claim_text}",
            drawing_number=f"CALC-{_safe_name(sheet.sheet_id)}",
            revision="A",
            scale_label="NTS",
            subject=sheet.subject_anchor,
        ),
        views=[],
        entities=[],
        dimensions=[],
        annotations=[],
        tables=[
            Table(title="Claim / Model", columns=claim_columns, rows=claim_rows),
            Table(title="Inputs", columns=input_columns, rows=input_rows),
            Table(title="Result", columns=result_columns, rows=result_rows),
            Table(title="Evidence chain", columns=evidence_columns, rows=evidence_rows),
        ],
    )
    return DrawingModel(subject=sheet.sheet_id, sheets=[drawing_sheet])


def calc_package_files(book: CalcBook) -> tuple[OutputFile, ...]:
    """Every ``calc/`` file for a release package (WO-114 deliverable 3).

    The canonical ``calc/calc_book.json`` + ``calc/audit_index.json``,
    plus one ``calc/<sheet>.pdf`` per discharged obligation rendered
    through the existing `DrawingModel` PDF renderer. Deterministic:
    sheets already sorted by id, PDF via the fixed-parameter renderer.
    """
    from regolith.backends.drawings.audit import assert_ship_ready
    from regolith.backends.drawings.renderer_pdf import render_pdf
    from regolith.backends.drawings.style import resolve_style

    style = resolve_style(None)
    files: list[OutputFile] = [
        OutputFile.of("calc/calc_book.json", calc_book_json_bytes(book)),
        OutputFile.of("calc/audit_index.json", audit_index_json_bytes(book)),
    ]
    for sheet in book.sheets:
        drawing = calc_sheet_drawing(sheet)
        # WO-123 F141 (escalated, not landed): `calc_package_files`
        # returns a bare tuple (no `Result`), so a drafting-audit
        # failure here can only be a loud warning, not the hard
        # `assert_ship_ready` refusal `DrawingsBackend.produce` gives
        # mech/fluid/civil/opt-trace drawings. Making calc sheets
        # equally gating needs this function's signature to grow a
        # `Result[..., BackendError]` (a caller-visible change to every
        # `calc_package_files` call site) -- out of this WO's landed
        # scope; ledgered here rather than silently left non-gating.
        gate_error = assert_ship_ready(drawing, sheet.sheet_id, style)
        if gate_error is not None:
            _log.warning(
                "calc sheet %s failed the drafting audit (non-gating, F141): %s",
                sheet.sheet_id,
                gate_error.message,
            )
        pdf = render_pdf(drawing, style)
        files.append(OutputFile.of(f"calc/{_safe_name(sheet.sheet_id)}.pdf", pdf))
    _log.info("calc package: %d file(s)", len(files))
    return tuple(files)
