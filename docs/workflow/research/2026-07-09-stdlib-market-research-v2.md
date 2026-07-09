# Standard-library and solver market research v2 (cycle-28 refresh)

Date: 2026-07-09. Author: market-research sub-orchestrator (cycle 28).
Status: ADVISORY input, NON-NORMATIVE. This memo does not decide
anything; binding decisions live in `docs/workflow/design-log/` and
`docs/spec/toolchain/00-architecture.md` (AD-1..29). It refreshes the
cycle-27 pair (`2026-07-08-stdlib-market-research.md` and
`2026-07-08-benchmarks-and-datasets.md`) against what ACTUALLY landed
in the WO-43..54 / feldspar WO-12..22 waves, fills the gaps those
memos did not cover (std.civil depth, std.cost record families,
feldspar solver-wrap priorities, pattern-pack content), and ends with
a WO-mappable recommendation table.

Read the two cycle-27 memos FIRST -- this memo assumes them and does
NOT restate what still stands. Where the old memo is still correct,
this memo says "stands" and moves on.

Scope discipline (the tripwire, unchanged from v1): recommendations
are CONTENT and CURATION only, never new compiler paths. The regolith
already carries patterns (contracts + `spec:` + `parts`/`matings`
kinds + the WO-28 rule engine + `advise:`), costing (claims + D95
sweeps + records + INV-22 pins + budgets + policy), and the solver
seam (feldspar packs, AD-19). Anything needing new core surface is
flagged OUT-OF-V1 in section 8 so it does not silently expand a WO.

## Table of contents

1. What landed since cycle 27 (the delta this memo audits against)
2. Audit -- cycle-27 shortlists vs. what shipped (landed / partial /
   missing / obsoleted)
3. std.civil content depth (WO-48) -- the gap the old memo deferred
4. std.cost record families (WO-54) -- USD-baseline schemas engineers
   expect
5. feldspar solver-wrap priorities (WO-20/21) + calibration content
6. Pattern-pack content beyond the seeds (WO-53, charter 26)
7. Prior-art / UX -- delta only (v1 sec. 7 stands)
8. Cross-cutting v1 flags (out-of-v1 surface asks)
9. Prioritized, WO-mappable recommendation table
10. Sources

---

## 1. What landed since cycle 27 (the delta this memo audits against)

Grepped `stdlib/`, `crates/`, and the feldspar `crates/feldspar-*`
tree; cross-checked `TODO.md` (both repos) and the regolith/11 sec. 8
catalog. State on 2026-07-09:

LITHOS -- LANDED (WO-45, cycle 28): the `std.*` package homes and
record content. `stdlib/` now carries `std.quantities`,
`std.materials` (metals), `std.contact` (pairs), `std.mech` (+ records
`fasteners.toml`, `bearings.toml`, `springs.toml`), `std.elec`
(+ `motor_frames.toml`), `std.fluid` (+ `pipe.toml`, `media.toml`),
`std.sheet_metal` (+ `capability.toml`), `std.intents`, `std.debug`,
`std.models`, and the vendor `jlc_2l` pack. Records are `community`
tier with `evidence = {method, trust_tier, reference}` blocks, sourced
directly off the cycle-27 benchmarks memo sec. 5. The two SEED
patterns exist: `std.mech.mechanisms/four_bar.hema` and
`std.elec.patterns/level_shifter.cupr`, each with a `magnetite.toml`.

LITHOS -- LANDED (cycle 28): WO-43 (`regolith build [--release]`),
WO-44 (the one `regolith.plugins` seam), WO-47 (`.calx` end-to-end at
L0-L1, all 5 disciplines), WO-49 (FluidPort medium binding), WO-51,
WO-52 (Mixer edge kind), plus WO-26/27/28/34 remainders. Calcite is
ELABORATED (02/03/04 + corpus) and awaiting owner ratification.

LITHOS -- STILL QUEUED: WO-48 (calcite lowering + `std.civil` -- HARD
gate on WO-47+WO-45, un-gates WO-50 civil / WO-54 civil / feldspar
WO-21), WO-53 (pattern libraries v1 -- the catalog GROWTH beyond the
two seeds), WO-54 (costing v1 -- `std.cost` does NOT yet exist on
disk), WO-50 (drawings), WO-40 (lints), WO-38/39 (LSP/editor), WO-24
end-to-end, WO-25 remainder.

FELDSPAR -- LANDED (cycle 28): the LIBRARY SPLIT is real. There is now
a dedicated `crates/feldspar-library` crate with numeric homes already
present: `elec.rs`, `heat.rs`, `fluids/{incompressible,compressible}.rs`,
`mech/{sections,statics,vibration}.rs`. WO-12 (payload ports), WO-16
(structured ports + ccx modal), WO-17 (ngspice elec tier -- code
complete, real binary not executed in sandbox, honest-absence path
tested), WO-22 (symbolic follow-ups) are DONE.

FELDSPAR -- STILL QUEUED: WO-13 (budget-seeking), WO-14 (regolith
boundary v2 / contract v2), WO-15 (parallel), WO-18 (CoupledGroup),
WO-19 (solver-pack kit), WO-20 (thermal-fluids: the CoolProp `thermo`
wrapper + the fluid-network solve + compressible tier), WO-21
(civil/structural `frame` consumer -- HARD-gated on lithos WO-48
producing `frame` payloads).

Net: the cycle-27 memos' single biggest assumption -- that the
`std.*` catalog and records were unbuilt -- is now HALF-realized. The
mech/elec/fluid record shortlists shipped almost verbatim; std.civil,
std.cost, and the pattern-catalog GROWTH are the live frontier this
refresh concentrates on.

## 2. Audit -- cycle-27 shortlists vs. what shipped

Legend: [LANDED] on disk now; [PARTIAL] home/seed exists, content
incomplete; [MISSING] not built, still queued; [OBSOLETED] superseded
by a decision.

### 2.1 std.mech.mechanisms (v1 memo sec. 1)

- four_bar -- [LANDED] as seed (`four_bar.hema`, provides `FourBar`).
- slider_crank, lead/ball screw, belt drive, gear train, bearing
  arrangement, spring (mechanism pattern) -- [MISSING]. The
  `std.mech.mechanisms/magnetite.toml` explicitly records these as
  catalog GROWTH deferred to a follow-up publish under WO-53 (its
  header cites the v1 memo's batch by name). NOT dropped -- recorded.
- Underlying DIMENSIONAL records the mechanisms consume -- [LANDED]:
  `fasteners.toml` (M6-M12 ISO), `bearings.toml` (6000/6200 boundary
  dims), `springs.toml` (A228 music wire). The v1 memo's sec. 5
  dataset shortlist is essentially fully transcribed.

Verdict: the mechanism CATALOG shortlist stands unchanged as the
WO-53 growth queue; ordering (slider_crank -> screws -> belt -> gear
-> bearing -> spring) is still right. No revision.

### 2.2 std.elec.patterns (v1 memo sec. 2)

- level_shifter -- [LANDED] as seed (`level_shifter.cupr`).
- decoupling, LDO, RC_debounce, reverse-polarity, TVS (the
  "structural advise, no numeric half" batch) -- [MISSING], queued
  under WO-53. Still the highest value-per-effort batch: their
  recognition is purely structural and their ABSENCE is the most
  common real defect. Re-affirmed as the #1 WO-53 growth batch.
- buck/current-sense/gate-driver (numeric-half patterns) -- [MISSING];
  now UN-blocked on the solver side, since feldspar WO-17 (ngspice)
  and `feldspar-library/elec.rs` LANDED. The v1 memo said these "want
  the feldspar ripple/AC half"; that half now exists, so the buck's
  ripple model has a home. UPGRADE: buck_converter moves from
  "gated" to "dispatchable with a numeric half" once WO-53 runs.
- motor-frame records (IEC/NEMA) -- [LANDED] (`motor_frames.toml`).

Verdict: stands, with one upgrade -- the ngspice tier landing means
the converter patterns are no longer solver-blocked.

### 2.3 std.fluid.circuits (v1 memo sec. 3)

- relief leg, filter loop, accumulator, regulator tree -- [MISSING],
  queued WO-53. Their numeric halves (network flow) gate on feldspar
  WO-20, which is STILL QUEUED (unlike elec). So this batch remains
  "ship contract + recognition now, numeric half with WO-20."
- pipe/media dimensional + property records -- [LANDED]
  (`pipe.toml`, `media.toml`: water/air/N2 + NPS/copper).

Verdict: stands. Fluid patterns are one wave behind elec because
WO-20 has not landed.

### 2.4 std.civil.assemblies (v1 memo sec. 4)

- Entire section -- [MISSING] and correctly so: `std.civil` itself
  does not exist yet (WO-48 gate). The v1 memo flagged this whole
  section forward-looking. Section 3 of THIS memo now supplies the
  content depth the v1 memo deferred.

### 2.5 Solver landscape (v1 memo sec. 5)

- ngspice WRAP -- [LANDED] (WO-17 done, honest-absence posture).
- CoolProp WRAP -- [MISSING] but CONFIRMED dispatchable: WO-20's own
  note records that a `cp312-abi3-manylinux2014_aarch64` CoolProp
  8.0.0 wheel exists and installs, deferred only because nothing
  depends on it yet. The v1 recommendation (WRAP CoolProp, MIT) is
  validated and unblocked on the platform axis.
- BUILD fluid-network + frame direct-stiffness -- [MISSING], the
  homes are stubbed/partial in `feldspar-library` (`fluids/*.rs`,
  `mech/statics.rs`, `mech/sections.rs`). Recommendation stands.
- SKIP OpenSeesPy as a shipped dependency, PyNite as out-of-band
  oracle only -- stands; nothing changed the licensing facts.

### 2.6 Costing (v1 memo sec. 6)

- Three record schemas (rate / quantity-break pricing / RSMeans-shaped
  unit-cost) + itemized table + currency-as-units -- [MISSING];
  `std.cost` not on disk. WO-54 queued. Section 4 of this memo
  sharpens the record FAMILIES and their fields.

## 3. std.civil content depth (WO-48) -- the gap the old memo deferred

The v1 memo listed civil ASSEMBLY PATTERNS (braced bay, moment frame,
etc.) but explicitly deferred the CONTENT DEPTH -- the tables and
record sets `std.civil` must ship before any assembly or estimator can
be credible. Per regolith/11 sec. 8, `std.civil` v1 is:
"occupancy/egress tables, load cases + code-edition combination sets,
transfer/opening classes, section and connection capacity tables,
envelope layer records, and reference building-code rule packs." This
section makes each concrete, ordered by "a structural/architectural
engineer expects this first," all as REGISTRY RECORDS (no new surface).

### 3.1 Load-combination sets (the spine -- ship first)

The single most-reached-for civil content. `std.civil` must ship
BOTH combination families as record sets, keyed by code edition (the
"code-edition combination sets" the catalog names), because an
engineer picks their governing set by jurisdiction:

- ASCE 7-16/7-22 **LRFD (strength)** combinations. The canonical set:
  (1) 1.4D; (2) 1.2D + 1.6L + 0.5(Lr or S or R); (3) 1.2D +
  1.6(Lr or S or R) + (1.0L or 0.5W); (4) 1.2D + 1.0W + 1.0L +
  0.5(Lr or S or R); (5) 0.9D + 1.0W; plus the seismic pair with
  E = rho*Q +/- 0.2*S_DS*D. Ship as a `combination` record: id, edition,
  method(=LRFD), and a term list {load_symbol, factor}, with the
  companion-load rule captured as alternative rows.
- ASCE 7 **ASD (allowable stress)** combinations: D; D+L;
  D + (Lr or S or R); D + 0.75L + 0.75(Lr or S or R); D + 0.6W;
  D + 0.75L + 0.75(0.6W) + 0.75(Lr or S or R); 0.6D + 0.6W. Same
  record shape, method=ASD.

These are the discrete axes WO-21's "combination sweeps as discrete
axes (structured Coverage)" consumes and the `forall` sweep the
calcite corpus uses. Load SYMBOLS (D, L, Lr, S, R, W, E) are the
fixed vocabulary; the magnitudes are project data.

### 3.2 Occupancy / egress tables (IBC-shaped)

- **Occupant load factors** (IBC Table 1004.5): net/gross floor area
  per occupant by use -- e.g. assembly-unconcentrated 15 net,
  assembly-concentrated 7 net, business 150 gross, mercantile 60
  gross, storage 300 gross, educational 20 net, residential 200
  gross. Ship as an `occupancy` record: use, basis(net/gross),
  area_per_occupant_ft2. This is the takeoff basis for egress AND the
  small_office/bus_shelter corpus occupancy claims.
- **Egress capacity factors** (IBC 1005.3): inches of egress width
  per occupant -- 0.2 in/occupant (stairs, sprinklered) and 0.15
  in/occupant (other components). Small record set; pairs with the
  stair/egress-core assembly pattern (sec. 6).
- **Live-load minimums** (ASCE 7 Table 4.3-1): uniform + concentrated
  by occupancy -- office 50 psf, corridors-above-first 80 psf,
  assembly-fixed 60 psf, stairs 100 psf, residential 40 psf. Ship as
  a `live_load` record: occupancy, uniform_psf, concentrated_lb.

### 3.3 Structural section + material families

The `frame` consumer (WO-21) needs section properties by name; the v1
memo already got AISC W-shapes transcribed into the benchmarks memo
(sec. 5.1). std.civil should ship the SECTION-PROPERTY families as
records (distinct from std.mech's fastener/bearing dims):

- **AISC steel shapes** (W, HSS-rect, HSS-round, angles, channels):
  A, d, b_f, t_w, t_f, I_x, S_x, Z_x, r_x, I_y, S_y, r_y, J, weight.
  Factual (AISC v15 database, redistributable). W-shapes first (the
  small_office frame), then HSS (braces) and angles.
- **Steel material grades**: A992 (Fy=50, Fu=65 ksi) for W-shapes,
  A500 Gr.C for HSS, A36 for plates/angles. Record: grade, Fy, Fu, E,
  spec-reference.
- **Concrete**: f'c classes (3000/4000/5000 psi), Ec = 57000*sqrt(f'c),
  unit weight (normalweight 150 pcf). Rebar (ASTM A615): #3-#11 bar
  areas + Grade 60 (Fy=60 ksi).
- **Wood/CLT** (defer): NDS reference design values are species/grade
  matrices -- OUT of v1 civil, note as future.

### 3.4 Connection + capacity tables

- **Bolt group** records: A325/A490 nominal shear/tension strengths by
  diameter, edge/spacing minimums. Feeds WO-21 connection checks.
- **Weld** records: E70XX electrode, fillet strength per 1/16 in leg.
- Transfer/opening classes (the catalog's "transfer/opening classes"):
  lintel/header capacity families over openings -- record the class,
  not a solver; the numeric check rides WO-21.

### 3.5 Envelope / rated-assembly layer records (earliest shippable)

The v1 memo already flagged these as the earliest-shippable civil
content (pure records, no numeric half): UL-shaped rated
wall/floor/roof families -- layer stackup, fire rating (hr), STC
(acoustic), R-value (thermal). Ship a `rated_assembly` record: id,
type(wall/floor/roof), layers[], fire_hr, stc, r_value, ul_reference.
These have NO solver dependency and can land in WO-48's L2-check half
before WO-21 exists. RECOMMEND: sequence these first within WO-48.

## 4. std.cost record families (WO-54) -- USD-baseline schemas

Per charter 27 and AD-29 the compiler ships NO prices; `std.cost`
ships SCHEMAS + reference estimators, projects ship numbers in
`magnetite.toml [profiles.cost.<name>]`. The v1 memo named three
schemas; this section pins the FIELD SETS engineers expect and the
family boundaries, USD baseline (currency is a unit family; conversion
records explicit + cited, never ambient).

### 4.1 rate record (labor / process / machine rates)

Fields engineers expect: `key`, `kind` (labor | machine | process),
`rate` (money per unit -- hour or operation), `basis` (per_hour |
per_op | per_setup), `region` (optional index key), `valid_until`,
`evidence`. Reference fixtures (fixture-grade, from benchmarks memo
sec. 6): shop machining $60-120/hr, assembly labor, construction
trades. The mech estimator's "setup + cycle time x rate" leg consumes
this directly.

### 4.2 pricing record (vendor price with quantity breaks)

The McMaster/JLCPCB shape. Fields: `key`, `item`, `breaks` (list of
{min_qty, unit_price}), `currency`, `valid_until`, `source`,
`evidence`. The quantity-break list is load-bearing (the elec BOM
estimator picks the break for the profile's quantity). Expired
`valid_until` -> INDETERMINATE naming the record (the one honesty
fixture to pin hard). Sub-families the estimators want:
- **mechanical hardware** pricing (McMaster shape: fasteners, stock).
- **PCB fab** pricing: a fab-parameter record (layers, area_cm2,
  finish) x quantity-break -- the elec BOM's fab-table half; jlc_2l
  already ships capability records, cost fixtures ride beside them.
- **raw stock/metal** pricing (per kg): the mech stock leg.

### 4.3 unit-cost record (RSMeans-shaped civil assembly)

The construction estimator's basis. Fields: `key`, `assembly`, `unit`
(sf, cy, lf, ea), `material`, `labor`, `equipment` (the three-way
split RSMeans uses), `total`, `location_index` (city cost index axis),
`valid_until`, `evidence`. The civil estimator multiplies the L6
takeoff quantities (member schedule, assembly areas) by these. Ship
the SCHEMA + fixture numbers only; never RSMeans data itself (it is
paywalled/copyrighted -- transcribing it is a licensing violation, and
the trust tier would be false).

### 4.4 currency + conversion records

Currency is a unit-family entry (USD baseline). A conversion record
is an explicit, cited, dated pair {from, to, rate, date, source} --
never ambient, never a live fetch inside a build. v1 ships USD only;
the machinery supports more without new surface.

### 4.5 itemized-estimate payload (the evidence, not a record)

The `table`-kind evidence the estimators emit: line items {item, qty,
unit_cost, record_ref, extended} + declared EXCLUSIONS (what was not
priced), content-addressed and byte-deterministic. This is shared
across all four track estimators -- one payload schema, not four.

## 5. feldspar solver-wrap priorities (WO-20/21) + calibration content

The library split (dedicated `feldspar-library` crate) means numeric
homes now have a clear address. Priorities, refreshed:

### 5.1 mech.struct direct stiffness (WO-21) -- the frame payload

Confirmed BUILD (not wrap): `feldspar-library/mech/statics.rs` and
`sections.rs` are the homes. The v1 recommendation stands. What
CALIBRATION/VALIDATION content should ride WITH it (the specific ask):

- The benchmarks memo sec. 1 already supplies FIVE exact frame
  calibration cases (propped cantilever, portal sway, two-span
  continuous, determinate truss, fixed-fixed) with worked reactions/
  moments/deflections and tolerances. These ARE the WO-21 calibration
  oracle -- no new numbers needed; the memo did the work. RECOMMEND
  WO-21 wire these five as its regression fixtures verbatim.
- ADD one INDETERMINATE cross-check the benchmarks memo lacks: a
  single-bay single-story portal with FIXED bases under combined
  gravity+lateral, validated against a slope-deflection hand solution
  (the memo's sec. 1.4 note that "beam-column moments require the 1x
  indeterminate solve"). This exercises the stiffness assembly beyond
  determinate reactions. Slope-deflection / moment-distribution are
  already in WO-21's deliverables as "cheap tiers/calibration
  partners" -- use them as the oracle, closed-form.
- PyNite (MIT) as the OUT-OF-BAND oracle for the full frame (multi-bay
  small_office) where hand solutions get impractical -- run offline,
  transcribe expected reactions/drift as fixtures; never ship PyNite
  as a pack dependency. OpenSeesPy stays SKIP (non-free redistribution).
- Section-property records (sec. 3.3) must land lithos-side FIRST
  (WO-48) so WO-21 consumes `I_x/S_x/Z_x` by digest, not by copy --
  the WO-21 hard gate. Modal (first-mode > 3 Hz footbridge) uses
  Rayleigh/Dunkerley as the cheap calibration tier against the eigen
  solve.

### 5.2 Fluid network -- Hardy-Cross (WO-20)

BUILD, in `feldspar-library/fluids/*.rs` (incompressible.rs exists).
Calibration content already supplied by benchmarks memo sec. 3:
Colebrook/Haaland friction (with the laminar 64/Re floor), series/
parallel reduction, Hardy-Cross loop-correction convergence to
|dQ|<1e-6, and the pump-operating-point intersection. Compressible
Fanno-line tier (lithos D141) is a separate formula home
(`compressible.rs`, present). RECOMMEND: WO-20 wire the sec. 3
benchmarks as fixtures; Hardy-Cross is the network-solve proof.

### 5.3 thermo / CoolProp wrapper (WO-20) -- CONFIRMED dispatchable

WRAP CoolProp (MIT), as the v1 memo said. The platform blocker the v1
memo could not confirm is now CLEARED: WO-20's own note records a
working `cp312-abi3-manylinux2014_aarch64` CoolProp 8.0.0 wheel,
deferred only for lack of a consumer. So the wrapper is a pure
scheduling question, not a portability risk. Calibration: benchmarks
memo sec. 3.4 supplies five IAPWS-95/Lemmon state points (water 293/
298/373 K, air, N2) with density/cp/viscosity and tolerances -- lock
the interpolation eps + domain boxes to these. In-process Python
library (spec 03), plain import, not subprocess.

### 5.4 elec ngspice (WO-17) -- LANDED, calibration present

Done. Benchmarks memo sec. 4 (RC step, RLC resonance, loaded divider,
BJT bias, NMOS bias) are the calibration set; the honest-absence path
is tested, real-binary tests code-reviewed. The remaining lithos-side
value is the CONVERTER pattern numeric halves (buck ripple) now that
the tier exists -- see sec. 6.

## 6. Pattern-pack content beyond the seeds (WO-53, charter 26)

The two seeds (four_bar, level_shifter) prove the machinery. The
GROWTH queue -- ordered by value-per-effort, all under existing
surface -- is where WO-53's follow-up publishing goes. Ordering
refreshed against what the solver tiers now support:

Batch A (ship first -- purely structural recognition, NO numeric
half, absence = common real defect):
1. std.elec.patterns: decoupling network, reverse-polarity protection,
   TVS/ESD clamp, RC_debounce, LDO. Recognition is structural (an IC
   power pin with no local cap; an exposed port with no clamp).
   Highest value-per-effort in the whole catalog.

Batch B (closed-form mechanism laws, no feldspar dependency):
2. std.mech.mechanisms: slider_crank, lead/ball screw, belt drive,
   gear train, bearing arrangement (a `matings` pattern), helical
   spring. Each a distinct `spec:` law shape; dimensional records
   already landed (WO-45).

Batch C (numeric-half patterns -- NOW un-blocked for elec, still
gated for fluid):
3. std.elec.patterns: buck_converter, current_sense, gate_driver --
   their ripple/AC halves have a home now that WO-17 + elec.rs landed.
4. std.fluid.circuits: relief leg, filter loop, accumulator, regulator
   tree -- still gate on feldspar WO-20 (not yet landed). Ship
   contract + recognition now; numeric half with WO-20.

Batch D (civil assemblies -- gate on WO-48 + WO-21):
5. std.civil.assemblies: rated wall/floor/roof families FIRST (records
   only, no solver -- shippable the moment std.civil exists), then
   braced bay + moment frame + spread footing + stair/egress core
   (numeric halves gate on WO-21).

Recognition-rule authority: every rule carries a `per:` citation to
the design literature (Shigley, Sclater & Chironis, Horowitz & Hill,
Idelchik, AISC/ASCE) exactly as DFM rules cite handbooks (charter 26
sec. 1.5). No new query predicate assumed -- if one is missing, WO-53
ESCALATES per AD-22 (charter 26 sec. 2), does not grow a side path.

## 7. Prior-art / UX -- delta only

The v1 memo's sec. 7 (KiCad/Fusion/Revit/SPICE prior art -> advisory +
version-pinned + no new discovery UI) STANDS unchanged and is not
restated. One delta worth recording: the plugin seam (WO-44, AD-26)
now LANDED means pattern packs and cost estimators can be delivered as
plugins through a real seam, reinforcing the v1 lesson -- recommendation
stays advisory and portable, surfaced through `magnetite new
--template`, `regolith doc` datasheets, LSP completion, and `regolith
explain`, all EXISTING channels. Resist any new discovery surface
(AD-28 rejects new severities and side query paths).

## 8. Cross-cutting v1 flags (out-of-v1 surface asks)

Everything above is shippable under the existing surface EXCEPT:

- **std.civil entirely gates on WO-48**; the numeric civil assemblies
  and estimators additionally gate on feldspar WO-21. Sections 3 and
  the civil rows of the table are WO-48+ scope, NOT WO-53/WO-45 v1.
- **Fluid-circuit numeric halves gate on feldspar WO-20** (still
  queued). Elec converter halves are now UN-blocked (WO-17 landed).
- **feldspar WO-21 hard-gates on lithos WO-48** producing `frame`
  payloads (payload schema is Rust-sourced lithos-side). Do not
  dispatch WO-21 before WO-48 lands.
- **Recognition query predicates** (WO-53): if matching a hand-rolled
  shape needs a predicate the AD-21 query surface lacks, ESCALATE per
  AD-22 -- do not grow a side query path.
- **No live vendor pricing inside a build** (AD-29): a fetch tool that
  writes fresh pricing records is future magnetite tooling, never
  runs in a build (determinism). std.cost ships schemas + math +
  fixtures only; no real priced data in `stdlib/`.
- **No compiler special-casing of `std`** (D135/D153 tripwire): all of
  the above is package content; `std.compute`/`std.fluorite` are the
  only compiler-owned names -- grep `std.` in `crates/` must stay
  clean of new record/estimator logic.
- RSMeans/vendor-catalog COPYRIGHTED data: ship SHAPES + fixture
  numbers only; transcribing paywalled data is a licensing + false-
  trust-tier violation.

## 9. Prioritized, WO-mappable recommendation table

Effort class: S (<= a day of authoring), M (a WO leg), L (a full WO or
multi-leg). v1-blocking = "v1 is not credible without it."

| # | Recommendation | Feeds WO / residual | Effort | v1-block |
|---|----------------|---------------------|--------|----------|
| 1 | std.elec.patterns Batch A (decoupling, rev-polarity, TVS, RC_debounce, LDO) -- structural advise, no numeric half | WO-53 growth | M | YES |
| 2 | std.mech.mechanisms Batch B (slider_crank, lead/ball screw, belt, gear, bearing arr., spring) | WO-53 growth | M | YES |
| 3 | std.cost 3 record schemas (rate, quantity-break pricing, RSMeans unit-cost) + itemized-table payload + currency-as-units, USD baseline, fixtures only | WO-54 | M | YES |
| 4 | std.cost expired-quote INDETERMINATE fixture (valid_until in the past) | WO-54 | S | YES |
| 5 | std.civil load-combination sets (ASCE 7 LRFD + ASD, code-edition keyed) | WO-48 | M | YES |
| 6 | std.civil occupancy/egress + live-load minimum tables (IBC/ASCE) | WO-48 | S | YES |
| 7 | std.civil rated wall/floor/roof layer records (no solver -- earliest civil content) | WO-48 (L2 half) | S | YES |
| 8 | std.civil AISC section-property + steel/concrete material-grade records (frame consumer basis) | WO-48 -> feldspar WO-21 | M | YES |
| 9 | Wrap CoolProp (MIT), aarch64 wheel confirmed; lock eps to benchmarks sec. 3.4 state points | feldspar WO-20 | M | YES |
| 10 | Build Hardy-Cross fluid-network solve + Colebrook/Haaland; fixtures from benchmarks sec. 3 | feldspar WO-20 | L | YES |
| 11 | Build frame direct-stiffness; wire benchmarks sec. 1 five cases as fixtures; PyNite out-of-band oracle | feldspar WO-21 | L | YES |
| 12 | std.civil connection/capacity records (bolt/weld groups, transfer/opening classes) | WO-48 -> WO-21 | M | no |
| 13 | std.elec.patterns Batch C (buck, current_sense, gate_driver) -- numeric half now un-blocked by WO-17 | WO-53 + WO-17 | M | no |
| 14 | std.fluid.circuits Batch C (relief leg, filter loop, accumulator, regulator tree) -- recognition now, numeric half w/ WO-20 | WO-53 + WO-20 | M | no |
| 15 | std.civil.assemblies numeric patterns (braced bay, moment frame, footing, egress core) | WO-53 + WO-48 + WO-21 | L | no |
| 16 | std.cost region/location-index axis on rate + unit-cost records | WO-54 | S | no |
| 17 | Wood/CLT (NDS) civil material family | future | M | no |
| 18 | CalculiX continuum-FEA wrap (Abaqus-deck stage pattern) | future mech-continuum wave | L | no |

## 10. Sources

Curation authority (design canon; recognition/DFM rules cite these
per charter 26 sec. 1.5):

[1] AISC Steel Construction Manual + Shapes Database v15.0 (free
download, factual section properties) --
https://www.aisc.org/publications/steel-construction-manual-resources/
[2] ASCE 7-16/7-22, Minimum Design Loads (load combinations LRFD/ASD,
live-load minimums Table 4.3-1) -- https://www.asce.org/
[3] International Building Code (IBC) Table 1004.5 occupant load
factors; 1005.3 egress capacity factors --
https://codes.iccsafe.org/content/IBC2021
[4] RSMeans unit-cost data (SHAPE only; data paywalled, not
transcribed) -- https://www.rsmeans.com/
[5] McMaster-Carr Product Information API (pricing record shape) --
https://www.mcmaster.com/help/api/
[6] CoolProp (MIT), PropsSI + aarch64 manylinux wheel --
https://coolprop.org/ ; confirmation in feldspar
docs/workflow/work-orders/WO-20-thermal-fluids-wave.md
[7] PyNite (MIT, out-of-band frame oracle);
OpenSeesPy non-free-for-commercial-redistribution (SKIP as shipped
dep) -- https://github.com/JWock82/PyNite
[8] Sclater & Chironis, Mechanisms and Mechanical Devices Sourcebook;
Shigley's Mechanical Engineering Design; Horowitz & Hill, The Art of
Electronics; Idelchik, Handbook of Hydraulic Resistance; Roark's
Formulas for Stress and Strain -- the pattern/DFM `per:` citation base.

Prior in-repo memos this refresh builds on (read them, not restated
here): docs/workflow/research/2026-07-08-stdlib-market-research.md
and docs/workflow/research/2026-07-08-benchmarks-and-datasets.md.
