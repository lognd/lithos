# stdlib/ -- the `std.` catalog (D135, WO-45)

Governance (regolith/11 sec. 8, D135):

- `std.` is a RESERVED namespace prefix in the magnetite registry: only
  the lithos project publishes under it.
- Nothing in the compiler special-cases `std` (grep `std.` in `crates/`
  stays clean of new logic), with the one documented exception that the
  unit tables (what `std.units` would be) live in `regolith-qty` because
  quantities are load-bearing at L1, before package resolution runs.
  `std.quantities` (below) is therefore a nominal package: it declares
  the namespace/claim-form surface the tracks already assume, so a
  project's `magnetite.toml` can depend on it like any other package,
  but it ships no records of its own -- the math lives in `regolith-qty`.
- **In-repo development home:** each `stdlib/<package>/` directory is a
  real magnetite package (its own `magnetite.toml` + record/model
  content). CI and the example corpus (`examples/`) consume these
  in-repo copies directly, via `regolith.magnetite.manifest.resolve_dependencies`
  pointed at `stdlib/` as a local search path -- no network, no separate
  "path source" concept invented (checked `magnetite/sources.py` first,
  per the WO note: `resolve_dependencies` already IS local-path
  resolution; `Sources`/`Registry` in `sources.py` is a distinct concern,
  URL-based routing for a future fetch step, not needed here).
  Publication to the public registry (out of scope, regolith/11 sec. 10)
  would be the same act as for any third-party package; the project
  signing key confers the tier (INV-14).
- **Tier honesty (D58):** every record here that transcribes a
  real-world datasheet/handbook value without an attached certified
  test report says `tier=community` in-file, and cites its source.
  Nothing here claims `tier=certified`.

## Packages (v1)

| package | kind(s) | content |
|---|---|---|
| `std.quantities` | quantities | namespace/claim-form declarations only (math in `regolith-qty`) |
| `std.materials` | materials | starter metal/polymer records, `tier=community` |
| `std.contact` | materials | dry/greased contact-pair friction records, `tier=community` |
| `std.mech` | interfaces, matings | mount/flange interface packs, process capability packs (cnc/forged/formed/cast/molding/sheet/tube/turned/weld/joining/gear/linear/spring/bearings/seals), bolted/press/bearing matings |
| `std.sheet_metal` | process | sheet-metal process capability records; the DFM RULE-PACK half is EXCLUDED (WO-28 engine remainder owns the rule format) -- this package is the record content + package home only |
| `std.elec` | interfaces, matings, components | port/family/protocol/bus packs (buffers, buses, digital, families, logic, power, protocols, sense) PLUS (WO-66, D174/D179) a GENERATED `passive_family` E-series batch (`records/e_series.toml`, IEC 60063 resistor/capacitor parametric families) and a hand-cited `connectors.toml` batch (JST-XH/PH, Molex KK, screw-terminal classes). |
| `jlc_2l` | process | JLCPCB 2-layer fab + basic SMT assembly capability records (vendor-named, rides beside `std.elec`, NOT under the `std.` prefix) |
| `std.fluid` | materials | media property tables + fitting/loss/pipe-schedule records; WO-60 (D166) added a `components.toml` batch (pump, ball valve, in-line filter, metering orifice), real-catalog cited |
| `std.intents` | verbs | intent-verb schemas (`sense`, `actuate`) |
| `std.debug` | verbs | debug/probe/indicate verb schemas |
| `std.models` | models | registration manifest binding the EXISTING `python/regolith/harness/models/` code -- the code does not move, this package only names it |
| `std.mech.mechanisms` | matings, process | pattern library (D144/AD-28, WO-53 seed + Batch B; WO-60 Batch C): `four_bar`, `slider_crank`, `lead_screw`, `belt_drive`, `gear_train`, `bearing_arrangement`, `helical_spring`, `flexure_pivot`, `toggle_linkage` -- coupler-law `mating`s, `advise:`-only recognition rules (`dfm:` block) |
| `std.elec.patterns` | interfaces, components, process | pattern library (D144/AD-28, WO-53 seed + Batch A): `level_shifter`, `decoupling`, `reverse_polarity`, `tvs_clamp`, `rc_debounce`, `ldo` -- `block`s + reference impls, `advise:`-only recognition rules (`erc:` block) |
| `std.civil` | occupancy, loads, matings, sections, materials | WO-48 slice C + WO-60 widening: occupancy/egress tables (IBC), load cases + ASCE 7/AISC/NDS/geotech combination sets, transfer classes as real `mating`s with `dof: kept=` (`Pinned`/`Moment`/`Bearing`/`Roller`/`BasePlate`/`EmbeddedPost`), starter section/material/soil records PLUS (WO-60, D166) a real AISC 16th-ed. `w_shape` family (16 sections) and `hss_square` family (28 sections, ASTM A500 Grade C) so section search has a real multi-member domain; `astm_a500_grc` material added to match. The reference building-code rule pack is EXCLUDED (`TODO(WO-28)`: the engine remainder it needs is still blocked upstream). WO-66 (D174) adds a GENERATED `sections_channels_angles.toml` (`steel_channel`/`steel_angle` families, same AISC v16.0 edition) as an ADDITIVE file beside `sections.toml` -- zero existing rows touched or renamed. |
| `std.cost` | rates, pricing, unit_costs, models | WO-54 (D147, toolchain/27): rate/pricing/unit-cost FIXTURE records (every number invented -- never transcribed vendor/RSMeans data, research note 2026-07-09 sec. 4) + the harness-half naming of the reference estimator models (`cost_elec_bom`/`cost_fluid_bom`/`cost_civil_takeoff`, the std.models code-does-not-move precedent). Includes the deliberately-expired `acme.quote_2025q4` negative-fixture pricing source. |
| `ti.logic` | components | WO-60 (D166): TI 74HC-series glue-logic component records (SN74HC02 quad NOR, SN74HC138 3-to-8 decoder, SN74HC688 8-bit identity comparator) -- the `nor_glue` candidate family for WO-56's `by select(nor_glue, cpld, mcu_chip_selects)` demo. Vendor-named, rides beside `std.elec` (regolith/11 sec. 2's own worked example row), NOT under the `std.` prefix. |
| `microchip.cpld` | components | WO-60 (D166): ATF1502AS/ATF1502ASL 32-macrocell CPLD component records (two speed grades, -7 and -25) -- the `cpld` candidate for the same WO-56 demo. Vendor-named. |
| `st.mcu` | components | WO-60 (D166): STM32F4 FSMC (RM0090) external-bus-interface chip-select record -- the `mcu_chip_selects` candidate for the same WO-56 demo (an MCU's own EBI/FSMC decode instead of external glue). Vendor-named. |

| `std.fasteners` | components | WO-66 (D174): ISO metric fastener grids -- socket head cap screws (ISO 4762), hex bolts (ISO 4014), hex nuts (ISO 4032), plain washers (ISO 7089), GENERATED from `tools/stdlib/gen_fasteners.py` over the committed `tools/stdlib/data/iso_fasteners.toml` table (D178 shape ratification). |
| `std.bearings` | components | WO-66 (D174): deep-groove ball bearing grid (60xx/62xx/608 class, ISO 15 boundary dims) + LM_UU linear bushing seed, hand-cited (D180). |
| `std.motion` | components | WO-66 (D174): NEMA 17/23 stepper rated-point classes, Tr8 leadscrew class, GT2 belt/pulley class, MGN12/15 linear rail seed, hand-cited (D180). |
| `std.machines` | components | WO-66 (D174, feeds WO-67/AD-35): 3-axis mill / FDM printer / CO2 laser CLASS records (travel/kinematics/spindle-or-nozzle), hand-cited (D180). |
| `std.tooling` | components | WO-66 (D174, feeds WO-67/AD-35): solid-carbide end-mill and ISO 235/DIN 338 jobber-drill geometry classes, hand-cited (D180). |

`std.fluid.circuits` / `std.civil.assemblies` (D144 pattern libraries,
remaining catalog batches) are catalog GROWTH, not this WO's seed
(charter `docs/spec/toolchain/26-pattern-libraries.md` sec. 3
non-goal).

## Record format

Record BODIES that are ordinary language source (interface/mating/
process declarations consumed by a track's front end) are authored in
that track's own syntax, exactly like `examples/registry/*.cupr`. Data
records with no track-specific syntax yet (materials, contact pairs,
fluid media/pipe tables) are authored as plain TOML under each
package's `records/` directory and loaded by
`regolith.magnetite.stdlib_records.load_toml_records` into the ordinary
`regolith.magnetite.records.Record` model -- Python-side data
authoring only, no new Rust grammar (this WO is Python + records, no
Rust per its `Language:` header).
