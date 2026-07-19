"""The waveform/mask record class (D263.1, WO-151).

Spec: `docs/spec/regolith/02-quantity-core.md` sec. 5b (the record
home) and `docs/spec/cuprite/03-behavioral-layer.md` sec. 7 (the
elec-track cross-reference). A named `mask=`/waveform reference in
the corpus (`monotonic_rise`, `cell_ovp`, ...) resolves through this
module to real, cited, unit-declared data instead of nothing
(`crates/regolith-lower/src/claims/comparison.rs`'s NAMED-mask
residual: the Rust claims lowerer keeps the ref text as an opaque
payload-channel residual by design -- resolving it against real data
is this record class's job, not a rewrite of that text).

The evidence-posture taxonomy (`authored` | `measured` |
`model_derived`, D263.1) is orthogonal to the sec. 6 trust tier and
structurally complete from day one: the UNREACHABILITY doctrine
(D246, "cannot forge a pass") means an authored (hand-drawn) waveform
can never be mistaken by the pipeline for a verified expectation.
`authored` is the only posture any authoring-surface code path (a
GUI, a hand-editor) can construct; `measured` requires instrument-
provenance fields to construct at all (D257 ruling 2's "no
constructor without a citation" precedent); `model_derived` is
unconstructible without a resolving calc-sheet/evidence content hash
that only the pipeline holds.
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from typani.result import Err, Ok, Result

from regolith.errors import MagnetiteError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# D263.1's evidence-posture taxonomy: orthogonal to the sec. 6 trust
# tier (`community`/`vendor`/...), which stays on the `evidence` clause
# below unchanged.
Posture = Literal["authored", "measured", "model_derived"]

# The permanent language rule (cuprite/03 sec. 7, hematite/02 sec. 2 for
# geometric curves): no splines, ever.
Interp = Literal["linear", "hold"]

RecordClass = Literal["waveform", "mask"]

Kind = Literal["nominal", "envelope", "tolerance"]


# frob:doc docs/modules/py-magnetite.md#magnetite-waveform
class Axes(BaseModel):
    """The record's time/value units, declared ONCE (charter 41's
    per-record units discipline, generalized here)."""

    model_config = ConfigDict(frozen=True)

    t: str
    value: str


# frob:doc docs/modules/py-magnetite.md#magnetite-waveform
class Segment(BaseModel):
    """One piecewise point `(t, v)` in a waveform/mask's segment list.

    `t = 0` is the CONSUMING WINDOW's start (the spec's alignment
    rule): the anchor event lives in the citing claim's `during`/
    `within d after e` text, never here -- one meaning, no event
    vocabulary needed in the record itself."""

    model_config = ConfigDict(frozen=True)

    t: float
    v: float


# frob:doc docs/modules/py-magnetite.md#magnetite-waveform
class AuthoredProvenance(BaseModel):
    """Design-intent provenance for an `authored`-posture record (D260
    ruling 3): a hand-drawn expectation, trust-tier authored/asserted,
    never dressed as model-backed or measured. This is the ONLY
    provenance shape any authoring-surface code path (a GUI, a hand-
    editor) can reach -- unreachability by construction, not a runtime
    posture check."""

    model_config = ConfigDict(frozen=True)

    posture: Literal["authored"] = "authored"
    tool: str
    author: str
    date: str


# frob:doc docs/modules/py-magnetite.md#magnetite-waveform
class MeasuredProvenance(BaseModel):
    """Captured-trace provenance for a `measured`-posture record.

    `instrument`/`date`/`operator` are REQUIRED constructor arguments
    (no defaults): a `measured` record is unconstructible without them,
    the same "no constructor without a citation" precedent as D257
    ruling 2's `Citation`. The measured-trace IMPORTER that would
    populate these fields from a live capture is deferred (charter 40
    sec. 6); this shape exists so that importer has somewhere to land
    without a second design pass."""

    model_config = ConfigDict(frozen=True)

    posture: Literal["measured"] = "measured"
    instrument: str
    date: str
    operator: str


# frob:doc docs/modules/py-magnetite.md#magnetite-waveform
class ModelDerivedProvenance(BaseModel):
    """Computed provenance for a `model_derived`-posture record.

    `calc_sheet_hash` is REQUIRED (no default, non-empty, algorithm-
    tagged like every other content hash in this registry, INV-22):
    there is no public constructor path a GUI or hand-editor could
    call to mint a `model_derived` record without a resolving hash.
    The hash's RESOLUTION against a real calc sheet (does this digest
    correspond to an actual, discharged calc-sheet in the SAME
    package's `calc/` family) is `resolve_mask_ref`'s job at ref-
    resolution time, not this model's -- a syntactically well-formed
    but non-resolving hash still fails at resolution, mirroring
    `harness_pack.check_expectation_provenance`'s `calc_sheet` ref
    check exactly (one unreachability doctrine, two call sites)."""

    model_config = ConfigDict(frozen=True)

    posture: Literal["model_derived"] = "model_derived"
    calc_sheet_hash: str

    def _hash_well_formed(self) -> bool:
        """Structural (not cryptographic) shape check: `<algo>:<digest>`,
        INV-22's pinning shape. Real resolution happens at ref-lookup
        time against actual calc-sheet digests."""
        return ":" in self.calc_sheet_hash and bool(
            self.calc_sheet_hash.split(":", 1)[1]
        )


Provenance = AuthoredProvenance | MeasuredProvenance | ModelDerivedProvenance


# frob:doc docs/modules/py-magnetite.md#magnetite-waveform
class WaveformEvidence(BaseModel):
    """The house evidence clause (`regolith.magnetite.records.Evidence`
    shape, D58), reused rather than re-invented: `method`/`trust_tier`/
    `reference`. A record's sec. 6 trust tier is orthogonal to its
    D263.1 posture -- an `authored` record can be `trust_tier =
    "community"` OR `"vendor"`; posture answers "is this a verified
    number", trust tier answers "how much do we trust the source"."""

    model_config = ConfigDict(frozen=True)

    method: str
    trust_tier: str
    reference: str


def _content_hash(package: str, key: str, row: dict[str, object]) -> str:
    """The same stable content-hash rule every stdlib record row uses
    (`regolith.magnetite.stdlib_records.row_hash`) -- one hashing home,
    never a second rule for this record class."""
    canonical = repr(sorted((package, key, str(sorted(row.items())))))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# frob:doc docs/modules/py-magnetite.md#magnetite-waveform
class WaveformMaskRecord(BaseModel):
    """The `waveform`/`mask` record class (D263.1, regolith/02 sec. 5b).

    Frozen (`ConfigDict(frozen=True)`); constructed ONLY through
    `construct_authored`/`construct_measured`/`construct_model_derived`
    below -- direct `WaveformMaskRecord(...)` construction still type-
    checks (pydantic needs a real constructor to validate against) but
    every in-repo call site goes through the three named constructors
    so the posture-appropriate provenance shape is what pydantic's own
    discriminated-union validation enforces, not a hand-rolled `if`.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    package: str
    key: str
    record_class: RecordClass = Field(alias="class")
    quantity: str
    axes: Axes
    kind: Kind
    interp: Interp
    segments: tuple[Segment, ...]
    provenance: Provenance
    evidence: WaveformEvidence
    content_hash: str

    # frob:doc docs/modules/py-magnetite.md#magnetite-waveform
    @classmethod
    def construct_authored(
        cls,
        *,
        package: str,
        key: str,
        record_class: RecordClass,
        quantity: str,
        axes: Axes,
        kind: Kind,
        interp: Interp,
        segments: tuple[Segment, ...],
        tool: str,
        author: str,
        date: str,
        evidence: WaveformEvidence,
    ) -> WaveformMaskRecord:
        """The ONLY constructor an authoring-surface code path (a GUI,
        a hand-editor) can reach: builds an `AuthoredProvenance`
        directly, no posture parameter to mis-set."""
        row = {
            "quantity": quantity,
            "axes": axes.model_dump(),
            "kind": kind,
            "interp": interp,
            "segments": tuple(s.model_dump() for s in segments),
        }
        record = cls(
            package=package,
            key=key,
            **{"class": record_class},
            quantity=quantity,
            axes=axes,
            kind=kind,
            interp=interp,
            segments=segments,
            provenance=AuthoredProvenance(tool=tool, author=author, date=date),
            evidence=evidence,
            content_hash=_content_hash(package, key, row),
        )
        _log.debug("constructed authored waveform/mask record %s/%s", package, key)
        return record

    # frob:doc docs/modules/py-magnetite.md#magnetite-waveform
    @classmethod
    def construct_measured(
        cls,
        *,
        package: str,
        key: str,
        record_class: RecordClass,
        quantity: str,
        axes: Axes,
        kind: Kind,
        interp: Interp,
        segments: tuple[Segment, ...],
        instrument: str,
        date: str,
        operator: str,
        evidence: WaveformEvidence,
    ) -> WaveformMaskRecord:
        """Requires `instrument`/`date`/`operator` as REQUIRED keyword
        arguments (no defaults anywhere in this signature) -- a
        `measured` record is unconstructible without them, by the
        Python call signature itself, not a runtime posture check."""
        row = {
            "quantity": quantity,
            "axes": axes.model_dump(),
            "kind": kind,
            "interp": interp,
            "segments": tuple(s.model_dump() for s in segments),
        }
        record = cls(
            package=package,
            key=key,
            **{"class": record_class},
            quantity=quantity,
            axes=axes,
            kind=kind,
            interp=interp,
            segments=segments,
            provenance=MeasuredProvenance(
                instrument=instrument, date=date, operator=operator
            ),
            evidence=evidence,
            content_hash=_content_hash(package, key, row),
        )
        _log.debug("constructed measured waveform/mask record %s/%s", package, key)
        return record

    # frob:doc docs/modules/py-magnetite.md#magnetite-waveform
    @classmethod
    def construct_model_derived(
        cls,
        *,
        package: str,
        key: str,
        record_class: RecordClass,
        quantity: str,
        axes: Axes,
        kind: Kind,
        interp: Interp,
        segments: tuple[Segment, ...],
        calc_sheet_hash: str,
        evidence: WaveformEvidence,
    ) -> Result[WaveformMaskRecord, MagnetiteError]:
        """Requires `calc_sheet_hash` (a resolving calc-sheet digest
        that only the pipeline holds) as a REQUIRED keyword argument;
        additionally refuses a structurally malformed hash outright
        (empty, or missing the `<algo>:` tag) so a bare placeholder
        string can never pass even the shape check. Real RESOLUTION
        against an actual discharged calc sheet happens later, at
        `resolve_mask_ref` time -- this constructor enforces only the
        "there is a hash at all, and it looks like one" half."""
        provenance = ModelDerivedProvenance(calc_sheet_hash=calc_sheet_hash)
        if not provenance._hash_well_formed():
            _log.warning(
                "refused model_derived construction for %s/%s: "
                "calc_sheet_hash %r is not a resolving hash",
                package,
                key,
                calc_sheet_hash,
            )
            return Err(
                MagnetiteError(
                    kind="model_derived_unresolvable_hash",
                    message=(
                        f"{package}/{key}: model_derived posture requires a "
                        f"resolving calc-sheet hash (<algo>:<digest>), got "
                        f"{calc_sheet_hash!r}"
                    ),
                )
            )
        row = {
            "quantity": quantity,
            "axes": axes.model_dump(),
            "kind": kind,
            "interp": interp,
            "segments": tuple(s.model_dump() for s in segments),
        }
        record = cls(
            package=package,
            key=key,
            **{"class": record_class},
            quantity=quantity,
            axes=axes,
            kind=kind,
            interp=interp,
            segments=segments,
            provenance=provenance,
            evidence=evidence,
            content_hash=_content_hash(package, key, row),
        )
        _log.debug("constructed model_derived waveform/mask record %s/%s", package, key)
        return Ok(record)


def _parse_segment(row: dict[str, object]) -> Segment:
    return Segment(t=float(row["t"]), v=float(row["v"]))


def _parse_provenance(
    package: str, key: str, row: dict[str, object]
) -> Result[Provenance, MagnetiteError]:
    posture = row.get("posture")
    if posture == "authored":
        try:
            return Ok(
                AuthoredProvenance(
                    tool=str(row["tool"]),
                    author=str(row["author"]),
                    date=str(row["date"]),
                )
            )
        except KeyError as exc:
            return Err(
                MagnetiteError(
                    kind="malformed_provenance",
                    message=f"{package}/{key}: authored provenance missing {exc}",
                )
            )
    if posture == "measured":
        try:
            return Ok(
                MeasuredProvenance(
                    instrument=str(row["instrument"]),
                    date=str(row["date"]),
                    operator=str(row["operator"]),
                )
            )
        except KeyError as exc:
            return Err(
                MagnetiteError(
                    kind="malformed_provenance",
                    message=(
                        f"{package}/{key}: measured provenance missing "
                        f"instrument-provenance field {exc} (D257-style "
                        "no-constructor-without-a-citation)"
                    ),
                )
            )
    if posture == "model_derived":
        calc_sheet_hash = str(row.get("calc_sheet_hash", ""))
        provenance = ModelDerivedProvenance(calc_sheet_hash=calc_sheet_hash)
        if not provenance._hash_well_formed():
            return Err(
                MagnetiteError(
                    kind="model_derived_unresolvable_hash",
                    message=(
                        f"{package}/{key}: model_derived posture requires a "
                        f"resolving calc-sheet hash, got {calc_sheet_hash!r}"
                    ),
                )
            )
        return Ok(provenance)
    return Err(
        MagnetiteError(
            kind="missing_posture",
            message=(
                f"{package}/{key}: no recognized `posture` (a waveform/mask "
                "record is unrepresentable without one -- D263.1)"
            ),
        )
    )


# frob:doc docs/modules/py-magnetite.md#magnetite-waveform
def load_waveform_mask_records(
    path: str, package: str
) -> Result[tuple[WaveformMaskRecord, ...], MagnetiteError]:
    """Parse every `[[waveform]]` row in a `records/*.toml` file (D263.1,
    the ordinary magnetite record-class mechanism -- no new plugin
    kind). A row missing `posture`, or naming an unrecognized one, is a
    loud per-row error, never a partial load."""
    file_path = Path(path)
    if not file_path.is_file():
        return Err(
            MagnetiteError(kind="not_found", message=f"no record file at {file_path}")
        )
    try:
        with file_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        return Err(MagnetiteError(kind="malformed_toml", message=str(exc)))

    records: list[WaveformMaskRecord] = []
    for row in data.get("waveform", ()):
        if not isinstance(row, dict) or "key" not in row:
            return Err(
                MagnetiteError(
                    kind="missing_key",
                    message=f"{file_path}: a waveform/mask row has no 'key'",
                )
            )
        key = str(row["key"])
        record_class = row.get("class")
        if record_class not in ("waveform", "mask"):
            return Err(
                MagnetiteError(
                    kind="malformed_class",
                    message=(
                        f"{file_path}: {key}: class must be 'waveform' or "
                        f"'mask', got {record_class!r}"
                    ),
                )
            )
        axes_row = row.get("axes")
        if not isinstance(axes_row, dict):
            return Err(
                MagnetiteError(
                    kind="missing_axes",
                    message=f"{file_path}: {key} has no 'axes' table",
                )
            )
        provenance_row = row.get("provenance")
        if not isinstance(provenance_row, dict):
            return Err(
                MagnetiteError(
                    kind="missing_provenance",
                    message=f"{file_path}: {key} has no 'provenance' table",
                )
            )
        evidence_row = row.get("evidence")
        if not isinstance(evidence_row, dict):
            return Err(
                MagnetiteError(
                    kind="missing_evidence",
                    message=f"{file_path}: {key} has no 'evidence' table",
                )
            )
        provenance = _parse_provenance(package, key, provenance_row)
        if provenance.is_err:
            return Err(provenance.danger_err)
        try:
            segments = tuple(_parse_segment(s) for s in row["segments"])
            record_row = {
                "quantity": str(row["quantity"]),
                "axes": axes_row,
                "kind": str(row["kind"]),
                "interp": str(row["interp"]),
                "segments": tuple(s.model_dump() for s in segments),
            }
            record = WaveformMaskRecord(
                package=package,
                key=key,
                **{"class": record_class},
                quantity=str(row["quantity"]),
                axes=Axes(t=str(axes_row["t"]), value=str(axes_row["value"])),
                kind=row["kind"],
                interp=row["interp"],
                segments=segments,
                provenance=provenance.danger_ok,
                evidence=WaveformEvidence(
                    method=str(evidence_row["method"]),
                    trust_tier=str(evidence_row["trust_tier"]),
                    reference=str(evidence_row["reference"]),
                ),
                content_hash=_content_hash(package, key, record_row),
            )
        except (KeyError, ValueError) as exc:
            return Err(
                MagnetiteError(
                    kind="malformed_row",
                    message=f"{file_path}: {key}: {exc}",
                )
            )
        records.append(record)
    _log.debug(
        "loaded %d waveform/mask record(s) from %s (package=%s)",
        len(records),
        file_path,
        package,
    )
    return Ok(tuple(records))


def _strip_call_args(ref: str) -> str:
    """`monotonic_rise(5ms)` -> `monotonic_rise`: bare-name lookup only
    (WO-151 out-of-scope list: `from_fn` parameterized mask families
    are CUT, cycle-37 recon sec. 4a -- the call-argument text is not
    interpreted, only stripped for the lookup key)."""
    paren = ref.find("(")
    return ref[:paren] if paren != -1 else ref


# frob:doc docs/modules/py-magnetite.md#magnetite-waveform
def resolve_mask_ref(
    ref: str,
    records_dirs: tuple[str, ...],
    package: str = "",
    calc_sheet_digests: frozenset[str] = frozenset(),
) -> Result[WaveformMaskRecord, MagnetiteError]:
    """Hash-pinned lookup by name for a `mask=`/waveform-profile ref
    (WO-151 deliverable 3): scans every `records/*.toml` file under
    `records_dirs` for a `[[waveform]]` row whose `key` matches the
    ref's bare name (call-argument text stripped, see
    `_strip_call_args`).

    A `model_derived`-posture match additionally resolves its
    `calc_sheet_hash` against `calc_sheet_digests` (the SAME package's
    real, discharged calc-sheet digests) -- mirroring
    `harness_pack.check_expectation_provenance`'s `calc_sheet` ref
    check exactly; an unresolving hash refuses here, not silently.

    NOTE (escalated in this WO's close-out): the full quantity/axes
    dimension check against the citing claim's subject (spec sec. 5b)
    is regolith-qty's job in the compiler core (Rust); this Python
    registry surface resolves the NAME and the hash, and returns the
    record's own declared `quantity`/`axes` for the caller (the
    compiler core, `regolith.compiler`) to dimension-check -- this
    function does not perform that check itself, since only
    `regolith.compiler` may import `regolith._core` (AD-4)."""
    name = _strip_call_args(ref)
    for records_dir in records_dirs:
        dir_path = Path(records_dir)
        if not dir_path.is_dir():
            continue
        for toml_file in sorted(dir_path.glob("*.toml")):
            loaded = load_waveform_mask_records(str(toml_file), package)
            if loaded.is_err:
                _log.warning(
                    "resolve_mask_ref: %s failed to load (%s), skipping",
                    toml_file,
                    loaded.danger_err.message,
                )
                continue
            for record in loaded.danger_ok:
                if record.key != name:
                    continue
                if isinstance(record.provenance, ModelDerivedProvenance):  # noqa: SIM102
                    if record.provenance.calc_sheet_hash not in calc_sheet_digests:
                        _log.error(
                            "resolve_mask_ref: %s/%s (model_derived) cites "
                            "calc_sheet_hash %r which does not resolve to a "
                            "real calc sheet in this package",
                            record.package,
                            record.key,
                            record.provenance.calc_sheet_hash,
                        )
                        return Err(
                            MagnetiteError(
                                kind="model_derived_unresolvable_hash",
                                message=(
                                    f"mask ref {ref!r} resolves to "
                                    f"{record.package}/{record.key}, whose "
                                    "model_derived calc_sheet_hash does not "
                                    "resolve to a real calc sheet"
                                ),
                            )
                        )
                _log.debug(
                    "resolve_mask_ref: %r -> %s/%s", ref, record.package, record.key
                )
                return Ok(record)
    _log.warning("resolve_mask_ref: %r did not resolve under %s", ref, records_dirs)
    return Err(
        MagnetiteError(
            kind="not_found",
            message=f"mask ref {ref!r} resolves to nothing under {records_dirs}",
        )
    )
