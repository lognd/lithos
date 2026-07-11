# WO-97 -- Bounded sketch-segment optimization (`in [lo, hi] minimize`)

Status: drafted (2026-07-11, D205 escalation; NOT dispatched -- design
question open, see below)
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
