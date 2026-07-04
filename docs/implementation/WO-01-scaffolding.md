# WO-01: Repository scaffolding (hybrid Rust/Python workspace)

Status: done
Depends: --
Language: both (see `00-architecture.md`; REWRITTEN by it -- this WO
creates the workspace that document specifies)

## Goal

A cargo-workspace + maturin + uv monorepo an agent can clone, run
`make install` on, and get a green `make check` -- with the compiled
(empty) `rockhead._core` extension importable from Python and one
end-to-end smoke test crossing the boundary.

## Deliverables

- `Cargo.toml` workspace: members `crates/*`; shared
  `[workspace.package]` (version, edition, license);
  `[workspace.lints]` (clippy pedantic subset, `-D warnings`);
  `[workspace.dependencies]` for the blessed set (AD-15 list:
  logos, rowan, serde, schemars, blake3, ciborium, rayon, thiserror,
  tracing, indexmap, camino, num-rational; dev: insta, proptest,
  criterion).
- `rust-toolchain.toml` pinned stable; `.cargo/config.toml` if
  needed for platform linkers only.
- All nine crates from AD-2 created with lib.rs module docstrings
  naming their substrate doc, one placeholder unit test each;
  `rockhead-py` as the pyo3 cdylib (abi3-py312) exposing
  `core_version()` and `init_logging()` only.
- `pyproject.toml`: maturin build backend, dist name `rockhead`
  (the settled umbrella name; languages hematite/cuprite -- see
  extension registry below), Python >= 3.12; deps
  `pydantic>=2`, `typani`, `python-dotenv`, `typer`, `httpx`; dev:
  `pytest`, `ruff`, `ty`, `coverage`, `datamodel-code-generator`.
  uv-managed (`uv.lock` committed).
- `python/rockhead/` package skeleton per AD-2 (`compiler.py` facade
  stub, `orchestrator/`, `harness/`, `quarry/`, `cli/`,
  `logging_setup.py` per `~/.claude/refs/logging.md`, `py.typed`,
  `_core.pyi` stub for the two exposed functions).
- **Extension registry module**: `rockhead-syntax`'s registry (may be a
  stub crate module at this WO) is the ONLY place the extension
  strings live, re-exported to Python. Per D78 the languages are
  named: **`.hem` (mech) and `.cupr` (elec)**; the corpus rename
  sweep has landed, so the module recognizes only `.hem`/`.cupr`
  (no legacy extensions).
- `Makefile` with the AD-13 target table (`install`, `dev`, `check`,
  `test`/`test-rs`/`test-py`, `snapshots`, `schema` (stub), `fmt`,
  `lint`, `typecheck`, `coverage`, `bench`, `fuzz` (stub), `build`,
  `clean`). `check` runs cheapest-first per AD-13.
- CI skeleton (`.github/workflows/ci.yml`): fast gate + 3-OS matrix
  + maturin-action wheel build per AD-12 (fuzz/determinism jobs may
  land as stubs marked TODO with the AD reference).
- `.gitignore` per the standard block plus `target/`, `.rockhead/`,
  generated-but-uncommitted artifacts; `git init` if not a repo.
- `cargo-deny` config (licenses, advisories, duplicate versions).

## Acceptance

- `make install && make check` green on a clean clone (linux at
  minimum; CI proves the matrix).
- `python -c "import rockhead; print(rockhead.core_version())"` prints the
  workspace version -- the smoke test crossing Rust->Python.
- A pytest asserts `rockhead._core` log records reach Python `logging`
  through the pyo3-log bridge (AD-8 proven end-to-end at day one).
- `cargo test` and `pytest` each collect and pass placeholder tests
  in every crate/package.
- No file may import `rockhead._core` except `rockhead/compiler.py` and
  `rockhead/logging_setup.py`; `make check` greps for violations (AD-4).
