# `regolith optimize`: the optimization engine (stub)

STATUS: WORKING at the engine layer (`regolith optimize`, the discrete
driver, the trace/resume/pin mechanics) AND at the `by select(...)`
discrete impl-strategy surface (D161/D168, WO-56's completion
dispatch): grammar through lowering through a real `ChoicePoint` is
end to end (see sec. "`by select(...)` end to end" below). STILL
DESIGNED (not built) for calcite `section: free` resolution over
`std.civil` catalogs and full `policy:` objective-expression parsing
-- those remain WO-56 deliverables 4/5, escalated in the WO ledger
(the recorded corpus/tributary-load gap, not invented past it).

## `by select(...)` end to end (D161/D168)

`impl <Iface> by select(<ref>, <ref>, ...)` is the sixth impl strategy
(regolith/08 sec. 4): a closed, human-declared candidate list. Every
`select` header lowers to a first-class, subject-keyed
`BuildPayload.choice_points` entry (D168; SCHEMA_VERSION 22 -> 23,
`regolith-lower::contracts::select_choice_point`) -- the SAME
flownets/frames/harnesses/contract_graph precedent, never a side
channel (AD-22). `regolith.orchestrator.optimize.
domains_from_choice_points` reads that real payload field and builds
the discrete driver's `(domains, evaluator, screen, objective)` tuple
from a declared, closed-form per-candidate cost table (the same
documented closed-form-only discipline `discrete_domains_from_spec`'s
placeholder already used -- no `eval`, no private scoring path).

`examples/tracks/cuprite/ebi_decode.cupr` is the worked demo: an
external-bus-interface address-decode choice between `nor_glue`
(discrete 74HC glue logic), `cpld` (a CPLD), and `mcu_chip_selects`
(the MCU's own FSMC controller). `tests/test_wo56_ebi_decode.py`
compiles it for real, extracts its `choice_points`, runs
`optimize_discrete`, and proves the policy-flip property: reversing
the declared cost table's preference order flips which candidate
wins, with the winning pin's lockfile `cause: optimize(cost,
trace=<digest>)` naming the real trace.

Deliverable 2's remainder (per-candidate resolution against the full
static/monomorphization tier) and deliverables 4/5 (the calcite L3
section search over `std.civil`, moving the five corpus designs'
`section: free` claims to real verdicts) are NOT built this dispatch
-- see the WO-56 file's "Partial dispatch record" (updated) for the
exact escalation.

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
