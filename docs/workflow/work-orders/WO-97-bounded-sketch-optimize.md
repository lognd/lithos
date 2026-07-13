# WO-97 -- Bounded sketch-segment optimization (`in [lo, hi] minimize`)

Status: in-progress (2026-07-12: the promotion half landed --
`b.length = in [lo, hi] minimize` now promotes to a
`SegmentLength::Bounded` closure segment across the corpus. The
continuous-optimizer STEP-emission half is honestly DEFERRED on the
whole corpus per D209's own honest-deferral arm: every bounded-slot
part's governing structural claim defers `no_model`, so its evaluator
is `optimizer_evaluator_deferred` and no part can be pinned to a
genuine `optimize(...)` value yet -- an F123/F124-shaped
model-gap escalation. See the close-out ledger below. D209 answered
the D205 design question -- the evaluator IS the discharge pipeline
specialized per candidate.)

## D209-coupling update (2026-07-13, D218.3 dispatch; coordinator assigns final D/F numbers)

The E1/E2 blockers are DISCHARGED for the honestly-resolvable
`arm_a6` UpperArm chain -- a bounded slot now pins from a REAL
margin search:

- New coupling module `python/regolith/orchestrator/optimize_sketch.py`
  (the D209 evaluator specialized to bounded profile-width slots):
  per candidate width -> section second moment `I(b) = t*b**3/12` ->
  `mech.beam.cantilever_deflection` DischargeRequest against
  `beam_bending.py`'s already-registered closed-form channel ->
  feasible iff the deflection margin discharges -> objective = the
  slot width (minimize). Winner pinned as a genuine
  `LockRow.cause = optimize(...)`; each candidate stores STEP-able
  realized geometry.
- F126.1 recognize-by-call-form lives IN the evaluator (it drives the
  cantilever model with candidate geometry in hand), NOT in the
  standalone `translate()` path -- a standalone route would be
  verdict-neutral (translate has no geometry, so it could only defer)
  while churning fleet deferral-reason goldens, so the value lands
  where geometry exists.
- E2 resolved by CONSTRUCTION: the coupling selects "the part's
  governing claim" from the declared part (`FeatureProgram.part_name`
  + the named `mech.deflection(...)` claim), never an
  `ObligationResult.subject_ref` content hash -- no new linkage
  channel or schema bump needed.
- Discharge channel is the blessed built-in closed-form lithos model
  (`beam_bending.py`, `mech.beam.cantilever_deflection`) -- NO feldspar
  change required (the WO's explicitly-allowed alternative).
- Proof: `tests/orchestrator/test_wo97_arm_a6_bounded_optimize.py`
  (4 tests) -- the REAL compiled `arm_a6` payload's bounded slot pins
  to `UpperArm.UpperArmSection.b ~= 24mm` (minimal feasible; the 1.5mm
  limit is slack) with `optimize(...)` cause + realized-geometry
  digest; a tightened limit BINDS the constraint (winner moves off the
  lower bound, proving a real search, not a rubber stamp); an
  unreachable limit terminates `infeasible` (the honest
  `optimizer_evaluator_deferred` outcome, WingSpar's fate).

STILL DEFERRED (evidence-backed, honest):
- `uav_talon` WingSpar: `bending: derived(sf=1.5)` reaction, no
  declared scalar load -> the cantilever force input does not resolve
  from declared data, so the slot stays `optimizer_evaluator_deferred`
  (never a fabricated load).
- `arm_a6` Forearm + `cubesat` SidePanel: same coupling reaches them
  the moment their governing claim's inputs are resolved into a
  `CantileverSlot` (Forearm carries an analogous literal-load
  deflection claim; wiring the multi-part discovery/resolution loop
  and the section-orientation-per-part is the remaining follow-on).
- Rust `staged_build` literalization of `SegmentLength::Bounded` ->
  `Pinned(winner)` and STEP emission under `regolith preview`, plus
  the fleet golden enrollment (deliverables 5/6), are the remaining
  integration -- the Python coupling proves the pin + STEP-able
  geometry at the API level; the CLI/`preview` surfacing and fleet
  goldens land next (kept out of this change to avoid destabilizing
  fleet release_ok, which stays true -- no corpus/waiver edits here).

  UPDATE (2026-07-13, WO116R-F2, `wo116r2` slice): the `arm_a6
  UpperArm.b` STEP-emission half of deliverable 6 is now LANDED.
  `optimize_sketch.stage_pinned_slot` literalizes the winning width
  (`Bounded -> Pinned` at the realizer-program level -- the pinned
  candidate substituted as a plain literal) and routes it through
  `staged_build`'s override channel, so the pinned geometry lands as a
  native STEP artifact where preview/ship read part bytes
  (`test_pinned_slot_ships_a_visible_step_that_differs_from_unpinned`).
  WO-97 STAYS honest-partial: the OTHER three flagship slots
  (`uav_talon` WingSpar -- `derived(sf=1.5)` reaction with no declared
  load; `arm_a6` Forearm + `cubesat` SidePanel -- the multi-part
  discovery/resolution loop) remain deferred per their reopen criteria,
  and no fleet-corpus/waiver edits were made (fleet release_ok stays
  true, D224/D232's fleet-corpus boundary honored).

## Close-out ledger (2026-07-12; coordinator assigns final D/F numbers)

LANDED (committed, `make check` green):
- Rust promotion: `crates/regolith-ir/src/sketch.rs::bind_lengths`
  now recognizes the bounded optimize-slot RHS `in [lo, hi]
  minimize|maximize` and emits `SegmentLength::Bounded { lo, hi,
  direction }` (unit-unified with the walk's plain pins through the
  new shared `unify_unit` helper; a malformed slot -- bad direction
  word, mixed-unit or non-positive/inverted range -- is a NAMED
  unsupported reason, never a silent plain-pin fallback). WO-104 left
  the `Bounded` variant inert ("WO-97 is the consumer"); this is the
  consumer. `close_walk` keeps WO-104's existing free-length treatment
  (test-only; not wired into the build/check diagnostic path, verified).
- The bounded slot surfaces end to end into the lowered
  `FeatureProgram` sketch payload (`"length": {"bounded": {lo, hi,
  direction}}`), verified for all four named flagship targets:
  `uav_talon` WingSpar.SparCapFlat.b [3,8], `arm_a6`
  UpperArm.UpperArmSection.b [24,40] + Forearm.ForearmSection.b
  [18,32], `cubesat` SidePanel.PanelOutline.a [94,96]. (The 2026-07-11
  target list named "SidePanel" per-face; the actual corpus carries
  ONE bounded slot on SidePanel.PanelOutline.a -- recorded, not
  invented around.)
- Census/regression test `tests/orchestrator/test_wo97_bounded_promotion.py`
  (the deliverable-7 census, scoped to the landed surface): the four
  flagship slots promote as bounded, not `Unsupported`.
- Rust unit tests: bounded slot promotes; malformed slots are named
  unsupported reasons. Corpus promotion snapshot updated (cubesat
  SidePanel now `Promoted`).

ESCALATED (deliverables 3/4/6 + the "resolve to `optimize(...)`
LockRow" acceptance -- BLOCKED, evidence-backed, F123/F124-shaped):

E1 (the decisive finding). D209 rules the bounded-slot evaluator IS
the discharge pipeline specialized per candidate, with feasibility =
`margin >= 0` on every claim naming the slot's part and objective =
the slot value, and it EXPLICITLY specifies that a deferring claim's
model makes the whole optimize defer with `optimizer_evaluator_deferred`
(never a fabricated closure). Empirically, EVERY bounded-slot part in
the corpus is in exactly that deferring state: the governing
structural claims (`mech.deflection`, `mech.stress.von_mises`,
bearing/bolt inputs) all defer `no_model` / `*_inputs_missing` /
`unsupported_op` -- there is no registered built-in model for the
feldspar-tier structural claims these parts carry. Probed at
`BuildTier.BUILD` over uav_talon / arm_a6 / cubesat / printer_k1 /
pillow_block / lug_bracket / regen_chamber: zero bounded-slot part has
a governing claim that discharges to a numeric margin. So D209's
honest outcome for the ENTIRE current corpus is
`optimizer_evaluator_deferred`, and deliverable 6 (four flagships emit
real STEP under `regolith preview` with a genuine optimizer-pinned
value) + the acceptance criterion "resolve to a `LockRow.cause =
optimize(...)`" are UNACHIEVABLE until a structural claim model is
registered. This is the same shape as F123/F124 (WO-104's arc-extrusion
half deferred on a missing Rust closure solve): the promotion/coupling
DESIGN is settled, the missing piece is a model, not wiring.

E2 (a real infra gap the coupling needs). Building the per-candidate
feasibility predicate "margin >= 0 on every claim NAMING the slot's
part" (D209) requires attributing each `ObligationResult` to its
owning part in the Python orchestrator. Today `ObligationResult.
subject_ref` is a content-address hash and the Claim surface exposes
no owning-part label to Python, so "the part's claims" cannot be
selected without a new linkage. This is moot while E1 holds (every
claim defers regardless of candidate, so the search never runs), but
it is a prerequisite the coupling implementation will need the moment
a structural model exists -- recorded so it is not rediscovered.

REOPEN CRITERION (flip to done): a registered discharge model for the
bounded-slot parts' governing structural claim (the feldspar beam/
stress tier, or a built-in closed-form cantilever model matched to the
flagship `mech.deflection`/`mech.stress` claim kinds) AND the E2
result-to-part linkage, so the D209 evaluator (staged_build override =
FeatureProgram-at-candidate-x -> discharge -> margins) produces a real
`optimize(...)` LockRow and STEP for at least one bounded-slot part.
Then land deliverables 3/4/6 and the golden enrollment.

Language: Rust (IR + lower) + Python (orchestrator)
Spec: hematite/07 sec. 2a ("declared material-removal vocabulary"
  bullet: bounded `in [lo, hi]` slots "carry the `planner` cause --
  ordinary optimizer territory"); toolchain/28-optimization.md (AD-30);
  WO-55 (the optimizer engine), WO-70 (its proof fixtures, hand-built
  FeaturePrograms only); `crates/regolith-ir/src/solve/sketch.rs`,
  `crates/regolith-ir/src/sketch.rs`; `crates/regolith-lower/src/
  removal.rs` (the Ribs/PocketGrid bounded-slot precedent).

## Goal

Let a profile segment declared `b.length = in [lo, hi] minimize`
(`uav_talon` WingSpar.SparCapFlat, `arm_a6` UpperArm/Forearm,
`cubesat` SidePanel) survive sketch promotion, carry through the
lowered payload as a bounded planner slot, and get pinned by the
continuous optimizer against the OWNING PART's own declared claim
(e.g. WingSpar's deflection obligation) -- never a guessed literal --
so these profiles emit real STEP geometry under `regolith preview`.

## Why this is a WO, not a same-session landing

The keystone investigation (this dispatch) mapped the full chain and
found every link buildable by precedent EXCEPT ONE: the coupling
between the continuous optimizer driver and a part's claim.

What exists today:
- `crates/regolith-ir/src/sketch.rs::bind_lengths` rejects any
  constraint RHS that is not a plain quantity literal as an
  `Unsupported` "expression constraints are out of this increment"
  reason (see `pinned_quantity`); `SegmentLength` has only `Pinned`/
  `Free` (`crates/regolith-ir/src/solve/sketch.rs`). Adding a
  `Bounded(lo, hi)` variant plus `close_walk` support (treat it as
  `Free` for the closure equations -- IT IS resolved, just not yet
  pinned to a literal) is straightforward, same shape as the existing
  `Bounded` planner-slot enum in `crates/regolith-lower/src/
  removal.rs` (`SlotValue::Bounded`, `cause: "planner"`).
- The schema/payload surfacing, `SCHEMA_VERSION` bump, and
  `ResolvedFeatureParam { text: "[lo, hi]", cause: "planner" }`
  spelling are a direct copy of the removal.rs precedent.
- `python/regolith/orchestrator/optimize.py`'s
  `optimize_continuous_golden_section` driver is proven
  (`tests/orchestrator/test_wo70_uav_talon_optimize.py`) -- but ONLY
  against a hand-built `Evaluator` closure the TEST wrote itself
  (`_spar_cap_program` + a bespoke mass computation). There is no
  production caller anywhere that builds this evaluator generically.
- `python/regolith/orchestrator/programs.py::_family_ops` /
  `_one_family_op` show the actual production posture for EVERY
  existing bounded planner slot (Ribs/PocketGrid count, pitch,
  thickness): they stay `None`/unpinned and the whole program is
  reported non-convertible ("planner-bounded values stay pending
  until the optimizer pins them") -- geometry is intentionally NOT
  emitted rather than guessed. The CLI's `regolith optimize` command
  (`python/regolith/cli/app.py`) wires only `optimize_discrete`
  (choice points, `by select(...)`); nothing wires
  `optimize_continuous_golden_section` to a real per-part evaluator
  in production code.

The missing piece is not wiring -- it's a genuinely new mechanism:
**given a bounded sketch segment on part P, which of P's declared
claims does the search evaluate against, and how does the caller build
that FeatureProgram-at-candidate-x -> discharge -> feasible/objective
evaluator generically** (not per-test, hand-rolled once per profile as
WO-70's fixture does). Concretely:

1. How does the orchestrator discover the claim(s) a bounded segment's
   optimization must satisfy (WingSpar's deflection obligation is
   named in the flagship source, but is there a declared link from
   `SegmentLength::Bounded` to a specific claim id, or does the
   evaluator need to discharge ALL of the part's claims and take
   feasibility as "all pass")? Is this link declared in hematite
   surface syntax (new grammar) or inferred structurally (same part
   name)?
2. Building the per-candidate FeatureProgram requires substituting
   `x` back into the SAME sketch closure the profile promoted from --
   does that mean re-running `close_walk` per candidate (cheap,
   deterministic, already pure) with the segment's `Bounded` treated
   as a probe `Pinned(x)`? Where does that substitution live: a new
   Rust entry point, or does the Python side reconstruct the
   `FeatureProgram` payload directly (risking drift from the Rust
   closure solve -- NO DUPLICATION per CLAUDE.md)?
3. What is the objective when a part has more than one bounded
   segment (`UpperArm` AND `Forearm` in `arm_a6`, `SidePanel` in
   `cubesat` possibly repeated per face) -- one multi-dim continuous
   search (`nelder_mead`, already landed) per part, or N independent
   1-D golden-section searches? The charter's lexicographic objective
   order needs a concrete per-flagship declared source, not invented
   here.
4. Where does the discharge call live so it never becomes a second
   compiler entry point (AD-4: only `compiler.py` imports
   `regolith._core`) -- almost certainly `staged_build` (WO-57's seam,
   already named in `optimize.py`'s docstring as the plug point) but
   that seam itself is not yet proven against a REAL bounded sketch
   segment end to end.

## Deliverables (once the design question above is answered)

1. `SegmentLength::Bounded(lo, hi)` in `crates/regolith-ir/src/
   sketch.rs` + `close_walk` support in
   `crates/regolith-ir/src/solve/sketch.rs` (treat as an unresolved
   free length for the closure DOF count; never silently pin).
2. Lowered payload surface via `crates/regolith-lower`, `cause:
   "planner"` spelling matching removal.rs; `SCHEMA_VERSION` 28 -> 29,
   `make schema` (never hand-edit `_schema/`).
3. The claim-coupling mechanism decided by the design question above,
   landed in `python/regolith/orchestrator/programs.py` +
   `optimize.py` (or a new small module if the coupling needs its own
   home -- ONE home, no duplication).
4. `staged_build`/discharge wiring so the evaluator is a genuine
   build+discharge closure, never a hand-rolled per-profile mass
   formula (WO-70's fixture pattern was a PROOF of the driver, not the
   production shape).
5. Regenerate every fleet golden the schema bump touches; review each
   diagnostic_multiset delta (bare schema-version bump is fine, a new
   error-level row is a regression until proven intended).
6. Verify `uav_talon` WingSpar, `arm_a6` UpperArm/Forearm, `cubesat`
   SidePanel emit real STEP geometry under `.venv/bin/regolith preview
   <dir>` with a genuine (non-fabricated) optimizer-pinned value.
7. A census test; a design-log entry recording the final coupling
   decision; update the hematite/07 bullet's status.

## Acceptance criteria

- `make check` green (fmt, clippy, ty, core-import guard, Rust +
  Python tests).
- The four named flagship profiles' bounded segments resolve to a
  `LockRow.cause = optimize(...)` row that is a genuine search result,
  never a guessed literal.
- No new compiler entry point outside `compiler.py` (AD-4 unchanged).
- Golden diffs reviewed and reported, not just regenerated.
