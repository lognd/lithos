# WO-105 -- Fleet ship campaign: every example builds --release and ships

Status: open
Language: corpus authoring (design sources, magnetite manifests,
  memos) + small Python where a named discharge gap is trivially
  closable; NO verdict-machinery changes
Spec: D206/D207/D210 (the campaign law -- read them FIRST);
  regolith/12 sec. 3 (waive rules 1-9); D195/F116 (never invent
  windows); each flagship's WO close-out ledger (WO-70..94) for
  the wall-by-wall residual inventory.

## Goal

Every D210 fleet project reaches `build --release` green and ships
a complete package; every `examples/tracks/**` single-file design
builds `--release` green. Green means PROVEN OR ACCEPTED: first
discharge what the machinery honestly can, then author scoped,
memo-backed `waive` deviations for the genuinely-unbounded
residuals, per-project.

## Deliverables

1. Provisioning: `magnetite.toml` for dune_buggy, reaction_wheel,
   regen_engine (mirror a flagship manifest's shape); DELETE
   `examples/systems/cnc_router` (D210.2) retargeting its
   deferral golden at the flagship; fix any stale prose refs.
2. Per-project discharge pass BEFORE any waiver: re-run release
   builds on current master (post WO-98..104 merges); for each
   remaining deferral check the ledgered walls -- if a record,
   given, or claim-form fix the specs already permit closes it
   (e.g. declaring an explicit impl-side bound where a real
   narrowing exists, adding a missing std record row WITH a
   citable source, targeting a load the payload can carry),
   apply it as ordinary corpus authoring. NEVER fabricate a
   bound that the design does not actually assert (D195).
3. Waiver authoring: for each genuinely-unbounded residual,
   a SCOPED `waive` in the owning design file with: target +
   `on` scope, a basis naming the wall (WO ledger / design-log
   citation), `by doc(<memo>)` evidence -- one memo per project
   (`memos/release-residuals.md`) written per D207's required
   content (accepted set, why unbounded, retirement path).
   Prefer many scoped waivers over one blanket waiver; unscoped
   only where the claim genuinely fails artifact-wide.
4. Ship specs: each fleet project gets/updates its `--spec` (or
   auto-derivation coverage) so the package contains every
   applicable family (drawings, 3d, bom, instructions, boards,
   firmware/hdl, cost) -- absence must be the named-absent kind,
   not silence.
5. Evidence refresh (D210.5): regenerate every checked-in
   `.regolith/build/build_report.json` at RELEASE tier on final
   master; regenerate goldens; REVIEW diffs (no new error-level
   rows; acceptance counts are visible census data, not noise).
6. Close-out ledger: per-project table (obligations / discharged
   / deviated-accepted / notes) recorded in this WO file -- the
   fleet census the cycle closes on.

## Acceptance criteria

- Every fleet project: `regolith build --release` rc=0 with
  release_ok=true AND `regolith ship` emits a `ship --verify`-
  clean package.
- Every tracks corpus file: `--release` green (in-file waivers
  permitted); negative corpus unchanged-failing; registry/hdl
  parse clean.
- Zero fabricated bounds/windows: every acceptance traceable to a
  basis + memo; the census table distinguishes proven from
  accepted per project.
- `make check` green fleet-wide.

## Close-out ledger (WO-105 execution, 2026-07-12)

Status: in-progress. Deliverable 1 (provisioning) LANDED; the STEP-0
investigation (F125-E1) is CONCLUSIVE; the campaign body (deliverables
2-6, fleet-wide waiver/memo/ship authoring) is BLOCKED on three
machinery walls that fall OUTSIDE this WO's "no verdict-machinery
changes" scope and are escalated below with placeholder labels
(no design-log numbers self-assigned).

### Plan checklist

- [x] STEP 0: F125-E1 model-gap vs loading-condition investigation.
- [x] Deliverable 1: provision dune_buggy/reaction_wheel/regen_engine
      manifests; retire systems/cnc_router; retarget + regen its two
      goldens at the flagship. (committed)
- [x] Prove the memo->waiver->accepted-deviation pattern end to end
      (validated on cnc_router_r1 `land_straight`; reverted after
      validation -- see ESC findings for why it does not generalize).
- [~] Deliverable 2 (discharge pass): the honest discharges are
      already landed by WO-98..104; the remaining deferrals are
      genuinely unbounded (E1) or structurally unwaivable (ESC-1/2).
- [ ] Deliverable 3 (waiver authoring, fleet-wide): BLOCKED, ESC-1/2.
- [ ] Deliverable 4 (ship specs): not reached (gate never green).
- [ ] Deliverable 5 (evidence refresh): not reached.
- [x] Deliverable 6 (per-project census): below.

### F125-E1 VERDICT: (a) genuine model gap -- NOT a loading condition

Airtight, from the code and a live release build:

1. `default_registry()` (`harness/registry.py`) registers every
   built-in via `register_all`, THEN merges `regolith.plugins`
   packs (`load_packs`). It is the composition point the CLI build
   uses (`orchestrate.py:745`). Proof it loads: a live
   `regolith build --release examples/flagships/cnc_router_r1`
   discharges 9 obligations through real built-in models
   (`cam_parse_gcode_fanuc@1`, `cam_removal_gcode_fanuc@1`,
   `workload_realization_identity@1`) -- so model loading is NOT
   broken in CLI builds.
2. The `no_model` deferrals are for AUTHOR-LABELED claim kinds
   (`sag`, `twist`, `crit_speed`, `rack`, `tram`, `sink`, `flow`,
   `throat_life`, ...). Claim kind IS the claim's label
   (`claims.rs`; `translate()` docstring), so `sag: mech.deflection(...)`
   lowers to kind `sag`, not `mech.deflection`. There is no
   registered model named `sag`.
3. Feldspar (present as the sibling repo, NOT installed in the venv)
   registers `mech.static_deflection` + SI-impedance kinds
   (`feldspar/python/.../pack/models.py`), consumed only through the
   payload/FEA channel. Its FEA route emits `mech.deflection.tip` as
   an OUTPUT PORT, not a claim kind matching a bare hematite label.
   NONE of feldspar's registered kinds equals a corpus bare-label.
   Installing feldspar flips ZERO of these deferrals.
4. `translate()` DESIGNS this fall-through: its own docstring says a
   non-calcite `mech.deflection(...)` claim with no frame payload
   "must keep falling through to the ordinary path, preserving its
   existing deferral" -- there is no hematite closed-form translator
   that builds section/material/load inputs for an arbitrary part.

Conclusion: no invocation/wiring fix exists. These deferrals are the
exact genuinely-unbounded residue `waive`+memo (D206/D207) exists for.
Model-inventory gap per claim kind: every author-named structural/
kinematic/thermal/flow promise the corpus wrote WITHOUT a
`by model(...)` pin, a registered kind name, or a frame/FEA payload.

### Mechanism validation (PROVEN)

A `by doc(memos/release-residuals.md)` waiver on cnc_router_r1's
`land_straight` (a floor-free `geom.straightness` no_model deferral),
placed as a 4-space child of `part GantryBeam`, was ACCEPTED: memo
resolved to a blake3 digest, community tier (INV-14), no trust-floor
error, listed as an accepted deviation, verdict untouched (INV-2).
The replicable template is: memo at `<project>/memos/release-
residuals.md`; `waive <claim_name> [on <scope>]:` inside the owning
hematite/cuprite `part`/`interface` decl; `basis:` + `by doc(...)`.

### ESCALATIONS (machinery walls; out of WO-105 scope)

ESC-1 (blocks the fleet). Import-conformance obligations
(`import:std.civil`, `import:package.cupr`, ...) carry EMPTY
`subject_ref` by design ("empty for a file-level import",
`conformance_obligation` in `claims.rs`; discharge.py's own comment).
Waiver matching (`waivers.rs::classify`) matches only obligations
whose `subject_ref` equals the enclosing named decl's snapshot hash;
no healthy decl has an empty snapshot, and top-level `waive` is not
harvested. So EVERY project that imports a std.* package emits a
handful of `conformance_windows_unresolved` obligations that can be
NEITHER discharged (no scalar window on a bare import) NOR accepted
(unwaivable) -- and one unresolved obligation forces `release_ok=False`.
This is newly exposed: this is the first cycle to require
`release_ok=true` fleet-wide (F121 found the acceptance channel was
only just wired), so no flagship has ever passed the `--release`
gate. Needs a machinery decision (make file-level import conforms
non-gating, trivially self-conformant, or waivable) -- verdict
machinery, explicitly outside this WO.

ESC-2 (blocks the calcite fleet leg). The `waive` construct is not
harvested from calcite `structure` decls or top-level `require`
decls: `Decl::waivers()` scans a named Decl's descendants, but a
calcite structure body parses domain-specific statements as
`OpaqueIsland` children, and a top-level `require Structure:` is a
`RequireDecl` not enumerated by `file.decls()` for waiver harvest.
A `waive` placed in either yields `waivers=0` (verified on
timber_pavilion). So timber_pavilion and small_office cannot author
source waivers on their frame claims at all. Grammar/harvest wiring,
outside this WO.

ESC-3 (E2, from F125). `ObligationResult.subject_ref` exposes no
owning-part linkage to Python for the optimizer predicate; unrelated
to the ship gate but confirmed still open.

### Fleet census (obligations / discharged / deferred, RELEASE tier)

Counts are live `regolith build --release <path> --json` on this
tree. `discharged` = model-backed pass/verdict; `deferred` = the
INV-24 unresolved set (would be split into accepted-deviation vs
refusing ONCE ESC-1/2 unblock waiver authoring). No project reaches
`release_ok=true` today because of ESC-1 (every one imports std.*).

| Project           | obl | dischg | deferred | dominant deferral reasons |
|-------------------|-----|--------|----------|---------------------------|
| arm_a6            |  54 |   0    |    54    | conf-windows 34, no_model 10, unsupp_op 6 |
| cnc_router_r1     | 179 |   9    |   170    | conf-windows 81, no_model 58, unsupp_op 18 |
| cubesat           |  90 |   7    |    83    | conf-windows 42, no_model 23, unsupp_op 9 |
| espresso_machine  | 124 |   4    |   120    | conf-windows 41, no_model 32, impl_bound 17 |
| hydro_press_h30   |  24 |   5    |    19    | conf-windows 11, no_model 4, footing_area 2 |
| mainboard_mx      |  39 |   0    |    39    | no_model 14, conf-windows 11, unsupp_op 8 |
| printer_k1        |  68 |   0    |    68    | conf-windows 52, unsupp_op 7, no_model 4 |
| riscv_hart_rv1    |  79 |   1    |    78    | conf-windows 60, unsupp_op 15, no_model 3 |
| small_office      |  25 |   6    |    19    | conf-windows 7, frame_section 4, no_model 2 |
| timber_pavilion   |  10 |   6    |     4    | conf-windows 2, frame_load 1, frame_reaction 1 |
| uav_talon         |  29 |   0    |    29    | conf-windows 20, no_model 5, unsupp_op 2 |
| sdr_transceiver   |  90 |   5    |    85    | no_model 34, conf-windows 29, unsupp_op 11 |
| dune_buggy        | 218 |   0    |   218    | no_model 111, conf-windows 61, unres_limit 23 |
| reaction_wheel    |  25 |   0    |    25    | no_model 10, unres_limit 5, conf-windows 5 |
| regen_engine      |  30 |   0    |    30    | no_model 12, conf-windows 8, unres_limit 3 |

Fleet totals: ~1084 obligations, ~43 discharged, ~1039 deferred.
The conformance-windows column (~460 fleet-wide) is the D195
one-sided-promise residue -- the intended `waive` target, blocked in
part by ESC-1 (import edges) and entirely for calcite by ESC-2.

### What LANDED (committed on wo105-fleet-ship)

- 3 provisioning manifests (dune_buggy, reaction_wheel, regen_engine).
- systems/cnc_router retired; both its goldens retargeted at
  flagships/cnc_router_r1 and regenerated (reviewed: the deferral
  golden gained rows -- the promotion delta -- no error-level
  regressions).

### Scope NOT cut, deferred with cause

The fleet-wide waiver/memo/ship authoring (deliverables 3-5) is a
cycle-scale corpus effort (~1039 wall-cited waivers + 15 memos +
ship specs + full evidence/golden regen) that is additionally GATED
on ESC-1 (no project can go green while import conforms refuse) and
ESC-2 (calcite leg cannot author waivers). Neither is fixable within
this WO's charter. Recommended sequencing: land ESC-1 + ESC-2 (small,
targeted machinery slices) FIRST, then the per-project authoring
becomes the mechanical, dispatchable work the proven template
supports.

## D213/D214 machinery slice (close-out)

The two acceptance-machinery walls F126 named (ESC-1/ESC-2) blocked
the fleet campaign because a fleet build's `release_ok=true` gate had
no way to accept two genuinely-indeterminate residuals. Both are now
closed in `regolith-lower` (no schema bump -- `subject_ref` is an
existing field; the harvest change touches only the walk, never the
grammar). Labels below are PLACEHOLDERS for the design log.

### ESC-1 / D213 -- import-conformance obligations are addressable

- ROOT (verified): `claims.rs::conformance_obligation` looked up the
  enclosing declaration's snapshot for `subject_ref`, but a file-level
  `import` edge has an EMPTY `edge.subject` (`contracts.rs` sets it so),
  so the lookup returned the empty hash. An empty `subject_ref` made the
  obligation both unwaivable (no target could match it) and
  undischargeable (D195.3: no scalar window on a module edge). Every
  project imports `std.*`, so one such obligation forced
  `release_ok=false` fleet-wide.
- FIX (a): an import edge now takes a REAL `subject_ref` =
  `content_address("regolith.lower.import", <path>)` -- the import
  declaration's own content address. Verdict is UNCHANGED (still
  `conformance_windows_unresolved` deferred; no window fabricated).
- FIX (b): `waivers.rs::classify` recognizes the module-edge spelling
  `import(<pkg>)` and matches the file-level obligation whose claim name
  is `import:<pkg>`. It is file-global (matches regardless of the
  enclosing declaration the `waive` is written in, since the obligation's
  subject is the import's own address); a target matching no import edge
  is `Stale` (INV-12). The recorded match set carries the real subject
  hashes.
- TESTS (`waivers.rs`): the import obligation carries a nonempty
  `subject_ref`; a memo-backed `waive import(std.mech)` is Matched + a
  listed (non-blocking) deviation; a bare one is Matched + release-gated;
  a stale `waive import(std.nonexistent)` errors.

### ESC-2 / D214 -- waiver harvest is grammar-complete

- ROOT (verified): `waivers.rs::build_ledger` walked only
  `file.decls()`. Calcite/fluorite top-level `require` groups are NOT
  plain `Decl`s (they ride `File::fluid_requires` -- the AST's own
  `ast.rs` note "A top-level require is NOT a plain Decl"), so a `waive`
  authored inside a `require Structure:` body was never harvested,
  though it parses as a real `WaiveBlock` (the require body is a
  `stmt-block`, grammar.ebnf, which admits `waive-block`).
- FIX: the harvest walk now additionally visits `file.fluid_requires()`
  and `file.structures()`. A `MatchScope` enum carries the position's
  default matching domain: `SubjectRef(hash)` (hema/cupr decls, the
  historical behavior) or `FrameOrigin(name)` (a top-level require /
  structure position -- frame obligations key their `subject_ref` on the
  frame payload digest, not an EntityDb snapshot, so the scope is the
  file's structure name matched against a payload-ref origin).
- PRECISELY-RECORDED EXCLUSION (D214's escape clause): a `waive` inside
  a calcite `structure` BODY does NOT parse as a `WaiveBlock` today.
  `grammar.ebnf` declares `structure-body = { transfers-block | field |
  ctor-stmt | opaque-stmt }` and the parser (`parse_structure_body` ->
  `parse_generic_stmt`) routes a `waive` line to an `OpaqueIsland`.
  Admitting a waive-block there is a GRAMMAR change, which D214 forbids;
  it is recorded here as the one position not yet harvestable. The walk
  still scans `structure` descendants for `WaiveBlock` nodes (finding
  zero today) so it is correct-by-construction the day the grammar
  admits one. The natural, already-parseable home for a calcite
  frame-claim waiver is the top-level `require` body (now harvested).
- TESTS (`waivers.rs`): a top-level-require calcite frame-claim waive is
  harvested and Matched by claim name; a structure-body waive parses
  opaque and is (correctly) not harvested today.
- END-TO-END: splicing `waive Structure.deflect ... by doc(...)` into the
  REAL `examples/flagships/timber_pavilion/frame.calx` (top-level
  `require Structure:` body) took the build's waiver ledger from 0 to 1
  entry, Matched, with 0 stale diagnostics -- confirming the harvest on
  real corpus. (Experiment reverted; authoring the actual waivers is
  WO-105's own corpus pass.)

### Golden churn review

The import-obligation `subject_ref` change re-keys each import
obligation's `content_hash`. 23 corpus goldens churned, symmetric
223/223: EVERY changed line is a 64-hex `obligation_keys` entry; no
`obligation_count`, `diagnostic`, `reason`, `status`, or `verdict` row
changed (grep-verified). Regenerated via `REGOLITH_UPDATE_GOLDEN=1`.

### Escalations

None new. The queued follow-ons F124 (source trust-floor wiring,
lockfile match-set persistence) and F126.1 (label-named mech claim
routing) are untouched and remain out of this slice's scope.
