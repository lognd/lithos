# WO-22: Mech geometry realizer (feature IR -> OCCT -> STEP)

Status: done (engine half landed cycle 18, `b1ac9d8`: FeatureProgram
IR + build123d/OCCT interpreter + STEP export + GeometryRealizableModel
pack; the end-to-end half UNBLOCKED by WO-51 (cycle 28, D150-D152):
`lower.programs` emits real `FeatureProgram`s from `.hema` source and
`staged_build` promotes + realizes them with no caller-supplied
program -- the full declarative-to-STEP-to-hydraulics chain is proven
end to end on `examples/tracks/hematite/coolant_gallery.hema` (the
D152 exemplar; see `tests/orchestrator`'s no-caller-program acceptance
test). The ONE remaining residue of this WO's original acceptance
sentence CLOSES cycle 31 by WO-62 deliverables 1-2 (D171/AD-32):
`crates/regolith-ir/src/solve/sketch.rs`'s `close_walk` now solves the
labeled-close-edge case (a fully-pinned walk closes trivially; a
`free` segment alongside a close edge is the new `E0447`
under-constrained diagnostic) and `regolith-lower::feature_program`
sources a `Blank` op's thickness from the stage's
`process=laser_cut(sheet=<t>)` gauge (`cause: process(<proc>.sheet)`,
INV-21; a gauge-less unasserted sheet blank is `E0448`).
`sheet_bracket.hema`'s `BracketFlat` profile is now fully pinned
(`c.length = 80mm` asserted, mirroring `a`) and its `cut` stage's
`laser_cut(sheet=1.5mm)` supplies the blank thickness: the emitted
program converts (`regolith.orchestrator.programs
.emitted_realizer_programs`, generalized by WO-62 to promote a
cavity-less part too, keyed `<part>.<op_name>`) and realizes to real
STEP with no hand-authored program -- see
`tests/orchestrator/test_orchestrator.py::
test_sheet_bracket_emits_and_realizes_with_no_caller_program`.)
Depends: WO-19 (lowering emits the typed stage/feature structure --
NOT yet true; the emission gap is WO-29's deliverable 3),
WO-20 (the realizer registers as a model pack)
Language: Python (realizer adapter per AD-1: "OCCT via build123d");
Rust `regolith-api`/`regolith-oblig` only if BuildOutput needs a
serialized feature-program payload it does not already expose
Spec: hematite/05 (L3->L4->L6), hematite/06 Phase C items 8-9;
regolith/08 sec. L4; regolith/07 sec. 6 (planning as evidence)

AMENDMENT (cycle 24, D128/AD-25): the realized-geometry record this
WO produces is promoted by WO-42 into the Rust-sourced
`RealizedGeometry` schema (payload kind `geometry.realized`,
content-addressed, put into the WO-30 store) -- the AD-22 promotion
rule applied to the realizer's own record type. STEP stays the
pinned native artifact/evidence; the semantic content downstream
consumers read is the IR. No new realizer capability is implied
here; WO-42 owns the schema and the emission seam.

## Goal

A `.hema` part's stage pipeline realizes to real geometry: feature IR
drives build123d/OCCT, exports STEP, and a post-geometry verification
pass confirms the static topology predictions the compiler made.
This is roadmap Phase C items 8-9 -- the first time the toolchain
produces an artifact a machine shop can open.

## Deliverables

- Feature-program extraction: a serialized, deterministic feature
  program per part from the lowering output (stages, setups, feature
  ops with resolved parameters and Cause-typed resolutions). If
  `BuildOutput` lacks the payload, add it Rust-side (schema-versioned,
  AD-5) -- the Python realizer consumes ONLY the serialized form,
  never the CST (AD-4 coarse boundary).
- `regolith.realizer.mech`: build123d interpreter for the v1 feature
  set actually used by the corpus (`examples/` is the contract:
  sketch profiles, Extrude/Pocket/Fillet/Hole/Bend and the weldment/
  pattern forms the goldens exercise). Registered as a model pack
  (AD-19) discharging `geometry_realizable`-shaped obligations; the
  realized-geometry record (STEP hash, mass properties, topology
  summary) is content-addressed EVIDENCE, cached like any evidence.
- STEP export (AP242 baseline; PMI carry-through tracked as a cut if
  build123d's PMI surface is insufficient -- record, do not fake).
- Post-geometry verification pass: recompute mass/volume/bbox and the
  declared-measures the static core predicted (geom role kit,
  regolith/10 sec. 3a) from the realized solid; disagreement beyond
  model eps is a VIOLATED evidence value on the prediction claim
  (the static prediction was wrong -- loud, exactly the point).
- Determinism: same source -> byte-identical feature program and
  STEP content hash on one platform; cross-platform the HASH of the
  topology summary (not the STEP bytes -- OCCT bytes may differ) is
  the golden (extends the AD-6 determinism job honestly).
- Docs: realizer doc under `docs/spec/toolchain/`; TODO ledger flip.

## Acceptance

- `regolith build` on `examples/tracks/hematite/sheet_bracket.hema` (and the
  corpus parts the v1 feature set covers) emits STEP files a fresh
  OCCT session re-imports cleanly; mass properties match the entity
  DB's predictions within declared eps.
- A deliberately-wrong prediction fixture (predicted volume edited)
  yields violated post-geometry evidence, release-gated.
- Corpus parts OUTSIDE the v1 feature set defer honestly
  (indeterminate `geometry_realizable`, named unsupported op) --
  never a crash, never a silent skip.
- `make check` green; goldens updated in the same change.

## Cuts recorded this cycle

Full design writeup: `docs/spec/toolchain/22-mech-geometry-realizer.md`.

1. **Upstream blocker: no feature-program producer exists.** Checked
   `crates/regolith-api/src/session.rs::BuildPayload` directly: it
   carries only `diagnostics`/`resolutions`/`obligations`/`snapshots`/
   `evidence`/`ledger` -- no stage/feature-op structure at all.
   WO-19's promised "typed stage/feature structure" this WO depends on
   does not exist in this checkout. Adding it is `regolith-lower`
   work, explicitly out of WO-22's own scope (its dispatch reserves
   `regolith-lower`/`regolith-sem` for WO-28's territory). Delivered
   instead: `regolith.realizer.mech.schema.FeatureProgram` as the
   FORWARD CONTRACT a future lowering pass must emit, exercised via
   hand-built fixtures (`tests/realizer/mech/fixtures.py`) rather than
   the real `.hema` corpus end to end. `regolith build` on
   `examples/tracks/hematite/sheet_bracket.hema` therefore does NOT yet produce a
   STEP file -- that half of the acceptance criterion is BLOCKED on
   the missing producer, not cut by choice. Reopen criterion: once a
   WO adds feature-program emission to `BuildPayload`, wire
   `regolith.realizer.mech.pack.register` in as the consumer and this
   acceptance criterion becomes checkable end to end. THAT WO NOW
   EXISTS: WO-29 (lowering output surface, deliverable 3; design
   charter `../../spec/toolchain/23-lowering-output-surface.md`).
2. **Mass verification narrowed to volume + bbox.** No material
   density source exists anywhere in the repo (checked `regolith-qty`,
   `regolith-sem`, and the Python side) -- mass = density * volume
   needs a materials table this WO does not own. The delivered
   `GeometryRealizableModel` compares volume and the three bbox
   extents (both are exact from OCCT, no density needed); the
   deliberately-wrong-prediction acceptance fixture is proven against
   volume (`tests/realizer/mech/test_model.py::
   test_violated_for_deliberately_wrong_prediction`).
3. **Bend is a rigid-rotation approximation** (no bend-allowance /
   K-factor flat-pattern correction) -- real, checkable, never-crashing
   OCCT geometry, but not shop-accurate for a bent flange's true flat
   length. Reopen criterion: a sheet-metal unfold/K-factor model lands
   (a materials + process-pack question, not this WO's).
4. **Fillet edge selection is coarse** (`all`/`top`/`bottom`/
   `vertical` tags only) -- no feature-to-edge naming scheme exists to
   select "the edge feature X produced"; inventing one is a lowering
   design question, escalated rather than guessed at.
5. **PMI does not carry through STEP.** build123d 0.11.x's STEP export
   has no PMI (dimension/GD&T annotation) surface; AP242 geometry-only
   is what ships, per the WO's own "record, do not fake" instruction.
6. **The pack is intentionally NOT registered in
   `[project.entry-points."regolith.model_packs"]`.** That group is
   the WO-20 discovery seam for genuinely external third-party
   distributions; wiring this repo's own in-tree pack through it made
   `regolith-realizer-mech` load in every `default_registry()` call
   repo-wide and broke an unrelated WO-20 test
   (`tests/packs/test_pack_protocol.py::
   test_load_packs_composes_deterministically_sorted_by_name`) --
   confirmed by reproducing the failure before reverting. Until a real
   caller threads `geometry_realizable` obligations through the
   orchestrator, `regolith.realizer.mech.pack.register(registry)` is
   called directly (as the tests do).

Given items 1-4 are honest partial delivery rather than invented
workarounds, `make check` is green on everything actually shipped
(schema, interpreter, model/pack, tests), but the full acceptance
criterion tying this to `regolith build` on the real corpus remains
blocked on WO-19's missing feature-program emission.
