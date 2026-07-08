# WO-42: Realized-domain IRs (L4 payload schemas + the staged build loop)

Status: in-progress (see "Progress" section below -- scope beyond
the vocabulary/doc slice needs its own dispatch)
Depends: WO-30 (payload store + PayloadRef channel), WO-22 engine
half (the geometry producer to promote), WO-24 engine half (the
layout producer to promote), WO-32 D1/D2 (the flownet payload and
`regolith-lower::extract` are the first in-pipeline consumers).
GATES: WO-32 D4b's end-to-end half (extraction over
realizer-produced geometry instead of hand-authored fixtures), WO-34
(run extraction over real records), WO-25 (IR-derived manufacturing
reports/BOM).
Language: Rust (`regolith-oblig` schemas, `regolith-api`/`regolith-py`
realized-input channel, `regolith-lower` consumption); Python
(realizer promotion in `regolith.realizer.*`, orchestrator staged
loop, regenerated `_schema/`)
Spec: AD-25 (normative; this WO is its machinery) + design-log
2026-07-08-cycle-24 D128; regolith/08 sec. 1 (L4); AD-5/AD-17/AD-18/
AD-22; `../design/22-mech-geometry-realizer.md` (the forward
contract being promoted); `../design/20-solver-abstraction.md`
sec. 8 (the channel + kind vocabulary).

## Goal

The spec's L4 "REALIZED IR" level becomes real: realized geometry
and placed/routed layout are schema-versioned, content-addressed IRs
produced once by the realizers and consumed in-pipeline by lowering
-- so extraction (WO-32/WO-34), rule packs, and backends read typed
IRs cited by digest, never native CAD/EDA files, and a geometry or
layout change invalidates exactly the obligations built on it.

## Deliverables

1. **`RealizedGeometry` schema** (`regolith-oblig`, schemars,
   AD-5/AD-18): WO-22's Python forward contract
   (`regolith.realizer.mech.schema` -- realized-geometry record:
   STEP content hash, mass properties, topology summary) PROMOTED
   into Rust per the AD-22 rule (the hand-written Python version is
   deleted or demoted to a drift check in the same change). Extend
   with the fields the WO-32 extract seam reads (per-segment wetted
   geometry: flow areas, path lengths, bends, roughness class,
   elevation; wall data: E, thickness, diameter) and a per-stage
   structure. Payload kind `geometry.realized` (already in the D96
   vocabulary). One `SCHEMA_VERSION` bump for this WO's schema work
   (coordinate with whatever version is current at dispatch; bump
   ONCE); `make schema`; golden corpus re-keyed.
   **AMENDED (cycle 25, D131):** the landed shape drifted from the
   WO-32 extract seam's consumed record shape and is unified onto
   the seam's field list -- selector-keyed `paths` (segments:
   `role`, `flow_area`/`length`/`elevation_change` as `[lo, hi]`
   intervals, optional `bend {angle, radius}`, `roughness_class`
   label string validated against the extract seam's
   `ROUGHNESS_TABLE`, optional per-segment `wall`), REMOVING
   `RealizedStage`, `WettedSegment.bend_count`, the
   `RoughnessClass` enum, and per-stage `WallData` (never shipped
   to a consumer; no migration). "A per-stage structure" is
   realized by the pinned `<stage_name>.wetted` selector
   convention, not a stage list. `regolith-lower::extract` decodes
   this schemars type and deletes its private `RealizedRecord`
   mirror in the same change; extraction cites the supplied IR's
   payload digest (D128), so the in-record `snapshot_hash` dies
   with the mirror. One further `SCHEMA_VERSION` bump. Full
   rationale: design-log 2026-07-08-cycle-25 D131.
2. **`RealizedLayout` schema** (`regolith-oblig`): the elec
   placed/routed board content WO-24 produces -- board outline ref,
   placements (footprint, position, rotation, side), routed segment
   list (net, layer, width, length), copper summary, extracted
   parasitic slots, `.kicad_pcb` content hash pin. NEW payload kind
   `layout.realized`: add it to the D96 kind vocabulary in
   `../design/20-solver-abstraction.md` sec. 8 AND note it in the
   feldspar channel contract (feldspar OPEN-2 pins that list --
   record the addition in `../feldspar/docs/feldspar/`
   `09-model-integration.md` sec. 4's kind list in the same change).
3. **The realized-input channel**: `regolith-api::Session` compile
   calls accept realized-IR inputs (digest -> bytes, resolved by the
   caller; AD-17 purity: content-as-input, no IO in the pipeline);
   `regolith-lower` passes them to elaboration so
   `regolith-lower::extract` runs in-pipeline (D128) and extracted
   values carry the source IR digest as citation. The FFI crossing
   is coarse per AD-4 (one map of bytes, marshalled by `regolith-py`,
   reached via `compiler.py`). `regolith debug ir` gains a section
   listing the realized IRs supplied to the build (kind, digest,
   subject).
4. **Realizer promotion** (Python): `regolith.realizer.mech` emits
   `RealizedGeometry` as its primary semantic output (generated
   `_schema/` model), `put` into the WO-30 store; STEP stays a
   pinned side artifact + evidence. `regolith.realizer.elec` emits
   `RealizedLayout` the same way once its layout half runs (its
   KiCad-unavailable deferral stands -- the schema and the emission
   seam land now, exercised by the fixture-driven tests WO-24
   already uses). No pass, pack, or backend parses STEP/`.kicad_pcb`
   after this WO (grep-level reviewer criterion).
   **AMENDED (cycle 25, D130 -- the mech half's input contract).**
   The first deliverable-4 dispatch correctly escalated: the six
   extract-seam measures are not derivable from a `FeatureProgram`
   plus a B-rep solid (no wetted marker, no material source, no
   roughness mapping, no flow-path bend concept). Resolution: the
   wetted-path decomposition is DECLARED in the realizer's input.
   `regolith.realizer.mech.schema::FeatureProgram` gains part-level
   `flow_paths` (selector `<stage_name>.wetted` + declared
   segments: role, optional `bore` feature ref, Cause-tagged
   `flow_area`/`length`/`elevation_change`, optional `bend`,
   `roughness_class` label, optional geometric `wall`) and
   `material_props` (resolved E/density values, Cause-tagged,
   producer-side -- the realizer owns no physics table, WO-22 cut
   #2 stands); `FEATURE_PROGRAM_SCHEMA_VERSION` 1 -> 2. The
   realizer's duty is validate-and-emit: cross-check declared
   segments against the realized solid where geometry fixes the
   answer, emit declared measures as `[lo, hi]` intervals
   (degenerate points legal v1), and raise a named `RealizeError`
   on declaration/solid disagreement -- never guess, never
   silently prefer either side. Hand-authored `FeatureProgram`
   fixtures declaring `flow_paths` are legitimate producers until
   lowering populates them from hematite `.cavity(inlet=...)`
   queries (deferred, hematite/07 sec. 2a). Landing order: D131's
   shape unification and the `FeatureProgram` v2 extension are
   independent; the validate-and-emit pass + store `put` seam need
   both. Full rationale: design-log 2026-07-08-cycle-25 D130.
5. **The staged build loop** (orchestrator): lower -> realize
   (producing new IRs) -> re-lower with them, to a fixed point;
   termination by content addressing (unchanged IR inputs ->
   byte-identical re-lower, INV-10); every iteration logged with the
   IR digests that changed. Lockfile rows for realized IRs carry
   `cause: realizer(<pack>)` (INV-21).
6. **Docs**: AD-25 marked implemented where landed; regolith/08
   sec. 1 note updated from "decided" to "landed"; design/22's
   forward-contract section marked promoted; WO-22/24/34/25
   amendment notes flipped to point at the landed channel; this WO's
   Status line.

## Acceptance criteria

- The WO-22 fixture part round-trips end to end: the mech realizer
  emits a `RealizedGeometry` into the store; a re-lower consumes it;
  `regolith-lower::extract` values match the hand-computed fixture
  numbers to exact interval bounds and are cited to the IR digest.
- Changing the fixture geometry changes the IR digest and BREAKS the
  dependent payload goldens (the G42 anti-staleness property, proven
  with a second geometry variant).
- Same-source determinism: two staged builds produce byte-identical
  IR digests and payload digests; the staged loop terminates in one
  re-lower when realization adds nothing new (INV-10 test).
- A build whose geometry IR is absent lowers with the
  pre-realization placeholder intact and dependent obligations
  honestly indeterminate, naming the missing IR (D128's placeholder
  rule).
- Schema drift check green (`make schema` no-op after regen); no
  hand-written Python mirror of either schema survives (AD-22
  promotion verified by grep).
- `make check` green.

## Progress (this dispatch)

This pass scoped the whole WO per the dispatch protocol (README.md)
and landed the lowest-risk, no-code-dependency slice so a later
dispatch can proceed without re-deriving scope. Landed:

- **D2's doc half**: `layout.realized` added to the D96 kind
  vocabulary in `../design/20-solver-abstraction.md` sec. 8.3, and to
  the feldspar channel contract kind list
  (`../../feldspar/docs/feldspar/09-model-integration.md` sec. 4),
  in the same change (WO body's explicit requirement). `PayloadRef`
  itself (`crates/regolith-oblig/src/payload.rs`) needs no code
  change for a new kind string -- `kind: String` is unconstrained,
  confirmed by reading the struct.
- **Deliverable 1, schema half (this dispatch):** the `RealizedGeometry`
  schema landed in Rust (`crates/regolith-oblig/src/geometry.rs`):
  `RealizedGeometry` (feature-program hash, STEP content hash,
  `TopologySummary`, `stages: Vec<RealizedStage>`), `RealizedStage`
  (id, `wetted_segments: Vec<WettedSegment>`, `wall: Option<WallData>`),
  `WettedSegment` (flow area, path length, bend count, roughness
  class, elevation) and `WallData` (modulus, thickness, diameter) --
  the fields the WO-32 `regolith-lower::extract` seam needs, per this
  WO's field list. `content_digest()` mirrors
  `FlownetPayload::content_digest` (AD-18, `geometry.realized` domain
  tag; the D96 vocabulary entry needed no change). Exported via
  `regolith_oblig::encoding::export_schemas` and regenerated into
  `python/regolith/_schema/models.py` (`make schema`).
  `SCHEMA_VERSION` bumped once, 10 -> 11 (see coordination note below);
  golden corpus re-keyed (`tests/golden/data/*.json`, hash-values-only
  diff verified).
  AD-22 promotion: `python/regolith/realizer/mech/interpreter.py`'s
  hand-written `TopologySummary`/`RealizedGeometry` classes are
  DELETED; `realize_feature_program` now returns a thin non-schema
  `RealizedGeometryArtifact` (raw STEP bytes, a side artifact per this
  WO's own text, + the generated `RealizedGeometry` payload).
  `regolith.realizer.mech.model` and its tests updated to the new
  `realized.geometry.<field>` access pattern. `make check` green
  (fmt, clippy, ty, guard-core, schema-check, Rust + Python tests).
  **Stub left for deliverable 4:** `RealizedGeometry.stages` is
  emitted as `[]` in `realize_feature_program` -- per-stage
  wetted-geometry/wall-data extraction from the realized build123d
  solid (walking `FeatureProgram` stages, computing flow areas/path
  lengths/bends/roughness/elevation and wall E/thickness/diameter from
  the solid) is NOT implemented; a TODO comment marks the exact spot
  in `interpreter.py::realize_feature_program`. This is deliverable
  4's realizer-promotion work, explicitly out of this slice's scope.
  **Coordination note (schema-version race), RESOLVED at integration:**
  this dispatch observed an in-flight WO-32 D4a change
  (`Obligation.payloads: Vec<PayloadRef>`, D129) claiming version 10
  and bumped to 11 to avoid colliding. D4a landed separately and
  cleanly took 10; this WO's rebase onto that landed state confirmed
  10 -> 11 is the correct, final, non-conflicting ordering -- no
  squash needed.
- This status/progress note.

**Deliverable 3, the realized-input channel (this dispatch, second
pass):** landed end to end.
- `regolith-lower`: new `realized_input` module -- `RealizedInput`
  (`kind`, `subject`, `bytes`) and `RealizedInputs` (a `BTreeMap<digest,
  RealizedInput>`, AD-6 deterministic iteration), re-exported at the
  crate root. `lower()`/`lower_and_discharge()` gain a `realized_inputs:
  &RealizedInputs` parameter, threaded to `claims::build_obligations`
  and its `push_fluid_obligations` sub-pass.
- `regolith-lower::flownet_lower`: a new, additive `RealizedFlownetInputs`
  (wraps `AstFlownetInputs`; `geometry()` matches a `from=<ref>` edge's
  subject against the supplied `RealizedInputs`, extracting through the
  existing `extract_path` seam when found, deferring to `GeomExtract`
  otherwise) -- the WO's D128 in-pipeline wiring, kept minimal per the
  dispatch note not to touch `claims.rs`/`flownet_lower.rs` beyond a
  small additive hook (WO-32 D4a/D4b own the rest of that surface;
  nothing here conflicts with their `push_fluid_obligations` body,
  which is unchanged except for the new parameter it threads through).
- `regolith-api::Session::check`/`compile` gain the same
  `realized_inputs: &regolith_lower::RealizedInputs` parameter (caller-
  resolved, no IO added -- AD-17 purity preserved). New
  `regolith_api::debug_ir(paths, realized_inputs) -> Result<String,
  CoreError>`: runs `check()` and renders the compiler's own IR-stage
  counts plus a "realized IRs supplied" section (kind, digest, subject),
  `(none supplied)` when empty.
- `regolith-py`: `CoreSession.check`/`compile` and a new `debug_ir`
  pyfunction accept the coarse `list[(digest, kind, subject, bytes)]`
  crossing (AD-4 -- one list, not per-field calls), defaulting to `[]`
  via `#[pyo3(signature = ...)]`. `_core.pyi` updated (`RealizedInputEntry`
  type alias, new/changed signatures, `debug_ir` stub) and passes the
  WO-18 stub-consistency drift test.
- `python/regolith/compiler.py`: new frozen pydantic `RealizedInput`
  (`digest`, `kind`, `subject`, `payload_bytes`); `check`/`compile` gain
  `realized_inputs: tuple[RealizedInput, ...] = ()`; new `debug_ir(paths,
  realized_inputs=())` facade function.
- `regolith debug ir` (`python/regolith/cli/app.py`): the `ir` stage
  (previously unimplemented -- `debug_dump("ir", ...)` unconditionally
  panicked) now runs the real pipeline via `compiler.debug_ir`; `tokens`/
  `cst`/`ast` are unchanged. The CLI does not yet expose a flag to
  resolve realized-IR digests against the WO-30 store, so it always
  passes an empty channel today -- that resolution is the staged-build-
  loop orchestrator's job (deliverable 5), noted in the command's
  docstring rather than silently implied.
- Also fixed: `crates/regolith-ls` (WO-38's language server, which
  predates this dispatch) called `Session::check()` with the old
  arity; updated to pass an empty `RealizedInputs` (the LSP has no
  realized-IR source yet -- unaffected by this WO's scope).
- Tests: `regolith-lower` (new `realized_input` unit tests,
  `RealizedFlownetInputs` extract/defer tests in `flownet_lower.rs`),
  `regolith-api` (`Session::check` realized-input threading test,
  `debug_ir` tests), Python (`tests/test_ffi_bridge.py`,
  `tests/test_cli_app.py`). `make schema` not needed (no schema/type
  changed, no `SCHEMA_VERSION` bump -- this deliverable adds a runtime
  channel, not a wire-format type). `make check` green (fmt, clippy
  `-D warnings`, ty, guard-core, schema-check, Rust + Python tests,
  357+ tests total).
- **Escalation, none.** No design ambiguity was hit; the minimal-hook
  boundary the dispatch prompt set (do not touch `claims.rs`/
  `flownet_lower.rs` beyond an additive struct) was sufficient to close
  the WO text's literal requirement ("`regolith-lower::extract` runs
  in-pipeline... extracted values carry the source IR digest as
  citation") without touching WO-32 D4a/D4b's own body.
- **Deliberately NOT done here** (explicitly out of this dispatch's
  scope per the coordinator's brief): deliverable 2 (`RealizedLayout`
  schema), deliverable 4's realizer-`put`-into-store emission seam and
  the mech per-stage wetted-geometry/wall-data extraction stub left by
  the first pass, deliverable 5 (the staged build loop). A CLI flag
  resolving realized-IR digests against the WO-30 store for `debug ir`
  is also not built -- that channel only has a real orchestrator-side
  producer once deliverable 5 lands.

**Escalation -- deliverable 4's mech half (third pass), RESOLVED by
cycle 25.** The stage-extraction dispatch refused to guess (correctly,
per the dispatch protocol): the `FeatureProgram` input contract had no
wetted/cavity marker, no material-property source, no roughness-class
mapping, and no flow-path bend concept, so nothing in the schema fixed
what `RealizedGeometry`'s per-stage data should contain. The recon also
exposed a latent second blocker: deliverable 1's landed shape and the
extract seam's consumed `RealizedRecord` shape had drifted apart
(`bend_count` vs `bend {angle, radius}`, a 3-value roughness enum vs
the 5-label process table, point scalars vs `[lo, hi]` intervals,
stage list vs selector-keyed paths), while deliverable 3 pipes
realized-input bytes straight into `extract_path`, which decodes the
SEAM shape -- deliverable 4 had no single target to emit. Owner
resolution: design-log 2026-07-08-cycle-25 -- D130 (declared
`flow_paths` + `material_props` in `FeatureProgram` v2;
validate-and-emit realizer duty) and D131 (one wire shape, the
consumer's, in `regolith-oblig`; the seam's private mirror deleted).
Deliverables 1 and 4 carry matching amendment notes above; the mech
half is re-dispatchable against them.

**Escalation -- scope, not ambiguity (first pass, superseded above for
deliverable 3).** Deliverables 3, 4 (remainder),
5 are each independently substantial (a NEW `RealizedLayout` schema
with no existing Python source of truth yet since WO-24's layout half
only has KiCad-unavailable deferral fixtures -- deliverable 2; the
`regolith-api::Session`/FFI realized-input channel per AD-4's coarse
one-map-of-bytes crossing -- deliverable 3; `regolith-lower::extract`
in-pipeline wiring per D128 and the mech per-stage wetted-geometry/
wall-data extraction stub left by this dispatch -- deliverable 4
remainder; the orchestrator staged fixed-point loop with INV-10
termination proof -- deliverable 5). None of these has a design
ambiguity blocking it (AD-25/D128 already answered every open question
this dispatch found) -- the remainder is implementation volume across
`regolith-oblig`, `regolith-api`, `regolith-py`, `regolith-lower`,
`compiler.py`, and three Python realizer/orchestrator modules, each
needing its own hierarchical plan and its own `make check` cycle.
Recommendation for the next dispatch: 2+4 elec layout schema+emission
as one unit, 3 the FFI channel as a second gating both, 4's mech
stage-extraction remainder as a third (can run alongside 3), 5 the
staged loop last since it depends on 3.

Remaining (not started, tracked here so nothing is silently dropped,
updated after the deliverable-3 dispatch above): deliverable 2
(`RealizedLayout` schema + `layout.realized` emission); deliverable 1's
D131 shape unification (oblig schema + extract-seam mirror deletion +
fixture re-key + one `SCHEMA_VERSION` bump); deliverable 4's remainder
(the D130 `FeatureProgram` v2 extension, the validate-and-emit realizer
pass replacing the `stages: []` stub in
`interpreter.py::realize_feature_program`, and the realizer
`put`-into-WO-30-store emission seam for `RealizedGeometry`);
deliverable 5 (the orchestrator staged fixed-point
loop, INV-10 termination proof, `cause: realizer(<pack>)` lockfile
rows) -- depended on deliverable 3's channel, now available to build
against; deliverable 6's remaining doc updates (AD-25 "implemented
where landed" flip, regolith/08 sec. 1 "decided" -> "landed", design/22's
forward-contract section marked promoted, WO-22/24/34/25 amendment
notes -- deliverable 3's own landing is recorded above, not yet folded
into those cross-doc flips). Acceptance criteria still open: the WO-22
fixture end-to-end round-trip through a REAL orchestrator-resolved
store `put` (deliverable 3's Rust-side channel is proven with hand-
built fixtures in `regolith-lower`/`regolith-api` tests, not yet with a
real `regolith.realizer.mech` emission -- that wiring is deliverable
4's remaining job); the G42 anti-staleness property over a second
geometry variant; same-source determinism across a staged build
(needs deliverable 5's loop); the WO-30-store-backed `debug ir` CLI
flag (needs deliverable 5's resolver). Deliverable 1's schema-drift/
no-hand-written-mirror criteria remain met (unchanged by this pass).

## Non-goals

- New realizer capability (feature coverage, KiCad-real runs --
  WO-22/WO-35 territory; this WO promotes what exists).
- Solving anything (pack territory).
- Firmware/ELF map data as an IR (future; enters by the AD-25 rule
  when WO-37 needs it -- record, do not pre-build).
- Parametric geometry descriptors (`geometry.parametric` is a
  DISTINCT existing kind; untouched here).
- Salsa-style incremental re-lowering (the staged loop re-runs the
  whole pure pipeline; artifact-level incrementality via content
  addressing is already the AD-2 risk-register position).
