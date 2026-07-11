# WO-86 -- CG/moment-budget claim kind

Status: done
Language: Rust (regolith-ir budgets) + Python (translate/model) +
  corpus (uav_talon)
Spec: F112 ("CG/moment budget kind (uav)", verbatim); the uav_talon
  corpus (grep its sources for the CG/moment commentary -- the ask
  originated as its fleet escalation, the inline comments are the
  primary evidence, the WO-85 pattern); regolith/05-class budget
  arithmetic (mass budgets are the landed precedent -- READ how
  `mech.mass(all)` budgets lower and discharge before designing
  anything); hematite/03 (claim forms).

## Goal

A center-of-gravity / moment budget is mass-budget arithmetic with
a position weight: sum(m_i * x_i) over declared part masses and
positions, compared against a declared envelope. The uav's flight
stability ask needs the CG position claim to discharge from the
same declared data its mass budget already consumes.

## Deliverables

1. VERIFY FIRST (keystone, the WO-89 pattern): what the uav
   sources actually declare (the claim spelling they want), and
   what the landed mass-budget machinery already computes.
   Undeclared spellings are escalations with recommendations --
   do NOT invent grammar; if the existing budget forms cover the
   ask with a weighted-sum extension at the translate/model layer
   ONLY, prefer that (no grammar change).
2. The lowering/translate/model path for the declared form; part
   positions come from declared data (placements/mounts), never
   realized geometry in v1 (that is the realized-fact channel's
   future).
3. uav census before/after; goldens; tests; docs.

## Acceptance criteria

- The uav CG claim forms an obligation and discharges or defers
  with a specific named-input reason; zero fleet regression;
  no SCHEMA_VERSION bump (escalate if forced); make check green.

## Dependencies

None hard (WO-85/92 landed). Serializes with WO-88 at integration
only through goldens.

## Closeout (D204)

Deliverable-1 keystone finding: the WO's premise ("mass budgets are
the landed precedent") does not hold on inspection.
`close_budget` (`crates/regolith-ir/src/budget.rs`) is called from
`regolith-lower/src/contracts.rs` with an EMPTY contributions slice
for every `budget` block -- the doc comment there says the wiring is
future work ("the moment contributions land, `close_budget` starts
reporting E0432 with no pipeline change"); no evaluator anywhere
resolves `mech.mass(...)` to a numeric literal. And `uav_talon.cupr`
declared no CG claim at all pre-WO-86 -- only forward-looking
commentary citing WO-70's own W2 wall. There is no undeclared
spelling to discover (nothing was declared) and no landed weighted-
sum-extendable machinery to extend (mass budgets do not compute
either).

ESCALATED rather than invented: no new `kind=` budget-math syntax
(AD-22), no numeric CG model built over undeclared part-position
data. Implemented instead: one `require` claim in `uav_talon.cupr`
(`require CGEnvelope: cg_ok: mech.cg(members=[...]) in [0.40m,
0.55m]`) using the existing generic `require` call-form grammar (no
grammar change), and a translate-layer-only handler
(`python/regolith/orchestrator/translate.py::_translate_cg_moment`)
that forms a real, named obligation and defers it honestly
(`Deferral(reason="cg_moment_no_declared_position_data", ...)`,
naming both missing inputs). See design-log 2026-07-10-cycle-33 D204
for the full writeup and the sharpened WO-70 W2 reopen criterion.

uav_talon census: 28 -> 29 obligations (`cg_ok` new, deferred).
Zero fleet regression (`tests/golden/test_deferral_corpus.py`,
`tests/test_flagship_uav_talon_*`, `tests/harness/
test_wo70_uav_talon_discharge.py`, `tests/orchestrator/
test_wo70_uav_talon_optimize.py` all pass unchanged). No
SCHEMA_VERSION bump; no Rust changes. New tests:
`tests/orchestrator/test_wo86_cg_moment_budget.py` (4 cases: the
claim forms an obligation, defers with the named reason via
`translate` directly, defers via the real `discharge_all` path, and
`regolith check` stays clean over uav_talon). `make check` green.
