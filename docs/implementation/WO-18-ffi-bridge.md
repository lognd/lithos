# WO-18: FFI bridge, schema pipeline, typed facade

Status: todo
Depends: WO-06, WO-13 (schemas exist); gates WO-14, WO-15
Language: both (`rockhead-py`, `python/rockhead/compiler.py`, `_schema/`
codegen)
Spec: `00-architecture.md` AD-4/AD-5/AD-7/AD-8 (normative for this
WO); substrate `07` sec. 2 (obligations are self-contained and
serializable -- the fact the boundary design leans on)

## Goal

The one door between Rust and Python, complete: `CoreSession` /
`BuildOutput` bindings, the schema codegen pipeline, the typani
facade, typed stubs, and the drift checks that keep all of it honest.

## Deliverables

1. `rockhead-py`: `CoreSession` (open project root / file set),
   `check()` / `compile()` under `allow_threads`, returning
   `BuildOutput` with: pre-rendered diagnostics (colored + plain),
   JSON payload getters (diagnostics, resolutions, obligations,
   snapshot hashes), native scalar getters (counts, verdicts).
   `format(text)`, `debug_dump(stage, path)`, `core_version()`,
   `schema_version()`. Every entry point catch_unwind-wrapped:
   panic -> `CoreBug` (with Rust backtrace), infrastructure error ->
   `CoreError`. Zero logic in this crate (marshalling only).
2. Schema pipeline: `make schema` = schemars JSON Schema export from
   `rockhead-oblig`/`rockhead-api` -> datamodel-code-generator -> pydantic
   v2 frozen models in `python/rockhead/_schema/` (committed). CI drift
   check (regenerate + git diff --exit-code).
3. `rockhead/compiler.py` facade: the ONLY importer of `rockhead._core`;
   converts `CoreError` into typani `Result[T, CoreFailure]`; lets
   `CoreBug` propagate; asserts `schema_version` on import; parses
   JSON payloads into `_schema` models lazily (property-cached).
4. `rockhead/_core.pyi` stubs covering the full binding surface, strict-
   ty clean; a stub-consistency test (introspect the extension's
   `__all__` against the stub).
5. pyo3-log bridge finalized (`init_logging`), tracing spans named
   per pass; a pytest proving Rust pass-boundary spans arrive as
   Python log records with fields intact.
6. Round-trip property test: BuildOutput JSON -> pydantic ->
   canonical dict -> equals Rust's canonical form; obligation
   content hashes computed in Rust match hashes recomputed over the
   Python-parsed payload's canonical CBOR (INV-1 across the
   boundary).

## Acceptance

- `rockhead check examples/cubesat/` (via the facade, minimal CLI
  harness ok) returns a BuildOutput whose diagnostics render
  identically to the pure-Rust `rockhead-api` test harness (one
  renderer, AD-7).
- Kill test: a deliberately panicking debug hook raises `CoreBug`
  with a Rust backtrace; the process survives; no other entry point
  can raise anything but `CoreError`/`CoreBug`.
- `make schema` is idempotent; CI drift job red on any hand edit to
  `_schema/`.
- ty --strict green over `rockhead/` including `_schema/` and the stub.
