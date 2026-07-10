# WO-65: the five-design section-search verdict flip (WO-56 residual reopen)

Status: todo (GATED: dispatch only after feldspar WO-23 lands --
this is the WO-56 accepted residual's named reopen criterion, F108)
Depends: feldspar WO-23 (DONE, merged on feldspar main -- read its
close-out: the transfers/source_intensities seam + capacity cut),
WO-62 slice B (HARD: FramePayload.transfers rides its bump, D176),
feldspar WO-24's capacity forms (SOFT: without them, utilization
claims defer with `capacity_unresolved` -- specific, not blanket),
WO-56/WO-60 (landed). NO schema bump here (slice B owns it).
Language: Python (orchestrator wiring, corpus goldens).
Spec: docs/spec/toolchain/28-optimization.md sec. 5 (the WO-56
acceptance this completes), WO-56's Completion dispatch record (the
member-by-member audit plan it recorded), WO-48's close-out (the
original member list: footbridge G1/G2, bus_shelter G1, pole_barn
T1, small_office G2_AB/GR_AB), design-log 2026-07-09-cycle-31 D173.

## Goal

With demands derivable (feldspar WO-23), section search runs over
the five ratified calcite designs: `section: free` members resolve
via `optimize_discrete` over std.civil catalogs against real
utilization/deflection feasibility, corpus deferral goldens flip to
verdicts with `cause: optimize(...)` rows, and the WO-56 residual
closes.

## Deliverables

1. Per-member load-targeting audit (the WO-56 completion record's
   plan): classify each named member direct vs tributary; wire the
   tributary members through the new feldspar surface.
2. Section-search evaluator: candidates from the member's declared
   family over std.civil (metric-key members whose family has no
   landed rows keep a specific deferral -- the WO-60 honesty note
   stands; never guess conversions).
3. Corpus run + goldens: regenerated deferral/lockfile goldens; the
   flip is member-by-member accounted (flipped vs deferred + why).
   retaining_wall heel_sg stays geotech-deferred.
4. Docs: WO-56 residual closed (Status + ledger cross-note), guide
   optimization section's corpus example, this WO's ledger.

## Acceptance criteria

- Every auditable member either flips to a real verdict with an
  optimize cause + trace, or carries a SPECIFIC deferral reason
  (family-not-landed / tributary-not-declared) -- zero blanket
  deferrals remain in the five designs' structural claims.
- Zero churn in unrelated goldens; no schema change; `make install`
  + `make check` green; both Status lines updated.
