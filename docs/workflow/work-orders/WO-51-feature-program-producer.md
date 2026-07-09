# WO-51: the FeatureProgram producer (profile/Walk promotion + cavity->flow_paths)

Status: done (cycle 28, per D150/D151/D152 -- see the close-out
section at the end of this file; the one WO-22-side residue --
sheet_bracket's own STEP realization, which needs the close-edge
closure-solve increment and a sheet-gauge thickness source -- is
recorded on WO-22's Status line, not silently dropped)
Depends: WO-42 (staged build loop + realized-input channel, done),
WO-29/WO-19 (lowering output surface, done), WO-11 (Walk grammar +
sketch ledger, done -- this WO promotes its surface), WO-22 engine
half (done -- the realizer that consumes the program). Closes
WO-22's end-to-end half; flip both Status lines in the same change.
Language: Rust (`regolith-ir` feature_program, `regolith-lower`
emission pass) + Python (`staged_build` wiring) + fixtures.
Spec: design-log 2026-07-08-cycle-27 D143;
docs/spec/hematite/07-open-questions.md sec. 2a (the scheduled
deferral this executes); the scope note in
`crates/regolith-ir/src/feature_program.rs` (READ FIRST -- it names
exactly what is opaque); docs/spec/hematite/02-language.md secs. 5-6
(profiles/walks, `.cavity`); docs/spec/hematite/05-lowering.md;
toolchain/22-mech-geometry-realizer.md (the consumer contract);
toolchain/23-lowering-output-surface.md (AD-22 promotion rules).

## Goal

`regolith-lower` emits `FeatureProgram`s (including `flow_paths`)
from real lowered `.hema` source, ending the hand-authored-fixture
era: the profile/Walk surface promotes into typed IR
(`Walk -> SketchClosure`), declared `flow_paths` (D130) lower
directly, and `.cavity(inlet=...)`-derived wetted paths lower over
the v1 feature-op set. `staged_build`'s `feature_programs` input
becomes pipeline-produced (caller-supplied stays as an override for
tests).

## Deliverables

1. Walk promotion: the `Walk -> SketchClosure` conversion the
   feature_program.rs scope note defers -- profile walks (entities,
   branch pins, constraints ledger refs) become the typed sketch
   payload `FeatureProgram` ops reference; snapshot tests over the
   corpus profiles.
2. Emission pass in `regolith-lower` (a `lower.programs` pass after
   `lower.contracts`): per part, stages/setups/ops project into the
   `FeatureProgram` op set; unsupported ops are a NAMED diagnostic
   (never silent truncation).
3. `flow_paths`: declared flow_paths (D130) lower verbatim;
   `.cavity(inlet=...)` derives wetted-path segments over the v1
   feature-op set; a cavity the op set cannot express is the
   escalation diagnostic hematite/07 sec. 2a names (the syntax-gap
   criterion is this WO's escalation path, not a reopen).
4. `staged_build` consumes the emitted programs through the
   existing input channel; the fluorite extraction seam (WO-32)
   reads realizer output over REAL programs end to end -- un-todo
   the fluorite/03 status note in the same change.
5. Corpus: pillow_block + regen_chamber (cavity) exercise the pass;
   goldens updated by regeneration only.

## Acceptance criteria

- Every corpus `.hema` part either yields a `FeatureProgram` or a
  named unsupported-op diagnostic; zero silent gaps.
- The regen_chamber cavity produces flow_paths consumed by the mech
  realizer AND the fluorite `Pipe(from=...)` extraction over the
  staged loop -- the full declarative-file-to-geometry-to-hydraulics
  chain with no hand-authored program.
- hematite/07 sec. 2a entry flips to done-with-citation; WO-22
  Status flips; `make check` green.

## Non-goals

- New feature ops or walk grammar (surface is closed; gaps
  escalate).
- Realizer changes beyond consuming real programs (WO-22's engine
  stands).

## Cycle-28 escalation resolution (BINDING; supersedes conflicting lines above)

The first dispatch escalated three blockers; design-log cycle-28
D150/D151 resolve them:

1. Deliverable 1 (Walk -> SketchClosure) proceeds via the D150
   walk-step name labels (`a: line right`). The grammar increment
   (walk-block only: `walk-step = [ ident ":" ] rest-of-line`), the
   grammar.ebnf + hematite/02 walk-section updates, the track-header
   version bump, the constructive diagnostic for constraints naming
   an unbound segment, and the corpus label-promotion sweep (every
   fixture whose `constraints:` reference segment names) all ride
   THIS WO. The "surface is closed" non-goal is amended by D150 for
   exactly this production; everything else in it stands.
2. Deliverable 3 (cavity -> flow_paths) derives from the feature-op
   chain the cavity query touches, per D151: op-graph walk from
   inlet-face op to outlet-face op; per-segment fields each from a
   declared source fact; any underivable field is emitted honestly
   indeterminate (AD-25 GeomExtract, verbatim) -- never guessed.
3. The cavity exemplars are `examples/systems/regen_engine/injector.hema`
   and `examples/systems/dune_buggy/exhaust_intake.hema` (plus the
   xdomain pair) -- NOT regen_chamber.hema, which uses no cavity
   query; the WO body's mention of it is corrected by this note.

## Second-dispatch progress + escalations (cycle 28)

Landed (this dispatch, `make check` green):

1. **Deliverable 1 DONE.** D150 walk-step labels are syntax
   (`regolith-syntax::walk`: `WalkSegment.label`, `close_label`,
   `via_axis`, recorded `up`/`down` cardinals; no parser change --
   a `WalkStep` was already a one-line leaf). The constructive
   unbound-segment diagnostic is **E0442** (`regolith-sem`
   `profile::check_label_bindings`, wired into `lower.checks`; heads
   checked: `length`/`radius`/`angle` -- `diameter` excluded, see
   escalation 3). `Walk -> SketchClosure` lives beside the WO-23
   solver (`regolith-ir` `solve::sketch::sketch_closure_from_walk`):
   straight cardinal walks promote (pins, frees, recorded
   `close_edge`); arcs, `close via axis`, non-cardinal lines,
   expression constraints, mixed units, double pins each return a
   NAMED `WalkPromotion::Unsupported` reason. Corpus promotion
   outcomes are insta-snapshot-tested. `close_walk` honestly refuses
   a close-edge problem (solving the implicit return edge is the
   recorded next increment). grammar.ebnf + hematite/02 sec. 5
   updated, header 0.14 -> 0.15. Corpus sweep done (14 fixtures +
   negative 31/39 labeled); negative fixture 51 (E0442) added (renumbered from 48 at cycle-28 integration: WO-47 landed the calcite block as 48-50).

Escalations (evidence named; nothing invented):

1. **D151's exemplars do not contain the construct.** Zero `.cavity(`
   call sites exist anywhere in the corpus, INCLUDING
   `examples/systems/regen_engine/injector.hema`,
   `examples/systems/dune_buggy/exhaust_intake.hema`, and the xdomain
   pair ("cavity" appears only as ordinary binding names/comments).
   D151 both asserts these fixtures "DO use `.cavity(...)`" and
   forbids bending fixtures to the WO -- deliverable 3's cavity half
   cannot be exercised on the corpus until a fixture legitimately
   grows a cavity query (or a new exemplar is authored by decision).
2. **"Declared flow_paths lower verbatim" has no source surface.**
   D130's declared `flow_paths` are fields of the REALIZER-INPUT
   schema (`python/regolith/realizer/mech/schema.py`), not hematite
   syntax; no `.hema` production declares flow_paths, so there is
   nothing for `regolith-lower` to lower "verbatim". Needs a decision:
   either a hematite surface for declared flow paths or a rewording
   of deliverable 3 to cavity-derivation only.
3. **`throat.diameter` / `exit.diameter`** (regen_engine
   chamber.hema) spell a segment-metric head on revolve JUNCTION
   loci no syntax binds (the throat is the b/c arc junction, not a
   segment). E0442 therefore checks `length`/`radius`/`angle` only;
   the `diameter`-on-a-junction spelling is a latent corpus/spec
   inconsistency for the next cycle to rule on.

The escalations above were resolved by D152 (cycle 28); the third
dispatch completed the WO:

2. **Deliverable 2 DONE.** `lower.programs` runs after
   `lower.contracts` in both pipelines; `FeatureProgram` (now with
   the unconditional `regolith-ir::sketch` types, schemars
   single-sourced) carries `sketches` (promotion outcome per
   referenced profile) and cavity-derived `flow_paths`;
   **SCHEMA_VERSION 15 -> 16** (the WO-29 precedent: a
   `BuildPayload` field changed shape); `make schema` regenerated
   `python/regolith/_schema`. Ops outside the v1 set are the NAMED
   **E0443** warning -- never silent truncation.
3. **Deliverable 3 DONE per D152.** `.cavity(inlet=..., outlet=...)`
   resolves statically to the feature-op chain between the named
   port faces; per-segment fields each from a declared source fact
   (diameter as minimum section, depth as length, elevation 0 with
   cited D151 provenance, roughness from the stage's process
   capability record -- cross-checked against the extract seam's one
   ROUGHNESS_TABLE) or honestly indeterminate (AD-25). Misuse:
   **E0444** (unresolved port), **E0445** (inexpressible chain --
   hematite/07 sec. 2a's escalation diagnostic, live). "Declared
   flow_paths" was struck by D152 (dead text). The cavity-attribute
   claims (`volume`, `min_section`) lower to ordinary obligations
   that stay honestly indeterminate pending realizer-fact discharge
   (the AD-25 loop's job; the geometry now flows).
4. **Deliverable 4 DONE.** `staged_build` promotes emitted programs
   into the realizer contract (`orchestrator/programs.py`) keyed by
   the D130 `<stage>.wetted` selector subjects, caller-supplied
   programs kept as the override channel; a program the emitted IR
   cannot honestly complete is skipped with a named reason and stays
   pending. fluorite/03's status note un-todone in the same change.
5. **Deliverable 5 DONE.** New D152 exemplar
   `examples/tracks/hematite/coolant_gallery.hema` (authored new --
   the corpus never had a cavity call site); the full chain
   (declarative `.hema` -> emitted program -> realized STEP ->
   fluorite `Pipe(from=milled.wetted)` extraction to concrete
   scalars over the staged loop, NO hand-authored program) is the
   `test_staged_build_realizes_the_exemplar_with_no_caller_program`
   acceptance test. pillow_block/regen_chamber exercise the pass
   (E0443 warnings + non-promotable-walk reasons recorded in their
   programs); goldens regenerated, never hand-edited. Negative
   fixtures 51 (E0442), 52 (E0444), 53 (E0445) -- numbering checked
   after WO-47's calcite block took 48-50.
