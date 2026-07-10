# WO-65: the five-design section-search verdict flip (WO-56 residual reopen)

Status: un-gated (2026-07-10; WO-68 landed both blockers -- SCHEMA_
VERSION 25). Finding 3 (swept-obligation emission for nested named
claims inside `forall combo in ...:`) is fixed: `strength` obligations
now reach `BuildPayload.obligations` for all five designs. Finding 2
(no declared candidate-family field) is also closed:
`FrameMember.section_domain` now carries the family from each design's
`section: in registry(<family>)` (the five corpus designs updated,
WO-68's own deliverable 5); `frame_resolve.resolve_member` defers the
new, specific `frame_section_domain_unsearched` reason for these
members. What remains for THIS WO's reopen is exactly its original
scope: the section-search EVALUATOR itself (`optimize_discrete` over
the declared family, real std.civil catalog candidates, the verdict
flip) -- not landed by WO-68, which stopped at making the family
declarable and reachable per its own no-search-evaluator scope.
Previous blocked history (dispatched 2026-07-10; the per-member
audit ran, the tributary-transfer wiring landed (Python, real,
tested), and every named member's deferral reason was confirmed
honest and specific -- but the flip itself was NOT reachable that
pass: TWO independent blockers found, both outside this WO's
Language: Python / no-schema-bump scope) preserved below in "Dispatch
findings (2026-07-10)" and WO-56's matching dispatch record.
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

## Dispatch findings (2026-07-10)

Per-member audit result for the six named members (footbridge
G1/G2, bus_shelter G1, pole_barn T1, small_office G2_AB/GR_AB) --
EVERY one is `section: free` AND fed by a `Bearing(tributary=...)`
transfer:

1. Tributary-transfer demand resolution landed for real
   (`frame_resolve.resolve_tributary_demand`, consuming
   `FramePayload.transfers`/D176 -- WO-62 slice B, which post-dated
   this WO's original write-up). Tested, zero golden churn (no
   current obligation reaches it -- see finding 2 below).
2. `frame_section_free` is the correct, SPECIFIC deferral for all
   six: `FrameMember` carries no candidate-family field (adding one
   is a schema bump, out of scope), and inferring one from the
   member's `material` ref was rejected as an unprincipled numeric
   guess (`materials.toml` carries no material-class field, only
   `E_GPa`/`yield_MPa`). This satisfies the acceptance criterion's
   `family_not_landed` deferral class honestly.
3. A SEPARATE, more fundamental blocker: none of the five designs'
   `civil.utilization` ("strength") claims -- the `forall combo in
   std.civil.*.strength: strength: civil.utilization(...) <= 1.0`
   nested clause -- reach `BuildPayload.obligations` at all (verified
   live against `compiler.check`; confirmed absent from every
   `deferral_*.json` golden). This is a Rust lowering gap
   (`regolith-lower`'s swept-obligation emission for a nested named
   claim inside a `forall combo in ...:` block), not a Python
   orchestrator gap, and blocks the flip independently of finding 2.

Full detail in WO-56's "WO-65 dispatch record (2026-07-10)" section
(this WO's own predecessor ledger). Reopen criterion for WO-65: a
Rust dispatch lands `forall combo in ...:` nested-claim obligation
emission; THEN re-run this audit (finding 2 may still gate some
members on family, but `strength` claims for members with a resolved
`registry(...)` section, if any exist in a future corpus addition,
would already be reachable).
