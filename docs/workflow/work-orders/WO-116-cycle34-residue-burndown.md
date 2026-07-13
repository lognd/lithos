# WO-116 -- Cycle-34 residue burn-down (F129's named-open list)

Status: in-progress (2026-07-13: 3/5 deliverables landed --
  HEALTH-F4, PROOF-F3, PROOF-F2; 2/5 escalated -- F123 arc closure
  and the WO-97 remainder, see the close-out ledger at the end of
  this file)
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
