"""The binding-requirement bridge (WO-29 deliverable 4, Python half).

The D90 split: the Rust lowering emits RAW capability demands per
`architecture for <Computer>:` resource block (the
``regolith._schema.models.BlockRequirement`` payload field, spelled
comparator + un-resolved value text); THIS module screens. It turns
those raw demands into the numeric
:class:`regolith.realizer.elec.binding.BlockRequirement` the WO-24
allocation search consumes, and derives the
:class:`regolith.realizer.elec.binding.ComponentCandidate` table from
magnetite :class:`regolith.magnetite.records.RecordStore` records.

Scope (honest, not invented around):

- Only "candidate provides at least" demands (``>=`` / ``>``) become
  screening minimums -- that is the exact direction WO-24's
  ``binding._satisfies`` models (candidate amount >= minimum). Ceiling
  and equality demands (``<=`` / ``<`` / ``==`` -- a latency or
  context-switch bound the SUPPLIED part must stay under) are a
  different screen direction the WO-24 engine does not model; they are
  recorded (logged) and skipped here rather than force-fit backwards
  into a ">=" minimum. Extending the engine to a two-directional screen
  is WO-24 territory.
- The capability KEY convention (shared by BOTH sides this module
  builds, so they agree by construction): a NAMED demand
  (``latency <= ...``) keys by its capability name; the block-kind's
  implicit PRIMARY bound (a bare ``>= 20Mops`` on an ``executor``) keys
  by the block ``contract`` kind. A ``component`` record advertises its
  primary throughput under that same contract-kind key in
  ``Record.capabilities``.
- Value parsing is a bounded magnitude read (leading number + optional
  SI prefix), NOT a full unit system: trailing qualifiers (`f32`,
  `sustained`) are ignored for the scalar screen. Unit-DIMENSION
  reconciliation across demand and record is a harness/quantity-core
  concern, out of this bridge's scope.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from typani.result import Err, Ok, Result

from regolith._schema.models import BlockRequirement as RawBlockRequirement
from regolith.errors import MagnetiteError
from regolith.logging_setup import get_logger
from regolith.magnetite.records import Record, RecordKey, RecordStore
from regolith.realizer.elec.binding import BlockRequirement, ComponentCandidate

_log = get_logger(__name__)

#: SI decimal prefixes a promise value may spell (`20Mops`, `40MB/s`).
_SI_PREFIX: Mapping[str, float] = {
    "k": 1e3,
    "M": 1e6,
    "G": 1e9,
    "T": 1e12,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
}

#: The comparators whose demand direction the WO-24 screen models
#: (candidate amount >= minimum).
_MIN_COMPARATORS = frozenset({">=", ">"})


# frob:doc docs/modules/py-realizer.md#elec-bridge
def parse_magnitude(text: str) -> float | None:
    """The leading numeric magnitude of a spelled value, SI-prefix scaled.

    ``"20Mops f32 sustained"`` -> ``20e6``; ``"40MB/s"`` -> ``40e6``;
    ``"2 cycles"`` -> ``2.0``. Returns ``None`` when no leading number is
    present (never invents a magnitude). Only the first SI-prefixed unit
    token adjacent to the number is scaled; trailing qualifier words are
    ignored (documented scope).
    """
    text = text.strip()
    if not text:
        return None
    # Leading number (int or decimal).
    i = 0
    while i < len(text) and (text[i].isdigit() or text[i] == "."):
        i += 1
    if i == 0:
        return None
    try:
        magnitude = float(text[:i])
    except ValueError:
        return None
    # An immediately-adjacent SI prefix (first char of the unit token).
    rest = text[i:]
    if rest and rest[0] in _SI_PREFIX:
        # Only treat it as a prefix when a unit letter follows (so a bare
        # `m` meaning metre/milli ambiguity still scales -- the promise
        # vocabulary here is throughput/bandwidth, prefix-led).
        magnitude *= _SI_PREFIX[rest[0]]
    return magnitude


# frob:doc docs/modules/py-realizer.md#elec-bridge
def screening_requirement(raw: RawBlockRequirement) -> BlockRequirement:
    """One raw payload demand set -> the numeric WO-24 screening model.

    Keeps only the ``>=`` / ``>`` demands (the direction the allocation
    search screens); each becomes a ``min_capabilities`` entry keyed by
    the demand's capability name, or by the block ``contract`` kind for
    the unnamed primary bound. A demand whose value has no parseable
    magnitude is skipped (logged), never guessed.
    """
    minimums: dict[str, float] = {}
    for demand in raw.demands:
        if demand.comparator not in _MIN_COMPARATORS:
            _log.debug(
                "block %s: skipping non-minimum demand %s %s %r "
                "(WO-24 screen models candidate>=minimum only)",
                raw.block,
                demand.capability or raw.contract,
                demand.comparator,
                demand.value,
            )
            continue
        magnitude = parse_magnitude(demand.value)
        if magnitude is None:
            _log.warning(
                "block %s: demand %r has no parseable magnitude; skipped",
                raw.block,
                demand.value,
            )
            continue
        key = demand.capability if demand.capability else raw.contract
        minimums[key] = magnitude
    return BlockRequirement(block=raw.block, min_capabilities=minimums)


# frob:doc docs/modules/py-realizer.md#elec-bridge
def screening_requirements(
    raws: Sequence[RawBlockRequirement],
) -> list[BlockRequirement]:
    """Every raw payload block requirement mapped to its screening model,
    in payload order (AD-6 determinism preserved)."""
    return [screening_requirement(raw) for raw in raws]


# frob:doc docs/modules/py-realizer.md#elec-bridge
def candidate_from_record(record: Record) -> ComponentCandidate:
    """One registry record -> a screening candidate with its capabilities.

    The candidate's capability map is the record's typed
    ``capabilities`` slice (regolith/10 capability table); its
    ``record_key`` is the ``package/key@revision`` address string the
    lockfile pins.
    """
    addr = record.address
    return ComponentCandidate(
        record_key=f"{addr.package}/{addr.key}@{addr.revision}",
        content_hash=record.content_hash,
        capabilities=dict(record.capabilities),
    )


# frob:doc docs/modules/py-realizer.md#elec-bridge
def candidates_by_block(
    store: RecordStore,
    eligible: Mapping[str, Sequence[RecordKey]],
) -> Result[dict[str, list[ComponentCandidate]], MagnetiteError]:
    """The screening candidate table WO-24's ``bind_all`` consumes.

    ``eligible`` maps each block name to the registry addresses eligible
    to fill it (the caller's candidate-enumeration policy -- e.g. every
    ``component``-kind record whose contract matches the block). Each
    address is resolved through ``store`` (hash-pinning re-validated
    there) and projected to a :class:`ComponentCandidate`. A missing or
    malformed record is a :class:`MagnetiteError` VALUE (AD-7), never a
    bare exception.
    """
    table: dict[str, list[ComponentCandidate]] = {}
    for block, keys in eligible.items():
        cands: list[ComponentCandidate] = []
        for key in keys:
            fetched = store.get(key)
            if fetched.is_err:
                return Err(fetched.danger_err)
            cands.append(candidate_from_record(fetched.danger_ok))
        table[block] = cands
        _log.debug("block %s: %d candidate records projected", block, len(cands))
    return Ok(table)
