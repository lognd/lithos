# 28 -- The optimization engine (design charter; D159-D162, cycle 30)

> Charter for making regolith/07 sec. 7's specced-but-unbuilt
> orchestrator loops real: discrete allocation search over declared
> alternatives and derived decisions, and continuous bounded-domain
> refinement up to and including expensive realized-domain (geometry)
> evaluation. Ledger rule: AD-30 (00-architecture.md). Machinery:
> WO-55 (engine + schemas), WO-56 (discrete surface end-to-end),
> WO-57 (staged-loop optimization). Where this doc and a WO body
> conflict, this doc wins.

## 0. The gap this closes

The language has carried the full optimization SURFACE since the
value-source grammar settled: `in [lo, hi] minimize|maximize`
(bounded freedom, regolith/03), `policy: minimize` lexicographic
global objectives (SOPEN-4, regolith/12 sec. 4), `prefer`/`forbid`
(ordering / domain cuts), budgets with `allocate:` policies, and
regolith/07 sec. 7's two named engines (the lazy loop; conflict-
driven allocation search with nogoods). What exists in code:
`orchestrator/loop.py` (sensitivity fixpoint), `staged_build`
(AD-25), `NogoodCache`. What does not: the drivers, objective
extraction, a trace artifact, `regolith optimize` (the AD-10 verb),
and a pinning cause for search-chosen values. Consequence, recorded
in WO-48's close-out: every calcite corpus `section: free` claim is
honestly indeterminate awaiting exactly this engine.

## 1. Design decisions (load-bearing)

1. **One engine home.** `regolith.orchestrator.optimize` (AD-1:
   iteration/caching/scheduling are orchestrator work; compiler and
   harness stay pure). Two drivers, one contract:
   - `optimize_discrete`: conflict-driven greedy search (regolith/07
     sec. 7 verbatim): policy-ordered descent screened by the cheap
     tier; lazy full discharge on complete candidates; violated
     obligations carry blame sets; backjump non-chronologically;
     record nogoods in the EXISTING `NogoodCache` (persisted,
     revision-keyed). Domains: `ChoicePoint` candidate sets (D161
     `by select`), registry candidate queries (component binding,
     `section: free` over catalog tables), and future planner
     decision points -- all reach the driver as the same
     domain-of-candidates shape.
   - `optimize_continuous`: bounded refinement for `in [lo, hi]`
     variables. Strategies are IN-HOUSE, deterministic, seeded:
     `golden_section` (1-D), `nelder_mead` (N-D simplex, fixed
     deterministic init from the seed + domain corners). A strategy
     is a pure proposer: assignments in, next assignments out; ALL
     evaluation goes through the pipeline.
2. **Evaluation IS the pipeline.** A candidate is evaluated by
   building it (`build`, or `staged_build` when realization is in
   scope) and discharging its obligations; the objective value is
   read from the resulting evidence/budget/cost surfaces. No private
   scoring function ever exists (AD-22): if the objective cannot be
   expressed as claims + budgets + `policy: minimize`, it is not an
   objective yet.
3. **Objective extraction, not objective invention.** The engine
   consumes: feasibility = all demands dischargeable (claims are
   satisfiability, applied strictly first, regolith/03); then the
   `policy: minimize` list in declared (lexicographic) order; then
   per-variable `minimize`/`maximize` as the innermost tier.
   `prefer` orders candidate exploration; `forbid` cuts domains.
   Nothing new is parsed.
4. **The trace is evidence.** Every run emits an
   `OptimizationTrace` payload (Rust schema in `regolith-oblig`,
   AD-5; content-addressed, AD-18; store citizen on the D96 ref
   channel): strategy id + version, seed, budget declared/spent,
   per-candidate assignment + objective vector + verdict summary +
   evidence digests, nogoods recorded, winner, and termination
   status (`converged` / `budget_exhausted` / `infeasible`). The
   trace is the checkpoint (`--resume`), the audit surface, and the
   input to the D165 trajectory sheet.
5. **Winners pin with a cause.** Chosen values land in the lockfile
   as `cause: optimize(<objective>, trace=<digest>)` -- INV-21
   applied to search. Non-winners exist only in the trace. A later
   build with unchanged inputs replays the pin (no re-search unless
   asked: `optimize` is the AD-10 T2 tier, `build`/`check` never
   search).
6. **Determinism (INV-30).** Same sources + records + seed +
   budget + strategy version => identical winner and byte-identical
   trace. Ingredients: seeded strategies, ordered candidate
   enumeration (insertion/source order, AD-6 collections), the
   canonical encoder for every digest, and pipeline evaluation
   (already INV-10). INV-30 enters regolith/13 with its proof
   argument in the same change as WO-55 (house rule).
7. **The ladder's safety property is inherited.** The engine only
   proposes inputs and re-keys obligations; verdicts come from the
   same total discharge path (the loop.py contract, unchanged).
   `assume!`/`waive` never interact with search: an infeasible
   domain is reported infeasible, never silently waived past.
8. **Expensive evaluation discipline (D162).** An evaluation budget
   (max evaluations and/or wall-clock) is MANDATORY at invocation
   (flag or D164 config profile). Budget exhaustion returns
   best-feasible-so-far with an honest `budget_exhausted` status.
   Evidence caching makes resume/re-run incremental: an unchanged
   candidate re-evaluates to cache hits (proof: second run of a
   finished search performs zero new discharges). Realized-domain
   evaluation (geometry) is the same driver with `staged_build` as
   the evaluator; CFD-class models arrive as AD-19 packs, never
   in-tree.

## 2. The discrete surface: `by select(...)` (D161)

The sixth impl strategy (regolith/08 sec. 4 gains it; WO-56 lands
grammar + CST + lowering): `impl <name> by select(<ref>, <ref>,
...)` declares a closed candidate list. Every candidate passes the
full static tier independently (the integer-domain monomorphization
rule applied to impls); the choice lowers to a `ChoicePoint`
payload (subject, candidate refs, policy context); the discrete
driver decides; the pin is reviewable like any lockfile row. One
candidate = a degenerate pin, legal. Sovereignty: the human wrote
the list; AD-28's no-auto-substitution rule for `advise:` patterns
is untouched.

## 3. What already carries it

`NogoodCache` (search memory), `staged_build` (realization
evaluator), the evidence store (candidate caching), budgets/costing
(objective values with provenance), `policy:` parsing, lockfile
causes (INV-21 API), the D96 payload channel (trace storage). This
charter adds two schemas, one orchestrator module, one CLI verb,
and one impl-strategy keyword -- no new pipeline, no second
evidence model.

## 4. Non-goals (reopen criteria attached)

- **Multi-objective Pareto surfaces**: lexicographic order is the
  v1 doctrine (SOPEN-4). Reopen on a real design whose objectives
  cannot be honestly ordered.
- **Global optimality claims**: the engine reports the best
  candidate FOUND within budget; evidence never says "optimal".
  Reopen never -- this is honesty, not scope.
- **Third-party optimizer integration** (scipy/NLopt/CMA-ES libs):
  reopen on a real search our two strategies demonstrably cannot
  converge that a candidate library can, deterministically.
- **Topology synthesis** (inventing candidates not declared or
  queryable): violates sovereignty; the `select` list and registry
  queries are the candidate universe.
- **A new plugin kind for strategies**: in-tree strategies suffice
  v1; reopen when an out-of-tree strategy with a real user exists
  (then it enters through AD-26 with a kind addition, not a bespoke
  seam).

## 5. Acceptance shape (what the WOs must prove)

WO-55: both drivers green on synthetic domains with a fake cheap
harness; trace byte-identical across two seeded runs; resume
performs zero re-evaluation; INV-30 landed with proof argument.
WO-56: the five calcite corpus designs' `section: free` members
resolve via real section search over std.civil, moving the recorded
indeterminate `civil.utilization`/`mech.deflection` claims to real
verdicts (goldens updated -- THE flagship demo); an elec
`by select` EBI-style decode choice picks per `policy: minimize`
with the full trail (trace + cause + diff-visible pin). WO-57: a
parametric hematite corpus member with `in [lo, hi] minimize`
dimensions optimizes through the staged loop under a declared
budget; checkpoint/resume proven; budget exhaustion reports
honestly; all with closed-form models so CI runs it.
