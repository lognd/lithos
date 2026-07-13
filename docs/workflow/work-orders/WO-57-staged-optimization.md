# WO-57: realized-domain optimization (the expensive loop)

Status: done (cycle 30; staged evaluator behind the WO-55 seam,
  duct_vane exemplar, budget/interrupt/resume + incrementality proven
  -- see TODO.md and the WO-55 ledger. Status flipped by WO-106's
  consistency sweep, which caught the queue-vs-file desync.)
Depends: WO-55 (engine, evaluator seam, trace/resume; HARD).
Serializes with WO-56 at integration (both touch orchestrator/CLI
surfaces -- the integrator rebases the second; D159 sequencing note).
Language: Python (orchestrator evaluator wiring, exemplar corpus) +
Rust only if the exemplar needs a lowering fix (none expected). NO
SCHEMA_VERSION bump (D160).
Spec: docs/spec/toolchain/28-optimization.md secs. 1.8, 5
(NORMATIVE), 00-architecture.md AD-30 + AD-25 (staged loop),
design-log 2026-07-09-cycle-30 D162; regolith/03 (`in [lo, hi]
minimize`), regolith/08 (L4/staged build), hematite feature-program
surface as landed (WO-51).

## Goal

`optimize_continuous` evaluates candidates through the FULL staged
loop (lower -> realize -> re-lower -> discharge) under a mandatory
evaluation budget, with checkpoint/resume and cache-hit
incrementality -- the CFD-propeller-shaped workflow proven with
CI-runnable closed-form models.

## Deliverables

1. **Staged evaluator**: plug `staged_build` into the WO-55
   evaluator seam -- a candidate assignment of `in [lo, hi]`
   dimension variables re-lowers, re-realizes (mech realizer), and
   discharges; objective read from evidence/budget surfaces exactly
   as WO-55 defines. No engine changes (if one proves necessary,
   STOP and escalate per the dispatch protocol -- the seam was the
   WO-55 acceptance).
2. **Budget enforcement at the expensive tier**: per-evaluation
   wall-time accounting includes realization + discharge;
   `budget_exhausted` carries evaluations-completed and
   best-so-far; interruption (SIGINT-safe checkpoint write) leaves
   a resumable trace. Every evaluation start/end logged with
   timing.
3. **Incrementality proof**: a finished search re-run with
   unchanged inputs performs ZERO new realizations and ZERO new
   discharges (payload/evidence content-address hits; counts
   asserted). A one-record change re-evaluates only affected
   candidates.
4. **Exemplar corpus member** `examples/` hematite `duct_vane` (or
   extend an existing parametric member if a better fit exists --
   record the choice): >= 2 `in [lo, hi] minimize` dimensions, a
   mass-minimization `policy:`/direction objective, feasibility
   claims (deflection/stress) discharged by EXISTING closed-form
   models; golden-enrolled including its trace (seeded).
5. **CFD growth note, not scope**: the charter's AD-19 pack path
   for CFD-class evaluators recorded in the WO ledger + guide
   (what a pack must provide; nothing implemented).
6. **Docs**: guide walkthrough (author objective -> run optimize
   -> read trace -> resume), module docstrings, WO ledger.

## Acceptance criteria

- End-to-end: `regolith optimize --budget-evals N --seed S` on the
  exemplar converges to a feasible minimum; two same-seed runs are
  byte-identical (winner, trace, lockfile rows).
- Budget of 1 evaluation returns honestly (`budget_exhausted`,
  best-so-far = the eager candidate if feasible, else
  `infeasible`).
- Resume after interrupt completes without re-evaluating cached
  candidates (realizer + discharge call counts asserted).
- The chosen dimensions land in the lockfile with
  `cause: optimize(...)`; `regolith debug ir` shows the realized
  IRs of the winning candidate (AD-25 inspectability).
- No SCHEMA_VERSION change; `make install` + `make check` green;
  Status flipped in this change.
