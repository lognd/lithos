# Build System, Lockfile, Diagnostics

> Regolith spec. Identical CLI shape, lockfile schema, and diagnostic
> discipline for both languages.

## 1. Build tiers

| command | runs | latency target |
|---|---|---|
| `check` | L0-L3 static everything: parse, types/units, queries, borrows, monomorphized checks, symmetry, ledgers, capability/fit lookups, budget arithmetic, plus L5 obligations dischargeable by closed-form models | ms-s |
| `build` | + L4 realization, post-realization verification, T2 conformance, verification of the eager candidate | s-min |
| `optimize` | + the orchestrator loop | as needed |
| `build --release` | + refuse `todo!`/`assume!`/evidence-less waivers (per-item acknowledgment only); deviations (evidence-carrying waivers meeting trust floors) permitted and listed; full evidence ledger -- a green release means proven or explicitly accepted, nothing between (INV-24) | -- |

The elec track adds no verbs: synthesis/place-and-route are L4 realization
inside `build`; simulation is L5 discharge.

## 2. The lockfile

`<lang>.lock` pins everything resolution produced, making builds
reproducible and diffs reviewable:

- resolved free/bounded variables, each with its resolving cause
  (`dfm`/`drc` rule, `obligation:<id>`, `topology`/`structure` boundary,
  `budget:<name>`, `planner`, `extern:<ref>` for supplied plans/content,
  `derived(intent <name>)` for derived workloads, plus a
  `policy: prefer(...)` annotation when a preference was decisive --
  the full cause vocabulary INV-21 enumerates);
- allocated tolerances and shares (cause: `local` or `budget:<name>`);
- fit/standard expansions (ISO 286 deviations; logic-level thresholds);
- `any` canonical choices;
- evidence hashes; kernel/synthesizer versions; model-registry version;
- package versions and record revision hashes for every registry record
  consumed (`11-packages-and-stdlib.md`);
- planner plans (by hash; the plan artifact lives in the evidence cache);
- waivers.

Targets (`04-contracts.md` section 6) build with `--target <name>`; the
lockfile carries per-target sections for target-added resolutions, and
reserve consumption is materialized like any budget share.

A number that changes in review names its cause. The lockfile is the
defaults test's enforcement surface.

## 3. Reproducibility

Given (source, lockfile, tool versions): all **decisions and evidence
identities** are bit-reproducible -- canonical `any` representatives,
pinned solver branches, content-addressed evidence. Numerical evidence
*values* are reproducible per each model's declared `deterministic:`
flag; nondeterministic models (parallel FEA reductions, stochastic
solvers) must fold seeds/settings into their evidence hash inputs, so
cache identity never lies even where values wobble (INV-10).

## 4. Diagnostics

Rust-style, constructive, stated in the user's vocabulary, with stable
regolith-wide error-code families (messages are domain-specific; codes
and families are shared):

| family | class | examples |
|---|---|---|
| `E01xx` | parse / types / units / grammar | incompatible quantities; `==` on continuous |
| `E03xx` | references / ownership / structure | `E0301` ambiguous selection; `E0302` borrow conflict; `E0304` structure-class change; multiple drivers |
| `E04xx` | contracts | `E0410` capability vs demand; `E0420` ledger (DOF / driver / domain-crossing); `E0432` budget cannot close |
| `E05xx` | instances / symmetry | `E0501` index vs domain; `E0502` broken-orbit `any` |
| `E06xx` | rule packs (DFM / DRC / ERC) | rule violation with rule provenance |
| `E07xx` | evidence | indeterminate discharge; assumption in `--release` |

Errors are **batch-emitted with cross-references** (edit blast radius
shown at once via `check --explain`), never first-error-stops.

## 5. Trait coherence and override

All registry-like mechanisms -- material/component classes and `contact`
pair records, interface `refines`, signatures and harness impls -- share
one rulebook:

1. canonical (unordered where applicable) keys;
2. resolution picks the unique most-specific record, or errors;
3. `override <record> by <evidence>` shadows at the same key; the evidence
   clause is mandatory;
4. `use { A, B }` / `use <impl>` pins resolution when specificity or impl
   choice is ambiguous (`model=<impl>` on connections is this same pin);
5. every resolution is lockfile-provenanced.

## 6. The lock family

One mental model for "a human fixes an otherwise-resolved decision," in
every position: `locked:` entries in budgets and on planner decisions
(incl. `locked: pinmux(u_mcu.uart2.tx): pa2` -- the one place a
package pin may appear in design source), `use` in coherence,
`sequence: a before b` for planner ordering, `merge(a over b)` for
ownership, `hosted_on` for synthesized-block hosting. All
lockfile-visible. (Renamed from "the pin family" in cycle 1: `pins:`
was fatal vocabulary in a domain where "pin" means a package terminal;
the old `pins: x: locked(v)` form also double-marked one idea.)

The lock family is rung 2 of the expert ladder; the full doctrine for
overrides, hints, policies, and waivers -- including what `--release`
gates and what the evidence ledger lists -- is
`12-overrides-and-hints.md`.
