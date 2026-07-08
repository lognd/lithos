# WO-32: Fluorite lowering (flownet payload + the extraction seam)

Status: in-progress (D1+D2+D3+D4a+D4b+D5-partial landed; D6 and D5's
escalated FOPEN-1 half remain for the next dispatch -- see this
session's close-out note below)

DECISION NOTE (cycle 24, D128/AD-25 -- closes this WO's escalated
extraction-timing question): extraction runs IN-PIPELINE, per
fluorite/03 sec. 1's ratified wording taken literally.
`EdgeParams::GeomExtract` is ONLY the pre-realization placeholder --
an edge whose implementing part has no realized geometry IR yet
lowers with the selector intact and its dependent obligations stay
honestly indeterminate naming the missing IR; it is NEVER resolved
at discharge time. Realized geometry reaches the pipeline as a
compile INPUT (bytes by digest, orchestrator-resolved -- AD-17
purity preserved); the full realized-input channel and the
`RealizedGeometry` schema promotion are WO-42, which gates only this
WO's END-TO-END half -- D4a/D4b/D5/D6's machinery proceeds now
against hand-authored realized records (blessed as fixtures by the
dependency note below).

## Dispatch split (progress ledger)

This WO is landed in dependency order across dispatches:

- **D1 -- FlownetPayload schema (DONE).** `regolith_oblig::flownet`
  (fluorite/03 sec. 2): medium/nodes/reference/edges/states, the
  `EdgeParams::GeomExtract` selector seam, optional wall `Compliance`,
  `ScalarInterval` boundary fields. Exported from `export_schemas`,
  content-addressed under the `flownet` domain tag (AD-18).
  `SCHEMA_VERSION` bumped 8->9 (once); `_schema/` regenerated via
  `make schema`; the golden corpus was re-keyed (hash values only --
  counts and diagnostics unchanged) since the version folds into every
  content address.
- **D2 -- routed-geometry extraction seam (DONE).**
  `regolith_lower::extract`: pure, IO-free (`extract_path(bytes,
  selector, medium)`) producing per-segment flow area / length / bend /
  roughness (process-capability table) / elevation change, plus wall
  compliance + distensibility + Korteweg wave speed. Result carries a
  per-segment `role` slot so WO-34 wire runs share it verbatim (a fluid
  edge is a single-segment run). Errors are `ExtractError` (thiserror).
  Extraction surface + unit tests only.
- **D3 -- fluid lowering passes (DONE, integrated to master lineage
  this dispatch).** `flownet_lower.rs`/`elaborate_flownets` cherry-picked
  from branch `wo32-d3456` (edb4134) cleanly onto current master
  (36486e9); rebuilds and its 10 unit tests pass unmodified. Elaborates
  flownets per fluorite/03 sec. 1: calls `extract` for `from=` edges,
  builds `FlownetPayload`s, threads `driven_by=` promise givens,
  resolves curve/compliance record refs, keeps state domains symbolic.
  Still inert/unwired into the pipeline (no caller yet) -- that is D4b.
- **D4a -- claim lowering (DONE).** Prerequisite mechanics
  (`Obligation.payloads: Vec<PayloadRef>`, SCHEMA_VERSION 9 -> 10)
  landed in an earlier session on this dispatch's branch. This
  session landed the pass itself:
  - `flownet_lower::AstFlownetInputs` (the first REAL, non-test
    `FlownetInputs` impl -- previously only `FakeInputs` in the unit
    test module existed): harvests a `medium name -> props: registry(
    <ref>) ref name` index once from the parsed `.fluo` AST (the
    ONLY data claims.rs's PURE pipeline has on hand at this point,
    AD-17). `geometry`/`compliance` honestly return `None` --
    realized-geometry bytes and registry-record CONTENTS are IO,
    which `regolith-lower` never touches (`crates/regolith-lower/src/
    lib.rs`'s own module doc: "no IO, no rendering"); every `from=`
    edge falls back to its already-built deferred `GeomExtract`
    selector rather than a fabricated extraction. `medium`/`record`
    thread real ref NAMES with an empty digest (mirrors the existing
    deferred-ref idiom at `flownet_lower.rs:339`/`:799`) until D4b's
    orchestrator-backed `FlownetInputs` (reading the WO-30 content
    store) resolves real bytes and re-elaborates.
  - `claims.rs::push_fluid_obligations`: a fluorite `require` group is
    NOT a plain `Decl` (`File::fluid_requires` is its own accessor --
    "a top-level require is NOT a plain Decl", regolith-syntax/
    ast.rs), so it never reached `build_obligations`'s `file.decls()`
    loop at all -- confirmed by reading, not assumed. Added a
    dedicated pass: elaborates every file's flownet(s) via
    `elaborate_flownets` + `AstFlownetInputs`, then for each
    `fluids.*`-predicate require line (v1: one flownet per file,
    fluorite/02 sec. 1 "one medium per connected subnet") builds an
    `Obligation` whose `payloads` carries one `PayloadRef{ kind:
    "flownet", digest: payload.content_digest(), origin:
    <flownet name> }`; `subject_ref` is that same digest (fluorite has
    no `EntityDb` snapshot to key on the way hematite/cuprite decls
    do). 4 new unit tests in `claims.rs` cover the wiring end to end
    (payload-ref population, determinism, non-fluid-source silence).
  - Fallout: `cnc_router`/`espresso_machine` (pre-existing corpus
    members that already contain `.fluo` sources) legitimately gained
    obligations from this newly-wired pass; their goldens were
    regenerated (`REGOLITH_UPDATE_GOLDEN=1`) and reviewed -- purely
    additive key sets, no removed/changed entries. `make check` green
    (Rust `cargo test -p regolith-lower`: 105 passed; Python: 336
    passed, 21 xfailed). No `SCHEMA_VERSION`/schema change this
    session, so no `make install` rebuild was needed.
  - NOT done (explicitly out of this dispatch's scope, see D4b/D5/D6
    below): real geometry/compliance-record IO resolution (so every
    `from=` edge's payload still carries a deferred `GeomExtract`
    selector, not extracted scalars, until D4b); the FOPEN-1/
    transient-no-compliance checks (D5); `forall`-wrapped require
    lines (same known limitation as the generic claims path already
    documents at the top of this file -- sweep-domain detection needs
    grammar-surface structure this pass does not have).
- **D4b -- payload emission (DONE).** `LowerOutput.flownets` /
  `BuildPayload.flownets` (`IndexMap<String, FlownetPayload>` --
  no `FlownetName` newtype exists anywhere in the codebase, so the
  WO body's type mention is taken as descriptive, not literal; `String`
  matches every existing flownet-name usage in `claims.rs`/
  `flownet_lower.rs`) rides `SCHEMA_VERSION` 11 -> 12 (`make schema`
  regenerated; the golden corpus was re-keyed, hash values only --
  counts and diagnostics unchanged, same mechanics as every prior
  bump).
  - `crates/regolith-lower/src/claims.rs`: `push_fluid_obligations` now
    returns the `Vec<ElaboratedFlownet>` `elaborate_flownets` already
    built (it was the sole call site, AD-22 applied within a crate --
    no second elaboration for emission), threaded onto a new
    `ObligationSet.flownets` field.
  - `crates/regolith-lower/src/output.rs` /`lib.rs`: `LowerOutput`
    gained `flownets: IndexMap<String, FlownetPayload>`, populated in
    both `lower()` and `lower_and_discharge()` from
    `obligation_set.flownets` (name -> payload, source/elaboration
    order per AD-6).
  - `crates/regolith-api/src/session.rs`: `BuildPayload` gained the
    same `flownets` field, copied verbatim from `LowerOutput` in
    `build_output()`. `regolith-py`/the FFI needed NO changes --
    `BuildPayload` serializes generically via serde, so the new field
    crosses the boundary automatically.
  - Python: `python/regolith/orchestrator/payload_store.py` gained
    `PayloadStore.put_at(digest, data)` -- a caller-pinned-digest
    write, distinct from `put()` (which computes its own digest from
    bytes). This was a REQUIRED addition, not a convenience one: the
    digest already embedded in an obligation's flownet `PayloadRef` is
    `FlownetPayload::content_digest()` (Rust, AD-18 canonical CBOR +
    domain tag + `SCHEMA_VERSION`), which does NOT equal
    `blake3(json_bytes)` (`put()`'s scheme, plain hash over whatever
    bytes it is handed). Using `put()` here would have stored the
    payload under a digest the obligation's `PayloadRef` never named,
    making `resolve()` miss at discharge time for every flownet.
    `put_at` stores under the digest as given, no recomputation --
    consistent with `resolve()`'s own no-integrity-check read path.
  - `python/regolith/orchestrator/orchestrate.py::build()`: after
    parsing obligations (discharge-needing tiers only), constructs a
    `PayloadStore` rooted at the build's project directory (a new
    `_project_root()` helper resolves `paths[0]` to its parent when it
    is a single source FILE, since `.regolith/` roots beside a
    project, not inside one -- this also fixes a latent same-shaped
    issue in the pre-existing `EvidenceStore.load/save(paths[0])`
    calls for the single-file case, though only this call site was
    touched, staying inside D4b's scope) and, for every obligation's
    `kind: flownet` `PayloadRef`, looks up the named flownet in
    `payload["flownets"]`, validates it through the generated
    `FlownetPayload` pydantic model, and `put_at`s its
    `model_dump_json()` bytes under the ref's own digest. A ref naming
    a flownet absent from the payload (should not happen, producer-side
    invariant) is logged and skipped, not raised -- the referencing
    obligation's discharge will honestly fail to resolve later via the
    already-modeled `payload_not_found` `Err`.
  - Tests: `claims.rs::fluid_source_populates_the_flownets_emission_set`,
    `lib.rs::lower_populates_flownets_from_a_fluid_source`, and
    `tests/test_orchestrator.py::
    test_build_puts_flownet_payloads_under_the_obligations_own_digest`
    (drives the full pipeline through `build()` and asserts
    `PayloadStore.resolve` hits on the obligation's own digest).
  - `make check` green (Rust: `cargo test -p regolith-lower` 106
    passed, workspace `cargo test` all crates green incl. the pinned
    `regolith-oblig::tests::schema_version_is_pinned` updated to 12;
    Python: 337 passed, 21 xfailed).
  - Per D128, extraction over REAL realizer-produced `RealizedGeometry`
    IRs (vs. this dispatch's hand-authored/`GeomExtract`-placeholder
    fixtures) remains gated on WO-42's realized-input channel landing
    in `regolith-lower::extract`'s actual call sites -- D4b's emission
    machinery itself has no such gate and is exercised end-to-end here
    against what D4a already produces.
- **D5 -- checks + golden corpus (PARTIAL, this session; the
  transient/no-compliance half is DONE, FOPEN-1 medium-mismatch is
  ESCALATED).**
  - `regolith-diag`: new code `codes::TRANSIENT_NO_COMPLIANCE` (E0203,
    next free `FluidNet`-family offset after E0201/E0202).
  - `crates/regolith-lower/src/claims.rs::push_fluid_obligation`:
    for every `fluids.volume_consumed([<edges>], ...)` claim line,
    checks each named edge id against the elaborated `FlownetPayload`
    -- an edge whose `compliance` field is `None` (no `compliance=`
    record AND no realized-wall extraction; `03` sec. 1's "record
    takes precedence over extraction" already folds both sources into
    that one field) is undischargeable and gets E0203, sited to the
    claim line's span. `ObligationSet.diagnostics` (already a field,
    previously always empty) now carries these; `push_fluid_obligations`
    threads it through -- `regolith-lower/src/lib.rs` was already
    wired to extend the pipeline's diagnostics from
    `obligation_set.diagnostics`, so no lib.rs/output.rs change was
    needed. An edge id the claim names but the flownet does not
    declare is silently skipped (a different, undeclared-reference
    problem, not this check's job). Scope: only the `volume_consumed`
    claim form is covered (matches fixture 43 and the WO's own D5
    line); a `peak(...)`-wrapped transient claim over a fluid edge is
    a documented gap for a follow-up, not guessed at here (see the
    `transient_compliance_edges` doc comment).
  - 4 new unit tests in `claims.rs` (positive: a `dp` claim on a
    compliance-less edge stays silent; negative: `volume_consumed`
    over a compliance-less edge fires E0203; unknown-edge-id stays
    silent). `cargo test -p regolith-lower`: 113 passed (up from 106).
  - Fixture 43 (`examples/negative/43_fluo_transient_no_compliance.fluo`)
    flipped `# EXPECT-TODO: WO-32` -> `# EXPECT: E0203`, verified
    against real `regolith.compiler.check` output.
    `tests/golden/test_negative_corpus.py`: 24 passed / 20 xfailed (up
    from 23/21); `examples/negative/README.md` driver summary and
    EXPECT-TODO inventory updated to match.
  - **ESCALATION -- FOPEN-1 medium-mismatch (fixture 40) NOT
    implemented this session.** The check as specified needs
    edge->component->medium binding: fixture 40's `bad: Pipe(from=
    line.run)` edge would need to resolve `line.run`'s implementing
    part's OWN medium (`ShopAir`) and compare it against the net's
    declared `medium=Water` header. No wired machinery resolves that
    binding: `AstFlownetInputs`/`RealizedFlownetInputs::geometry`
    (`flownet_lower.rs`) only ever return net-level medium-props-by-
    name or raw extraction bytes, never a per-component medium tag,
    and no `impl FluidPort<medium=...>` binding exists anywhere in
    the codebase (grepped; zero hits) to read one from even if a
    companion hematite file existed. Structurally, the
    `FlownetPayload` schema itself cannot represent a mixed-medium net
    at all -- `regolith-oblig::flownet::MediumRef`'s own doc comment:
    "FOPEN-1 is enforced upstream of construction" -- so this is not a
    check "over the lowered payload" (D5's own framing) the way the
    compliance check is; it has to happen BEFORE/DURING payload
    construction, reading data the current elaboration inputs do not
    carry. Per the dispatch protocol (README.md sec. "Stick to the
    work order" / "on spec ambiguity, STOP and escalate"), this is
    left as a leaf that cannot complete cleanly without inventing a
    binding mechanism the WO does not specify. Fixture 40 stays
    `# EXPECT-TODO: WO-32` with its self-calibration note extended
    (see `examples/negative/README.md`'s inventory row). RECOMMENDATION:
    a follow-up WO (natural home: alongside WO-22's hematite `impl
    FluidPort` geometry-extraction work, since that is the same
    edge->component resolution FOPEN-1 needs) should thread a
    per-component medium tag through the extraction/elaboration
    inputs so this check has data to read.
  - `examples/fluid/` lowering goldens, the determinism test, and the
    INV-4 asymmetric-feed fixture (the rest of D5's own deliverable-5
    list) were NOT touched this session -- out of this dispatch's
    given scope (D5 checks + fixture flips only, per the dispatch
    prompt); left for the D6/close-out follow-up.
  - `make install` (maturin rebuild, required: `regolith-diag`/
    `regolith-lower` changed) then `make check`: GREEN (Rust workspace
    all green; Python 343 passed, 20 xfailed).
- **D6 -- docs (TODO).** Mark fluorite/03 implemented where landed;
  design/23 OpaqueIsland note; regolith/08 table row.

The DEMAND NOTE checks (FOPEN-1 mixed-medium; transient/volume-budget
no-compliance) ride D5 over the lowered payload; fixtures 40/43 stay
`# EXPECT-TODO: WO-32` until then.

---


DEMAND NOTE (from WO-31 D3 close-out): two fluid-discipline compile
checks are NOT front-end decidable and are deferred to this WO --
(1) FOPEN-1 mixed-medium rejection (needs edge->component->medium
binding), fixture `examples/negative/40_fluo_medium_mismatch.fluo`;
(2) the transient/volume-budget "neither compliance record nor
extractable wall" diagnostic (fluorite/03 sec. 1), fixture
`examples/negative/43_fluo_transient_no_compliance.fluo`. Both fixtures
are currently `# EXPECT-TODO: WO-32`; flip them to real `# EXPECT: Exxxx`
when this WO wires the checks over the lowered flownet payload.

Depends: WO-31 (front end), WO-30 (payload channel), WO-22 engine
half (realized-geometry records to extract from); the WO-29
remainder is upstream of LIVE-DESIGN extraction fixtures but NOT of
this WO's machinery (hand-authored realized records are legitimate
fixtures here -- the flownet payload itself is new production, not a
consumer side channel; AD-22 is satisfied because THIS WO is the
producer). GATES the feldspar fluids catalog having anything to
consume, and WO-34 (routed runs share deliverable 2's seam).
Language: Rust (`regolith-lower` fluid passes, `regolith-oblig`
FlownetPayload type); Python (regenerated `_schema/`, orchestrator
payload production wiring)
Spec: `docs/fluorite/03` (RATIFIED v1 -- normative for every rule
here); `../design/20-solver-abstraction.md` sec. 8.3 (the channel);
regolith/07 sec. 2; AD-5/AD-17/AD-18/AD-22/AD-23; AD-25 +
design-log 2026-07-08-cycle-24 D128/D129 (extraction timing +
the obligation payload channel);
design-log 2026-07-07-cycle-20 D93/D96/D99 (the seam).

## Goal

`.fluo` sources lower to ordinary obligations carrying a
content-addressed `FlownetPayload` ref plus scalar-interval givens,
with hydraulic/compliance parameters EXTRACTED from realized
geometry through one shared routed-geometry extraction module --
after this WO, `fluids.*` claims are real obligations any pack can
discharge, and hand-asserted hydraulic givens become unnecessary.

## Deliverables

1. **FlownetPayload schema** (`regolith-oblig`, fluorite/03 sec. 2
   verbatim): medium ref, nodes, reference, edges (kind, sense pair,
   params-or-GeomExtract, compliance-or-null, curve refs), states
   (edge params and net-level state variables). Schemars-derived;
   rides the WO-30 `SCHEMA_VERSION` line (bump once here if WO-30
   already shipped). Content address via the AD-18 encoder.
2. **The routed-geometry extraction seam** (D99/F102; ONE module,
   `regolith-lower::extract`): given a realized-geometry record ref
   and a path/role selector, produce typed extraction results --
   flow areas, length, bend angles/radii, roughness class, elevation
   change, and (from wall records: E, thickness, diameter) wall
   compliance + Korteweg wave speed. Pure and IO-free (AD-17): the
   record CONTENT is an input (the orchestrator resolves refs via
   the WO-30 store and passes bytes in); every result is cited to
   the geometry snapshot hash it came from. This module is shared
   verbatim by WO-34 (wire runs) -- design its result type with a
   segment list + per-segment environment slot now, used by fluid
   edges as a single segment run.
3. **Fluid lowering passes** (`regolith-lower`): elaborate flownets
   per fluorite/03 sec. 1 -- extraction for `from=` edges, record
   refs for curve/compliance params, promise-chain givens for
   `driven_by=` imposers, net checks via the AD-23 core (WO-31),
   symbolic state expansion (ONE swept obligation per claim;
   discrete axes into the WO-30 coverage/sweep encoding). Every
   fluid claim form lowers per the 03 sec. 3 table; the
   compliance-missing compile diagnostic (03 sec. 1) fires when a
   transient/volume-budget claim names an edge with neither record
   nor extractable wall.
4. **Payload emission**: `BuildPayload` gains
   `flownets: IndexMap<FlownetName, FlownetPayload>` (AD-4: payload
   field, not side artifact -- the D89 precedent); obligations
   reference flownets by content digest; the orchestrator `put`s the
   serialized payload into the WO-30 store at build time so
   discharge-time `resolve` works.
5. **Golden corpus**: the WO-31 `examples/fluid/` corpus lowers to
   golden obligation sets + payload JSON (snapshot-updatable);
   determinism test (same source twice -> identical payload
   digests, INV-10); INV-4 fixture: a symmetric manifold orbit with
   ASYMMETRIC feed refuses verify-one (givens-invariance).
6. **Docs**: fluorite/03 marked implemented where landed;
   `../design/23-lowering-output-surface.md` gains a one-line note that
   fluorite lowers with no OpaqueIsland debt (the F96 lesson applied
   forward); regolith/08 lowering-architecture table row for the
   fluid track.

## Acceptance criteria

- `regolith check examples/fluid/coolant_loop.fluo` (name per
  corpus) emits obligations whose `payloads` carry a resolvable
  `flownet` ref; `regolith debug ir` shows the elaborated net.
- Extracted parameters match hand-computed values for a fixture
  tube record (area, length, two bends, compliance) to exact
  interval bounds; the citation carries the geometry snapshot hash.
- A `driven_by=` imposer obligation's givens carry the promise ref
  (the cross-track chain is traceable end to end in the lockfile).
- Same-source determinism: byte-identical payload + obligation
  hashes across two builds.
- The dual-circuit `forall` fixture produces ONE obligation with a
  discrete axis (two enumerated points), not two obligations.
- No second extraction implementation exists (WO-34's reviewer
  criterion starts here: `extract` is the only module reading
  realized-record internals in `regolith-lower`).
- `make check` green; schema drift check green.

## Non-goals

- Solving networks (pack territory: feldspar fluids/prop).
- HxSegment COUPLED solving (the language guarantees shared zone
  datum names; the coupled solve is feldspar M8).
- Computed zone/config fields (WO-33).
- Wire-run extraction consumers (WO-34; the seam only, here).
- FOPEN-1/FOPEN-2 (compile-rejected upstream).
