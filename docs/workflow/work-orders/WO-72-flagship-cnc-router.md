# WO-72: flagship cnc_router_r1 (CNC router, built end-to-end)

Status: todo
Depends: the landed cycle-30/31 toolchain (SCHEMA_VERSION 25); NO
schema bump, NO crates/ changes (AD-22: escalate gaps into the
ledger). Template: WO-64's A->C arc and ledger discipline -- read
its FULL ledger first; this WO inherits its acceptance shape.
Language: corpus authoring + records refs + tests; Python only for
test/golden enrollment.
Spec: 31-flagships.md (NORMATIVE) + design-log 2026-07-10-cycle-32
D183 (this flagship's row names its REQUIRED surfaces); AD-33/D170
(parity bar); the track guides.

## Scope highlights

`examples/flagships/cnc_router_r1/`: a 600x600mm-class CNC router.
Architecture: frame + gantry (realize the plate/extrusion parts;
the gantry as a RealizedAssembly), spindle mount, motion (std.motion
leadscrews/rails/steppers), controller boundary + harness. Feldspar
surfaces REQUIRED: frame2d stiffness/deflection on the gantry beam
under a declared cutting-force case; bolted-joint checks on the
gantry joints; bearing life on the rail/leadscrew bearings
(ISO 281 over std.bearings-shaped ratings). Optimization REQUIRED:
gantry plate/beam dims minimized against the deflection claim
through the staged evaluator. CAM SELF-HOSTING REQUIRED: at least
one of its own realized plate parts carries `plan: extern(...)`
G-code verified by std.cam end-to-end (the WO-69 chain) -- the
machine's parts are checked for manufacturability on a machine
class from std.machines.

## Acceptance shape (inherited from WO-64 + D183)

- `regolith check` clean whole-project; corpus-enrolled (the
  flagships root is already in _CORPUS_ROOTS); contract-graph sheet
  golden.
- The D183-required surfaces DEMONSTRATED: real `regolith optimize`
  runs pinning with cause+trace; the named feldspar model families
  discharging with cited evidence; ship artifacts (sheets/schedules
  as applicable) deterministic and audit-clean.
- Parity accounting measured and ledgered (attention fully
  accounted; zero report errors/waivers); every todo!/wall recorded
  per-site with spec citations.
- `make check` green; Status flipped to done-or-honest-partial with
  the full ledger.

## Coordinator wiring dispatch (pre-flight, unblocks the D183
## bolted-joint/bearing-life surfaces above)

A flagship builder escalated live that two claim-kind wiring gaps
would block this WO's bolted-joint and bearing-life demonstrations
before the flagship's own corpus authoring even starts. Closed as a
standalone Python-only wiring dispatch (no crates/, no schema bump,
worktree-isolated); recorded here per that dispatch's own
instruction, since it exists to unblock this WO.

**(a) What routed where.**
`python/regolith/orchestrator/translate.py` had NO dispatch entry for
either claim kind (only `mech.deflection`/`civil.utilization` were
wired, via `_FRAME_MODEL_KIND`). Added:
- `_match_call_lhs` + a check right after the ordinary `_split_
  comparator` split: a `mech.bolt.joint_separation(...)`/`mech.
  bearing.l10_hours(...)` call whose predicate fits one physical
  source line resolves its comparator DIRECTLY (`form.op` is already
  `>=`/`<=`, never the `"require"` placeholder) -- this is the path a
  real single-line caller hits, and the one the new regression test
  exercises.
- `_split_named_call_predicate` + a `form.op == "require"` check
  (mirroring the frame-predicate precedent) for the shape a
  multi-line/keyword-heavy call lowers through instead -- kept for
  forward compatibility even though the corpus's OWN multi-line calls
  of this shape hit the `rhs`-single-source-line truncation noted in
  (d) below, so this path does not yet fire on real corpus text.
- Both funnel into `_translate_call_kwargs_claim`: the model's own
  `INPUTS` (now public on both `bolted_joint.py`/`bearing_life.py`,
  mirroring `link_budget.py`'s `INPUTS`/`_INPUTS` pattern) are read as
  literal `name=value` keyword arguments on the call itself
  (`_parse_call_kwargs`), with `given.loads` consulted as a lower-
  priority second source for future threading (a mating's `preload:`/
  `scatter=` never reaches `given.loads` today -- verified live, see
  (e)) -- a missing input defers by NAME
  (`<claim_kind>_inputs_missing`), never a silent drop.
- `mech.bolt.joint_separation` -> `BoltedJointModel`
  (`bolted_joint_separation_vdi2230@1`, already registered, now
  reachable).
- `mech.bearing.l10_hours` -> `BearingL10HoursModel`
  (`bearing_basic_rating_life_l10h@1`, NEW model, see (c)), now
  registered in `harness/models/__init__.py`.

**(b) Branch + commits.** Worktree
`.claude/worktrees/agent-a5bd384f696eaab50`; see the worktree's own
commit log for the itemized commits (model, registration, translate
routing, regression tests).

**(c) Bearing-life model landed in-tree.**
`python/regolith/harness/models/bearing_life.py`: ISO 281:2007 basic
(unmodified) L10/L10h, cited to the standard + feldspar's own
`docs/benchmarks-memo.md` sec. 11, worst-corner interval evaluation
(INV-9) plus a documented 50% conservative haircut standing in for
the un-applied `a_iso` factor (named cut, same shape as feldspar's
own `bearing_life.py`). Unit tests: `tests/harness/test_bearing_
life.py` (known-answer, discharge/violated, corner conservatism,
domain guard, determinism -- mirrors `test_bolted_joint.py`).

**(d) Corpus-file dispositions (honest, not forced).**
`examples/systems/reaction_wheel/shaft_bearings.hema`'s `b10` claim
and `examples/systems/dune_buggy/upright_hub_front.hema`'s `life`/
`static` claims (plus `engine_top_end.hema`'s `clamp`/`cap_bolts`
bolt claims) are UNCHANGED by this dispatch -- still `unsupported_op`
("comparator 'require' defers"), reason identical to before. Verified
live (not assumed): every one of these calls wraps its argument list
onto a second source line, and the Rust lowering's `rhs`/predicate
capture for the `op="require"` opaque path is truncated at that first
line's end (confirmed via direct `compiler.check` + `Obligation`
inspection -- e.g. `life`'s `rhs` is literally
`'mech.bearing.l10_hours(pair=tapered_32005,'`, cut off mid
argument-list, comparator and bound never seen). That is a Rust CST/
lowering limitation (`crates/regolith-lower/src/claims.rs`), out of
this dispatch's scope (no crates/ changes allowed) -- fixing it is a
named follow-up for whoever picks up the real corpus authoring here,
not something this wiring dispatch could discharge honestly. `tests/
golden/test_deferral_corpus.py -k dune_buggy` still passes unchanged
(same reason string), confirmed live; `reaction_wheel` was already
NOT enrolled in either golden suite (D148 note, `test_golden_
corpus.py`) so there is no golden to regenerate for it either way.

**(e) Feldspar-route decision.** Checked `feldspar.pack.register()`
(`../feldspar/python/feldspar/pack/models.py`, read-only): it exposes
exactly six `regolith.harness.Model`s through the plugin seam (WO-44/
AD-26) -- stress/deflection (x3 incl. the geometry-payload variant),
stiffness, and elec-rail (x2). `feldspar.library.bearing_life`
(ISO 281 L10/L10h, same citation) exists but is registered ONLY into
feldspar's own internal `feldspar.solve.SolverRegistry` (consumed by
the generic FEA/stress/deflection models' TARGET-kind dispatch), never
surfaced as a `mech.bearing.l10_hours`-claim-kind harness `Model`. No
live plugin-seam route exists today -- landing the thin in-tree model
(c) was the honest choice per the dispatch's own instruction; exposing
feldspar's bearing_life route through the plugin seam is a feldspar-
side follow-up (its own repo, its own WO), recorded here as a named
gap, not invented or worked around.
