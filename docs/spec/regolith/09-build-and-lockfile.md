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

## 7. `regolith ship` and the ship manifest (WO-25, L6)

`regolith ship` is the terminal step after a clean `--release`: it
drives every configured manufacturing backend (`regolith.backends.mech`,
`regolith.backends.elec`) over the SAME (lockfile, evidence, realized-
domain IR) triple `--release` already resolved, and folds every emitted
file into one signed manifest -- the package's own attestation. A
backend never decides anything (sec. 6 "backends serialize evidence");
`ship` itself refuses (named diagnostic, nonzero exit) before writing
anything unless the release gate (INV-24, trust floors) is clean.

The manifest (`manifest.json` at the package root) is:

```
{
  "design_hash": "blake3:<hex>",       // every source path's bytes, domain-tagged
  "lockfile_hash": "blake3:<hex>",     // the rendered regolith.lock text
  "evidence_rollup": [["<subject>", "<status>"], ...],  // sorted
  "files": [{"relpath": "<name>/<path>", "sha256": "<hex>"}, ...],  // sorted
  "signature": {
    "key_id": "<id>",
    "algorithm": "ed25519",
    "signature_base64": "<base64>"
  } | null
}
```

Every packaged file's path is `<backend-name>/<file-relpath>` (e.g.
`mech/step/bracket.step`, `elec/gerbers/board.gbr`); `files` lists every
one, sorted, hashed. The signature is computed over a domain-tagged
blake3 content address of every OTHER field (never folding itself in,
never signing raw bytes) -- the same envelope discipline `12-overrides-
and-hints.md`'s evidence-attestation machinery (INV-28) already
establishes, reused rather than reinvented. `signature` is `null` for an
unsigned package (still verifiable-by-hash via `--verify`, just without
an attributable signer).

`regolith ship --verify DIR` re-hashes every file listed in
`DIR/manifest.json` and checks the signature against a supplied trust
key set: a mismatched hash, a missing/extra file, an unknown signing
key, or a bad signature are each a distinct, named failure -- never a
silent pass.

## 8. `regolith build` (WO-43, D136)

`regolith build [--release] [--tier check|build|optimize|release]
[--out DIR] [--json]` surfaces the staged pipeline (WO-42 deliverable
5's lower -> realize -> re-lower loop) as one shell verb, so the whole
pipeline is drivable with no Python-API knowledge:

- Project discovery walks upward from the given path looking for
  `magnetite.toml` (the same manifest-anchored walk `regolith-ls`
  uses, WO-38 deliverable 1); `--out`'s default is
  `<project_root>/.regolith/build`, the same project-local, gitignored
  `.regolith/` home the evidence cache, payload store, native-artifact
  store, and cross-run nogood cache (EOPEN-13/D75, cuprite `08` sec.
  1a) already use.
- `--tier` selects a rung of the T0..T3 ladder directly (default
  `build`, T1); `--release` is shorthand for `--tier release` (T3, the
  INV-24 gate) and wins if both are given.
- Every run writes `regolith.lock` (this build's `realized_lock_rows`,
  WO-42 deliverable 5) and `build_report.json` (the full
  `StagedBuildReport`, machine-readable) to `--out DIR`.
- Output contract (AD-10): stdout carries the build report -- the ONE
  renderer's diagnostics text verbatim plus a one-line summary by
  default, or the full JSON report with `--json`. ALL logs go to
  stderr. Exit code 0 iff the build is clean AND (when the release
  tier ran) the gate passed; nonzero otherwise, with the refusal
  rendered on stdout as data, never only in a log line.
- `regolith ship --build DIR` (deliverable 3) consumes a prior
  `regolith build --release --out DIR`'s `regolith.lock` +
  `build_report.json` directly, without re-running the staged build --
  `regolith build --release --out DIR && regolith ship --build DIR
  --out ship/` is the two-command corpus demo (WO-25's first named
  blocker, now closed). `regolith ship` with no `--build` flag keeps
  its original behavior (reads `regolith.lock` from the project root
  and runs its own `staged_build`).
