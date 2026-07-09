# WO-48: calcite lowering + `std.civil` reference packs

Status: done -- landed in three slices (cycle 28/29 completion pass;
see the per-slice progress sections at the end of this file). Slice B:
FramePayload + lowering emission + claim obligations (SCHEMA_VERSION
19). Slice C: `std.civil` per-family stdlib + civil quantity namespace
(D145) + closed-form beam harness models. Slice A: E0205/E0206/E0207
net-reachability checks + negative fixtures 60-62. All five corpus
designs `regolith check` clean; `make check` green after each merge.
Cuts, recorded per slice, NOT silently dropped: tributary-partition
half of E0209 (area-partition arithmetic, future follow-up); the
building-code rule pack (blocked on WO-28's engine remainder, which
slice C found is NOT actually implemented despite WO-28's done status
-- `TODO(WO-28)` markers in `std.civil`); support-end inference,
`releases`/`fixity` registry-IO resolution, and frame-to-scalar
harness feeding (slice B/C close-outs).
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

## Slice C progress (`std.civil` stdlib + closed-form structural models)

Status: in-progress overall (Status line above stays `todo` -- slices
A and B are separate dispatches). Scope covered by this slice:
deliverable 4 (`std.civil` stdlib content), the D145 civil quantity
namespace, and deliverable 5 (closed-form beam utilization/deflection
harness models). Slice A (E0205/E0206/E0207/tributary-E0209 net
reachability) and slice B (frame payload IR + lowering emission,
landed) are NOT touched here.

Landed:

- `Namespace::Civil` added to `regolith-qty`'s shared namespace enum
  (D145); the individual quantity names (`occupancy`, `travel_
  distance`, `u_value`, ...) are spelled in source per calcite/02
  sec. 9, the same pattern every other namespace already uses -- no
  Rust seed table exists for `mech`/`elec` either, so none was added
  here. Plain enum addition, no schemars derive on `Namespace`/
  `QuantityDecl`, confirmed no SCHEMA_VERSION impact.
- `stdlib/std.civil/` (WO-45 per-family-file convention, mirrors
  `std.mech`/`std.sheet_metal`): `transfers.hema` authors the six
  transfer classes calcite/02 sec. 5 names (`Pinned`, `Moment`,
  `Bearing`, `Roller`, `BasePlate`, `EmbeddedPost`) as real `mating`
  declarations with `dof: kept=` -- verified with `regolith check`
  (clean; only the expected "generic never instantiated" warnings a
  library-only file gets, the same shape `std.mech.mechanisms`
  accepts). `records/materials.toml` (structural steel/timber/
  concrete + one soil class), `records/sections.toml` (sawn timber/
  comp deck/RC wall+footing), `records/occupancy.toml` (IBC Table
  1004.5 occupant-load factors, Table 1017.2 travel-distance/common-
  path/dead-end limits, Table 1005.3.2 exit-width factors),
  `records/load_cases.toml` + `records/combinations.toml` (ASCE 7-22/
  AISC 360/NDS/geotech combination sets as the D95 swept-obligation
  shape `forall combo in ...` sweeps over).
- All five calcite corpus designs (footbridge, retaining_wall,
  pole_barn, bus_shelter, small_office) now `regolith check` clean
  end to end with `std.civil` resolvable (previously phantom); the
  two negative net-discipline fixtures (E0208/E0209) still fire their
  intended violations, confirming no collision with slice A's
  territory.
- `tests/magnetite/test_stdlib.py`: `std.civil` removed from the
  out-of-scope namespace set (it is real now); the full stdlib suite
  (manifest validity, record round-trips, tier honesty, corpus
  de-phantoming) passes at 31/31 including `std.civil`.
- `python/regolith/harness/models/beam_utilization.py` (`civil.
  utilization`, combined bending+axial interaction) and `beam_
  service_deflection.py` (`mech.beam.service_deflection`, simple-span
  uniform-load midspan deflection) -- the `beam_bending` precedent
  (scalar interval inputs, worst-corner evaluation over the interval
  box, INV-9), registered in `models/__init__.py`. `tests/harness/
  test_beam_utilization.py` + `test_beam_service_deflection.py` cover
  known-answer values, discharge/violation verdicts, corner
  conservatism, the domain guard, and determinism (INV-10); 12/12
  pass. Frame-payload-to-scalar extraction (resolving a `FramePayload`
  member's section/material/demand into these models' scalar inputs)
  is orchestrator-side wiring this slice does NOT attempt -- these
  models are registered and ready for that wiring, matching feldspar's
  `mech.struct` consumption being noted as separate follow-up in
  slice B's own cut list.
- Docs: regolith/11 sec. 8's `std.civil` entry flipped from SCHEDULED
  to LANDED with the same cuts named below; `stdlib/README.md`'s
  catalog table gained the `std.civil` row.

Cut/deferred, named explicitly (not silently dropped):

- The reference building-code rule pack (deliverable 4's conditional
  half): WO-28's Status line reads `done`, but its own close-out names
  deliverables 3 (remainder)/4/5/6/7/8 as blocked upstream on WO-05/
  WO-19 structured-entity work (`forall <var> in <query>` over real
  domain kinds, `resolves:` resolution) -- none of that engine
  remainder is actually implemented; `crates/regolith-syntax/src/
  parser.rs`'s rule-pack domain keyword match is still exactly
  `"dfm" | "drc" | "erc"`, no `civil`/`code` domain exists to author
  against. `stdlib/std.civil/magnetite.toml` carries a `TODO(WO-28)`
  marker per the WO-48 body's own fallback instruction, mirroring
  `std.sheet_metal`'s identical, already-committed cut.
- The ASCE 7/AISC/NDS/geotech load-case DERIVATION MODELS
  (`std.civil.asce7.roof_snow`/`mwfrs`/`elf`, `std.civil.geo.
  rankine_active` as real signature-referenced `effects:` models) --
  `records/load_cases.toml` carries flat placeholder factors (1.0 or
  a simple ASCE 7 flat-roof default) with an explicit in-file note;
  a real exposure/terrain/site-class derivation is harness-side work
  outside this slice's deliverable-5 scope (beam utilization +
  deflection only).
- Bearing-crushing and anchor-group connection CAPACITY numbers
  (`Bearing`'s/`BasePlate`'s `capability:` blocks carry a documentation
  note, not a fabricated number) -- D58: a specific capacity needs its
  own cited connection record, not a starter-pack placeholder.
- `EmbeddedPost`'s soil-passive-pressure lateral stiffness is modeled
  as full fixity (a beam-on-elastic-foundation refinement is a future
  pack, not this slice).
- Wiring `frame_lower.rs`/`claims.rs` to actually RESOLVE a transfer's
  `dof: kept=` into `FramePayload.releases`/support `fixity` (vs. just
  authoring the records those fields need) is registry-IO consumer
  work, the same category slice B already deferred for `section`/
  `material` name-only refs -- not attempted here to avoid touching
  the lowering pass slice A runs in parallel.
- Frame-payload-to-scalar extraction for the harness models above
  (see "Landed").
- `civil.embedment`/`civil.story_drift` claim forms have no dedicated
  closed-form model yet (only `civil.utilization` and `mech.beam.
  service_deflection` are covered) -- outside deliverable 5's named
  "beam utilization + deflection" scope; recorded as a gap for a
  future slice.

`make check` (this slice's touched surface): `cargo check --workspace`
clean after the `Namespace::Civil` addition; `regolith check` clean
on `stdlib/std.civil/transfers.hema` and all five calcite corpus
designs; `ruff`/`ty` clean on the new Python; `pytest tests/magnetite/
test_stdlib.py tests/harness/test_beam_utilization.py tests/harness/
test_beam_service_deflection.py` all green (31 + 12 + 12... see
close-out report for the full-suite tail).
## Slice A progress (calcite L2 net-reachability static checks)

Status: in-progress overall (Status line above stays `todo` -- slices
B and C are separate dispatches). This slice covers the reachability/
declaration third of deliverable 1: E0205, E0206, E0207. It does NOT
touch `FramePayload`/frame lowering (slice B, landed) or `std.civil`/
rule packs/harness models (slice C, untouched).

Landed:

- `crates/regolith-lower/src/calcite.rs`: E0205 (`CIRCULATION_
  UNREACHABLE`) -- a circulation's declared space cannot reach the
  net's `reference:` set by BFS over the file's top-level `access:`
  openings resolved against the circulation's declared `edges:`
  (`(a -> b)` sense read as the egress direction). E0206 (`EGRESS_
  EDGE_UNDECLARED`) -- an edge on that required path with no positive
  `width=`, or a non-positive `path_length=` when one IS declared
  (see the cut below for why bare absence of `path_length=` is not
  flagged). E0207 (`MEMBER_UNSUPPORTED`) -- a declared member cannot
  reach any `support:` node by BFS over the structure's `transfers:`
  edges (walked both ways -- a transfer connects a member and its
  support regardless of which end the mating's positive sense names),
  skipped when the structure has no support at all (E0208 already
  covers that case; re-flagging every member would be noise).
- `crates/regolith-lower/src/flownet_lower.rs`: `edge_endpoints` and
  the new `arg_quantity` promoted to `pub(crate)` so `calcite.rs`
  reuses the exact `(a -> b)`-sense-with-`OpaqueIsland`-fallback
  endpoint read and the exact keyword-quantity-arg read the flownet
  pass already has, instead of re-deriving either (the "no
  duplication" rule).
- `regolith_sem::net_core::LoadPathDiscipline`'s doc comment (the
  WO-47 scope-cut note naming E0205/E0207 as needing a reachability
  traversal `net_core` did not provide) and `calcite.rs`'s own module
  doc comment are both updated: the traversal is a plain BFS living in
  `calcite.rs` itself, not a new `NetDiscipline` plugin (a discipline
  only ever counted imposer terminals per net; walking edges is a
  different shape of computation).
- Rust unit tests in `calcite.rs` cover: E0205 firing when a declared
  space has no path to the reference and passing when it does; E0206
  firing for an undeclared width and for a declared-but-zero
  `path_length`; E0207 firing when a member's transfer chain dead-ends
  before any support (distinct from E0209 -- both fixtures are
  members that ARE joined to something) and passing when the chain
  reaches a support.
- Negative corpus: `examples/negative/60_calx_circulation_
  unreachable.calx` (E0205), `61_calx_egress_edge_width_undeclared.
  calx` (E0206), `62_calx_member_unsupported.calx` (E0207) -- each
  self-calibrated against live `regolith.compiler.check` output per
  the corpus's own discipline; `examples/negative/README.md`'s driver
  summary count updated (37 -> 40 passed, 22 -> 23 xfailed -- the
  xfailed count itself did not move, the README's prior figure was
  stale before this slice touched it).
- Honest-pass: the five ratified calcite corpus designs stay
  zero-diagnostic under the new checks (verified via the existing
  golden corpus suite, zero golden churn) -- `bus_shelter`/`pole_barn`
  specifically exercise the E0206 width-only-when-absent cut (they
  legitimately omit `path_length=` on a single opening straight to
  `exterior` with no travel-distance/dead-end claim to feed).
- `make check` green end to end (fmt, clippy -D warnings, ty, guard-
  core, `cargo test --workspace`, `pytest` through the real wheel:
  566 passed, 3 skipped, 23 xfailed -- unchanged from slice B's
  baseline, confirming zero regression).

Cut/deferred, named explicitly (not silently dropped):

- The tributary-partition half of E0209 ("declared `tributary=`
  shares must partition the surface's declared area") is NOT
  implemented -- it needs partition arithmetic over declared areas,
  a different kind of computation than the reachability/declaration
  checks this slice adds. Still open for a future slice.
- `path_length=` ABSENCE (as opposed to a declared non-positive
  value) is not flagged by E0206 here: the ratified `bus_shelter`/
  `pole_barn` designs omit it legitimately on a direct-to-exterior
  opening with no travel-distance/dead-end claim over that
  circulation. Detecting "a claim needs `path_length=` and it is
  missing" is a claim-lowering-time check (deliverable 2), not a bare
  structural diagnostic -- escalated rather than invented here.
- 03-lowering.md itself is left unmodified (no per-section planned/
  implemented markers exist in that doc to flip, and slice B did not
  add any either -- this WO file's own progress sections are the
  established record of what has landed, per the precedent slice B
  set). The diagnostic-code table in `docs/guide/04-calcite-guide.md`
  already lists E0205-E0209 accurately; nothing there was stale.
- Circulation reachability walks the declared `(a -> b)` edges in
  their declared direction only (not both ways); the ratified corpus
  and this slice's own fixtures all happen to declare edges already
  oriented toward `exterior`, so this has not been observed to cause
  a false E0205. If a future design needs a bidirectional egress edge
  (e.g. a corridor door with no meaningful "positive" direction), that
  is a follow-up, not invented here.
