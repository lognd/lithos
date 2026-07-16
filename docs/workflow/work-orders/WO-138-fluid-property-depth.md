# WO-138 -- std.fluid property depth: the six missing media + roughness (D258.1/F158)

Status: partial (2026-07-16 dispatch) -- see "Close-out (partial dispatch)"
  below; NOT closed, do not flip to done. Rides after the D256 hash
  window; owns no schema bump.
Language: records (TOML) + `tools/stdlib/` generation scripts
  (the WO-66 pattern) + a small `fluid_resolve.py` widening.
Spec: F158 (`docs/workflow/design-log/2026-07-16-cycle-37.md`, the gap
  census this WO closes); D258 ruling 1 (representation: cited POINT
  TABLES when the source publishes a formulation/grid, COEFFICIENT
  ROWS only when the source itself publishes coefficients, NEVER a
  fit this repo invents); AD-34 (sourcing law: generated stdlib
  content comes from a deterministic `tools/stdlib/` script over a
  committed intermediate, reviewable diffs); D250 (every value cites
  standard+edition, no typical-value fallback, unverifiable inputs
  are NAMED ABSENCES -- the WO-134 precedent this WO follows exactly);
  `docs/spec/fluorite/03-lowering.md` sec. 2 (`FlownetPayload`
  medium-record consumption); `scratch_recon_thermo_fluids.md` secs.
  1.1-1.2, 2c, 3 (the source inventory and licensing table this WO's
  deliverables are drawn from -- elaborate these, do not re-invent).

## Goal

Every `registry(...)` medium name the fluid corpus declares either
resolves to a cited record or is a named, ledgered refusal; the
property chain (rho/mu/cp/pv vs T) is walkable end to end instead of
stopping at a single state point.

## Deliverables

1. `stdlib/std.fluid/records/roughness.toml` -- absolute-roughness
   table, one row per material/finish (drawn tubing, commercial
   steel, galvanized iron, cast iron, concrete, riveted steel),
   citing Colebrook 1939 (the equation's own roughness basis) and
   Moody 1944 Table 1 / the chart's roughness list as reprinted in
   White, *Fluid Mechanics*, 8th ed., Table 6.1 -- the repo's
   standing fluid citation. Roughness stays a MATERIAL-level record;
   do not duplicate it into `pipe.toml` unless a cited source states
   a per-product value.
2. Water/steam property-vs-T POINT TABLES (rho, mu via the companion
   IAPWS viscosity release, cp, saturation pv(T) from IF97 Region 4),
   generated at a fixed grid of states by a deterministic
   `tools/stdlib/gen_iapws_water.py` script, each row citing "IAPWS
   R7-97(2012), Region N eqs., evaluated at T,P". Valid range
   273.15-1073.15 K to 100 MPa per the release; do not extrapolate
   outside it -- out-of-range lookups are a named out-of-domain
   result, never a silent clamp.
3. NASA Glenn ideal-gas cp polynomial COEFFICIENT rows (McBride,
   Zehe, Gordon, NASA/TP-2002-211556, Sept 2002; public-domain US
   government work) for the starter set: air constituents, N2, O2,
   CO2, H2O(g). Transcribed verbatim as coefficients, never evaluated
   into a fitted curve this repo owns.
4. `egw_50_50` and `egw_60_40` (ethylene-glycol/water, D258
   licensing posture: a manufacturer engineering guide -- Dow or
   MEGlobal equivalent, the Swagelok/NatureWorks TDS precedent, NOT
   ASHRAE Fundamentals which is license-blocked) with rho/mu/cp(T)
   and pv(T) for the 50/50 row (feeds NPSH claims).
5. `gasoline_e10_summer` vapor pressure via the public EPA RVP
   volatility-regulation route, or a named refusal if the class
   detail needs ASTM D4814 (license-blocked).
6. `semisynthetic_5pct` and `SAE_10W40`: attempt a manufacturer TDS
   source for each; if none is found this WO's session, record an
   HONEST REFUSAL (the WO-134 Ulka-pump / busway precedent) rather
   than inventing a value -- coolant emulsions in particular rarely
   publish primary property data, so a refusal here is an EXPECTED,
   not a failing, outcome.
7. Widen `python/regolith/orchestrator/fluid_resolve.py`'s
   `MediumProps` (today `rho_kg_m3` + `mu_pa_s` only) to also walk
   `cp`, `pv`, and `k` (conductivity) when a record carries them,
   selecting the BRACKETING rows around the claim's corner
   temperature and taking the conservative bound per the claim's
   sense (INV-9 outward posture -- interpolation only ever widens,
   never narrows).
8. Every new record's `evidence` table follows the structured-
   citation shape D258 ruling 1 cross-references to
   `scratch_recon_digikey_processors.md` sec. 2.2 (`method`,
   `trust_tier`, `reference` at minimum; decomposed fields where the
   generating script already has them structured) -- additive over
   today's shape, not a parallel one.

## Out of scope

- Any friction-factor or minor-loss model or record (WO-139/WO-140).
- The feldspar pack bridge (WO-141) and the Moody figure (WO-143).
- A live IF97 region-equation evaluator in lithos -- feldspar's
  CoolProp-backed `thermo.properties` directions already cover
  runtime evaluation; this WO ships a generated point table, not a
  solver.
- SAE J300 / ASTM D4814 bulk transcription pending the named owner
  licensing decision (`scratch_recon_thermo_fluids.md` sec. 6.3).

## Acceptance

- Every corpus `registry(...)` medium name from F158's census
  (`egw_60_40`, `egw_50_50`, `semisynthetic_5pct`,
  `gasoline_e10_summer`, `grundfos_ups32`'s curve is WO-138/c5's
  pump-curve half -- see note below, `SAE_10W40`) resolves to a
  cited record OR appears in a REFUSALS section of this WO's
  close-out naming what would unblock it: `grep -rn 'registry(' examples/ | grep -E 'egw_60_40|egw_50_50|semisynthetic_5pct|gasoline_e10_summer|SAE_10W40'` cross-checked against `stdlib/std.fluid/records/*.toml`.
- `uv run python -m tools.stdlib.organization --check prefix|one_family|citations` passes with zero new issues.
- `uv run pytest tests/magnetite/test_stdlib.py -q` green.
- No record row lacks an `evidence` table:
  `grep -rLn 'evidence' stdlib/std.fluid/records/*.toml` returns empty for every new file.
- Zero fitted curves: each new record file's header comment states
  its representation class (point table / coefficient row) per D258
  ruling 1; a reviewer can grep for the absence of any interpolating
  polynomial this repo authored (only the NASA Glenn coefficients,
  which are transcribed, not fitted, are polynomial-shaped).
- `make check` green.

Note: the Grundfos UPS32 pump curve (`registry(grundfos_ups32)`,
sec. 1.2 of the recon) needs a manually-downloaded data booklet
(owner action item, `scratch_recon_thermo_fluids.md` sec. 6.4) --
if the booklet is not available this dispatch, ledger it as a
REFUSAL naming the exact fetch blocker, same as the other named
absences; do not block the rest of this WO on it.

## Escalation

Any medium whose only available source is a license-blocked
publication (ASHRAE, SAE J300, ASTM D4814) is a named refusal with
the licensing posture stated, not a workaround -- escalate the
licensing question itself to a design-log entry if the demo (WO-144)
turns out to need it discharged, never invent around it.

## Close-out (partial dispatch, 2026-07-16)

SHIPPED, cited, real (not invented):

- `stdlib/std.fluid/records/roughness.toml` -- 8 material rows
  (drawn tubing, commercial steel, wrought iron, asphalted cast
  iron, galvanized iron, cast iron, concrete range, riveted steel
  range), Moody 1944 Table 1 as reprinted White 8th ed. Table 6.1.
- `stdlib/std.fluid/records/water_saturation.toml` -- GENERATED by
  `tools/stdlib/gen_iapws_water.py` from the committed
  `tools/stdlib/data/iapws_water_saturation.toml` coefficient table:
  27 pv(T) point rows, 280.00-647.096 K, IAPWS R7-97(2012) Eq 30
  EVALUATED (never fitted), coefficients cross-checked against the
  `iapws` (jjgomera, MIT) reference implementation's own doctest
  (`_PSat_T(500) == 2.63889776` MPa, reproduced exactly).
- `stdlib/std.fluid/records/gas_cp_glenn.toml` -- GENERATED by
  `tools/stdlib/gen_nasa_glenn_cp.py`: 5 COEFFICIENT rows (N2, O2,
  Ar -- the air-constituent starter set -- CO2, H2O(g)), NASA/TP-
  2002-211556 7-term cp/R polynomial, values transcribed from the
  NASA CEA `thermo.inp` reference database, low-T range (200-1000 K)
  only.
- `media.toml` -- one new row, `gasoline_e10_summer`: pv only (rho/mu
  OMITTED, no source fetched this session), the public EPA 40 CFR
  1090.215 RVP regulatory ceiling (10.0 psi = 68948 Pa at 310.93 K
  test temp), a conservative upper bound per D258 ruling 3, NOT a
  measured typical value.
- `python/regolith/orchestrator/fluid_resolve.py` -- `MediumProps`
  widened with `cp_j_kgk`/`pv_pa`/`k_w_mk` scalars plus optional
  point-table fields (`rho_points`/`mu_points`/`cp_points`/
  `pv_points`/`k_points`) and a `bracket_conservative()` walk (worse-
  of-the-bracket, never interpolates a fabricated in-between value,
  `None` outside the table's own range -- INV-9 outward posture).

NAMED REFUSALS (this dispatch could not responsibly source these;
recorded per D250/D258 rather than guessed):

- `egw_50_50`, `egw_60_40` (ethylene-glycol/water mixtures) --
  REFUSED. The Dow "Engineering and Operating Guide" PDF and the
  MEGlobal equivalent were not machine-fetchable this session (the
  Dow DOWTHERM guide URL located by search is for a different fluid
  family, DOWTHERM SR-1/4000, not the plain ethylene-glycol/water
  antifreeze guide; engineeringtoolbox.com returned HTTP 403).
  Unblock: an owner-side fetch of the actual Dow ethylene-glycol
  Engineering and Operating Guide PDF (or an equivalent MEGlobal/
  Lyondell TDS), or the Mokon technical data sheet found by search
  (mokon.com/products/fluids/glycol-solutions/pdf/Ethylene-Glycol-
  Technical-Data.pdf, not fetched/verified this session either).
- `semisynthetic_5pct` -- REFUSED, as the WO body itself expects:
  coolant emulsions do not publish primary rho/mu/pv(T) data; no
  manufacturer TDS was found this session. Unblock: a specific
  manufacturer's TDS for a named semisynthetic coolant product.
- `SAE_10W40` -- REFUSED. SAE J300's viscosity-grade table is
  license-blocked for bulk transcription; no manufacturer TDS for a
  specific 10W-40 oil was fetched this session. Unblock: an owner
  licensing decision on SAE J300, or a named manufacturer TDS.
- `grundfos_ups32` pump H-Q curve -- REFUSED, per this file's own
  note above: the Grundfos data booklet needs a manual owner
  download (exceeded agent fetch limits in the recon dispatch too).

SCOPE CUT (named, not silently dropped): deliverable 2's rho(T)/
mu(T)/cp(T) liquid-water point tables (beyond the two single-point
`water`/`water_iapws_liquid` rows already in `media.toml`) are NOT
included this dispatch -- only the saturation pv(T) family
generated. IAPWS-IF97 Region 1's 34-term gamma-equation coefficient
table (and the companion IAPWS viscosity release) were not
independently sourced and cross-checked to the same evidence bar
this dispatch held Eq 30 to (a doctest-verified reference
implementation); shipping placeholder numbers without that check
would be exactly the invented-fit D250 forbids. Unblock: fetch/
verify the IAPWS-IF97 Region 1 coefficient table (or the companion
R12-08 viscosity release) against an independent reference
implementation, then add a sibling `gen_iapws_water_liquid.py`
generator following this WO's `gen_iapws_water.py` pattern.

Gate status this dispatch: `make check` green (see commits); the
three `tools.stdlib.organization` checks referenced in Acceptance
(`prefix`, `one_family`, `citations`) pass with zero NEW issues
(pre-existing baseline debt unchanged); `tests/magnetite/
test_stdlib.py` and `tests/orchestrator/test_translate_fluid_records.py`
green. Status is NOT flipped to closed: the egw_50_50/egw_60_40
non-refusal deliverable and the water rho/mu/cp depth remain open
for a follow-up dispatch with real fetch access to the named
sources above.
