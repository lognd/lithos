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

## Cuts recorded this cycle (dispatch of 2026-07-06)

This dispatch landed deliverables 1 and 2 of the claim-form lowering
list (unit-suffix bound resolution via `regolith-qty`; `within [lo,
hi]` windows splitting into two one-sided obligations), plus the new
`tests/golden/test_deferral_corpus.py` deferral-list golden the first
acceptance bullet names. It also fixed an upstream bug this work
surfaced: `regolith_syntax::ast::Field::value()` returns only the
FIRST value-ish CST child, silently dropping a claim predicate's
continuation text (the `within [...]` clause in particular) -- claims
lowering now reads the field's full source text past its `name:`
separator instead.

Everything else in this WO's deliverable list is an explicit, open cut
-- not silently dropped, not worked around with an invented shape:

1. **Temporal/containment typed payloads** (deliverable 3: `peak`/
   `settles`/`overshoot`/`rms(band=)`/`stays_within(mask)`). This is a
   genuine SPEC AMBIGUITY, escalated rather than resolved by
   invention: `regolith_oblig::ClaimForm` already carries typed
   variants for these forms (`Peak`, `Settles`, `Overshoot`, `Rms`,
   `StaysWithin`), but NONE of them has a comparator/limit field, and
   the corpus's actual usage is inconsistent with a single shape --
   `rms(v(out), band=...) < 20mV` and `peak(sig, during w) <
   material.sigma_y(T)/2` embed their bound OUTSIDE the call, while
   `settles(...)`, `stays_within(..., mask=...)`, and `overshoot(...)`
   in the corpus carry NO trailing comparator at all (the tolerance/
   mask IS the claim). Wiring `claims.rs` to actually construct these
   `ClaimForm` variants requires deciding, per form, whether/where a
   bound attaches -- a schema-shape decision, not a parsing detail.
   Per the dispatch protocol this is escalated to a design-log entry
   rather than guessed; guessing wrong here would need a schema
   regeneration (`make schema`) to undo. Consequently the acceptance
   bullet's `require Survival: settle/shock`/`require Noise: floor`
   claims are NOT hit by this dispatch (they remain `unsupported_op`
   deferrals) -- an honest miss on that half of bullet 1, recorded here
   rather than claimed done.
2. **dB term resolution for `require Link`** (the second acceptance
   bullet, Kestrel's `margin >= 6dB`). NOT discharged end-to-end. The
   claim's comparator sits mid-expression
   (`comms.pa_out + antenna.gain - path_loss(...) >= gs_uhf437.sensitivity
   + 6dB during op = downlink`), unlike every other require-line claim
   in the corpus (which all lead with `subject: <comparator> <bound>`).
   Every term but the trailing `6dB` is an entity-field reference or a
   function call with no numeric value threaded through the obligation
   today (`given_for_decl` only captures `material`/`loads` fields, not
   arbitrary cross-entity references). Reaching this claim needs BOTH
   expression-level comparator splitting AND entity-value threading
   with its own `Cause`-typed resolution (deliverable 4's "non-literal
   bounds resolved through the entity DB" note) -- each a design
   question in its own right, out of this dispatch's safe scope. The
   `link_budget.py` pack stays registered and unit-tested, just
   unreachable from the real corpus obligation.
3. **Name-matched conformance bound extraction** (deliverable 4, first
   half). `conformance_windows` in `claims.rs` still extracts the FIRST
   comparator-bound field per side (documented as a WO-19-era
   positional cut); matching promised bounds by NAME needs the WO-12
   contract IR's field identity, which does not exist yet. Left as is.
4. **Buck efficiency + transient packs.** Blocked upstream, not by
   pack-authoring effort: `Efficiency.eta` is a `forall i(out) in
   [0.2A, i_max]:` sweep-domain claim (`claims.rs`'s own documented
   "every obligation here is a single-point obligation" limitation --
   sweep-domain claim-line structure is not exposed at this grammar
   surface), and `Regulation.transient`/`Regulation.softstart` are
   instances of cut 1 above. No pack is useful until one of those two
   upstream gaps closes; adding one now would ship dead code.
5. **Numeric reduced-tier base class + lumped thermal reference pack,
   planner-model base class, INV-12 match-set-growth lockfile diff.**
   Not started. Each is its own design surface (the reduced-tier
   worst-corner-sweep contract API, the planner artifact's content-
   addressed evidence shape and `cause: planner` lockfile row, and a
   lockfile schema extension to carry waiver match sets across builds
   so a diff can flag growth) that this dispatch did not have room to
   design safely alongside the claim-lowering work above. Recorded
   here as fully open rather than half-built under time pressure.

Net: this dispatch is a genuine, tested, `make check`-green partial
completion of WO-26 -- 2 of 4 claim-lowering deliverables plus the
deferral-list golden infrastructure the acceptance criteria require,
with the remaining scope named precisely enough that a follow-up
dispatch can pick any cut up without rediscovery.
