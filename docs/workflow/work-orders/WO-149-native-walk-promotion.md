# WO-149 -- native-walk fitting / "promote to native profile" (v1.5, UNSCHEDULED) (D261.4)

Status: open (Depends: WO-148, done; v1.5 -- NOT scheduled this cycle,
  named here only so the reopen criterion and scope are recorded
  before the pressure to slip it in mid-build arrives)
Language: Rust (`regolith-lower` promotion-surface extension) +
  Python (studio-side consumer, if/when dispatched -- graphite's
  half is a separate future graphite WO, not opened here).
Spec: `scratch_recon_graphite_cad.md` sec. 6c (option (c), "parameter
  extraction: trace -> fitted primitives -> existing constructs" --
  disposition v1.5, explicitly NOT the v1 spine); sec. 7b (reopen
  criterion: "the first user who traces a plate and then needs to
  parametrize it"); `crates/regolith-ir/src/sketch.rs:133-167`
  (`WalkPromotion` -- cardinal lines only; arcs, non-cardinal/`angled`
  lines, revolve closure are each a NAMED `WalkPromotion::Unsupported`
  today; this future WO is the promotion-surface extension that would
  change that).

## Goal (deferred -- this is a scope-freezing stub, not a dispatch)

A traced `.rgp` profile whose fit is EXACT against a small set of
primitives (lines at any angle, arcs) can be "promoted" to a native
hematite `profile` block (`walk:` + `constraints:`) emitting
walk/constraint text a human could review as design intent, rather
than staying a resolved-outline extern reference -- turning a traced
plate into a parametric, editable native profile.

## Why this is NOT scheduled

The recon (sec. 6, option (a) vs (b) vs (c)) is explicit: emitting
native walk/constraint text for a GENERAL dense trace (dozens of
segments at arbitrary measured angles) is either unreadable (tens of
non-obviously-related constraint lines) or requires extending
`regolith-lower`'s promotion surface to accept pinned non-cardinal
lines -- a golden-hash-affecting change with its own window
adjudication, not a rider on the scan-trace v1 slice (WO-146..148).
Shipping this before there is a real user need risks building fitting
machinery nobody exercises against real traces yet.

## Reopen criterion (the ONLY thing that un-freezes this WO)

The first real user who traces a plate through the WO-146..148 /
WO-G11..G13 pipeline and then explicitly needs to parametrize it
(edit a traced dimension as design intent rather than re-trace) is
the trigger. Until that user and that trace exist, this WO stays
`open` in name only -- do not dispatch it speculatively.

## Deliverables (when eventually dispatched -- NOT this cycle)

1. Promotion-surface extension in `regolith-lower`: accept PINNED
   non-cardinal lines and arcs (measured angle/length constraints,
   not solved) -- this is the same extension the recon names as the
   natural trigger for closing `WalkPromotion::Unsupported`'s
   non-cardinal-line gap.
2. A "promote to native profile" action (studio-side, when
   dispatched) that emits walk+constraints text WHEN the fit is
   exact against the closed primitive set (lines + arcs; no spline
   fallback, per the language's permanent no-splines rule).
3. Fit-quality honesty: a promotion that is NOT exact (residual above
   a stated tolerance) is REFUSED, not silently approximated -- the
   user stays on the extern-`.rgp` path for that trace.

## Out of scope (this cycle, entirely)

- Everything above is out of scope for cycle 37. This WO file exists
  only to record the reopen criterion and prevent silent scope creep
  into WO-146/147/148/G11/G12/G13.

## Acceptance

- This WO is not dispatched this cycle. Its acceptance criterion, for
  NOW, is that it stays un-dispatched and its reopen criterion is
  legible: a future coordinator reading this file alone can decide
  whether the trigger has occurred, without re-deriving the recon's
  option (c) argument.

## Escalation

If pressure arises during WO-146..148/WO-G11..G13 dispatch to fold
any native-walk-promotion behavior into those WOs "since we're
already in the area," escalate rather than absorb -- this WO's
existence is the record that the scope was deliberately deferred, not
overlooked.
