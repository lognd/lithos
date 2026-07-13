# WO-116 -- Cycle-34 residue burn-down (F129's named-open list)

Status: done (2026-07-13: all 5 deliverables landed across three
  dispatches -- HEALTH-F4/PROOF-F3/PROOF-F2 (dispatch 1), the D231
  schema bump + F123 closed-form solve (dispatch 2), and the
  realizer-emission + staged_build/preview integration halves,
  WO116R-F1/F2 (this `wo116r2` slice). See the final close-out ledger
  at the end of this file.)
Language: mixed -- Rust (arc closure, Bounded->Pinned) + Python
  (CLI seam, exemplar, status vocabulary); no schema bump without
  D225 escalation.
Spec: F123 (tangent-arc closure ruling + reopen criterion); F128.4
  (PROOF-F2/F3, WO-97 deliverable-6 remainder); F129 (HEALTH-F4);
  WO-104 + WO-97 ledgers (the exact residuals).

## Goal

The five inherited residuals close, flipping WO-104 to done and
retiring F129's non-owner-gated open list.

## Deliverables

1. F123: Rust tangent-arc walk-closure solve beside `close_walk` --
   compute each arc's endpoint from tangent continuity + radius,
   verify closure, emit the resolved outline + arcs into the
   profile the emission pass reads; `GantryBeam`
   (`saw_stock(extrusion(BeamSection, l=820mm))`) emits real STEP
   end to end; flip WO-104 Status to done (its acceptance sentence
   completes).
2. WO-97 remainder: Rust `SegmentLength::Bounded -> Pinned`
   literalization after a successful bounded-slot search + preview
   STEP surfacing (the optimizer-pinned arm_a6 UpperArm.b geometry
   becomes a visible preview/ship artifact).
3. PROOF-F2: `regolith optimize` gains the compiled choice_points
   seam (replacing the `--spec` placeholder path where the WO-55
   ledger documented the caller-supplied seam).
4. PROOF-F3: duct_vane corpus exemplar enrolled (the continuous
   staged-evaluator demo gets a corpus twin).
5. HEALTH-F4: WO Status-line vocabulary normalized (one enumerated
   set; the health consistency leg already parses them -- align the
   stragglers and pin the vocabulary in workflow/README).

## Acceptance

- GantryBeam STEP + census enrollment; WO-104 done.
- A bounded-slot search leaves pinned IR + a preview STEP artifact.
- `regolith optimize` runs a compiled design's choice_points
  without hand-supplied domains (subprocess test).
- duct_vane in the corpus test net; demos/demo2 optionally points
  at it.
- `make check` + health green after `make install`.

## Escalation

Each deliverable is independent; land serially, commit per piece.
If the arc solve needs numerics beyond a closed-form/Newton step,
escalate rather than importing a solver dependency.

## Close-out ledger (2026-07-13, this dispatch)

LANDED (3 of 5, each its own commit on `wo116-residue-burndown`):

- HEALTH-F4: the four Status-line stragglers (`DONE`,
  `SCALAR HALF DONE`, `landed-with-accepted-residuals`,
  `done-honest-partial`) retired to the existing vocabulary
  (`done`/`honest-partial`); the full enumerated set (`todo`/`open`,
  `in-progress`, `honest-partial`/`partial`, `phase`, `done`, `cut`)
  is now pinned in `docs/workflow/README.md` next to the existing
  `## Status` section, naming exactly what
  `tools/health/consistency.py::_wo_status_map` parses (the first
  word only) and its gating rule (`done*`/`cut*` vs `todo`; anything
  else is a non-gating reported residual by design).
- PROOF-F3: `examples/tracks/hematite/duct_vane.hema` (a standalone
  single-file bounded `in [lo, hi] minimize` profile, `bed.hema`'s
  shape) enrolled in `tests/golden/test_golden_corpus.py`'s `_CORPUS`
  -- checks clean, zero diagnostics, no regression in the existing
  375 golden tests. `demos/demo2_continuous_printer.py` is left
  pointed at printer_k1 (the acceptance line only asks duct_vane be
  an OPTION); its docstring already records why printer_k1 was
  chosen, so re-pointing it is a documentation-only follow-on, not
  gating.
- PROOF-F2: `regolith optimize --costs <cost-table.json>` (mutually
  exclusive with `--spec`) compiles `project` for real and drives its
  lowered `BuildPayload.choice_points` through the already-landed
  `domains_from_choice_points` builder -- no hand-supplied domains.
  Proven with a real subprocess test
  (`tests/test_cli_optimize_compiled_seam.py`) against the compiled
  `ebi_decode.cupr` exemplar (WO-56's own fixture): the winner is the
  declared-cheapest candidate, exactly the same shape
  `demos/demo1_select_ebi_decode.py` proves in-process.

ESCALATED (2 of 5, evidence-backed, not invented around):

**WO116-F1 (F123 tangent-arc closure -- blocked on an uncaptured
constraint, not on numerics).** The closure math for a tangent arc
between two CARDINAL straight segments is genuinely closed-form, no
Newton iteration: the turn angle is fully determined by the
neighboring segments' own (already-known) headings (`ClosureSegment.
angle_deg`), so the arc's chord displacement is the elementary fillet
identity `(r*sin(phi), sign*r*(1-cos(phi)))` in the incoming-tangent
frame, rotated by that tangent's heading -- no fitting, no
iteration, exactly the "closed-form" arm this WO's own escalation
clause anticipated as the acceptable case. The BLOCKER is one level
up: the arc's RADIUS is never captured anywhere in the IR today.
`GantryBeam`'s `BeamSection` profile writes `c.radius = 6mm` /
`j.radius = 6mm`, but `crates/regolith-ir/src/sketch.rs::length_item`
only recognizes a `<base>.length = <rhs>` constraint shape (a
`.radius` suffix does not match its `strip_suffix(".length")`, so the
constraint is silently skipped by `bind_lengths` -- confirmed by
grep: no `.radius` handling exists anywhere in
`regolith-syntax`/`regolith-lower`/`regolith-ir` for a sketch arc).
`ArcGeometry` (`crates/regolith-ir/src/sketch.rs`) carries only
`bulge`/`join`, no radius field. Landing the closed-form solve
therefore requires adding a `radius` field to `ArcGeometry` -- a
`JsonSchema`-derived struct generated verbatim into
`python/regolith/_schema/models.py` (confirmed: every prior field
addition there is commented with the `SCHEMA_VERSION` bump that
accompanied it, e.g. WO-85/D194 -> 27, WO-104 -> 29 this cycle) --
which is a schema-surface change this WO's hard rules forbid without
a D225 escalation. Recorded here rather than self-authorized: the
closure solve is a small, mechanical follow-on ONCE a coordinator
approves the `ArcGeometry.radius` field + its `SCHEMA_VERSION` bump;
no solver dependency is needed either way. WO-104's Status stays
`in-progress` (its acceptance needs the arc-extrusion half; that half
is not landed).

**WO116-F2 (WO-97 remainder -- deferred as a consequence of F1, plus
its own genuine integration surface).** The remaining Rust
`SegmentLength::Bounded -> Pinned` literalization + `regolith preview`
STEP surfacing is a `staged_build`-seam integration this WO's time
budget did not reach independently of F1 (it is its own multi-file
change: a `staged_build` override path that re-runs `close_walk` with
the D209-pinned candidate substituted for the `Bounded` slot, then
routes the resulting `FeatureProgram` through the existing preview/
ship producers) -- the Python-level coupling
(`python/regolith/orchestrator/optimize_sketch.py`) already proves
the arm_a6 UpperArm.b pin end to end at the API level (F125/F128.2's
ledger); what is missing is solely the CLI/`preview` wiring named in
the WO-97 close-out ledger's own "STILL DEFERRED" list. Queued,
evidence-backed, not gating this cycle's health bar (F129's own
framing: "none gating").

`make check` green (fmt, clippy, typecheck, guard-core, schema-check,
Rust + Python tests) after `make install`; see the per-commit log on
`wo116-residue-burndown`. Status stays `in-progress`: 3/5 landed, 2/5
escalated per the WO's own "escalate rather than invent" clause.

## Remainder slice close-out (2026-07-13, `wo116r-arc-schema` worktree, D231 grant)

D231 granted the cycle's single schema bump, scoped to
`ArcGeometry.radius` + its direct consumers (the F123 closure solve,
the GantryBeam end-to-end acceptance, the WO-104 Status flip, and the
WO116-F2 remainder). This slice landed the schema half and the
closed-form solve half; it did NOT reach the realizer-emission and
staged_build/preview integration halves -- recorded here rather than
invented around, per the WO's own "escalate rather than invent"
clause.

LANDED (commits on `wo116r-arc-schema`, based on master 06a21cd):

- `ArcGeometry.radius: Option<f64>` (`crates/regolith-ir/src/sketch.rs`):
  a `<name>.radius = <qty>` constraint item now captures into the
  matching arc segment (`bind_lengths` gained a `radius_item` sibling
  parse to `length_item`), scoped to a PLAIN pinned quantity only -- a
  `free`/bounded radius slot stays uncaptured, unchanged from the
  pre-D231 status quo (never a fabricated reject of the existing
  corpus: `pillow_block.hema`/`molded_clip.hema`/`regen_chamber.hema`
  all still promote exactly as before). `SCHEMA_VERSION` 29 -> 30
  (`regolith-util::canon`, `regolith-oblig::lib` test); `make schema`
  regenerated `python/regolith/_schema/{__init__,models}.py`.
- F123 closed-form tangent-arc closure (`crates/regolith-ir/src/solve/
  sketch.rs`): `arc_chord()` computes the elementary fillet identity
  `(r*sin(phi), sign*r*(1-cos(phi)))` in the incoming-tangent frame,
  rotated by the tangent heading, from the two neighboring cardinal
  headings alone (no fitting, no iteration) -- wired into BOTH
  `close_walk`'s linear-gap sum (`accumulate_gap_and_free`, extracted
  to satisfy the workspace's `too_many_lines` clippy lint) and
  `close_edge_solution`'s `closure_gap` (the labeled-close-edge path
  `GantryBeam`'s `BeamSection` actually uses, `k: close`). A
  radius-less arc still contributes nothing (unchanged WO-104 status
  quo). New tests: a stadium/racetrack profile (two straight legs +
  two 180-degree tangent arcs) closes exactly for any radius; a
  disagreeing pair of legs still reports the EXISTING
  `SKETCH_RESIDUAL_INCONSISTENT` diagnostic (never a fabricated
  closure); a radius-less arc is unchanged.
- Golden corpus regenerated for the schema bump (`REGOLITH_UPDATE_
  GOLDEN=1`): 30 files, diff reviewed -- every changed line is a
  hash-shaped field (`obligation_keys`, `subject_anchor`, hex
  `detail` suffixes) fed by `SCHEMA_VERSION` entering the canonical
  hash input; zero diagnostic-count or error-level changes anywhere
  in the corpus.
- `make install` + `make check` green (fmt, clippy, ty, guard-core,
  schema-check, Rust + Python tests, health all-green) on this slice.

NOT REACHED (escalated, evidence-backed, not invented around):

**WO116R-F1 (GantryBeam end-to-end STEP + WO-104 Status flip).** The
closure solve now verifies a radiused walk closes, but it exposes only
a scalar residual (`SketchSolution.residual`) and free-length
resolutions -- NOT the resolved per-vertex outline/arc-endpoint
geometry a realizer needs to actually draw the profile. Confirmed by
reading the realizer: `python/regolith/realizer/mech/interpreter.py`'s
`_profile_face_with_arcs` already consumes a `Sketch(outline=...,
arcs=...)` where `outline` carries EVERY vertex position (including
arc endpoints) and `arcs` names which segments are `ProfileArc`s --
the OCCT `RadiusArc` wiring is real and unit-tested (`test_arc_
profile.py`), but nothing produces that resolved outline for a
closure-solved walk today. Landing this needs: (1) a new Rust-side
resolved-outline type (vertex positions in walk order, arc endpoint
pairs) computed by the SAME `arc_chord` math and exposed on
`SketchSolution` or a sibling struct, crossing the FFI/schema exactly
as `SketchClosure` does (the D205 escalation forbids recomputing this
in Python, so it cannot be duplicated at the `programs.py` layer); (2)
a `saw_stock(extrusion(<profile>, l=<len>))` source-recognition path
in `python/regolith/orchestrator/programs.py` (today's
`_weldment_piece_programs_from_source` docstring explicitly excludes
it, "the `extrusion(<profile>)` custom section... is NOT recognized
here"); (3) census/STEP test enrollment. This is its own schema/FFI
surface (arguably its own WO-shaped increment, charter 30 sec. 1.3),
not a wiring gap this slice's remaining budget reached. WO-104 Status
stays `in-progress`.

**WO116R-F2 (WO-97 remainder: Bounded -> Pinned literalization +
preview STEP).** Unchanged from the prior dispatch's F2 finding (still
not reached): the `staged_build` override path that re-runs
`close_walk` with the D209-pinned candidate substituted for the
`Bounded` slot, then routes the resulting `FeatureProgram` through the
existing preview/ship producers, so the optimizer-pinned `arm_a6
UpperArm.b` geometry ships as a visible STEP artifact. The
Python-level coupling already proves the pin end to end at the API
level (F125/F128.2's ledger); the CLI/`preview` wiring is what remains.

`make check` green (fmt, clippy, ty, guard-core, schema-check, Rust +
Python tests) after `make install` on this slice. Status stays
`in-progress`: the D231-granted schema bump + F123 closed-form solve
landed; the realizer-emission/staged_build integration halves (WO116R-
F1/F2) are escalated, not invented around.

## Final close-out slice (2026-07-13, `wo116r2` worktree -- integration)

The two escalated integration halves are now LANDED, with NO further
schema change (SCHEMA_VERSION stays 30, D231/D225): the resolved
geometry flows through EXISTING shapes only -- the realizer's own
`Sketch.outline`/`arcs`/`ProfileArc.to` (its forward contract, not the
versioned schema), fed by a marshalled JSON string across the FFI (the
`obligation_content_hashes` precedent), never a new versioned field.

**WO116R-F1 (GantryBeam real STEP end to end + WO-104 done) -- LANDED.**
The prior slice's finding (the closure solve exposed only a scalar
residual, not the resolved outline the realizer draws) is closed by
COMPUTING the resolved outline in Rust and marshalling it, rather than
adding a schema field:

- `crates/regolith-ir/src/solve/sketch.rs::resolve_outline`: the
  forward walk placing every vertex of a fully-determined radiused
  profile from the SAME closed-form `arc_chord` math the F123 closure
  verification uses (so the realized geometry can never disagree with
  the closure check). Radius-less arcs / still-free segments are an
  honest `None`, never a fabricated vertex. Unit tests assert the real
  `gantry_beam.hema` BeamSection endpoints EXACTLY (`c` ends (74, 70),
  `j` ends (-7, 12)) and the honest-`None` skips.
- `regolith_api::resolve_extrusion_outline` + the
  `resolve_extrusion_outline` FFI pyfunction + `compiler` facade:
  parse -> `profile_walks` -> `sketch_closure_from_walk` ->
  `resolve_outline` -> JSON. The `arc_chord` geometry stays
  single-sourced in Rust (D205), no versioned schema shape changes.
- `orchestrator/programs.py` recognizes `saw_stock(extrusion(<profile>,
  l=<L>))` (the F122 weldment-recognition precedent, one level up) and
  emits a `<part>.body` program building `Sketch(outline, arcs=
  ProfileArc(...))` from the resolved outline; each `ProfileArc.to` is
  the same resolved vertex the outline carries (bit-identical), so the
  interpreter's end-vertex arc lookup matches exactly. `GantryBeam`
  (cnc_router_r1) now realizes real STEP end to end via `staged_build`
  (1 solid, real 6mm fillet arc edges, bbox to the -7mm front toe);
  `CarriagePlate` stays honestly non-convertible (non-literal `rect(1.1
  *w, ...)`). Census/STEP test `test_extrusion_section_parts_realize_
  real_step` + the escalation census keeps CarriagePlate out. **WO-104
  flipped to done** (both halves of its acceptance sentence closed).

**WO116R-F2 (Bounded -> Pinned literalization + preview STEP) -- LANDED.**
`optimize_sketch.stage_pinned_slot`: after the D209 margin search,
literalize the winning width (`Bounded -> Pinned`) and route the pinned
program through `staged_build`'s override channel so its native STEP
lands in the project's `NativeArtifactStore` -- exactly where
preview/ship read part bytes. The optimizer-pinned `arm_a6 UpperArm.b`
(~24mm) ships a visible STEP artifact; a deferring search ships nothing
(never a fabricated pin). Test
`test_pinned_slot_ships_a_visible_step_that_differs_from_unpinned`
proves the pinned STEP exists and differs from a build at a different
width. (This is the arm_a6 STEP-emission WO-97 deferred; WO-97 itself
stays honest-partial for the other three flagships -- see its ledger.)

All 5 original deliverables are now landed. `make install` + `make
check` green (fmt, clippy, ty, guard-core, schema-check, Rust + Python
tests, health all-green); zero golden error-level regressions; no
schema drift. Status -> done.
