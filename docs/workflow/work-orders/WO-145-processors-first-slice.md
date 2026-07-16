# WO-145 -- processors first slice: structured citations + ti.mcu MSP430FR5 (D257)

Status: open (rides after the D256 hash window, same serialization
  law as every lithos code WO this cycle -- no other lithos code
  work lands until D256 merges; this WO owns no schema bump itself)
Language: records (TOML) + Python (pydantic v2 citation models +
  a health-check strengthening in `tools/stdlib/organization.py`).
Spec: D257 (`docs/workflow/design-log/2026-07-16-cycle-37.md`: the
  DigiKey/manufacturer-datasheet split -- DigiKey is discovery-only
  at runtime, NEVER committed; all committed parametric data is
  transcribed from manufacturer datasheets under per-value
  citations); D257 ruling 1 (processor catalogs are vendor-named
  record packages beside `ti.logic`/`st.mcu`/`microchip.cpld` -- the
  ordinary magnetite mechanism, NEVER a new plugin kind, NEVER the
  AD-26 seam, which is behavior, not data); D257 ruling 2
  (citations become STRUCTURED: `Citation`/`Cited[T]` decomposing the
  prose `evidence.reference` into `document`/`revision`/`date`/
  `page`/`table`/`url` fields, the per-field-evidence precedent
  already established at `stdlib/std.power/records/
  transformer_dry_type.toml:75`'s `xr_ratio_evidence`); D257 ruling 3
  (datasheet ingestion is HUMAN-IN-THE-LOOP transcription with a
  machine assist, confirmed against the RENDERED page image -- the
  WO-134B merged-cell lesson, independently reproduced by this
  recon's own prototype misreading a wrapped "VCC+0.3" bound; NO
  automated corpus factory); D257 ruling 4 (first slice: citation
  models + health tightening, then ONE package `ti.mcu`, ONE family
  MSP430FR5 (TI SLASE54D Rev. D), uniform core only, ~30-60 cited
  values per part, tier=community); charter 39 secs. 1-2 (naming
  taxonomy: vendor content never under `std.`; ordinary magnetite
  package mechanism) and sec. 5.4 (the citation-presence health
  check this WO tightens); AD-26 (`00-architecture.md:768`, the ONE
  plugin seam -- explicitly NOT used here, see Out of scope);
  `scratch_recon_digikey_processors.md` secs. 2-3 (the citation model
  design and the SLASE54D parameter schema this WO elaborates, not
  re-derives).

## Goal

A processor parametric value cannot exist in this repo without a
machine-checkable citation to a specific manufacturer datasheet page
and table -- proven by landing one real family (MSP430FR5, TI
SLASE54D Rev. D) whose every value cites page + table, human-
confirmed against the rendered PDF page.

## Deliverables

1. `Citation` / `Cited[T]` / `CitedInterval` / `MeasCondition`
   pydantic v2 models (`ConfigDict(frozen=True)`), per the recon's
   sec. 2.1 sketch: `Citation` carries `manufacturer`, `document`,
   `revision`, `date`, `page`, `table`, `url` (structured fields
   replacing the prose `reference` string ONLY -- `method` and
   `trust_tier` stay exactly where they are today at the evidence-
   table level, unchanged semantics); `Cited[T]` pairs a value with
   its `Citation` and a `confirmed: bool` human-review flag;
   `CitedInterval` maps a datasheet MIN/TYP/MAX with its `Citation`
   and a `MeasCondition` (the Vcc/temp/config corner the spec holds
   at) onto `regolith-qty`'s `Interval { lo, hi, unit }` shape at
   lowering time. No public constructor accepts a bare value where a
   `Cited[...]` is required -- an uncited value is unrepresentable
   at the type level, not just a lint violation.
2. Health-check strengthening (`tools/stdlib/organization.py`, charter
   39 sec. 5.4): the citation-presence check tightens from "the
   `evidence.reference` string is non-empty" to "every structured
   citation field is present, `document`+`revision` pair is known" --
   for any record using the new `Cited[...]` shape. Existing prose-
   `reference` records (std.power, ti.logic, st.mcu) are UNCHANGED
   and continue passing the current, looser check -- this WO adds a
   stricter check for the new shape, it does not retrofit or break
   the existing corpus.
3. `stdlib/ti.mcu/` package (new, vendor-named per D257 ruling 1,
   NEVER `std.processors`): `magnetite.toml` manifest + one record
   family for MSP430FR5 (covering FR5994/FR59941/FR5992/FR5964/
   FR5962, sharing one `Citation.document` = SLASE54D since one
   datasheet covers all five parts, per the recon sec. 3.7 ragged
   edge 5), UNIFORM CORE ONLY:
   - identity + package/pinout envelope (package code, pin count,
     body dims, pitch -- NOT the alternate-function pin-mux table,
     which the recon marks RAGGED and out of this slice).
   - absolute maximum ratings (SLASE54D sec. 8.1, p.29): Vcc/Avcc to
     Vss, Vcc/Avcc differential, per-pin voltage (with the symbolic
     "Vcc+0.3" bound stored as a string-or-number union and flagged
     `confirmed=false` until a human resolves it -- the recon's
     ragged-edge 1), diode current, storage temperature, ESD ratings.
   - recommended operating conditions (sec. 8.3, p.30): Vcc range,
     Ta/Tj range, decoupling cap, max MCLK frequency UNDER EACH named
     `MeasCondition` (0/N wait states -- the recon's multi-condition
     example, never collapsed to one number).
   - thermal resistances per package (RthetaJA, RthetaJC, PsiJT).
   - peripheral inventory counts (UART/SPI/I2C/ADC channels+bits/
     timers/DMA/comparators/GPIO) and memory sizes (FRAM/flash/SRAM/
     backup RAM) -- NOT the address map (ragged, deferred).
   ~30-60 cited values total, `tier=community`, every value
   `confirmed=true` after human review against the RENDERED page
   (200 dpi `pdftoppm` render, per D257 ruling 3 -- not the text
   dump).
4. `tools/stdlib/gen_processors.py`: a deterministic generator over a
   committed intermediate (the WO-66/AD-34 pattern), with the offline
   extraction spike (`proto_ingest.py`-style `pdftotext -layout` +
   heuristic front end) feeding it -- output is the reviewed,
   confirmed TOML, never the raw extraction.
5. `tools/stdlib/SOURCES.md` row for `ti.mcu`/SLASE54D: doc number,
   revision, date, license posture, fetch URL, fetch date, generating
   script (the WO-66 sourcing-law convention).

## Out of scope

- DigiKey ANYWHERE in this WO. No API call, no cached response, no
  discovery loader. The discovery loader (D257 sec. 4.2) is a LATER,
  SEPARATE work order; committed API data of any kind is forbidden
  by D257, not merely deferred.
- Electrical/timing matrix tables (sec. 3.4/3.5 of the recon: active-
  mode supply current vs frequency/memory-mode, LPM currents, I/O
  DC characteristics, peripheral timing) -- RAGGED, per-vendor,
  transcribed point-by-point on demand by a LATER slice, not bulk
  here.
- The alternate-function pin-mux table (sec. 3.1) -- per-vendor
  format, no uniform schema, a later slice.
- Any `mcu_pack` firmware-codegen binding (AD-26's `mcu_pack` plugin
  kind) -- that is firmware-family BEHAVIOR, a separate concern from
  this record catalog; not this WO.
- Any second manufacturer package (`st.mcu` widening, `microchip.mcu`,
  `nxp.mcu`, etc.) -- this WO is `ti.mcu`/MSP430FR5 only.
- ST datasheet fetches -- the recon hit a bot-wall on st.com; that is
  a named owner action item, not retried here under any workaround.

## Acceptance

- The `Citation`/`Cited[T]`/`CitedInterval`/`MeasCondition` models
  exist and are unit-tested: constructing a `Cited[float]` without a
  `Citation` is a type/constructor error, not a runtime check --
  `uv run pytest <new test path> -k citation -q` proves it.
- `uv run python -m tools.stdlib.organization --check
  prefix|one_family|citations` passes with zero new issues, AND a
  new assertion (or new check mode) proves the STRICTER rule applies
  to `ti.mcu` records specifically: every `ti.mcu` value's citation
  has `document`, `revision`, `page`, `table` all non-empty.
- `stdlib/ti.mcu/magnetite.toml` + its record file(s) exist, package
  name is `ti.mcu` (never `std.processors`):
  `test -f stdlib/ti.mcu/magnetite.toml && grep -q '^name = "ti.mcu"' stdlib/ti.mcu/magnetite.toml`.
- Every value in the new record family is `confirmed = true`:
  `grep -c 'confirmed = false' stdlib/ti.mcu/records/*.toml` returns
  0 in the shipped file (any `confirmed=false` values from
  auto-extraction were resolved by human review before commit, or
  are absent from the file entirely if unresolved).
- The symbolic "Vcc+0.3" abs-max bound is represented honestly (not
  silently resolved to a bare 4.1 V number without provenance of the
  resolution) -- a test or the record's own structure shows the
  symbolic relationship is preserved or explicitly resolved with its
  own citation.
- `tools/stdlib/SOURCES.md` has a `ti.mcu`/SLASE54D row.
- Existing `std.power`/`ti.logic`/`st.mcu` citation checks are
  UNCHANGED and still pass: `uv run pytest tests/magnetite/test_stdlib.py -q` green, no regression.
- `make check` green.

## Escalation

Any datasheet table that resists the uniform-core schema (a matrix,
a cross-reference, a symbolic bound this WO cannot represent even as
a named ragged edge) is a FINDING recorded in the close-out, not a
silent omission and not an invented resolution -- the recon's own
ragged-edge taxonomy (sec. 3.7) is the reference for what "expected
ragged" looks like; anything beyond that list escalates to the
coordinator.
