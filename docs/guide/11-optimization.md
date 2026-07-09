# `regolith optimize`: the optimization engine (stub)

STATUS: WORKING at the engine layer (`regolith optimize`, the discrete
driver, the trace/resume/pin mechanics); DESIGNED for the language-
level surface (`policy:` objective extraction from real designs, the
`by select(...)` discrete impl strategy, calcite `section: free`
resolution) -- those land with WO-56/57.

## What it is

`regolith optimize` runs the T2 search tier (regolith/09 sec. 1):
after `check` (T0, static) and `build` (T1, realize + discharge),
`optimize` adds the orchestrator's conflict-driven allocation search
and bounded continuous refinement over the SAME pipeline `build`
already runs -- it never invents a private scoring function
(`docs/spec/toolchain/28-optimization.md`, AD-30).

Two drivers, one contract:

- **Discrete** (`optimize_discrete`): a policy-ordered greedy search
  over declared candidate domains (a `ChoicePoint`: a subject plus its
  closed candidate list), with cheap-tier screening, lazy full
  discharge, and blame-set backjumping recorded as nogoods (never
  retried).
- **Continuous** (`optimize_continuous_golden_section` /
  `optimize_continuous_nelder_mead`): in-house, deterministic, seeded
  strategies for `in [lo, hi]` bounded variables. No scipy, no
  third-party optimizer (AD-30).

Every run emits an `OptimizationTrace` (content-addressed, stored in
the project's payload store) -- the checkpoint, the audit surface, and
the `--resume` input. A feasible winner pins into `regolith.lock` as
`cause: optimize(<objective>, trace=<digest>)` (INV-21); an infeasible
domain reports honestly and pins nothing.

## Today's CLI surface

```
regolith optimize <project> --spec spec.json --budget-evals N \
    [--seed N] [--resume <trace-digest>] [--json]
```

A budget (`--budget-evals`) is MANDATORY -- there is no silent
unbounded search. `--spec` is a placeholder evaluator surface (a
closed-form JSON cost table over declared choice-point domains) until
WO-56 wires real `policy:`/`by select(...)` extraction from lowered
source into the same driver signatures; see
`regolith.orchestrator.optimize.discrete_domains_from_spec`'s
docstring for the exact spec shape and the seam WO-56/57 replace.

## Reference

- Charter: `docs/spec/toolchain/28-optimization.md`
- Architecture: `00-architecture.md` AD-30
- Determinism proof: `docs/spec/regolith/13-invariants.md` INV-30
- Engine module: `python/regolith/orchestrator/optimize.py`
