# D205 -- bounded sketch-segment optimize: escalated, not landed

Date: 2026-07-11
Dispatch: keystone investigation for optimizer-driven sizing of
bounded sketch segments (`b.length = in [3mm, 8mm] minimize` on
`uav_talon` WingSpar, `arm_a6` UpperArm/Forearm, `cubesat` SidePanel).

## Decision

STOPPED after the keystone per the dispatch's hard gate: NO code
changes landed. Drafted WO-97
(`docs/workflow/work-orders/WO-97-bounded-sketch-optimize.md`) instead
of proceeding, because the optimizer<->claim coupling for sketch
segments requires genuinely new design, not wiring.

## What was verified buildable by precedent (not the blocker)

- `SegmentLength::Bounded(lo, hi)` + `close_walk` support in
  `crates/regolith-ir` -- same shape as `SlotValue::Bounded` in
  `crates/regolith-lower/src/removal.rs`.
- Payload/schema surfacing (`SCHEMA_VERSION` bump, `cause: "planner"`
  spelling) -- direct copy of the removal.rs precedent.
- The continuous optimizer driver itself
  (`optimize_continuous_golden_section`,
  `python/regolith/orchestrator/optimize.py`) -- already landed and
  proven (WO-55/WO-70).

## What is NOT an existing mechanism (the blocker)

`tests/orchestrator/test_wo70_uav_talon_optimize.py` proves the driver
against a per-test, hand-built `Evaluator` closure
(`_spar_cap_program` + a bespoke mass formula) -- it does not
demonstrate any production path that builds an evaluator generically
from a real part's declared claims. The production posture for every
EXISTING bounded planner slot (Ribs/PocketGrid count/pitch/thickness,
`python/regolith/orchestrator/programs.py::_family_ops`) is to leave
the value unpinned and refuse to realize geometry until the optimizer
pins it -- there is no code anywhere that runs that pin automatically
against a discharged claim. `regolith optimize`
(`python/regolith/cli/app.py`) wires only the discrete driver (choice
points), never the continuous one, to a real evaluator.

Landing bounded sketch segments therefore requires deciding, as new
design (not precedent-following wiring):

1. how a bounded segment names/discovers the claim(s) it must satisfy
   (declared link vs. structural inference by part name);
2. how the per-candidate FeatureProgram is built without duplicating
   the Rust closure solve in Python (re-run `close_walk` per
   candidate, treating the probed segment as `Pinned(x)`, is the
   leading candidate but is a new Rust-callable surface, not existing
   today);
3. the multi-bounded-segment-per-part objective shape (one
   `nelder_mead` search vs. N independent 1-D searches);
4. where the discharge call lives without creating a second compiler
   entry point (AD-4) -- `staged_build` (WO-57's named seam) is the
   likely home but is unproven against a real bounded sketch segment.

## Status

hematite/07 sec. 2a's bullet ("bounded `in [lo, hi]` slots carry the
`planner` cause -- ordinary optimizer territory") is UNCHANGED: it is
still true that these are planner/optimizer territory, but "ordinary"
undersells it -- the sketch-segment case is the first bounded slot
whose claim-coupling has no production precedent, which is exactly
why WO-97 exists rather than a same-session landing. No reopen: this
is new forward work, not a reversal of a prior decision.
