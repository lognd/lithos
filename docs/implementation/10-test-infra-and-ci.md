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

`crates/rockhead-syntax/tests/snapshots.rs` snapshots tokens, CST, AST,
and formatter output over a representative slice of the corpus (one
`.hem`, one `.cupr`, the Kestrel integration file) plus a diagnostics
case over deliberately broken source. Accepted `.snap` files are
committed under `crates/rockhead-syntax/tests/snapshots/`. Update flow:
edit code, run the tests, then `make snapshots` (never hand-edit a
`.snap`). These are the human-readable companion to the byte-hashed
golden corpus (`tests/golden/`).

## Benches (`criterion`, AD-11)

`crates/rockhead-syntax/benches/parse.rs` times lex, parse, and format
over every source file in `examples/cubesat/` (the Kestrel workload),
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
`maturin upload` to PyPI for the `rockhead` distribution
(`MATURIN_PYPI_TOKEN` from `secrets.PYPI_API_TOKEN`).

The determinism hash is single-sourced with the golden suite: both use
`tests/golden/_util.stable_snapshot`, so "what is compared" never
desyncs between the local goldens and the cross-OS CI check.
