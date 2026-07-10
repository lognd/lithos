# 30 -- Geometry lowering depth: coverage, closure, assemblies (design charter; D171, cycle 31)

> Charter for the mech L3->L4 path growing from "parts realize" to
> "machinery realizes": the WO-22 residue closed, an honest feature-
> coverage ledger, and assembly realization as a first-class L4 IR.
> Ledger rule: AD-32 (00-architecture.md). Machinery: WO-62. Where
> this doc and a WO body conflict, this doc wins.

## 0. The gap this closes

The declarative-to-STEP chain is proven narrow (coolant_gallery,
D152) and honest about its skips -- but the skips are unlisted, the
sheet-metal residue (closure solve, gauge source) blocks a corpus
member, and NOTHING realizes an assembly: matings verify as
contracts while machines exist only as unplaced part sets. The
owner's bar (design machinery declaratively, hand-parity) fails at
exactly these three walls.

## 1. Design decisions (load-bearing)

1. **Close-edge closure solve.** A sketch profile with free/derived
   segment lengths solves to a closed loop where a unique closure
   exists (linear chain solve over the profile's constraint set,
   deterministic order); an over/under-constrained profile is a
   CONSTRUCTIVE diagnostic naming the residual edge and the missing
   constraint class -- never a silently-open profile, never a
   least-squares fudge. Home: `regolith-ir::sketch` (the recorded
   increment site).
2. **Sheet-gauge source.** `process=laser_cut(sheet=<t>)` (and
   sibling sheet processes) is a value SOURCE for blank thickness
   (cause: `process(<proc>.sheet)`, INV-21) consumed by the sheet
   feature path; a sheet part without a gauge source and without an
   asserted thickness is a compile diagnostic. sheet_bracket
   realizes to STEP (the WO-22 acceptance sentence completes).
3. **The feature-coverage ledger.** The realizer PUBLISHES, as
   drift-checked data (the schema-check pattern applied to
   capability), the FeatureProgram op classes it supports:
   op kind x parameter envelope -> `realizes | skips(named
   diagnostic)`. An op outside the ledger yields the named skip and
   an honestly indeterminate dependent obligation -- a partial
   solid is unrepresentable. The ledger is versioned content: what
   "declarative mech" may claim IS this file, and coverage growth
   is ledger diffs (reviewable), never silent interpreter drift.
   Corpus + flagship demands drive growth; a demanded-but-unsupported
   op in a flagship is an ordinary WO-shaped escalation.
4. **Assemblies realize: `RealizedAssembly`** (one more first-class
   L4 IR by AD-25's growth rule; cycle-31's ONE schema bump, 23->24,
   owned by WO-62 per the D168 train rule):
   - INPUT: the mating graph the contracts already carry (align/
     coincident/distance/angle vocabulary, hematite/03) over parts
     with RealizedGeometry digests.
   - SOLVE: deterministic sequential placement over a spanning
     order of the mating graph (root part at identity; each part
     placed by its mates to already-placed parts; placement order =
     source order, AD-6). A mate loop whose closure residual
     exceeds the interface tolerance is a DIAGNOSTIC citing the
     loop's mates -- the tolerance-stack machinery owns slack,
     the solver never hides it.
   - OUTPUT: `RealizedAssembly { parts: [(part id, geometry digest,
     transform)], dof_states, mass, com, interferences }` --
     content-addressed, store citizen, cited by claims. STEP
     assembly export rides the existing exporter seam; extracted
     mass/COM enter the measured entity DB like any T2 fact;
     pairwise interference facts feed realized-fact rules (an
     interference is a release-gated diagnostic with both part
     names and the overlap measure).
5. **Optimization composes for free.** Nothing optimizer-specific
   lands here: assembly-realized facts (mass, COM, interference,
   envelope) are ordinary evidence, so `in [lo,hi] minimize` dims
   and `by select` candidates already trade against them through
   the cycle-30 staged evaluator. This charter widens what a
   candidate EVALUATION can see; the engine is untouched (AD-30).

## 2. What already carries it

FeatureProgram v2 + interpreter + STEP export (WO-22/51), the
staged loop (AD-25), RealizedGeometry + the extract seam (WO-42/32),
the mating vocabulary and ledgers (L2/L3), the drawings/audit
surface (AD-27) which gains assembly views for free once the IR
exists, `regolith debug ir` inspectability.

## 3. Non-goals (reopen criteria attached)

- **Kinematic motion** (joint sweeps, collision-over-motion,
  mechanism simulation): reopen on flagship-1 phase-B evidence that
  a static placed assembly is insufficient for its acceptance --
  expected eventually, not built speculatively (the mechanisms
  packs, AD-28/D144, are where joint LAWS already live).
- **Free-form/topology synthesis**: AD-30's sovereignty rule
  stands; the optimizer explores DECLARED spaces. Reopen never in
  this form; a declared-lattice/declared-rib-pattern vocabulary
  would be the honest route and needs its own charter.
- **A second geometry kernel**: OCCT via build123d remains the one
  realizer seam (AD-1). Reopen only on a proven kernel-blocking
  defect.
- **Full GD&T-driven variational assembly solve**: the placement
  solve is nominal + tolerance-residual checks; statistical stack
  analysis stays with the budget machinery (D63's cut stands).

## 4. Acceptance shape (what WO-62 must prove)

sheet_bracket.hema realizes to STEP (closure solve + gauge source,
goldens enrolled); the coverage ledger exists, is drift-checked
against the interpreter, and every corpus skip is ledger-listed; a
new assembly exemplar (>= 4 parts, >= 5 mates including one
deliberate interference variant) realizes to a placed
RealizedAssembly + STEP assembly, deterministic across two runs,
with mass/COM extracted, the interference variant caught as a
release-gated diagnostic naming both parts, and one `in [lo,hi]
minimize` dimension optimized against an assembly-level mass claim
through the staged evaluator (the composition proof).
