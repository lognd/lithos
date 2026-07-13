# `regolith optimize`: the optimization engine (stub)

STATUS: WORKING at the engine layer (`regolith optimize`, the discrete
driver, the trace/resume/pin mechanics), the `by select(...)` discrete
impl-strategy surface (D161/D168, WO-56's completion dispatch): grammar
through lowering through a real `ChoicePoint` is end to end (see sec.
"`by select(...)` end to end" below), AND the calcite `section: free`
section search (WO-65's reopen, over `std.civil` catalogs, landed
2026-07-10): `regolith.orchestrator.frame_resolve.search_free_section`
runs `optimize_discrete` with candidates = the member's declared
family's std.civil rows, feasibility = the design's DECLARED
utilization + deflection bounds evaluated through the SAME harness
models discharge uses, under the same `value + eps <= limit` margin
rule -- a winner can never fail its own claims at discharge --
and objective = mass-per-length ascending
(no corpus design declares a `policy:` block, so this is the disclosed
tie-break default, not full `policy:` objective-expression parsing --
that remains a future extension). The winner pins canonically: trace
persisted (`store_trace`), lockfile row via `winner_lock_row`
(`<structure>.<member>.section = <member>=<key>` with
`cause: optimize(mass_per_length, trace=<digest>)`), consumed
std.civil rows as record pins on the build's lock section. The winner
is then LITERALIZED into the FramePayload the civil drawing/schedule
producers consume (`ship.derive_producer_inputs` reads the build's own
`frame_lock_rows` and rewrites each searched member's `section.name`
from the `free` placeholder to the pinned key), so the plan +
Member Schedule sheets (`civil_plan_section`) render the real section
instead of `unresolved`.

**Fleet proof (D218.2).** In `examples/flagships/small_office/` the two
`section: in registry(std.civil.w_shape)` girders both flip to real
optimizer-pinned sections off their resolved (tributary) demand:
`G2_AB` -> `w16x40` (the lightest w_shape clearing its span/360
deflection claim; lighter shapes clear strength but deflect too far)
and `GR_AB` -> `w8x10` (the lighter roof girder). Both carry a
`cause: optimize(mass_per_length, trace=<digest>)` lock row and both
appear by name in the rendered Member Schedule -- see
`tests/test_flagship_small_office_sheets.py`. footbridge's `deflect`
flips the same way (winner `w16x40`). Members whose claims genuinely
cannot discharge for any candidate defer honestly (never a forced
winner) -- see WO-65's "Close-out ledger" for the member-by-member
accounting of the remaining pre-existing, out-of-scope deferrals.

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
static/monomorphization tier) is NOT built this dispatch. Deliverables
4/5 (the calcite L3 section search over `std.civil`) landed under
WO-65's reopen (`frame_resolve.search_free_section`, see above) --
see the WO-56 file's "Cross-note: WO-65 reopen execution" and WO-65's
own "Close-out ledger" for the exact accounting.

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

## FEA-in-the-loop (WO-76, D184, `34-topology.md` sec. 1)

A value "determined by FEA" needs NO new mechanism: it is an ordinary
`in [lo, hi] minimize|maximize` dim whose feasibility claim happens to
be discharged by an FEA-class model. The engine walks the domain, the
FEA model draws the feasible boundary, the winner pins with its trace
-- exactly the composition `optimize_continuous_golden_section` +
`ModelRegistry.discharge` already support. WO-76's exemplar wires this
together for real, once, with honest cost accounting.

### Environment audit (deliverable 1)

`which ccx gmsh` is empty in this environment, so feldspar's
discretized ccx/gmsh tier (`tier="discretized"`, its own WO-08) cannot
run here -- unchanged from WO-27's recorded cut ("no ccx/gmsh needed
... feldspar's own internal planner always finds its closed-form
direction sufficient"). The MOST EXPENSIVE tier that genuinely runs is
feldspar's `fea_static_stress@1` closed-form-analytic model
(`mech.static_stress`), and it is also the ONLY model registered for
that claim kind in this repo -- no built-in regolith model competes
for it (WO-27's own conformance module notes this). `regolith optimize`
therefore forces the FEA tier through claim-kind exclusivity: an
honest structural equivalent of rung-5 `model=` pinning, substituting
for the SOURCE-LEVEL pin, which this environment cannot yet exercise
(see "Known gap" below).

### Exemplar

`examples/tracks/hematite/lug_bracket.hema`'s `LugEye` part: a pinned
thick-wall eye idealized through the same cylinder claim family
`manifold.hema` already uses. `OuterWall.outer_radius in [20.5mm,
21.5mm] minimize` -- mass falls monotonically as the wall thins, but
the FEA-discharged `mech.static_stress <= 110MPa` claim goes
`violated` below roughly 20.8mm, so the search's true minimizer sits
at the FEA-drawn feasible boundary strictly inside the declared
bounds, not at either authored endpoint (contrast WO-64's
monotonic-to-the-bound recipe, where no constraint ever binds).

Tests: `tests/orchestrator/test_wo76_fea_loop.py` --
`test_environment_audit_ccx_gmsh_discretized_leg_stays_unexercised`
(deliverable 1, live-checked), `test_fea_loop_optimize_converges_with_
forced_model_trace` (every candidate's trace evidence cites
`fea_static_stress@1`; wall time recorded per evaluation),
`test_fea_loop_resume_reevaluates_nothing_cached` (INV-30
byte-identical resume trace; a tripwire registry proves ZERO new FEA
discharges on replay).

### Cost table (this environment, one measured run, `tol=1e-6`)

Per-evaluation wall time for `registry.discharge()` against the
closed-form-analytic `fea_static_stress@1` model, golden-section
search to convergence (17 evaluations; candidates 16/17 tied nearest
the boundary, winner index 16):

| eval # | outer_radius (m) | status | model | wall time (ms) |
|---|---|---|---|---|
| 1 | 0.020882 | violated | fea_static_stress@1 | 32.00 |
| 2 | 0.021118 | discharged | fea_static_stress@1 | 6.91 |
| 3 | 0.021264 | discharged | fea_static_stress@1 | 14.48 |
| 4 | 0.021028 | discharged | fea_static_stress@1 | 9.52 |
| 5 | 0.020972 | discharged | fea_static_stress@1 | 5.70 |
| 6 | 0.020938 | violated | fea_static_stress@1 | 9.65 |
| 7 | 0.020993 | discharged | fea_static_stress@1 | 6.10 |
| 8 | 0.020959 | discharged | fea_static_stress@1 | 6.35 |
| 9 | 0.020951 | violated | fea_static_stress@1 | 9.72 |
| 10 | 0.020964 | discharged | fea_static_stress@1 | 10.33 |
| 11 | 0.020956 | discharged | fea_static_stress@1 | 6.76 |
| 12 | 0.020954 | discharged | fea_static_stress@1 | 9.67 |
| 13 | 0.020953 | violated | fea_static_stress@1 | 10.59 |
| 14 | 0.020955 | discharged | fea_static_stress@1 | 9.31 |
| 15 | 0.020954 | violated | fea_static_stress@1 | 8.68 |
| 16 | 0.020954 | discharged | fea_static_stress@1 | 6.38 |
| 17 | 0.020954 | discharged | fea_static_stress@1 | 11.12 |

At the closed-form-analytic tier, per-evaluation cost is single-digit
to low-double-digit milliseconds, dominated by Python/pydantic
marshalling and process warm-up (eval #1), not solve time -- the
solve itself is a closed-form expression. The honesty this table
records is structural, not timing-dramatic: the discretized ccx/gmsh
tier (unrunnable here) is where per-evaluation cost would move from
milliseconds to seconds-to-minutes; nothing in this environment can
show that number without the tooling WO-27 already named as a
recorded cut. Wall time varies run to run (marshalling/GC noise,
folded into `EvalOutcome.verdict_summary` per row, never into the
trace's structural fields) but the winner and the discharge/violated
pattern are byte-identical across reruns (INV-30). Resume reruns the
SAME 17-candidate sequence at zero additional discharges (all
replayed from the stored trace) -- the cache-hit incrementality D184
asks for.

### Known gap (escalated, not silently worked around)

Rung 5 `model=<impl>` (regolith/12 sec. 2 table row 5) is a
parsed-but-unwired vocabulary item: `regolith-syntax` lexes `model` as
a keyword and the schema carries `Claim.model_pin`, but no parser rule
ever produces a populated `model_pin` -- confirmed by inspecting
`gear_reducer.hema`'s and `machine.hema`'s own lowered obligations,
whose `model_pin` stays `None` despite `model=fea_contact` /
`model=fea_modal` appearing in source. `lug_bracket.hema` declares
`model=fea_static_stress` in the same documented-but-unparsed style
as those two corpus members (for provenance) and its ENVIRONMENT NOTE
records the same finding. Wiring the grammar is a `crates/` change,
out of WO-76's Python-only, no-crates/ scope; escalated to "main" at
dispatch time. The tests exercise the same forcing EFFECT honestly
through claim-kind exclusivity (above) rather than inventing a Python-
side side channel, which D184 explicitly forbids.

## Reference

- Charter: `docs/spec/toolchain/28-optimization.md`
- Topology/FEA-loop charter: `docs/spec/toolchain/34-topology.md` sec. 1
- Architecture: `00-architecture.md` AD-30
- Determinism proof: `docs/spec/regolith/13-invariants.md` INV-30
- Engine module: `python/regolith/orchestrator/optimize.py`
- FEA-loop tests: `tests/orchestrator/test_wo76_fea_loop.py`
