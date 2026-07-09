# WO-55: optimization engine core + the cycle-30 schema slice

Status: todo
Depends: nothing undone (consumes landed WO-30 payload channel,
WO-42 staged loop, the cycle-28 NogoodCache, WO-14 lockfile causes).
Gates: WO-56, WO-57, WO-58's trace-sheet slice, WO-59's trace view.
Language: Rust (`regolith-oblig` schemas, ONE SCHEMA_VERSION bump
20->21 per D160) + Python (`regolith.orchestrator.optimize`, CLI).
Spec: docs/spec/toolchain/28-optimization.md (NORMATIVE charter),
00-architecture.md AD-30 (+ AD-1/5/18/22), design-log
2026-07-09-cycle-30 D159/D160/D162; regolith/07 sec. 7 (the two
engines, verbatim doctrine), regolith/03 (value sources +
objective directions), regolith/12 sec. 4 (`policy:` objectives),
regolith/13 (INV-30 lands here).

## Goal

`regolith optimize` exists and works: one engine
(`regolith.orchestrator.optimize`) with a discrete conflict-driven
driver and a continuous in-house-strategy driver, evaluating
candidates only through the real pipeline, emitting a
content-addressed `OptimizationTrace`, pinning winners with
`cause: optimize(...)`, deterministic per INV-30.

## Deliverables

1. **Schemas** (`regolith-oblig`, the ONE cycle-30 bump, D160):
   `OptimizationTrace` (strategy id + version, seed, budget
   declared/spent, ordered candidate entries: assignment, objective
   vector, verdict summary, evidence digests; nogood keys recorded;
   winner; termination status `converged|budget_exhausted|
   infeasible`) and `ChoicePoint` (subject id, ordered candidate
   refs, policy context) as payload kinds on the D96 ref channel
   (`optimize.trace`, `optimize.choice`). `make schema` regenerated
   and committed. If WO-58's producers have escalated a DrawingModel
   field gap per AD-22 before this slice merges, fold it into the
   same bump (coordinate via the WO files' ledgers).
2. **Objective extraction** (`orchestrator/optimize.py`): read the
   lexicographic `policy: minimize` list, per-variable directions,
   and `prefer`/`forbid` from the lowered payload/lockfile surfaces;
   feasibility = all demands dischargeable. No new grammar.
3. **Discrete driver** `optimize_discrete`: policy-ordered greedy
   descent over domain-of-candidates inputs, cheap-tier screening,
   lazy full discharge (`discharge_all`), blame-set backjumping
   (non-chronological), nogoods via the existing `NogoodCache`
   (persisted; keys fold consumed record revisions as landed).
4. **Continuous driver** `optimize_continuous`: `golden_section`
   (1-D) and `nelder_mead` (N-D) as pure, seeded, deterministic
   proposers (in-house; no scipy); domain-corner-derived
   deterministic initialization; evaluator injected (plain `build` +
   discharge here; `staged_build` arrives in WO-57 -- design the
   evaluator seam so WO-57 adds no engine change).
5. **Trace + resume + pinning**: every run puts an
   `OptimizationTrace` to the payload store; `--resume <trace>`
   skips evaluated candidates (evidence-cache hits, zero new
   discharges -- proven by test); winners land as lockfile rows
   `cause: optimize(<objective>, trace=<digest>)` through the
   existing Cause-typed API (INV-21).
6. **CLI**: `regolith optimize` (typer): `--budget-evals`,
   `--budget-seconds`, `--seed`, `--resume`, `--json`. A budget is
   MANDATORY (flag or D164 config once that lands; until then flag
   with a documented default refusal). T2 tier: `check`/`build`
   remain search-free. stdout is data; logs to stderr; every
   iteration logged.
7. **INV-30** in regolith/13 WITH proof argument (same change):
   optimization reproducibility + attribution -- ingredients:
   seeded strategies, source-ordered enumeration (AD-6 collections),
   canonical digests (AD-18), pipeline evaluation (INV-10).
8. **Docs**: charter cross-refs, `docs/guide/` optimize section
   stub, module docstrings.

## Acceptance criteria

- Discrete: on a synthetic 3-choice-point domain with a fake cheap
  harness, the driver finds the policy-best feasible assignment,
  records a nogood for an injected infeasible combination, and never
  retries it (nogood cache hit asserted).
- Continuous: both strategies converge on fixture objectives
  (1-D quadratic; 2-D Rosenbrock-lite with feasibility cut) within
  budget; identical winner + byte-identical trace across two runs
  with the same seed; different seed => trace differs but both
  feasible.
- Resume: interrupting at half budget then `--resume` completes with
  zero re-evaluations of cached candidates (discharge-call count
  asserted).
- Budget exhaustion returns best-so-far + `budget_exhausted` (never
  an exception, never a silent success).
- Lockfile row carries `cause: optimize(...)` with the trace digest;
  `regolith optimize --json` round-trips through the generated
  schema models.
- INV-30 test family green beside the engine; `make schema` drift
  check green; SCHEMA_VERSION is exactly 21; `make install` then
  `make check` green.
