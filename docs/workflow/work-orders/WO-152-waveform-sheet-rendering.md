# WO-152 -- waveform/mask records on sheets: rendering + the AUTHORED badge (D263.1)

Status: open (Depends: WO-151, done)
Language: Python (`python/regolith/backends/` calc-sheet/harness
  rendering through the ONE renderer, AD-7). No Rust, no schema
  changes.
Spec: D263 ruling 1 (WO-152 lands after WO-151's record class);
  charter 41 rule 6 (`docs/spec/toolchain/41-artifact-presentation.md`:
  the ONE renderer, axes/ticks/unit-labeled titles -- "a polyline is
  not a chart"); charter 41 ruling 4 (provenance line on rendered
  sheets -- the AUTHORED badge rides here); D260 ruling 3 (evidence
  honesty: an authored curve must render with an explicit `AUTHORED
  (design intent)` badge, never visually mistakable for a
  model-backed or measured trace); `scratch_recon_signal_design.md`
  sec. 4f (the demo beat: the calc sheet renders the envelope with
  the AUTHORED badge; the bring-up harness view shows the same mask
  beside the tap's expected scalar); WO-151's record schema (the
  interface this WO consumes -- do not re-derive or re-validate
  record content here).

## Goal

A calc sheet or harness view citing a waveform/mask record renders it
as a real chart (axes, ticks, unit-labeled title, per charter 41 rule
6) through the ONE renderer, with an unmistakable `AUTHORED (design
intent)` badge on any `authored`-posture record, and a mask overlay
on the claim's own chart where a claim cites one -- golden-enrolled
so graphite gets the same rendering for free as an SVG artifact.

## Deliverables

1. Calc-sheet rendering of `class = "waveform"` and `class = "mask"`
   records through the existing ONE renderer (the same charter-41-
   governed code path other sheet figures use -- no second renderer,
   AD-7): segment plot for waveforms, envelope band for masks
   (`kind = envelope`/`tolerance`), axes/units from the record's
   declared `axes`/`quantity`.
2. The AUTHORED badge: any record whose provenance `posture ==
   "authored"` renders with an explicit, visually distinct `AUTHORED
   (design intent)` label on the sheet -- never rendered
   indistinguishably from a `measured` or `model_derived` trace.
3. Mask-overlay rendering: where a claim (`stays_within(x,
   mask=<ref>)`) cites a mask record, the claim's own discharge chart
   (the signal/quantity being checked) overlays the mask's envelope
   on the same axes, so the containment is visually verifiable, not
   just numerically asserted.
4. Golden-corpus enrollment: the `monotonic_rise(5ms)` fixture WO-151
   landed gets a real rendered sheet in the golden corpus (calc sheet
   or harness view, whichever the fixture's claim context uses).
5. Harness/bring-up view integration: the same mask record, where
   relevant to a tap's bring-up story, appears beside the tap's
   expected scalar in the existing harness pack rendering
   (`harness_pack.py`'s output family), reusing the same chart
   component, not a duplicate one.

### Post-completion feature audit (D260 ruling 2, required)

End this WO with a recorded design-log pass over adjacent affordances
the landed rendering makes obvious (e.g. whether a claim citing
MULTIPLE masks over the same window wants a combined overlay, whether
the AUTHORED badge convention should extend to any other provenance-
posture-carrying artifact type already in the fleet) -- each argued
in, deferred with a reopen criterion, or argued out. Findings are
logged, not folded into this WO.

## Out of scope

- Any graphite-side code -- WO-G15 renders the SAME records
  independently in the Artifacts hub (read-only view); this WO does
  not touch graphite, though it must not diverge from the rendering
  conventions WO-G15 will need to match (coordinate field/label
  naming, not implementation).
- Any change to WO-151's record schema or validation.
- Editing (authoring) records anywhere in this WO -- rendering only;
  WO-G16 is the editor.
- The charter-37 stimulus-channel amendment, digital vectors, clocks,
  splines -- unchanged out-of-scope carryover from WO-151.

## Acceptance

- `regolith build --release <fixture-citing-monotonic_rise>` produces
  a calc sheet whose rendered output shows an envelope chart with
  axes/units and the record's name: a golden-diff test asserts the
  chart's presence and the AUTHORED badge text.
- A test constructs a claim citing a mask record and asserts the
  claim's own discharge chart shows the mask overlay on the same
  axes (not a separate, disconnected figure).
- Two different posture records (authored vs. a stubbed
  model_derived fixture, if available from WO-151's test fixtures)
  render visibly differently -- a golden-diff or an explicit
  string/attribute assertion proves the AUTHORED badge only appears
  on the authored one.
- The harness/bring-up view renders the same mask beside a tap's
  expected scalar for at least one fixture: `demos/out/
  demo17_physical_bringup_pack/` (or a new equivalent demo) shows
  both in the same view.
- The post-completion feature audit is recorded in the cycle's
  design log.
- `make check` green; golden corpus regenerated in the same change.

## Escalation

If the ONE-renderer discipline (AD-7/charter 41) turns out unable to
express a mask overlay without a second rendering code path, escalate
to the coordinator rather than quietly standing up a parallel
renderer -- charter 41's "one renderer" rule is normative, not a
suggestion this WO may work around.
