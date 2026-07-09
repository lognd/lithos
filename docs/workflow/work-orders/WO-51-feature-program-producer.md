# WO-51: the FeatureProgram producer (profile/Walk promotion + cavity->flow_paths)

Status: in-progress (deliverable 1 DONE -- D150 labels + E0442 +
Walk -> SketchClosure + corpus sweep + grammar/spec updates, cycle
28; deliverables 2/4/5 not started; deliverable 3 re-blocked: see
"Second-dispatch progress + escalations" at the end of this file)
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

Remaining: deliverable 2 (the `lower.programs` emission pass +
FeatureProgram sketch payload + SCHEMA_VERSION bump + unsupported-op
diagnostics), deliverable 4 (`staged_build` pipeline-produced
programs + fluorite/03 un-todo), deliverable 5 goldens, WO-22 flip,
hematite/07 sec. 2a flip -- all gated behind the escalations above
only where flow_paths are concerned; deliverables 2/4 are
dispatchable as-is on top of deliverable 1's promotion.
