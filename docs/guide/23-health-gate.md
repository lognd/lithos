# Is everything still proven? -- `make health`

`make check` proves the *code* is sound (formatting, lints, types, unit
and golden tests). `make health` proves the *whole repo* is still
sound: every fleet project still ships, every optimization still has a
physical proof, and the docs/goldens/waivers still agree with each
other. It is the cycle-close bar and the standing answer to "is
everything still proven?" (D219).

## One command, four legs

```
make health
```

runs four legs cheapest-first. Each also runs alone, and each reports
ONE standardized row -- `leg`, `ok`, counts, an evidence pointer -- into
a machine-readable `.regolith/health/health_report.json` plus a loud
verdict block:

```
  [PASS] check        rc=0                                     make check (fmt, clippy, ruff, ty, guard-core, schema, tests)
  [PASS] consistency  failed=0 sweeps=6                        all sweeps clean
  [PASS] demos        demos=16                                  demos/run_all.py + tests/test_wo108_demos.py
  [PASS] fleet        green=15 mismatch=0 projects=15          tests/golden/data/fleet_census.json
HEALTH: PASS
```

| leg | make target | what it proves |
|-----|-------------|----------------|
| `check` | `make health-check` (alias of `make check`) | the existing code gates -- it CALLS `make check`, never re-implements a gate |
| `fleet` | `make health-fleet` | every D210 project builds `--release` green, ships a hash-verified package, and matches the census golden |
| `demos` | `make health-demos` | every live proof pack -- WO-108 optimization + WO-115 feature -- is complete + deterministic (reuses the one runner + test) |
| `consistency` | `make health-consistency` | the standardization sweeps below |

## The fleet leg

Discovers every fleet project (an `examples/` directory with a
`magnetite.toml`, minus documented exemptions -- currently none), then
per project drives the real CLI:

```
regolith build --release <project> --json --out <tmp> [--spec ship.spec.json]
regolith ship  <project> --build <tmp> --out <pkg>    [--spec ship.spec.json]
```

and asserts `release_ok=true`, zero stale waivers, a package whose every
manifest file re-hashes clean, and a per-project census
(`{obligations, discharged, accepted_deviation, violated, families}`)
byte-equal to `tests/golden/data/fleet_census.json`. One mech-heavy
project (dune_buggy) ships twice and every deterministic artifact is
byte-compared.

Regenerate the census golden the ordinary golden way, then REVIEW the
diff before committing:

```
REGOLITH_UPDATE_GOLDEN=1 make health-fleet
git diff tests/golden/data/fleet_census.json
```

A new backed `waive ... by doc(...)` moves `accepted_deviation`; a bare
(unbacked) waiver harvests stale and fails the leg. Either way the
census moves -- **acceptance creep cannot land silently** (proven by
`tests/health/test_health.py`).

## The consistency leg

Cheap, build-free sweeps that the repo still hangs together:

- **dnum** -- every `D`/`F` design-log number has exactly one primary
  heading (addenda, `D170-a` / "F115 addendum", are allowed).
- **wo_status** -- TODO never marks a WO done that its file has not
  started (the residual-tracking `- [ ]` and `honest-partial` Status
  conventions are reported, not gated).
- **extension** -- the four source extensions live in the one Rust
  registry; the core FFI reports exactly them and no Python file keeps a
  competing list.
- **goldens** -- `tests/golden/` carries no uncommitted drift.
- **waivers** -- every `by doc(<ref>)` resolves to a memo file and the
  fleet leg saw zero stale waivers fleet-wide.
- **worktrees** -- stale git worktrees are reported (never gating).

## Runtime and CI

`make health` is heavy -- roughly 15-25 minutes, dominated by the fleet
leg's 15 release builds + ships and the determinism double-ship. It is
NOT part of `make check`; instead `make check` gains a cheap
`health-smoke` (one small project, one demo probe, the build-free
consistency sweeps) so the fast gate still catches a broken seam. Run
the full `make health` at cycle close (and in a dedicated CI job -- see
`docs/spec/toolchain/10-test-infra-and-ci.md`).
