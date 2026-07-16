"""Structured per-value citations (WO-145, D257 ruling 2).

The house `evidence = { method, trust_tier, reference }` shape
(``regolith.magnetite.records.Evidence``) stays exactly as-is: `method`
and `trust_tier` keep their D250/D58 semantics unchanged. What this
module adds is the ONE justified divergence -- decomposing the prose
`reference` string into structured, machine-checkable fields
(`document`, `revision`, `date`, `page`, `table`, `url`) for records
whose provenance is a specific manufacturer datasheet page and table,
per the `xr_ratio_evidence` precedent already established at
`stdlib/std.power/records/transformer_dry_type.toml:75`.

The type rule (D257 ruling 2): there is no public constructor for a
datasheet value that does not also carry a `Citation` -- `Cited[T]`
and `CitedInterval` both require one at construction time, so
pydantic's own validation makes an uncited value a parse/type error,
never a lint finding a reviewer could miss.
"""

from __future__ import annotations

from pydantic import AnyHttpUrl, BaseModel, ConfigDict


class Citation(BaseModel):
    """One manufacturer datasheet page+table citation for a value.

    `document`/`revision`/`date` identify the exact printing (a
    datasheet is revised; a stale revision citing a value that moved is
    a silent wrong-answer risk). `page`/`table` are the machine-
    checkable heart of D257 ruling 2 -- what lets the stdlib health
    check assert "every field present" instead of "string non-empty".
    `quote` is an optional short verbatim excerpt (<=125 chars) of the
    cited cell, kept for human reviewability without re-fetching.
    """

    model_config = ConfigDict(frozen=True)

    manufacturer: str
    document: str
    revision: str
    date: str
    page: int
    table: str
    url: AnyHttpUrl
    quote: str | None = None


class MeasCondition(BaseModel):
    """The Vcc/temperature/config corner a datasheet spec holds at.

    Datasheets routinely publish the SAME parameter under several named
    configurations (e.g. max MCLK at 0 vs 1 FRAM wait states); collapsing
    those to one number silently picks a corner. Every `CitedInterval`
    carries its own condition so a consuming rule can pick the worst
    corner instead of an arbitrary one.
    """

    model_config = ConfigDict(frozen=True)

    vcc_v: float | None = None
    temp_c: float | None = None
    note: str | None = None


class Cited[T](BaseModel):
    """A datasheet value paired with its `Citation`.

    `confirmed` records the D257 ruling 3 human-in-the-loop gate: an
    auto-extracted value lands `confirmed=False` until a person checks
    it against the RENDERED datasheet page (not the text dump -- the
    WO-134B merged-cell lesson); for `tier=community` records this is
    advisory, but every value this WO ships is confirmed by
    construction (page-image review happened before transcription).
    """

    model_config = ConfigDict(frozen=True)

    value: T
    citation: Citation
    confirmed: bool = False


class CitedInterval(BaseModel):
    """A datasheet MIN/(TYP)/MAX with its citation and measurement corner.

    `lo`/`hi` accept `str` alongside `float` so a SYMBOLIC bound (TI
    SLASE54D's "VCC + 0.3 V" absolute-maximum pin voltage, sec. 8.1
    p.29) is representable honestly rather than silently collapsed to
    its printed worst-case number -- a value this WO's own record file
    demonstrates (see `stdlib/ti.mcu/records/msp430fr5.toml`, the
    `any_pin` row's `hi_symbolic` next to the datasheet's own printed
    `hi_resolved_v = 4.1`, both under the same page-29 citation).
    Maps 1:1 onto `regolith-qty`'s `Interval { lo, hi }` (+ `unit`) at
    lowering time (a later WO); this model only carries the cited
    datum, it does not lower it.
    """

    model_config = ConfigDict(frozen=True)

    lo: float | str | None
    hi: float | str | None
    typ: float | None = None
    unit: str
    citation: Citation
    conditions: MeasCondition = MeasCondition()
    confirmed: bool = False
