# WO-154 -- sim/timing gate spec deltas + the INV ledger entry text (D264)

Status: open (Depends: none -- docs-only, dispatchable in parallel
  with WO-153; the proof argument's enforcing halves land in
  WO-155/156/157, but the invariant TEXT and the spec deltas are
  fully specifiable now)
Language: docs (`docs/spec/cuprite/04-structural-layer.md`,
  `docs/spec/cuprite/09-hdl-coverage.md`, charter 38's registry
  tables, `docs/spec/regolith/13-invariants.md`).
Spec: D264 (`docs/workflow/design-log/2026-07-16-cycle-37.md`: the
  cuprite sim/timing gate rulings 1-7, this WO covers rulings 3-6);
  `scratch_recon_cuprite_sim_gate.md` sec. 4f (the four named spec
  deltas this WO elaborates verbatim, not re-derives), sec. 4e (the
  INV-TBD text + proof-argument sketch this WO promotes to a real
  ledger entry with a coordinator-assigned number), sec. 1
  (the DFM precedent this gate clones -- two layers: compile-time
  rule family + release-gate claim family with census-golden
  regression); `docs/spec/regolith/13-invariants.md:615` (INV-33
  RESERVED, do not reuse; INV-34 claimed by WO-150 -- this WO's new
  entry takes the NEXT free number after both, confirmed at
  implementation time); `docs/spec/cuprite/04-structural-layer.md`
  sec. 5 (existing `budget kind=timing` vocabulary this WO extends
  with the deferred `setup_slack`/`corners` reopen criterion, NOT
  implemented here); charter 39 sec. 4 (the "pad-check bar" DFM
  quality precedent this gate's proof argument cites by analogy).

## Goal

Every spec surface the cuprite sim/timing gate needs is ratified
BEFORE the enforcing code (WO-155/156) lands: the stimulus-binding
grammar clause, the coverage-matrix flip points, the `signal_table`/
`sim/` registry entries, and the invariant ledger's new entry with a
full proof-argument sketch -- so WO-155/156 implement against a
settled spec, never inventing vocabulary mid-implementation.

## Deliverables

1. `docs/spec/cuprite/04-structural-layer.md` sec. 5 addition: the
   timing-fact vocabulary decision for v1 -- contribution-sum
   budgets only (the grammar the parser already accepts,
   `crates/regolith-syntax/src/parser.rs:257`,
   `crates/regolith-ir/src/budget.rs:46`); `setup_slack(...)` and
   `corners(...)` as NAMED DEFERRALS with an explicit reopen
   criterion ("first design whose corner spread flips a verdict",
   per the recon sec. 4a) -- written as a deferred-item entry in the
   same style as the track's other reopen-criterion deferrals
   (hematite/07 sec. 2a, cuprite/08 sec. 1a, fluorite/04, calcite
   charter sec. 7), so CLAUDE.md's tripwire on deferred questions is
   satisfied by this WO, not left implicit.
2. A stimulus-binding clause on behavioral/extern impls: the
   `by sim(<stimulus-ref>)`-shaped spelling (mirroring the existing
   `by extern(ref, <hdl-dialect>)` clause), argued against the
   Unambiguous-first and Single-Home mantras in the spec change
   itself (why this spelling, why it composes with the existing
   `impl ... by extern(...)` grammar rather than introducing a
   parallel binding mechanism). Lands in
   `docs/spec/cuprite/03-behavioral-layer.md` (the extern/behavioral
   binding home) with a cross-reference from 04-structural-layer.md
   sec. 5's budget vocabulary.
3. `docs/spec/cuprite/09-hdl-coverage.md`: flip the SVA/covergroup
   coverage-matrix rows' "fixture column" annotations to name the
   real dischargeable path once `hdl.sim_assert` becomes
   source-generic (WO-155) -- this WO writes the SPEC TEXT of the
   flip; the actual model change is WO-155's.
4. Charter 38 (emission/registry charter) registry-table additions:
   the `signal_table` payload-kind row (stimulus/expectation vectors,
   digest-addressed, provenance/trust-tier fields per the D260 seam)
   and the `sim/` artifact family row (`sim/<subject>/trace.vcd`,
   `sim/<subject>/sim_report.json`), written in the same table
   format as the existing `harness/` family row precedent
   (charter 40 sec. 3).
5. `docs/spec/regolith/13-invariants.md` new entry (number
   coordinator-assigned; NEXT FREE after INV-34, confirm at
   implementation time -- do not reuse INV-33, RESERVED per D253.4,
   or INV-34, claimed by WO-150). Full text:

   > **INV-<N> (cuprite sim/timing honesty).** Every released
   > cuprite design's simulation and timing verdicts are grounded:
   > (a) a shipped sim artifact always names the exact stimulus
   > digest, source digest, and tool version that produced it; (b)
   > an authored (drawn/typed) stimulus or expectation can never
   > carry, or upgrade to, a model-backed or measured trust tier;
   > (c) a behavioral subject with no sim coverage and a clocked
   > subject with no timing budget appear as named absences on the
   > audit surface, never as silence.

   Proof-argument sketch (written now; the ENFORCING code that
   discharges each leg lands in WO-155 (a, functional sim), WO-156
   (timing's share of a/c), and WO-157 (the totality of c, the
   coverage sweep) -- per house law "new guarantees need a proof
   argument in the SAME change," this WO's entry is marked
   provisional/parked in the ledger until the enforcing WOs land,
   exactly the pattern the ledger already uses for a multi-WO
   guarantee (cf. how INV-24's acceptance-ledger proof accreted
   across WO-98 and its dependents) -- the WO body must say this
   explicitly so `violated` is never silently read as `discharged`):
   - (a) by construction: the sim model's evidence is built only
     from the `DischargeRequest`'s own payload digests and the
     seam-resolved tool version (the AD-19 cache-key law already
     folds tool version into `Model.version`,
     `verilator_adapter.py:8-11`); a ship-path check (the INV-32
     tap-agreement pattern, charter 40 sec. 3) refuses a `sim/`
     artifact whose digests do not re-verify against the payload
     store.
   - (b) by unreachability (the D246/D260.3 "cannot forge a pass"
     pattern): the stimulus payload model's provenance field for
     authored artifacts has a tier vocabulary containing only
     authored/asserted; no constructor accepts a model/measured tier
     for an authored `signal_table` -- the same unrepresentability
     move as D257's citation-less datasheet value.
   - (c) by totality of the coverage sweep: the parity/coverage
     producer enumerates subjects from the SAME lowered entity set
     the build used (not from the claims that happen to exist), so
     every HDL extern edge or `on <clk>` body either matches a
     sim/timing obligation or produces a named-absence row (the
     WO-114 zero-unexplained-rows partition precedent,
     `tools/health/fleet.py:36-40`).

## Out of scope

- Any code change (Rust or Python) -- this WO is spec text and the
  invariant ledger entry only.
- Assigning the real INV number, E-code numbers, or SCHEMA_VERSION
  bump negotiation -- those are implementation-time coordinator
  decisions this WO's text explicitly defers to (it writes "N",
  never guesses a number).
- Flipping `docs/spec/cuprite/09-hdl-coverage.md`'s rows to claim the
  path is ACTUALLY dischargeable before WO-155 lands -- this WO
  writes the spec text describing the intended post-WO-155 state;
  if WO-155 has not landed yet when this WO closes, the flipped rows
  must say so (e.g. "pending WO-155"), never claim a capability that
  does not exist yet.
- `setup_slack`/`corners(all)` IMPLEMENTATION -- named deferral only.

## Acceptance

- `docs/spec/cuprite/04-structural-layer.md` sec. 5 contains the v1
  contribution-sum scoping decision and a reopen-criterion entry for
  `setup_slack`/`corners`, checkable by grep for the deferred-item
  heading style already used elsewhere in the file.
- `docs/spec/cuprite/03-behavioral-layer.md` contains the
  `by sim(<stimulus-ref>)` clause with its mantra-argument paragraph.
- `docs/spec/cuprite/09-hdl-coverage.md`'s SVA/covergroup rows are
  updated with the intended-state annotation (naming WO-155 if not
  yet landed).
- Charter 38's registry tables contain the `signal_table` payload-kind
  row and the `sim/` artifact-family row, in the existing table
  format (reviewer diff-checkable against the `harness/` row
  precedent).
- `docs/spec/regolith/13-invariants.md` contains the new entry
  verbatim as drafted above (with "N" or the coordinator-assigned
  number), explicitly marked as depending on WO-155/156/157 for its
  enforcing code, checkable by `grep -n "cuprite sim/timing honesty"
  docs/spec/regolith/13-invariants.md`.
- `make check` green (docs-only WO; this confirms no doc-lint
  breakage).

## Escalation

If the `by sim(<stimulus-ref>)` spelling conflicts with an existing
grammar production in a way the spec text cannot resolve by
composition (not just naming), escalate to the coordinator before
inventing a parallel binding mechanism -- this is exactly the kind
of grammar decision `00-architecture.md`/the parser's own grammar
file governs.
