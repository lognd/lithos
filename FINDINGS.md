# Audit findings -- cycle-29 fresh pass (HEAD 6c3f23f)

Scope: recently-touched costing subsystem (Python harness + orchestrator), the calcite egress-BFS fix, the magnetite manifest boundary, and the model registry / estimator-selection contract.

## HIGH

### H1. Civil takeoff defeats the cross-currency guard (silent EUR->USD discharge) [FIXED]

**Fix**: `civil_takeoff_estimate` (`python/regolith/harness/models/cost_common.py`) now derives the line's extended-interval currency from the unit-cost record itself (`uc.unit.split("/", 1)[0]`, e.g. `"EUR/m"` -> `"EUR"`) instead of hardcoding `profile.currency`. A mismatched record now reaches the `_finish` currency guard and is rejected with `currency_mismatch`, matching the BOM/fluid-BOM paths. Added `test_civil_takeoff_rejects_line_currency_mismatched_with_profile` mirroring the existing BOM test. Verified with `uv run pytest tests/harness/test_cost_estimators.py tests/orchestrator/test_costing.py`, `uv run ty check python/regolith`, `uv run ruff check`, and the full `uv run pytest` suite (674 passed).


- **Where**: `python/regolith/harness/models/cost_common.py`, `civil_takeoff_estimate`, line 371 (`extended=_interval(member.length.lo * uc.lo, member.length.hi * uc.hi, profile.currency)`), interacting with the guard in `_finish` lines 224-246.
- **What's wrong**: The cross-currency guard added in bb97b9f lives in `_finish` and compares each line's `line.extended.unit` against `profile.currency`. The BOM and fluid-BOM estimators set the extended unit from the record's own currency (`chosen.unit_price.unit`, lines 299 and 337), so the guard can see a mismatch. But `civil_takeoff_estimate` hardcodes the extended unit to `profile.currency` regardless of the unit-cost record's actual currency `uc.unit` (e.g. a record with `unit = "EUR/m"`). Because the line is labeled with the profile currency before the guard runs, `line.extended.unit != unit` is never true for the takeoff path -- the guard is structurally bypassed.
- **Failure scenario**: A profile with `currency = "USD"` selects a per-meter unit-cost record whose `unit_cost = { lo=..., hi=..., unit = "EUR/m" }`. `civil_takeoff_estimate` multiplies member length by the EUR figures, stamps the extended interval `"USD"`, and `_finish` sums/totals it under `"USD"` with no complaint. A EUR-priced record silently discharges a USD `mfg.cost` upper-bound claim -- the exact class of bug bb97b9f closed for the other two bases, still open here.
- **Fix direction**: Derive the line currency from the record, not the profile: set the extended interval's unit from `uc.unit` (strip the `/<unit_basis>` suffix so `"EUR/m"` -> `"EUR"`), so a mismatched record reaches the `_finish` guard and is rejected as `currency_mismatch`. Add a test mirroring `test_bom_estimate_rejects_line_currency_mismatched_with_profile` for the takeoff path.

## MEDIUM

### M1. Costing frame takeoff never normalizes member length to meters (1000x cost on mm-authored frames) [FIXED]

**Fix**: Added a shared `LENGTH_TO_M` table and `length_interval_to_m()` helper to `python/regolith/harness/models/cost_common.py` (the ONE home now referenced by both `frame_resolve.py`'s `_LENGTH_TO_M` alias and `civil_takeoff_estimate`, closing the second-copy risk the finding called out). `civil_takeoff_estimate` now converts each member's `length` to metres before multiplying by the per-meter unit cost, and a member with an unrecognized length unit becomes a declared exclusion (`nothing_priced` when it's the only member) rather than a silent 1000x misprice. Added `test_civil_takeoff_normalizes_mm_authored_member_length` and `test_civil_takeoff_excludes_member_with_unrecognized_length_unit`. Verified with the same commands as H1.


- **Where**: `python/regolith/orchestrator/costing.py`, `_frame_member_lines` line 475 (`length = _interval_from(member.get("length"))`), feeding `civil_takeoff_estimate` in `cost_common.py` lines 363-374.
- **What's wrong**: `_frame_member_lines` copies the raw `length` interval out of the frame payload with its authored unit intact (`mm` or `m`) and does no conversion. `civil_takeoff_estimate` then computes `extended = member.length.lo * uc.lo` where `uc` is a per-meter unit cost (`unit_basis == "m"`), with no check that `member.length.unit == "m"`. The sibling module `frame_resolve.py` (same payload surface) explicitly normalizes length via `_length_m` / `_LENGTH_TO_M` and defers on an unrecognized unit -- the costing path skips that discipline entirely.
- **Failure scenario**: A member authored `length = 8000mm` lands as `{lo:8000, hi:8000, unit:"mm"}`. The takeoff multiplies `8000 * (USD/m)` instead of `8 * (USD/m)`, over-costing that member 1000x. No guard fires because the length unit is never inspected and the extended interval is stamped `profile.currency` (see H1). The obligation discharges against a grossly inflated upper bound.
- **Fix direction**: Reuse the length normalization `frame_resolve` already owns -- convert `member.length` to meters in `_frame_member_lines` (or in `civil_takeoff_estimate`) via a shared `_LENGTH_TO_M`, and defer/exclude a member whose length unit is unrecognized. Extract the conversion into one shared home to avoid a second copy of the unit table.

## LOW

None found in the audited surface.

## Notes

**Verified correct (do not re-audit):**
- **M6 estimator-selection alignment** (`costing._estimate_fn_for` vs `ModelRegistry.select`): both iterate `candidates(CLAIM_KIND)` in identical `(cost, model_id)` order and use the same `accepts_payloads` predicate over the same `available_payloads` construction, so they agree on the winner for multi-basis docs.
- **bb97b9f currency guard** is correct for the BOM and fluid-BOM bases. Only civil takeoff is defective (H1).
- **6e874a3 boolean rejection** in `manifest._parse_cost_profiles` (lines 182-209): correct.
- **5d48281 undirected egress** in `calcite.rs check_circulation`: correct per calcite/02 sec. 2.
- **Expired/unresolved pricing** (`resolve_profile_inputs`, `_expiry_of`): fail-closed, correct.

**Skimmed / not deep-audited (audit boundary):**
- Rust crates other than the calcite egress fix were not read line-by-line.
- `magnetite.resolve_dependencies` nominal pinning only -- consistent with documented WO-16 non-goal, known limitation not a finding.
- Schema/serialization boundary checked only where it touches costing; FFI bridge and Rust-side cache-key threading not independently exercised.
- `regolith-ls` / editor tooling out of scope.
