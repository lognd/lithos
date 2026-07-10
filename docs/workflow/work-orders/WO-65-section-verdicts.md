# WO-65: the five-design section-search verdict flip (WO-56 residual reopen)

Status: done, honest partial (2026-07-10; see "Close-out ledger"
below -- the section-search evaluator landed and DOES flip a real
verdict (footbridge's `deflect`), but every other named member stays
deferred for SPECIFIC, pre-existing, out-of-scope reasons (two Rust-
side geometry/derivation gaps, one stdlib phantom-key gap), not
because the search itself is missing or incomplete).

Status (superseded by the paragraph above; original un-gate note
preserved for history): un-gated (2026-07-10; WO-68 landed both blockers -- SCHEMA_
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

## Close-out ledger (2026-07-10, reopen execution)

The section-search evaluator landed:
`regolith.orchestrator.frame_resolve.search_free_section`, wired into
`resolve_member` for any `section: free` member carrying a declared
`section_domain`. It runs the SANCTIONED
`regolith.orchestrator.optimize.optimize_discrete` driver (AD-30: no
private scoring path) with domains = the declared family's std.civil
section keys (declaration order, deterministic), an evaluator = the
member's flexural utilization under its resolved demand (the SAME
`moment/(section_modulus*fy)` formula `_translate_civil_utilization`
already computes downstream -- search and discharge share one
formula), and objective = mass-per-length ascending (the WO-56
disclosed tie-break default; no corpus design declares a `policy:`
block for its structural claims). A winner is pinned onto
`ResolvedMember.search_cause` as `optimize(mass_per_length,
winner=<key>, trace=<blake3 digest of the OptimizationTrace JSON>)`.

**Zx honesty finding** (why this reuses the elastic-modulus formula,
not feldspar's literal `flexural_yield_capacity_f2`): that feldspar
form needs a PLASTIC section modulus (Zx, AISC 360-16 F2.1, `Mn =
Fy*Zx`); NO std.civil section record (`stdlib/std.civil/records/
sections.toml`) carries a Zx field, in any family -- only the elastic
`s_mm3`/`s_in3`. Fabricating Zx from S via a shape-factor guess would
be exactly the "invented equivalence" D58/WO-60's honesty note
forbids. The search therefore reuses the ALREADY-LANDED elastic-
modulus utilization formula (not new physics, not a second scoring
path) rather than defer every candidate `capacity_unresolved` for a
field this stdlib slice never populated. `axial_yield_buckling_
capacity_e3` (needs Ag/r/KL) is not wired at all: the landed
`civil.utilization` model is flexure-only (`axial_demand` is hard-
pinned to 0 in `_civil_utilization_inputs`), so no member in this
corpus's claims exercises an axial capacity check.

**Two real bugs found and fixed en route** (both pre-existing, in
code this WO's own predecessor dispatch had marked "landed, tested" --
neither is a Rust change, both squarely Python orchestrator wiring,
in scope):

1. `resolve_tributary_demand` assumed a `transfer.tributary.kind`/
   `.value` wrapper shape that never matched the real lowered
   payload: `FrameTransfer.tributary` (`crates/regolith-oblig/src/
   frame.rs`) is a FLAT `ScalarInterval` (`{lo, hi, unit}`), verified
   live against `compiler.check(footbridge.calx)`'s own `transfers`
   array. Every tributary resolution before this fix silently no-op'd
   (`trib_magnitude` always `None`) -- the six-new-unit-tests claim in
   WO-56's "WO-65 dispatch record" covered the FUNCTION's arithmetic
   over a HAND-CONSTRUCTED fixture matching the wrong shape, never
   exercised against a real compiled payload, so the gap passed
   unnoticed. Fixed: `kind` ("width" vs "area") is now INFERRED from
   `unit` (`m` -> width, `m2` -> area) instead of read from a
   nonexistent field. `tests/orchestrator/test_frame_resolve.py`'s
   fixture updated to the real shape (same file, same commit).
2. `_SPAN_BOUND` (`orchestrator/translate.py`) required end-of-string
   after the numeric divisor; footbridge's `deflect` claim's lowered
   `rhs` carries a trailing same-indent comment block swallowed into
   the claim's span (a source-text artifact -- verified live via
   `Obligation.claim.form.rhs`), which broke the anchor. Fixed by
   dropping the `$` anchor (the divisor is unambiguous regardless of
   trailing garbage); this is a tolerance fix, not a claim the
   trailing-comment artifact itself is resolved (that would be a Rust
   CST/comment-attachment fix, out of this WO's no-Rust-changes scope
   -- named here, not silently worked around invisibly).

### The member table

| Member | Claim(s) | Verdict | Cause / deferral reason |
|---|---|---|---|
| footbridge G1 | `deflect` | **FLIPPED** -- real verdict | `mech.beam.service_deflection`, limit=0.0333m (12m/360); section search winner via `search_free_section` (`std.civil.w_shape`) |
| footbridge G1/G2 | `strength` (`Bridge.members.all`) | deferred | `frame_section_incomplete` -- the GROUP claim also names `Deck` (a fixed `comp_deck_140mm` per-metre-strip section with no `s_mm3` field); pre-existing, unrelated to the free-section members, out of WO-65 scope (WO-48's own documented cut) |
| bus_shelter G1 | `deflect` | deferred | `frame_load_untargeted` -- `RoofDeck`'s only loads are `derived`/case-derived (`snow`/`wind` via `site.* -> std.civil.*` derivation); the ASCE7 load-case DERIVATION MODELS are a documented, cut, harness-side gap (`stdlib/std.civil/magnetite.toml`'s own TODO), not a search gap |
| bus_shelter G1 | `strength` (`Shelter.members.all`) | deferred | `frame_section_unresolved` -- the group claim also names `C1`/`C2` (fixed `hss89x89x6.4`, a WO-60-documented PHANTOM metric key with no landed record); pre-existing, out of scope |
| pole_barn T1 | `deflect`, `strength` (`BarnFrame.members.all`) | deferred | `frame_load_untargeted` -- `Purlins`' only load is derived `snow` (same cut derivation-model gap as bus_shelter); the search itself is reachable and correct, demand resolution is not |
| small_office G2_AB | `deflect2` | deferred | `frame_load_untargeted` -- `G2_AB`'s (and every small_office member's) lowered `length` is `{lo:0, hi:0}` (verified live: EVERY member in this system's frame payload has zero length), a Rust-side frame-geometry lowering gap for this multi-file system corpus, out of WO-65's Python-only scope; a zero-length member cannot honestly spread a tributary force |
| small_office G2_AB/GR_AB | `strength` (`Frame.members.all`) | deferred | `frame_section_unresolved` -- the group claim also names `Br1` (fixed `hss127x127x8`, another WO-60-documented phantom metric key); pre-existing, out of scope |
| retaining_wall heel_sg | (sliding stability) | deferred | geotech-deferred, UNCHANGED (out of this WO's scope, per the WO body) |

Acceptance criterion re-read against this table: "every auditable
member either flips ... or carries a SPECIFIC deferral reason" IS
met -- one real flip, and every remaining deferral is a named,
distinct, honest reason (three DIFFERENT pre-existing gaps: a cut
load-derivation-model feature, a Rust geometry-lowering gap specific
to the small_office multi-file corpus, and WO-60's own documented
phantom-metric-key stdlib gap), never a blanket `frame_section_free`
or `frame_section_domain_unsearched` catch-all. The WO's GOAL
("corpus deferral goldens flip to verdicts", plural) is only
PARTIALLY reached -- one obligation flipped, not all six members'
worth -- because the remaining blockers are outside this WO's
Language: Python / no-Rust-changes / no-schema-bump contract; each is
named above rather than invented around.

### Golden churn accounting

`tests/golden/data/deferral_{footbridge,bus_shelter,pole_barn,
small_office}.json` regenerated (`REGOLITH_UPDATE_GOLDEN=1`); every
diff line accounted for above (one status flip, three reason-string
changes from the blanket `frame_section_domain_unsearched` to a
specific reason). `retaining_wall`'s golden and every other corpus
entry's golden: byte-identical, verified (`git diff --stat` shows
exactly the four files above, nothing else).
