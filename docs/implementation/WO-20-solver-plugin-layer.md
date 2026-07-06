# WO-20: Solver plugin layer (packs + subprocess adapter)

Status: done (cycle 18)

> Close-out notes (recorded deviations, all argued): SCHEMA_VERSION
> 3->4 lives in regolith-util per AD-18 (one-line touch outside the
> "oblig only" scope line); orchestrator cache/discharge/orchestrate
> gained pack-aware keying + `BuildReport.pack_errors` (demanded by
> the acceptance criteria); `load_packs` returns a total
> `PackLoadOutcome` (skip-loudly semantics) rather than the design
> sketch's bare Result; `SolverSpec` carries `cost: int` +
> `version`, domain via signature tags (no DomainGuard type exists);
> `SolverResponse` carries `schema_version` + `coverage_bits`;
> non-finite bits or a missing settings digest on a
> non-deterministic solver are MalformedResponse (INV-10 enforced).
Depends: WO-13, WO-18 (schemas/FFI), harness spine (TODO.md sec. 6)
Language: Python (`regolith.harness`); Rust `regolith-oblig` for the
`SolverResponse` schema only (AD-5)
Spec: regolith/07 sec. 2-4; regolith/11 sec. 3 (`models` kind);
design: `20-solver-abstraction.md` (normative for this WO), AD-19

## Goal

External model packs load into the harness registry by entry-point
discovery, and a non-Python solver executable can discharge an
obligation through one subprocess adapter speaking the existing
serialized schemas. No signing in this WO (that is WO-21).

## Deliverables

- `harness/plugin.py`: `PackInfo`, `load_packs(registry)` over entry-
  point group `regolith.model_packs`; deterministic composition
  (built-ins first, then packs sorted by name); `PackLoadError`
  (duplicate model id / entry point raised / bad signature) -- a bad
  pack is skipped LOUDLY (named in the build report), never a silent
  partial load. `default_registry()` gains the composition point.
- Evidence-hash keying extended per AD-19: fold the discharging
  model's `(pack_name, pack_version)`; built-ins carry
  `("regolith", MODEL_REGISTRY_VERSION)`. This touches
  `harness/evidence.py` and the Rust-side cache-key threading the
  same way BE-1 did.
- `SolverResponse` schema in `regolith-oblig` (+ schemars export,
  `make schema` regeneration, `SCHEMA_VERSION` bump).
- `harness/adapter.py`: `SolverSpec`, `SubprocessSolverModel(Model)`,
  `solve_via_subprocess`. Wire protocol per the design doc: request
  JSON on stdin, `SolverResponse` JSON on stdout, stderr bridged to
  logging, timeout enforced; every failure arm (`SpawnFailed`,
  `Timeout`, `MalformedResponse`, `SchemaVersionMismatch`,
  `NonzeroExit`) maps to `harness.adapter_error` indeterminate
  evidence. Non-deterministic solvers fold their settings digest
  (existing INV-10 mechanism); `solver_version` is always folded.
- Pack-protocol conformance suite `tests/packs/`: a reusable pytest
  module a pack runs against itself (registers, matches a synthetic
  obligation, discharges, keys fold pack version, determinism holds),
  exercised in-repo by a tiny fixture pack (a fake entry point + a
  fake solver executable that echoes a canned response).

## Acceptance

- A fixture pack installed in the test env is discovered, its model
  selected and discharged end-to-end via `orchestrator.build`; a
  duplicate-model-id pack is rejected with the named diagnostic.
- The fixture SUBPROCESS solver discharges an obligation; killing it
  / timing out / feeding it garbage each yields `harness.adapter_error`
  indeterminate (asserted distinct from violated), never an exception.
- Bumping the fixture pack's version changes the evidence cache key
  for its model's evidence and no other (INV-1 extension test).
- `make check` green; `make schema` drift-clean.
