# WO-51: the FeatureProgram producer (profile/Walk promotion + cavity->flow_paths)

Status: todo
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
