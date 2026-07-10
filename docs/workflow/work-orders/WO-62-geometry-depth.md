# WO-62: geometry depth (closure solve, gauge source, coverage ledger, RealizedAssembly)

Status: todo
Depends: WO-22/51 (feature chain, landed), WO-42 (L4 IR machinery,
landed), WO-55/57 (staged evaluator, landed). Owns cycle-31's ONE
SCHEMA_VERSION bump 23->24 (D168 train rule: serialized, one owner).
Language: Rust (`regolith-ir::sketch` closure solve;
`regolith-oblig` RealizedAssembly schema; lowering/value-source
plumbing for the gauge source) + Python (realizer: coverage ledger,
mate solve, STEP assembly export, extraction).
Spec: docs/spec/toolchain/30-geometry-lowering.md (NORMATIVE),
00-architecture.md AD-32 (+ AD-25/30), design-log
2026-07-09-cycle-31 F109/D171; hematite/03 (matings), hematite/05
(L3->L4), WO-22's Status ledger (the residue's exact recorded
sites), regolith/03 (value sources -- the gauge source is one).

## Goal

Machinery realizes: the sheet residue closes (sheet_bracket ->
STEP), the realizer's honesty becomes a drift-checked coverage
ledger, and mate graphs solve to a placed, content-addressed
`RealizedAssembly` with extracted mass/COM and interference
diagnostics -- composing with the cycle-30 optimizer untouched.

## Deliverables

1. **Closure solve** (`regolith-ir::sketch`, the recorded increment
   site): profiles with free/derived segment lengths solve to
   closed loops where uniquely determined (deterministic linear
   chain solve); over/under-constraint is a constructive diagnostic
   naming the residual edge + missing constraint class. Fixtures
   both ways.
2. **Sheet-gauge source**: `process=laser_cut(sheet=<t>)` (+
   sibling sheet processes as the grammar already spells them)
   supplies blank thickness with `cause: process(<proc>.sheet)`
   through the INV-21 API; gauge-less unasserted sheet part = a
   compile diagnostic. sheet_bracket.hema realizes to STEP; golden
   enrolled; WO-22's Status sentence completes -- flip WO-22 to
   done in the same change, citing this WO.
3. **Feature-coverage ledger**: realizer-published data (op class x
   parameter envelope -> realizes | skips(diagnostic id)),
   drift-checked against the interpreter the way schema-check works
   (a supported-op set derived from code must equal the committed
   ledger); every current corpus skip is ledger-listed; docs page
   generated or referenced from the guide.
4. **`RealizedAssembly` schema + kind** (`assembly.realized`; the
   ONE bump 23->24; `make schema`): parts (id, geometry digest,
   transform), dof_states, mass, com, interferences. Store citizen
   on the D96 channel.
5. **Mate solve + export + extraction** (Python realizer):
   deterministic sequential placement over the mating graph
   (source-order spanning; root at identity); loop closure residual
   > interface tolerance = diagnostic citing the loop's mates; STEP
   assembly export through the existing exporter seam; mass/COM
   into the measured entity DB (T2); pairwise interference facts ->
   release-gated realized-fact diagnostics (both part names +
   overlap measure).
6. **Exemplar**: `examples/tracks/hematite/gantry_carriage.hema`
   (or better-fitting name): >= 4 parts, >= 5 mates, one deliberate
   interference variant fixture; plus the COMPOSITION PROOF -- one
   `in [lo, hi] minimize` dimension optimized against an
   assembly-level mass claim through the landed staged evaluator
   (zero engine changes; if the engine needs a change, STOP and
   escalate).
7. **Docs**: charter cross-refs, guide section (assemblies +
   coverage ledger), WO-22 + this WO's Status/ledgers.

## Acceptance criteria

- sheet_bracket realizes; closure diagnostics constructive both
  ways; gauge cause visible in the lockfile.
- Coverage-ledger drift check green and RED when an op is added to
  the interpreter without a ledger row (negative test).
- Assembly exemplar: placed deterministically (byte-identical
  RealizedAssembly + STEP across two runs), mass/COM extracted and
  claimable, interference variant caught release-gated with both
  names, mate-loop overconstraint fixture yields the loop
  diagnostic.
- Composition: the optimize run pins the dim with
  `cause: optimize(...)` and the trace's evaluations show staged
  realization (assembly facts in evidence).
- SCHEMA_VERSION exactly 24; `make schema` green; expected
  all-corpus digest churn only (verify structure/count stability);
  `make install` then `make check` green; Status flipped.
