# WO-48: calcite lowering + `std.civil` reference packs

Status: todo
Depends: WO-47 (typed calcite CST), WO-45 (the stdlib home it adds
`std.civil` to), WO-28 engine remainder (the rule-pack format the
code packs are written in -- the egress/occupancy L2 checks do NOT
depend on it and may land first if WO-28 is still open; split the
dispatch on that seam). Pattern: WO-32 (fluorite lowering -- the
proven grammar->lowering->schema->corpus->docs slice sequence; use
the same D1..Dn split discipline from its close-out).
Language: Rust (`regolith-lower`, `regolith-ir`/`regolith-oblig`
schema) + Python (packs, orchestrator seam); one SCHEMA_VERSION
bump coordinated at dispatch.
Spec: docs/spec/calcite/03-lowering.md (post-WO-46, NORMATIVE),
00-architecture.md AD-25 (realized-IR growth rule) / AD-22
(one producer per fact), design-log 2026-07-08-cycle-26 D133/D135;
regolith/13 INV-15 (ledger conservation -- the load-path check's
family), INV-24 (release gate); the WO-32 close-out (the
FlownetPayload precedent every step mirrors).

## Goal

Calcite designs check and build for real: circulation/egress and
load-path L2 checks fire over the typed CST, calcite claims lower
to obligations, the frame IR exists as a realized-domain payload
(AD-25 growth rule), and `std.civil` ships the load-combination +
occupancy/egress reference content the corpus cites -- ending the
last phantom references.

## Deliverables

1. L2 static checks in the lowering passes per 03-lowering's
   definitions: egress (travel distance/exit width/dead-end over
   the circulation graph), occupancy arithmetic, load-path
   conservation on the AD-23 net (a load with no path to a
   foundation is a leak -- the INV-15 family, its own E-code
   block); honest-pass + deliberate-violation fixtures each.
2. Claim lowering: the 03-lowering claim-family table ->
   obligations with correct given/payload citation (the
   `push_fluid_obligations` precedent in `claims.rs`).
3. Frame IR: the 03-lowering sec. 4 field list as a schemars schema
   in `regolith-oblig`; kind string `frame` (DECIDED, D139/D145 --
   both kind tables already carry it, cycle 27; do not re-extend);
   emission from the lowered member/transfer/load data;
   content-addressed via the ONE encoder.
4. `std.civil` under `stdlib/` (WO-45's layout): load cases +
   combination sets, occupancy/egress tables, starter structural
   records; the reference building-code rule pack IF the WO-28
   format exists by then, else its package home + records with a
   `# TODO(WO-28)` marker (record the cut).
5. Closed-form structural harness models (the `harness/models/`
   precedent): beam utilization + deflection against the frame IR's
   members -- enough for the corpus's non-FEA claims; feldspar
   consumption of the frame IR is feldspar-side follow-up (note it
   in feldspar's TODO, do not implement there).
6. Goldens: calcite corpus enters the golden/obligation corpus;
   fluorite/hematite/cuprite goldens unchanged.
7. Docs: 03-lowering flipped planned->implemented per section;
   regolith/08 + design/23 gain the calcite rows (the fluid-track
   precedent); regolith/11 sec. 8 `std.civil` entry flipped.

## Acceptance criteria

- The five-design corpus: violations fire (each L2 check proven
  both ways), clean designs produce stable obligation goldens.
- Frame IR round-trips through the payload store and appears in
  `regolith debug ir`.
- Zero golden churn outside calcite; `make check` green; one
  SCHEMA_VERSION bump.

## Non-goals

- FEA/frame solving (feldspar-side, its Phase 6 WO); BIM export;
  detailing; scheduling (charter sec. 7 stands as amended cycle 27).
- Drawing sheets and schedules backends (WO-50, D140) and cost
  takeoff estimators (WO-54, D147) -- both consume what this WO
  produces; note their gates in the close-out, do not build them.

## Slice B progress (frame payload IR + lowering emission)

Status: in-progress overall (Status line above stays `todo` -- slices
A and C are separate dispatches, still outstanding).

Scope covered by this slice: deliverable 3 (`FramePayload` schema +
its lowering emission) and the deliverable-4 obligation rows that
reference the frame. Slice A (E0205/E0206/E0207 + tributary-E0209 net
reachability) and slice C (`std.civil` stdlib records, the code-pack
rule pack, closed-form beam harness models) are NOT touched here.

Landed:

- `FramePayload` in `crates/regolith-oblig/src/frame.rs`: joints (with
  an `Option<JointAt>` position, `None` for a support-only joint whose
  anchor is unresolved), members (role/a/b/length/orientation/section/
  material/releases), supports, literal loads, and the combinations
  ref -- calcite/03 sec. 4's field list verbatim, mirroring
  `flownet.rs`. SCHEMA_VERSION 18 -> 19 (`regolith_util::canon` +
  `regolith-oblig`'s pinned test). The `Datum` discriminant is tagged
  `datum_kind`, not `kind`, to avoid perturbing the shared anonymous
  `Kind`/`Kind1`/... enum-name pool `datamodel-code-generator` assigns
  across the WHOLE exported schema document (a real trap hit and fixed
  during this slice -- see `encoding.rs`'s `export_schemas` comment).
- `crates/regolith-lower/src/frame_lower.rs`: pure, IO-free elaboration
  from parsed `.calx` structures into `FramePayload`s. Joint synthesis:
  member anchors (`from (refs..) to (refs..)`, read off the anchor
  line's `OpaqueIsland` -- the front end records it whole, never a
  typed `Field`) resolve against the file's `grid`/`level` datums
  (declaration-order index x spacing; declared elevation); two anchors
  sharing the same tuple coalesce onto one joint id, satisfying "member
  ends meeting at a shared anchor coalesce" (03 sec. 4); a
  point-anchored footing (`from (A, base) to (A, base)`) is legal,
  zero length, orientation `"point"`. A declared `support:` node with
  no member anchor of its own gets its OWN `support:<name>` joint with
  `at: None` -- v1 does NOT attempt to infer which member end a
  support physically sits at purely from the transfer graph (the
  corpus's transfer edges name which member/support pair is joined,
  never which specific end; inferring that would need real load-path
  traversal, slice A's job, not this one's). Section/material refs are
  name-only (digest is IO-resolved registry content, unavailable in
  this pure pass -- the `AstFlownetInputs` precedent); `releases`/
  support `fixity` stay honestly empty pending `std.civil` transfer/
  support-role records (slice C).
- Obligation emission: `push_calcite_frame_obligations` in `claims.rs`
  (the `push_fluid_obligations` precedent) -- one structure per file in
  v1 (every calcite corpus design declares exactly one `structure`);
  every require claim whose predicate matches one of the five 03 sec.
  5 frame-referencing forms (`civil.utilization`, `mech.deflection`,
  `civil.story_drift`, `civil.bearing_pressure`, `mech.first_mode`)
  gets a `PayloadRef{ kind: "frame", digest, origin }`. `LowerOutput`/
  `BuildPayload.frames` (name -> payload) threads through
  `regolith-api` exactly like `flownets`/`harnesses`; the Python
  orchestrator's `_put_frame_payloads` (mirrors `_put_flownet_
  payloads`) stores each referenced payload into the WO-30 store
  before discharge; `regolith debug ir` gained a `frames: N` line
  (the acceptance criterion: "Frame IR round-trips through the payload
  store and appears in `regolith debug ir`" -- verified: the frame
  payload is stored under its own AD-18 digest and the debug report
  counts it).
- Goldens: the five ratified calcite corpus designs (footbridge,
  retaining_wall, pole_barn, bus_shelter, small_office) lower with
  zero diagnostics and each emits the frame(s) 03 sec. 4 specifies;
  SCHEMA_VERSION 19 re-fold touched the WHOLE corpus (content hashes
  fold in `schema_version` unconditionally, same as every prior bump
  -- confirmed against the WO-50 SCHEMA_VERSION 18 precedent commit,
  not something specific to this slice's payload shape). Rust unit
  tests in `frame_lower.rs` cover: one frame per structure, shared-
  anchor coalescing (exactly two member-derived joints for the
  footbridge's twin-girder/deck fixture, not four), support-only
  joints carrying no fabricated position, role/section/material
  resolution (including the `section: free` `FreeKw`-not-`Ident`
  lexing wrinkle), span length/orientation derivation from grid
  spacing, the point-anchored footing legality case, literal load
  entry extraction, the `forall combo in <ref>` combinations read
  (and its honest-empty case when a require group names no sweep --
  the retaining-wall stability claim), and digest determinism.
- `make check` green end to end (fmt, clippy -D warnings, ty, guard-
  core, `cargo test --workspace`, `pytest` through the real wheel:
  566 passed, 3 skipped, 23 xfailed).

Cut/deferred, named explicitly (not silently dropped):

- Which specific member END a support attaches to (vs. just "this
  structure has this support") -- v1 gives every support its own
  anchor-less joint; a future slice wanting real reaction positions at
  supports needs either a grammar extension (an anchor on `support:`
  itself) or a load-path traversal that isn't this slice's to add.
- `releases`/support `fixity` are structurally present but always
  empty until `std.civil` transfer/support-role records exist (slice
  C's `dof: kept=` authoring) -- dependent obligations stay honestly
  indeterminate per the AD-25 rule, not fabricated.
- `combinations` is a name-only `RecordRef` (digest empty) -- pack
  identity resolution is registry IO, out of this pure pass; consumers
  resolve it the same way `section`/`material` name-only refs resolve.
- feldspar's `mech.struct` direct-stiffness consumption of the `frame`
  payload is feldspar-side follow-up (noted per the WO body; not
  implemented here).
- Drawing sheets (WO-50) and cost takeoff (WO-54) both consume this
  slice's `frame` payload; their own WOs' gates are unaffected --
  nothing here builds toward either.
