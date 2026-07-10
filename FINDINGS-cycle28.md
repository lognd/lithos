# Cycle-28 audit findings

Scope: costing chain, calcite/frame chain, drawings, plugin/D154 seam,
feldspar WO-20/WO-21 residuals, cross-repo frame payload contract.
Read-only audit. lithos 7e7b687, feldspar 24592cc. Known-accepted
items from the brief are not re-reported. 0 HIGH / 6 MEDIUM / 3 LOW.

## HIGH

None found. The money/determinism seams checked most closely (the
`as_of` expiry seam, deferral-never-cached rule, content-address
stability) hold up; the defects below are real but each is bounded by
an unusual trigger or currently masked by the frame
property-resolution indeterminacy.

## MEDIUM

### M1. Cross-currency line items summed as one currency (silent wrong total)
- File: `python/regolith/harness/models/cost_common.py:224-232`
  (`_finish`); line units come from `chosen.unit_price.unit` in
  `bom_estimate`/`fluid_bom_estimate`.
- `_finish` sets total unit to `profile.currency` and sums each line's
  numeric `extended.lo/.hi` with no check that line currency equals
  `profile.currency` (or matches across lines). No currency-consistency
  validation exists in the chain (`resolve_profile_inputs` doesn't
  check it either).
- Scenario: profile `currency = "USD"` but a selected pricing record's
  `unit_price` is `"EUR"`. Estimator sums `100 (EUR) + 50 (USD)` into
  `total {lo:150, unit:"USD"}`; claim `mfg.cost(x) <= 160 USD`
  discharges against a meaningless number. Evidence payload looks
  internally consistent.
- Fix: in `_finish`/`resolve_profile_inputs`, reject or defer when any
  priced line's currency differs from `profile.currency`, naming the
  record and unit.

### M2. Feldspar frame consumer silently drops distributed loads whose target is not a member id [FIXED]

Fixed in feldspar `audit-fixes` branch (commit 2df6f6c):
`solve_frame_payload` now scans every `load_case`-matching load before
assembling members and returns `SolveError.OutOfDomain` naming the
target if a `"distributed"`-kind load's target matches no member id,
instead of silently contributing zero. Tributary/`on [...]` resolution
itself is left as lithos-side future work per the finding's fix
direction. Test:
`test_unmatched_distributed_load_target_is_honest_indeterminate`
(fails before the fix -- the old code returned `Ok` with the load
silently dropped; passes after).

Original finding:
- File: `python/feldspar/library/struct.py:276`.
- Distributed loads apply only when `load["target"] == mid`. But
  `regolith-lower::frame_lower::on_target`
  (crates/regolith-lower/src/frame_lower.rs:502) extracts the first
  name in the source `on [<target>]` bracket, which for civil designs
  is typically a level/region/deck name, not a member declaration
  name. A region-targeted load matches no member and no joint ->
  contributes zero.
- Scenario: `loads: live: 4.1 kPa on [Deck]` where `Deck` is a
  slab/level, not beam `G1`. `solve_frame_payload` (a documented
  public seam callers may drive with out-of-band EA/EI) solves with
  the load entirely absent, understating demand; a downstream
  deflection/utilization check reads "safe." Masked for the registered
  direction (OutOfDomains on properties first) but live for direct
  callers.
- Fix: resolve load-target-to-member (tributary/`on [...]`), or until
  then make an unmatched non-`derived` target an honest `OutOfDomain`
  rather than a silent drop.

### M3. Frame consumer uses interval `.lo` only for loads and lengths (unconservative silent result) [FIXED]

Fixed in feldspar `audit-fixes` branch (commit 2df6f6c), together with
M4 (same call sites): loads (both member distributed UDLs and joint
point loads) are now solved at the interval's `.hi` (conservative)
corner via `_scalar_to_si`, and a single `assumptions` entry records
the `.hi` corner choice ("lengths/geometry solved at their (degenerate)
nominal value" -- see M4). Test:
`test_propped_cantilever_udl_matches_closed_form` /
`test_empty_member_release_defaults_to_rigid_and_is_recorded` were
extended to assert the `.hi`-corner assumption string is present (2
assumptions instead of 1; failed before the fix since the old code
never appended a corner-choice assumption, passes after).

Original finding:
- File: `python/feldspar/library/struct.py:254, 298, 339`.
- Every payload `ScalarInterval` is collapsed to its lower bound. For
  a load magnitude, `lo` is the least demanding value; the
  conservative choice for a safety check is `hi`. Not documented as a
  deliberate lower-corner solve; result payload doesn't record which
  corner was used.
- Scenario: load `[3.5, 4.5] kN/m` solved at `3.5` understates end
  forces ~22%; utilization discharges as safe when the upper bound
  would exceed capacity. Uncatchable by inspecting the result.
- Fix: choose the corner explicitly (drive loads at `.hi` for safety,
  or solve both corners), and record it in `assumptions`.

### M4. Frame consumer ignores `ScalarInterval.unit` on member length (assumes meters) [FIXED]

Fixed in feldspar `audit-fixes` branch (commit 2df6f6c): member length
is normalized to SI meters via a new `_length_to_si_m` helper (built
on `feldspar.core.UnitSystem.builtin()`), which also asserts the
payload-contract expectation that a resolved length is a degenerate
(`lo == hi`) interval (an honest `OutOfDomain` if that invariant
breaks, rather than silently picking one bound). The load-value unit
at 298/339 is normalized the same way via `_scalar_to_si`; an
unrecognized unit label (e.g. a compound like `kN/m`, which the
built-in unit table does not carry) is an honest `OutOfDomain` naming
the unit rather than an assumed-SI mix. Tests:
`test_member_length_in_millimeters_is_normalized_to_si` (fails before
the fix -- old code multiplied the raw `6000.0` by orientation
unit-vectors, producing a physically wrong stiffness/reaction; passes
after) and `test_member_length_nondegenerate_interval_is_honest_indeterminate`
(new degenerate-interval guard).

Original finding:
- File: `python/feldspar/library/struct.py:254` (param named
  `length_m`).
- Consumer treats the numeric length as meters, never inspecting
  `m["length"]["unit"]`. `member_length`
  (crates/regolith-lower/src/frame_lower.rs:392-402) only *defaults*
  to `"m"`; it propagates whatever unit the grid/level datum offsets
  carry. EA/EI are supplied in SI, so a non-meter length silently
  mixes units in the stiffness assembly.
- Scenario: datums resolving in `mm` -> `length {lo:12000, unit:"mm"}`
  used as 12000 m, a 1000x error destroying the stiffness matrix. No
  boundary assertion.
- Fix: normalize/assert the length unit (convert to m or
  `OutOfDomain`); same guard for the load-value unit ignored at
  298/339.

### M5. thermo CoolProp `PropsSI` ValueError unguarded (crash instead of honest OutOfDomain) [FIXED]

Fixed in feldspar `audit-fixes` branch (commit 7020951): `fn`'s
`PropsSI` call is now wrapped `try/except ValueError ->
SolveError.OutOfDomain`, and a non-finite return is likewise rejected
as `OutOfDomain` (mirrors `struct.py`'s mapping). Test:
`test_propsi_valueerror_is_honest_out_of_domain_not_a_crash`, using
`(T=273.16, P=611.0)` for water -- inside the declared box but just
below the triple-point pressure at Tmin, a real CoolProp `ValueError`
trigger (verified against the installed `CoolProp` package). Confirmed
failing (unhandled `ValueError` propagating out of `fn`) before the
fix and passing after.

Original finding:
- File: `python/feldspar/library/thermo.py:146-148`.
- No try/except around `PropsSI`, which raises `ValueError` for
  unsupported/out-of-range states and can return non-finite values.
  The rectangular T-P `Domain` box does not guarantee CoolProp accepts
  every interior point (saturation line, sub-triple-point, rejected
  `T,P` pairs). Contrast `struct.py:340-347` which correctly maps
  `ValueError -> SolveError.OutOfDomain`.
- Scenario: water density at an in-box corner on the saturation dome
  -> `PropsSI` raises -> unhandled crash instead of recoverable
  `OutOfDomain`, aborting the build.
- Fix: wrap `propsi(...)` in `try/except ValueError -> OutOfDomain`
  and reject non-finite returns (mirror `struct.py`).

### M6. Persisted cost estimate may not match the discharging model's verdict for a mixed-basis subject
- File: `python/regolith/orchestrator/costing.py` (`_estimate_fn_for`
  cascade + `persist_estimates`).
- `persist_estimates` re-derives the estimator from populated bases in
  a fixed priority (frame > bom > flownet) and claims it reproduces
  "the SAME one the discharging model computed." But the model is
  chosen by registry D94 kind competition on per-basis signatures, not
  this cascade. A doc carrying multiple bases (e.g. subject `"all"`
  with both `frame_members` and `bom`) gets a civil-takeoff evidence
  payload while the claim may have been discharged by `bom_estimate`
  -> auditable evidence total differs from the verdict.
- Fix: thread the model's selected estimate digest through the
  obligation result and reuse it, or guarantee/assert one basis per
  doc.

## LOW

### L1. Cost profile quantity/markup accept booleans
- File: `python/regolith/magnetite/manifest.py:182,192`.
  `isinstance(True,(int,float))` is True, so `quantity = true` ->
  `1.0` silently. Fix: reject `bool` explicitly.

### L2. Calcite egress reachability treats access openings as directed edges (possible false E0205)
- File: `crates/regolith-lower/src/calcite.rs:142-155` fed by
  `:212-214`. BFS follows each opening only in its `(from -> to)`
  sense; a reverse-authored opening would report a genuinely connected
  space unreachable. Safe only if the spec guarantees egress-directed
  authoring. Fix: push both directions if openings are bidirectional,
  else document/test the orientation invariant.

### L3. Hardy-Cross all-imposer loop silently uncorrected [FIXED]

Fixed in feldspar `audit-fixes` branch (commit ee7f3d3): when a
cycle-basis loop's `denominator == 0.0` (only possible for an
all-imposer loop, since real pipes always contribute a positive `k`),
`_hardy_cross_solve` now returns `SolveError.OutOfDomain` (tag
`all_imposer_loop`) naming the loop's edges instead of `continue`-ing
past it. Test: `test_all_imposer_cycle_loop_is_honest_indeterminate`
builds two parallel imposer edges between the same node pair
(continuity fully satisfied, 0.6e-4 + 0.4e-4 = 1e-4) -- confirmed the
pre-fix code reported "converged in 1 iterations" for this case
(verified by reverting the fix and rerunning); passes (honest `Err`)
after.

Original finding:
- File: `python/feldspar/library/fluids/network.py:466-470`
  (`if denominator == 0.0: continue`). A cycle-basis loop of only
  fixed-flow imposer edges is skipped every iteration; its head
  imbalance is never driven to zero yet `max_dq` stays 0, so an
  infeasible loop can report "converged." Fix: detect non-zero head
  imbalance on an all-imposer loop and return
  `OutOfDomain`/`NoConvergence`.

### M7. Frame consumer's joint point-load loop silently drops loads whose target is not a joint id [FIXED]

Self-spotted follow-up (found while fixing M2, cycle-28 audit; not in
the original auditor's report -- filed and fixed as its own item per
coordinator instruction). Fixed in feldspar `audit-fixes` branch
(commit 7cb584e).

- File: `python/feldspar/library/struct.py` (joint point-load loop,
  originally `if load["case"] != load_case or load["target"] not in
  joint_index: continue`).
- The joint point-load loop combined the `load_case` mismatch check
  and the `target not in joint_index` check into one `continue`,
  exactly the same silent-drop pattern M2 named for distributed
  loads: a `"point"`-kind load whose target matches no joint id
  contributed zero to `joint_loads` instead of erroring, understating
  demand with no trace in the result payload.
- Fix: split the case-mismatch and kind checks from the target-match
  check; a `"point"`-kind load (for the active `load_case`) whose
  target matches no joint id now returns `SolveError.OutOfDomain`
  naming the target, instead of silently dropping it.
- Test: `test_unmatched_point_load_target_is_honest_indeterminate`
  (`tests/unit/test_library_struct.py`) appends a `"point"` load
  targeting `"NoSuchJoint"` to the propped-cantilever fixture;
  confirmed `Ok` (load silently dropped) before the fix, `Err`
  (`OutOfDomain` naming `"NoSuchJoint"`) after.

## Notes

Checked and correct (don't re-verify): `as_of` clock seam single-homed
in `load_cost_context`, expiry -> uncached deferral, pins recorded
only after the expiry gate, unparseable `valid_until` treated as
expired; `load_cost_records` first-key-wins with sorted paths;
`price_break_at` tie/below-threshold handling; `discover_plugins`
per-kind dedup and sorted deterministic composition; `ship.py`
derived/explicit merge and backend namespacing; `civil_plan_section`
correctly preserves `length.unit` (unlike M4) and sorts; `frame.rs`
`datum_kind` tag choice; `parse_cost_claim_args` (E0438) validation.

Deliberately skipped/skimmed: `orchestrator/translate.py` cost
lowering and any frame-resolution orchestrator code newer than 7e7b687
(active churn at audit time; M6 flagged from the `costing.py` side
only); the 23 xfails and recorded cuts; feldspar `mech/frame.rs` Rust
linear algebra (trusted its benchmark suite; audited the Python
boundary feeding it); stdlib numeric content pedantry (contract shape
only per brief).
