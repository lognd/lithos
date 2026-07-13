# WO-113 -- Corpus data enrichment + waiver burn-down (Class D, fleet-wide)

Status: honest-partial (campaign executed fleet-wide 2026-07-13; named machinery residuals WO113-F1..F5 below)
Language: corpus authoring (.hema/.cupr/.fluo/.calx + std.*
  records + memos); Python only for census tooling if needed.
Spec: D224 (the three authoring rules -- provenance, same-change
  burn-down, honest failures fix the DESIGN); D220 (terminal waiver
  classes); D216 (trust floors met or author-revised, never
  waived around); gates: WO-109/110/111/112 landed (the discharge
  channels must exist before inputs are worth declaring).

## Goal

Every claim whose model now exists and whose inputs a real
engineering drawing would carry gets those inputs DECLARED with
provenance, discharges for real, and loses its waiver in the same
change. The fleet census flips from 45/929 discharged/waived toward
majority-discharged, with the remaining waivers all in D220.2's
closed classes.

## Deliverables

1. Fleet-wide inputs pass, project by project (worked in dependency
   order: the seven zero-discharge projects first -- arm_a6,
   dune_buggy, mainboard_mx, printer_k1, reaction_wheel,
   regen_engine, uav_talon): declare the named missing inputs
   (bearing ratings from manufacturer tables as std.* records;
   loads/speeds/duty derived from already-declared design data
   with in-file derivations; datasheet citations otherwise).
   The arm_a6 `mech.bearing.l10_hours` set (c_rating, p_exponent,
   p_load, speed_rpm) is the type specimen.
2. Same-change burn-down: each real discharge deletes its waive
   block and regenerates the project memo; stale-waiver listings in
   ship output must be ZERO at the end (the gate lists them --
   an unmatched waiver left behind is debt, and the health
   consistency leg already checks memo/waiver integrity).
3. D224.3 design fixes: where real inputs yield VIOLATED, fix the
   DESIGN (resize, re-spec, pick the real part) with the rationale
   recorded in-file; every such fix is enumerated in the close-out.
4. Trust-floor pass per D216: floors met at tier where a certified
   channel exists; author-revised (per-claim, recorded rationale)
   where aspirational; NEVER memo-waived around.
5. Final: fleet evidence refresh (release build reports), census +
   goldens regenerated, per-project before/after discharge counts
   in the close-out ledger.

## Acceptance

- Zero projects discharge zero obligations.
- Every remaining waiver fleet-wide sits in a D220.2 class, and
  the close-out proves it by enumeration (the WO-117 census golden
  encodes it permanently).
- No fabricated values: spot-checkable provenance on every added
  datum; `make check` + fleet ship green.

## Escalation

A claim that cannot discharge because of a MODEL or MACHINERY gap
discovered here (not inputs) goes back to the coordinator as a
named residual -- never silently re-waived without a 2(c) F-number.
This WO is large: the coordinator may dispatch it in per-project
slices; each slice follows this file.

## Close-out ledger (2026-07-13, branch wo113-enrichment-campaign)

Fleet: 15/15 `build --release` clean, ZERO violated, all census
golden rows verified against fresh builds; `tests/golden` suite
green (150 passed). Fleet discharged total: 45 -> 72.

### Per-project before/after (discharged / accepted, census counts)

| project         | before   | after    | what changed |
|-----------------|----------|----------|--------------|
| cnc_router_r1   | 10 / 141 | 11 / 140 | F132.1: Burin's real machine record (derived from machine.hema's own axis travels); Spoilboard stock trimmed 830x530->830x520mm (D224.3 -- the real Y overhang the honest record exposed); stale makeable waiver deleted; cost profiles added (7 claims advance to the Rust marker wall) |
| arm_a6          | 0 / 44   | 10 / 34  | 3x ISO 281 bearing (std.bearings 6006/6004/6002 records + pose-derived loads), VDI 2230 base bolts (ISO 898-1 preload), 3x cantilever deflection (SI inputs), 3x DFM makeable (tap-drill dias + shop records); 8 waivers burned |
| printer_k1      | 0 / 61   | 2 / 59   | payload_ok deflection (declared plate/pattern geometry), BedCarriage DFM (shop records); 2 waivers burned; 5 cut-family bases refreshed |
| uav_talon       | 0 / 29   | 1 / 28   | tip_defl gust case (the WO-70 test's committed 220N derivation) + D224.3 DESIGN FIX: spar depth domain [3,8]mm -> [52,60]mm (flat strip violated by 1000x; corpus now agrees with its own test suite) |
| reaction_wheel  | 0 / 24   | 3 / 21   | b10 (NEW std.bearings 707C angular-contact record), crit_speed (k/m derived from declared shaft/flywheel geometry, feldspar pack model), mount_rise (declared 1.8W promise over derived conduction R); 3 waivers burned |
| dune_buggy      | 0 / 201  | 3 / 198  | FrontHub.life (NEW std.bearings 32005 tapered-roller record + mass-budget-derived corner load), rollcage crush_space + proof_crush (declared case loads + declared tube section); 3 waivers burned |
| mainboard_mx    | 3 / 39   | 3 / 36   | WO109-F3 half: 3 refclk shadowing waivers deleted (claims were already discharging) |
| riscv_hart_rv1  | 4 / 78   | 4 / 75   | WO109-F3 other half: 3 clk SI shadowing waivers deleted |
| espresso_machine| 4 / 96   | 4 / 96   | boiler tap-drill dias/depths + shop records + water_iapws_liquid medium record + cost profiles; every chain advanced to a NAMED terminal machinery wall (no honest discharge available yet) |
| regen_engine    | 0 / 29   | 0 / 29   | WO113-F4: NO Class D surface exists -- every residual is Class B/C/E machinery (classified in memo) |
| sdr_transceiver | 5 / 78   | 5 / 78   | thermal inputs sourceable but cuprite-blocked (WO113-F3); no other Class D surface |
| cubesat         | 7 / 74   | 7 / 74   | same: cuprite thermal claims behind WO113-F3 |
| hydro_press_h30 | 7 / 15   | 7 / 15   | no Class D surface (frame/limit machinery residuals) |
| small_office    | 6 / 17   | 6 / 17   | glycol medium (egw_60_40) + grundfos pump curve NOT declarable offline-verifiably; stays honestly deferred per D224.1 |
| timber_pavilion | 6 / 3    | 6 / 3    | no Class D surface |

### Records added (all D224.1a, cited, SOURCES.md rows added)

- stdlib/std.bearings/records/angular_contact_ball.toml: 707C class
  (ISO 15:2011 dims; conservative LOW end of the published catalog
  rating range -- low is conservative for L10 lower bounds).
- stdlib/std.bearings/records/tapered_roller.toml: 32005 (ISO 355
  dims; same conservative-low posture; p = 10/3 documented at use).
- stdlib/std.fluid/records/media.toml: water_iapws_liquid (IAPWS-95
  at 318.15K -- the espresso design's own declared hot-tank corner;
  the first of the three WO-112 Class-4 missing fluid records).
  egw_60_40 and semisynthetic_5pct are NOT added: their table values
  could not be verified offline this session (D224.1 refusal --
  transcription without the table in hand is fabrication risk).
- Project shop records (machine + tap-drill tool sets, each citing
  the std.machines class record + ISO 261 tap-drill table):
  arm_a6/records/shop.toml, printer_k1/records/shop.toml,
  espresso_machine/records/shop.toml; cnc_router_r1's existing
  record corrected per F132.1.

### D224.3 design fixes (law 3)

1. cnc_router_r1 Spoilboard: stock 830x530 -> 830x520mm (the honest
   machine record exposed a real 10mm Y-travel overhang).
2. uav_talon WingSpar: depth domain [3,8]mm -> [52,60]mm minimize
   (honest gust inputs showed the flat strip violates tip_defl by
   three orders of magnitude; the repo's own committed tests already
   modeled the spar as a 3x60mm section; WO-97 promotion test's
   mirrored bounds updated in the same change).

### Findings / escalations (2(c)-shaped, each named at its waivers)

- WO113-F1: turned parts (cnc_lathe Shaft/Shoulder/Disk ops) project
  no FeatureProgram (v1 feature-op set is mill-only), so their
  manufacturable claims cannot ground. Reopen: turned-op projection.
- WO113-F2: minimize-bound parts (optimizer domains) realize no
  geometry in the staged loop, so DFM has no bbox (arm_a6 UpperArm/
  Forearm; the known cycle-34 realization residual, now named at the
  affected waivers). Reopen: optimizer->params realization.
- WO113-F3: the CUPRITE claim lowering normalizes call forms and
  drops BOTH inline kwargs and claim-suffix `given` bindings
  (verified live on reaction_wheel driver.cupr), so sourceable
  thermal inputs (declared T_env, design loss budgets, vendor
  datasheet R_thJA) have no declaration channel. Class E. Reopen: a
  cuprite kwarg/given threading increment. Blocks ~13 thermal claims
  fleet-wide (reaction_wheel, regen_engine, dune_buggy x2, cubesat
  x3+, sdr x2, espresso x2).
- WO113-F4: regen_engine has NO Class D surface at all; its
  zero-discharge status cannot be flipped by data authoring (Class
  B/C/E owners named in its memo).
- WO113-F5: round-stock (Tube/Bar) weldments realize no geometry
  (espresso boilers), so their DFM claims cannot ground despite full
  input declaration. Reopen: round-stock weldment realizer.
- Cost chain (16 claims, espresso 6 + cnc_router 7 + arm/uav/others'
  budget forms): profiles + quantity now resolve; the terminal wall
  is the ALREADY-ESCALATED Rust bare-form cost_bom marker emission
  gap -- data is no longer the blocker anywhere on the cost surface.
- D216 trust floors: no fleet claim currently pins a floor above
  what its channel's tier provides (the SI/bearing/beam discharges
  ride unsigned community/fixture tiers by construction); no
  author-revision was needed this pass; memo signing stays
  owner-gated (D216.3).

### Acceptance vs. the WO's own bar

- "Zero projects discharge zero obligations": NOT met for
  regen_engine alone -- escalated as WO113-F4 (a model/routing gap,
  exactly the WO's named escalation shape, not silently re-waived).
- Every remaining waiver sits in a D220.2 class by construction:
  Class A conformance edges, D195-gated windows (owner queue), 2(c)
  machinery exclusions carrying F-numbers (F131.1/F131.2, WO113-F1..
  F5, F132.3 family gaps, the Rust cost-marker gap), and
  author-intent exclusions. The WO-117 census flip encodes the
  per-class accounting permanently.
- No fabricated values: every added datum carries in-file provenance
  (record citation, in-file derivation from declared design data, or
  a named standard's table value); three record families were
  REFUSED for want of verifiable sources (glycol/coolant media, the
  Ulka pump curve, dune_buggy heat-source powers).
