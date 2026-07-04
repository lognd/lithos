# WO-19: Lowering pipeline (end-to-end assembly driver)

Status: in-progress (wired end-to-end + green; lowering depth partial)
Depends: WO-05..WO-13 (the libraries it wires), WO-18 (payload surface);
gates WO-15 golden corpus, the bulk of WO-17, WO-14 real inputs

> STATUS (cycle 11): the pipeline is wired end-to-end -- Session::check
> runs passes 1-5, Session::compile adds static discharge against a
> persisted `.rockhead/` evidence cache, BuildPayload is typed, schema
> is at v2, `make check` green. Over examples/cubesat the pipeline
> lowers 40 obligations + snapshot records (real, deterministic --
> INV-10 holds; obligations rose 21 -> 40 after the parser
> sibling-ejection desync was fixed, recovering the previously-ejected
> `require` blocks -- see docs/audit/TRIAGE.md). Value sources in nested
> blocks are now reached, so resolutions are Cause-typed and non-empty
> (INV-21 activated); the count is low only because the corpus is
> literal-heavy. RECORDED PARTIAL (needs fuller WO-05 grammar, not a
> defect). The conforming corpus is now clean over cubesat -- parse
> noise was cut 984 -> 31 by treating unknown top-level declarations as
> opaque (not errors) and dropping the false global duplicate-name
> check (INV-18 is scope-aware), then 31 -> 0 on cubesat by fixing the
> comment-led-body desync (TRIAGE cycle 11). Residual corpus parse
> diagnostics (18, all in mech `.hem`) are unrelated domain-body opaque
> constructs (`walk`/`constraints`/`regions`), not top-level ejections.
> Closing this to `done` needs the residual grammar (value-sources ->
> resolutions, impl/for name attribution), per-subject INV-20 gating,
> and INV-11 monomorphization.
Language: Rust (`rockhead-lower`, NEW crate per AD-17; `rockhead-api`
wiring; `rockhead-oblig` schema additions; `rockhead-py`/facade payload
surface refresh)
Spec: substrate/06 (execution ladder), substrate/07 sec. 2,
substrate/05, substrate/13 (INV-1/10/11/15/17/18/20/21/27);
`00-architecture.md` AD-17 (normative), AD-4/AD-5/AD-6/AD-8/AD-18

## Goal

WO-07..13 landed as standalone, tested libraries with no caller. This
WO builds the one assembly driver (AD-17): parsed source -> entity DB
snapshots -> semantic checks -> contract IR -> content-addressed
obligations -> (compile only) static discharge, populating every
`BuildPayload` field so `check`/`compile` return real data and the
golden corpus and invariant suite have something to bite on.

## Deliverables

1. Crate `crates/rockhead-lower/` per AD-17: pure (no IO, no `Err`),
   `lower(sources) -> LowerOutput` and
   `lower_and_discharge(sources, &mut cache) -> LowerOutput`; one
   `tracing` span per pass (`parse`, `lower.entities`, `lower.checks`,
   `lower.contracts`, `lower.claims`, `lower.discharge`); per-subject
   INV-20 gating; deterministic order everywhere (sorted file order,
   source decl order, blessed collections only).
2. Pass 2 (`entities.rs`): AST -> declaration table (imports + name
   resolution; ambiguity is E0301 data, INV-18) -> per-scope
   `EntityDb` snapshots via `PredictedDelta::commit`; every defaulted
   value becomes a `rockhead_qty::Resolution` (Cause-typed, INV-21).
3. Pass 3 (`checks.rs`): monomorphization expansion (INV-11), then
   queries, ownership/borrows, stages/scopes, profile DOF ledgers,
   symmetry orbit table -- each producing diagnostics (values).
4. Pass 4 (`contracts.rs`): contract IR construction + Mech/Elec
   ledgers + `close_budget` + conformance checks (INV-13/15).
5. Pass 5 (`claims.rs`): `RequireClaim` -> `Claim` -> one `Obligation`
   per sweep point; `subject_ref` = canonical snapshot hash (AD-18);
   hashes via `Obligation::content_hash` (INV-1 keys).
6. Pass 6 (`discharge.rs`): the WO-13 toy closed-form subset via
   `decide_margin` + `EvidenceCache`; cache hit on second run.
7. `rockhead-api` wiring: `Session::check` = passes 1-5,
   `Session::compile` = 1-6 with cache IO in `Session` (`.rockhead/`,
   `CacheCorrupt` on corruption); `BuildPayload` becomes typed
   (`Vec<Resolution>`, `Vec<Obligation>`, `Vec<SnapshotRecord>`, new
   `evidence: Vec<Evidence>`).
8. Schema surface: `SnapshotRecord` added to `rockhead-oblig`;
   `Resolution`/`Cause` gain `JsonSchema` and join `export_schemas`;
   `SCHEMA_VERSION` bumped; `make schema` regenerated; `_core.pyi`,
   native getters, and facade updated; WO-18's cut deliverable 6
   (obligation-hash round-trip across the FFI) implemented.

## Acceptance

- `Session::check` over `examples/cubesat/` returns non-empty
  obligations, resolutions, and snapshot records; every resolution
  carries a `Cause` (INV-21); double build is byte-identical on
  `payload_json()` (INV-10).
- `compile()` differs from `check()` by evidence: first compile
  discharges the toy subset, second compile hits the cache (WO-13's
  acceptance, now end-to-end).
- INV-20 fixture: a file with a parse/L1 error produces zero
  later-pass span records for that file (observable via pass logging).
- INV-27 fixture: a golden example split across two files joined by
  an import yields identical verdicts, resolutions, obligation keys,
  and snapshot hashes.
- INV-1 fixture: mutating each obligation key component (claim,
  subject, given, record hash) changes the content hash (cache miss).
- `make schema` idempotent, drift check green, ty --strict green;
  `make check` green; every `todo!("STUB WO-19")` gone and its
  `#[ignore]`d tests un-ignored before Status flips to done.

## Implementation notes

Module layout and public stub signatures for `crates/rockhead-lower/`
are specified in the cycle-11 design log (Fable architect escalation,
AD-17/AD-18). The crate is scaffolded architecture-first per the stub
convention: types + module layout + `#[ignore]`d tests land, then the
six pass bodies. Decision 2 (AD-18 canonical-encoder move to
`rockhead_util::canon`) must land BEFORE WO-19 records any golden
hashes -- migrating `EntityDb::snapshot_hash` changes snapshot values,
and nothing durable pins the old ones yet.
