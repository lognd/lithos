# Test infrastructure and CI/CD (AD-11 / AD-12)

Reference for the fuzz/snapshot/bench/coverage scaffolding and the
GitHub Actions pipeline. This is the operational companion to AD-11
(testing strategy, per layer) and AD-12 (CI/CD and platforms); it does
not add new decisions, only documents where each piece lives and how to
run it.

## Make targets

| target      | what it does                                                  |
|-------------|---------------------------------------------------------------|
| `snapshots` | `cargo insta review` -- accept/reject CST/AST/diag/format snaps |
| `bench`     | `cargo bench --workspace` -- criterion over the Kestrel corpus |
| `coverage`  | `cargo llvm-cov` (degrades if absent) + `coverage.py` (pytest) |
| `fuzz`      | run each cargo-fuzz target ~60s (degrades without nightly)     |

`make check` stays the fast gate; none of the four heavy targets above
are part of it.

## The repo health gate (`make health`, WO-106 / D219)

| target             | what it does                                                    |
|--------------------|----------------------------------------------------------------|
| `health`           | the four-leg repo health gate (check + fleet + demos + consistency); writes `.regolith/health/health_report.json` |
| `health-fleet`     | leg 2 alone: every D210 project builds `--release` + ships clean, census golden compared |
| `health-demos`     | leg 3 alone: every live WO-108 proof pack complete + deterministic |
| `health-consistency` | leg 4 alone: the standardization sweeps (D/F numbers, WO status, extensions, goldens, waivers, worktrees) |
| `health-smoke`     | the cheap subset wired into `make check` (one project, one demo, the build-free sweeps) |

`make health` is heavy (~15-25 min, dominated by the fleet leg's 15
release builds + ships + the determinism double-ship) and is NOT part of
`make check`; `make check` instead runs `health-smoke`. The census golden
(`tests/golden/data/fleet_census.json`) regenerates with
`REGOLITH_UPDATE_GOLDEN=1 make health-fleet` and is diff-reviewed like any
golden. CI runs the full gate in its own scheduled/cycle-close `health`
job (a superset of `fast-gate`), separate from the per-push `fast-gate`
so the push loop stays fast.

## Fuzzing (`fuzz/`, AD-3)

A DETACHED cargo workspace (empty `[workspace]` table) so it can build
under nightly + sanitizers while the root workspace stays pinned to
stable 1.90.0. Three libFuzzer targets, each asserting the AD-3
invariants "never panics" and (for the front-end) "the CST covers every
input byte":

- `fuzz_lexer` -- token spans partition `[0, len)` exactly.
- `fuzz_parser` -- the rowan CST text is byte-identical to the source.
- `fuzz_cbor_decode` -- decoding/re-encoding arbitrary CBOR never panics.

`make fuzz` seeds the lexer/parser corpora from `examples/` before
running. Requires a nightly toolchain and `cargo-fuzz`
(`rustup toolchain install nightly && cargo install cargo-fuzz`); without
them it prints a SKIP line and exits 0. Long ad-hoc runs:
`FUZZ_TIME=3600 make fuzz` or `cargo +nightly fuzz run fuzz_parser`.
See `fuzz/README.md`.

## Snapshots (`insta`, AD-11)

`crates/regolith-syntax/tests/snapshots.rs` snapshots tokens, CST, AST,
and formatter output over a representative slice of the corpus (one
`.hema`, one `.cupr`, the Kestrel integration file) plus a diagnostics
case over deliberately broken source. Accepted `.snap` files are
committed under `crates/regolith-syntax/tests/snapshots/`. Update flow:
edit code, run the tests, then `make snapshots` (never hand-edit a
`.snap`). These are the human-readable companion to the byte-hashed
golden corpus (`tests/golden/`).

## Benches (`criterion`, AD-11)

`crates/regolith-syntax/benches/parse.rs` times lex, parse, and format
over every source file in `examples/systems/cubesat/` (the Kestrel workload),
reporting per-file throughput. Run with `make bench`.

## CI/CD (`.github/workflows/`, AD-12)

`ci.yml` jobs:

1. `fast-gate` (linux) -- `cargo-deny` then `make install && make check`.
2. `matrix` -- {ubuntu, macos, windows} `make test`, each publishing a
   corpus hash from `tests/determinism_hash.py`.
3. `determinism` -- downloads the three per-OS hashes and asserts they
   are byte-identical (AD-6 / INV-10; same source => same obligation
   keys everywhere).
4. `fuzz-smoke` -- nightly + cargo-fuzz, 60s per target.
5. `wheels` -- `maturin-action` abi3 wheels: manylinux_2_28,
   musllinux_1_2, macos universal2, windows.

`release.yml` (tag `v*`): the same wheel matrix plus an sdist, then
`maturin upload` to PyPI for the `regolith` distribution
(`MATURIN_PYPI_TOKEN` from `secrets.PYPI_API_TOKEN`).

The determinism hash is single-sourced with the golden suite: both use
`tests/golden/_util.stable_snapshot`, so "what is compared" never
desyncs between the local goldens and the cross-OS CI check.
