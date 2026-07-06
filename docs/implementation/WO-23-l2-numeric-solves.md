# WO-23: L2 numeric solves (statics, stiffness, sketch DOF)

Status: done (cycle 18)

> Close-out notes: the three solvers live in `regolith-ir::solve`
> (feature `solve`, default-on; faer 0.24 no-default-features,
> single-threaded for determinism); E0440 SINGULAR_SYSTEM + E0441
> SKETCH_RESIDUAL_INCONSISTENT added; the L2 stiffness tier
> discharges fat-margin claims in `lower.discharge` end-to-end from
> source, and the statics feed lands computed reactions in envelope
> obligations' `given.loads` (INV-1 hash-change proven). TRACKED
> CUTS, blocked upstream (not this WO's scope): the Walk ->
> SketchClosure bridge waits on WO-11's typed constraint surface
> (corpus walks carry lengths as unbound text); real `connect` ->
> `Mating` lowering waits on WO-19's opaque-island residue, so the
> statics feed is proven at IR level by construction -- the
> `connect` -> `Mating` half is now WO-29 deliverable 5 (lowering
> output surface). Arcs/
> non-cardinal angles in sketch closure deferred (documented).
> Stiffness at L2 never emits Violated (lumped network is a
> conservative lower bound). NOTE for CI: baseline `deny.toml` has
> pre-existing failures under modern cargo-deny; this WO added one
> documented ignore (paste, RUSTSEC-2024-0436) and zero new errors.
Depends: WO-12 (contract IR), WO-11 (profile/walk ledger half)
Language: Rust (`regolith-ir` behind a `solve` cargo feature, `faer`
for linear algebra) -- AD-1: "deterministic compiler work, not
harness physics"
Spec: hematite/05 L2; hematite/06 Phase D item 12 + "Later" (sketch
solver, OPEN-5 residue; language surface closed D65); regolith/13
INV-15 (ledger conservation), INV-10

## Goal

The three deterministic numeric solves the compiler owns: rigid-body
statics, the stiffness network, and exact sketch constraint closure
(the DOF ledger's missing residual half). These are compiler passes
with bit-reproducible outputs, not harness models.

## Deliverables

- `regolith-ir::solve` module (feature-gated `solve`, on by default
  in the wheel): `faer` dependency scoped here only.
- Rigid statics: reaction/interface-load solve over the assembly
  connection graph (matings -> constraint directions), feeding
  interface-envelope `given.loads` so promise obligations carry REAL
  computed envelopes instead of declared-only ones.
- Stiffness network: the lumped spring network solve behind
  `mech.stiffness(...)` claims at L2 (joint/member stiffness from
  registry-record data), discharging fat-margin stiffness claims
  statically (the `lower.discharge` toy tier grows real teeth).
- Sketch solver: exact residual closure for profile walks --
  the existing conservative DOF ledger (WO-11) keeps soundness; this
  adds the numeric solve that flags an EXACTLY-constrained-but-
  inconsistent sketch (residual nonzero) and resolves `free` sketch
  parameters with Cause-typed resolutions (INV-21 API, existing).
- Determinism per AD-6: fixed assembly/summation order (source
  order), no HashMap iteration, outward-rounded interval outputs;
  results land in the 3-OS golden hash diff.
- Singular/ill-conditioned systems are DIAGNOSTICS (underconstrained/
  overconstrained families already exist for the ledger; add the
  numeric-rank case), never a panic, never NaN in outputs (the
  canonical encoder rejects non-finite -- keep it that way by
  construction).

## Acceptance

- A bolted bracket fixture: computed reaction loads match the
  hand-calculated known answer within outward-rounding; the interface
  envelope obligation carries the computed loads.
- A stiffness-network fixture discharges a `>= kN/mm` claim
  statically; thinning the margin below the model eps defers it to
  the harness (indeterminate at L2, not violated).
- A deliberately inconsistent exactly-constrained sketch yields the
  new diagnostic; the conservative ledger fixtures stay green.
- 3-OS determinism job green with the new outputs folded in.
- `make check` green; INV-15's cross-boundary fixture un-xfailed if
  this WO completes the populated-walk feed it was blocked on.
