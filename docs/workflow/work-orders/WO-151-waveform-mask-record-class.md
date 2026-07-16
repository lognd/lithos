# WO-151 -- waveform/mask record class + spec section + the authored-posture refusal (D263.1-3)

Status: open (Depends: the D256 hash window, merged -- touches
  lithos code)
Language: docs (spec section, regolith/02 sec. 5) + Python (pydantic
  v2 record models, `ConfigDict(frozen=True)`; registry resolution
  for `mask=` refs; the E11xx diagnostic wired into
  `harness_pack.py`).
Spec: D263 (`docs/workflow/design-log/2026-07-16-cycle-37.md`: the
  waveform/mask record class + spec section + refusal diagnostic
  lands FIRST, before any graphite rendering or editing; the record
  home comes before the surface); D260 ruling 3 (evidence honesty --
  an authoring surface can only emit source whose evidence posture is
  AUTHORED; a hand-drawn expected waveform is design intent, trust-
  tier authored/asserted, never dressed as model-backed or measured);
  `docs/spec/regolith/02-quantity-core.md` sec. 5 (masks as
  "piecewise envelopes over a window ... registry objects,
  from_table/from_fn, hash-pinned"; the vocabulary already exists,
  the DATA does not -- `crates/regolith-lower/src/claims/
  comparison.rs:364-372`: "a NAMED mask ... is a hash-pinned reference
  whose text is never rewritten -- its containment semantics stay the
  recorded payload-channel residual"); `docs/spec/cuprite/
  03-behavioral-layer.md` sec. 7 (masks/stimulus profiles as
  piecewise segment sequences; constraint-solving over waveforms
  RETIRED per D46, not reopened here); D257 ruling 2 (structured
  citation shape, coordinated field names); D246 (claims/evidence
  stay source-only forever -- the unreachability doctrine this WO's
  posture refusal follows exactly, "cannot forge a pass"); F155
  (E11xx bring-up diagnostic family, next free slot E1104 --
  `crates/regolith-diag/src/code.rs:491-505` shows E1101-E1103
  assigned; confirm the next free slot at implementation time);
  `python/regolith/backends/harness_pack.py` (the Provenance model
  and the expected-signals resolver this WO's refusal wires into --
  provenance kinds today are exactly `"none"`/`"calc_sheet"`/
  `"claim"`; an authored waveform must never become a fourth,
  silently-trusted kind); `scratch_recon_signal_design.md` secs.
  4a-4d (the record-shape strawman, the posture taxonomy, the units
  discipline, and the deferred-importer design this WO elaborates --
  NOTE the recon's internal WO-146 maps to THIS WO under D263's
  renumbering; this file uses the D263 numbers throughout).

## Goal

A named `mask=`/waveform reference in the corpus (`monotonic_rise`,
`cell_ovp`, etc.) resolves to real, cited, unit-declared data instead
of nothing; the evidence-posture taxonomy (`authored` | `measured` |
`model_derived`) is structurally complete from day one so an
authored (drawn) waveform can NEVER be mistaken by the pipeline for a
verified expectation.

## Deliverables

1. New spec subsection (regolith/02 sec. 5b, or an 11-packages
   record-class entry -- coordinator's placement call) giving the
   waveform/mask record its concrete TOML shape: `class = "waveform"
   | "mask"`, `axes = { t = <unit>, value = <unit> }` (units declared
   ONCE per record, per charter 41's discipline generalized to
   records), `quantity` (dimension check vs. the consuming claim's
   subject), `kind = nominal | envelope | tolerance`, `interp =
   linear | hold` (no splines -- permanent language rule), `segments`,
   `provenance` (posture + tool/author/date), `evidence` (D257
   structured shape). The alignment rule: `t = 0` is the CONSUMING
   WINDOW's start; the anchor event lives in the claim's `during`/
   `within d after e` text, never in the record (one meaning, no
   event vocabulary needed in the record itself).
2. pydantic v2 record models (`ConfigDict(frozen=True)`) implementing
   the schema above, with the posture-construction refusal built by
   UNREACHABILITY, not a runtime check: the `authored`-posture
   constructor is the ONLY one any authoring-surface code path can
   reach; `measured` requires the instrument-provenance fields to
   construct at all (D257's "no constructor without a citation"
   precedent); `model_derived` is UNCONSTRUCTIBLE without a
   resolving calc-sheet/evidence content hash that only the pipeline
   holds -- there is no public constructor path a GUI or hand-editor
   could call to mint one directly.
3. Registry resolution for `mask=`/waveform-profile refs: hash-pinned
   lookup by name, with the units/dimension consistency check (a
   claim's subject quantity/units vs. the cited record's declared
   `quantity`/`axes` disagreeing in dimension is a diagnostic, at the
   point the ref resolves -- one home for the check, regolith-qty's
   job).
4. The E11xx diagnostic `bringup_expectation_authored_posture`
   (exact code = next free E11xx slot, `regolith-diag/src/code.rs`,
   confirm at implementation time -- E1104 if none has landed since
   E1103) wired into `harness_pack.py`'s expected-signal provenance
   resolution: citing an `authored`-posture record where an
   `expected_signals` reference or a `model=` pin requires a verified
   expectation refuses with this diagnostic, naming the ref and its
   posture, and stating the record remains usable as a mask/stimulus
   (`stays_within`, `structure: transient`) -- never silently
   accepted as a verified value. An `explain` entry for the new code
   is included (WO-131 law).
5. Negative tests: constructing an `authored` record with a
   `model_derived`-shaped provenance (no resolving hash) fails at the
   constructor; an `expected_signals` reference naming an authored
   record raises the new diagnostic; a posture-less record is
   unrepresentable (constructor requires the field).
6. One real corpus mask record: `buck_converter.cupr:34`'s
   `monotonic_rise(5ms)` gets real data (a `records/masks.toml` row,
   posture `authored`, tier `community`) so at least one existing
   `mask=` reference in the fleet stops pointing at nothing.

### Post-completion feature audit (D260 ruling 2, required)

End this WO with a recorded design-log pass over what small adjacent
affordances the landed record class now makes obvious (e.g. other
named masks in the corpus this record shape could now backfill,
whether the `kind = tolerance` derivation rule needs a companion
`kind = envelope` convenience constructor) -- each finding argued in,
deferred with a reopen criterion, or argued out explicitly. Do not
fold any of those findings into this WO's own scope; they are logged
for a future WO.

## Out of scope

- Any graphite-side rendering or editing -- WO-G15/WO-G16 (separate
  repo). This WO's deliverable is the record home ONLY.
- The charter 37 stimulus-channel amendment (whether `regolith test`
  scenarios gain a `stimulus:` channel) -- named as a deferred,
  owner-gated cut (D263 ruling 2 census item 5's stimulus-pairs
  entry); not this WO.
- Digital bus/vector patterns, clocks-as-drawings, splines, in-GUI
  claim editing, `from_fn` parameterized mask families -- all CUT
  per the recon's sec. 4a census (several permanently, with named
  reopen criteria where not permanent); this WO does not implement
  any of them.
- The measured-trace importer -- deferred, yoked to charter 40 sec.
  6's live-capture reopen trigger (ruling 5); the `measured` posture
  shape is DESIGNED here (deliverable 2) but no importer code lands.
- Calc-sheet rendering of these records -- WO-152.

## Acceptance

- The new spec subsection exists with the full record shape,
  grep-checkable: `grep -n 'class = "waveform"\|class = "mask"\|posture'
  docs/spec/regolith/02-quantity-core.md` (or wherever placed) shows
  all three.
- `uv run pytest <new test path> -k waveform_record -q` green,
  covering: authored construction succeeds; model_derived construction
  without a resolving hash fails; measured construction without
  instrument fields fails; posture-less construction fails.
- `regolith explain E11xx` (the assigned code) prints a real entry
  naming the ref and its posture, not a placeholder.
- A fixture build citing an authored record as an `expected_signals`
  target shows the new diagnostic: a test asserts the diagnostic code
  and message directly.
- `buck_converter.cupr:34`'s `monotonic_rise(5ms)` resolves to a real
  record: `grep -rn 'monotonic_rise' stdlib/ examples/` shows both
  the reference and a defining record.
- The post-completion feature audit is recorded as a design-log entry
  (not skipped): `grep -n "WO-151" docs/workflow/design-log/*.md`
  (the close-out's own cycle log) shows the audit's findings.
- `make check` green.

## Escalation

If the units/dimension consistency check surfaces an existing corpus
`mask=` reference whose claim subject and mask quantity disagree in a
way that reveals a pre-existing corpus bug (not this WO's own new
code), record it as a FINDING in the close-out rather than silently
fixing unrelated corpus files inside this WO's scope.
