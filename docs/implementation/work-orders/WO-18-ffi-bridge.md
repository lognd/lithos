# WO-18: FFI bridge, schema pipeline, typed facade

Status: done
Depends: WO-06, WO-13 (schemas exist); gates WO-14, WO-15
Language: both (`regolith-py`, `python/regolith/compiler.py`, `_schema/`
codegen)
Spec: `../00-architecture.md` AD-4/AD-5/AD-7/AD-8 (normative for this
WO); regolith `07` sec. 2 (obligations are self-contained and
serializable -- the fact the boundary design leans on)

## Goal

The one door between Rust and Python, complete: `CoreSession` /
`BuildOutput` bindings, the schema codegen pipeline, the typani
facade, typed stubs, and the drift checks that keep all of it honest.

## Deliverables

1. `regolith-py`: `CoreSession` (open project root / file set),
   `check()` / `compile()` under `allow_threads`, returning
   `BuildOutput` with: pre-rendered diagnostics (colored + plain),
   JSON payload getters (diagnostics, resolutions, obligations,
   snapshot hashes), native scalar getters (counts, verdicts).
   `format(text)`, `debug_dump(stage, path)`, `core_version()`,
   `schema_version()`. Every entry point catch_unwind-wrapped:
   panic -> `CoreBug` (with Rust backtrace), infrastructure error ->
   `CoreError`. Zero logic in this crate (marshalling only).
2. Schema pipeline: `make schema` = schemars JSON Schema export from
   `regolith-oblig`/`regolith-api` -> datamodel-code-generator -> pydantic
   v2 frozen models in `python/regolith/_schema/` (committed). CI drift
   check (regenerate + git diff --exit-code).
3. `regolith/compiler.py` facade: the ONLY importer of `regolith._core`;
   converts `CoreError` into typani `Result[T, CoreFailure]`; lets
   `CoreBug` propagate; asserts `schema_version` on import; parses
   JSON payloads into `_schema` models lazily (property-cached).
4. `regolith/_core.pyi` stubs covering the full binding surface, strict-
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

- `regolith check examples/systems/cubesat/` (via the facade, minimal CLI
  harness ok) returns a BuildOutput whose diagnostics render
  identically to the pure-Rust `regolith-api` test harness (one
  renderer, AD-7).
- Kill test: a deliberately panicking debug hook raises `CoreBug`
  with a Rust backtrace; the process survives; no other entry point
  can raise anything but `CoreError`/`CoreBug`.
- `make schema` is idempotent; CI drift job red on any hand edit to
  `_schema/`.
- ty --strict green over `regolith/` including `_schema/` and the stub.

## Implementation notes (cut scope, named per house rule)

`Session::check`/`compile` discover and parse every recognized source
file under the given roots and collect real parser diagnostics -- that
part of the pipeline (parse -> diagnostics -> rendered text) is fully
wired and tested. `BuildPayload.resolutions`/`.obligations`/
`.snapshot_hashes` are left empty: no work order before WO-18 wires an
`AST -> EntityDb -> IR -> Obligation` assembly driver (WO-07..13 land
those layers as standalone, tested libraries with no end-to-end
caller). `compile()` therefore delegates to `check()` -- there is no
"toy-model subset" discharge implementation anywhere in the repo to
call. Deliverable 6 (the obligation-hash round-trip property test) is
consequently CUT here for the same reason: there are no obligations in
a `BuildOutput` yet to round-trip. This assembly driver is the natural
scope of a follow-on work order; flagging it explicitly rather than
inventing a pipeline the architecture doc does not specify.
