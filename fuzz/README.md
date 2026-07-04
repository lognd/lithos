# rockhead-fuzz

`cargo-fuzz` targets for the compiler front-end, per AD-3 (fuzzing is
part of the parser's definition of done) and AD-11 (the Rust-fuzz test
layer).

## Targets

| target             | invariants (AD-3)                                        |
|--------------------|----------------------------------------------------------|
| `fuzz_lexer`       | never panics; token spans partition `[0, len)` exactly   |
| `fuzz_parser`      | never panics; CST text is byte-identical to the source   |
| `fuzz_cbor_decode` | never panics decoding/re-encoding arbitrary CBOR bytes   |

## Requirements (nightly)

`cargo-fuzz` builds with libFuzzer + sanitizers, which need a **nightly**
Rust toolchain -- the root workspace is pinned to stable 1.90.0
(`rust-toolchain.toml`), so this crate is a DETACHED workspace (note the
empty `[workspace]` table in `Cargo.toml`) and is invoked with an
explicit nightly.

```sh
rustup toolchain install nightly
cargo install cargo-fuzz
```

## Running

`make fuzz` runs every target for a short CI budget (~60s each) and
degrades with a clear message if nightly or `cargo-fuzz` is missing.

Ad hoc, long runs:

```sh
cargo +nightly fuzz run fuzz_parser                 # until Ctrl-C
cargo +nightly fuzz run fuzz_parser -- -max_total_time=3600
FUZZ_TIME=300 make fuzz                              # 5 min per target
```

## Corpus

Seed inputs live under `corpus/<target>/`. `make fuzz` seeds the lexer
and parser corpora from `examples/` before running so the fuzzer starts
from real hematite/cuprite source. The seed files are not committed
(only this directory's `.gitkeep`); the fuzzer grows the corpus locally.
