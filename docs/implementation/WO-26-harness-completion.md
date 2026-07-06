# WO-26: Harness completion (claim-form lowering + remaining tiers)

Status: todo
Depends: WO-19 (claims.rs), WO-20 (numeric tier ships as packs where
external); Rust half touches `regolith-lower`/`regolith-oblig`
Language: both -- Rust for claim-form lowering in `claims.rs` /
`translate` inputs, Python for `orchestrator.translate` + packs
Spec: regolith/07 sec. 1-2 (claim forms), sec. 6 (planner models);
regolith/02 sec. 5 (time/frequency forms); TODO.md sec. 6 residuals;
`harness-phase-c.md` "Not yet built"

## Goal

Close every tracked harness gap so the corpus claims that today
defer honestly can actually discharge: the temporal/containment
claim forms lower to DischargeRequests, bound parsing stops being
positional/literal-only, and the remaining tracked packs land.

## Deliverables

- Claim-form lowering (the WO-05/WO-19 tracked cuts, in order of
  corpus value):
  1. unit-suffix resolution on bound text (a `20 mV` bound resolves
     through `regolith-qty`, not string matching);
  2. `within [lo, hi]` demanded windows -> two-sided requests;
  3. temporal/containment forms `peak`/`settles`/`overshoot`/
     `rms(band=)`/`stays_within(mask)` with their `during`/
     `within .. after` windows -> typed request payloads (the model
     declares which forms it serves via its signature);
  4. name-matched (not positional-first) conformance bound
     extraction; non-literal bounds resolved through the entity DB
     where the value has a Cause-typed resolution.
  Each step un-defers named corpus claims; each records what still
  defers (the deferral list is an asserted golden, so regressions
  and progress are both loud).
- dB term resolution for `require Link:` so the link-budget pack
  discharges the Kestrel downlink end-to-end (the tracked
  `harness-phase-c.md` gap).
- Remaining tracked packs: buck efficiency + transient claims
  (`# TODO(harness)` marker in `harness/models/__init__.py`).
- Numeric tier: the reduced-tier contract (worst-corner sweep over a
  numeric model, coverage declared per regolith/07 sec. 2 sweeps) as
  a base class packs implement; lumped thermal as the in-repo
  reference numeric pack.
- Planner adapters: the planner-model shape (plan artifact as
  content-addressed evidence, lockfile cause `planner`) as a base
  class; the WO-22 realizer and WO-24 binding retrofit onto it if
  they landed first (one shape, NO DUPLICATION).
- INV-12 residual: the waiver match-set-GROWTH check over the
  lockfile diff (TODO sec. 5 remaining surface), now that lockfile
  materialization exists.

## Acceptance

- The corpus deferral-list golden shrinks with each lowering step;
  `require Survival: settle/shock` and `require Noise: floor` class
  claims produce typed requests (discharged or model-absent
  indeterminate -- not `unsupported_op` deferrals).
- Kestrel `require Link: margin >= 6dB` discharges through
  `elec.link.margin` end-to-end via `orchestrator.build`.
- A waiver whose match set grows across builds is flagged from the
  lockfile diff (INV-12 fixture un-cut).
- `make check` green; `harness-phase-c.md` updated to current truth.
