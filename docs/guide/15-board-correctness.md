# Board correctness: the encoded checklist

WO-79 (charter `docs/spec/toolchain/36-board-correctness.md`, D187)
turns the professional board-review checklist into `erc:` rule packs
under `stdlib/std.board_correctness/`, one file per wave-1 family:

| Family (charter sec. 2) | Pack | Rules |
|---|---|---|
| 1. PDN/decoupling | `pdn_decoupling` | `shunt_cap_presence`, `shunt_cap_value_class`, `bulk_per_rail_presence`, `shunt_cap_placement` (realized-fact tier) |
| 2. Bring-up/config straps | `bringup_config` | `strap_not_floating`, `debug_header_presence`, `reset_supervision_required` |
| 3. Interface protection | `interface_protection` | `esd_on_exposed_connector`, `vbus_inrush_protection`, `tvs_on_exposed_net` |
| 4. Clock discipline | `clock_discipline` | `crystal_load_cap_lower`, `crystal_load_cap_upper`, `single_driver_clock_net`, `source_termination` |
| 5. DFT test points | `dft_test_points` | `test_point_on_critical_net`, `test_point_min_pad_size`, `test_point_probe_clearance` |

Every rule carries a `per:` citation (vendor datasheet section,
standard, or textbook reference -- see each pack file for the exact
sources) and both a `pass:` and a `fail:` `expect:` fixture (the
AD-21 mandatory-fixture law): `regolith rules test
stdlib/std.board_correctness/*.cupr` runs all 30 cases.

## 1. Attaching the packs to a board

A `board` decl attaches the whole wave via one stage, exactly like
any other `process=` reference (D-C level 1, `21-rule-packs.md`):

```
board MyBoard:
    stage checklist: process=board_correctness(
        pdn_decoupling, bringup_config, interface_protection,
        clock_discipline, dft_test_points)
```

Attach a subset by naming only the packs you want -- each bare
dotted-identifier argument attaches independently.

## 2. Declaring a family N/A

There is no separate "N/A" syntax: the coverage-visibility guarantee
(charter 36 sec. 1b) comes from the audit surface listing which
attached rule fired, passed, or deferred for a subject, not from a
new declaration form. To make a family's non-applicability EXPLICIT
and visible (rather than silent, i.e. simply not attaching the pack),
attach it anyway and waive the specific rule with a basis, the same
ladder every other rule violation/deferral rides (design/21 D-D):

```
waive erc(pdn_decoupling.bulk_per_rail_presence) on MyBoard:
    basis: "logic-only daughtercard, bulk reservoir lives on the
            carrier board this card mates into" [by "REV-A schematic
            review"]
```

A waived rule still RAN (coverage-visible, attributed, release-gated
unless basis-carrying) -- that is the difference between "N/A" and
silence charter 36 sec. 1 names as the whole point.

## 3. Record fields the rules read

The stdlib records feeding these packs' `per:`-cited facts (sourcing
law, `32-stdlib-depth.md` sec. 1):

- `stdlib/std.elec/records/crystals.toml`: `cl_pf` (specified load
  capacitance) on each crystal component, feeding `clock_discipline`'s
  load-cap sizing rules -- read at rule-eval time through the WO-87
  registry dereference (an `x.cl` term resolves via the crystal
  entity's `record` measure into the loaded record's `cl_pf`).
- `stdlib/std.elec/records/connectors.toml`: `exposure_class` field
  on every wire-to-board connector record, feeding
  `interface_protection`'s exposed-connector sweep.
- `stdlib/std.elec/records/capacitors.toml` (WO-87): `capacitance_pf`
  on the MLCC classes; the entity-population pass derives the pdn
  application tiers (load < 1nF <= bypass < 10uF <= bulk) from it.
- `stdlib/std.elec/records/mcus.toml` (WO-87): `power_pin_names`
  (the datasheet power-pin table), the source of `power_pins`
  entities.
- `stdlib/std.elec/records/{protection,dft}.toml` (WO-87): the
  `tvs`/`test_point`/`debug_header` classes the protection and DFT
  counts read.
- `examples/registry/{rp2040,atsamd21,stm32g0}.cupr`: each MCU
  record's `demands:` block gains `debug_header:` and
  `reset_supervisor:` fields, cited to the part's own datasheet
  section, feeding `bringup_config`'s bring-up rules.

Records reach the rule engine through the ONE loader (magnetite) as
the `registry.records` realized-input payload (D198); the CLI `check`
and `build` verbs resolve and attach it automatically.

## 4. The hazard fixture board

`examples/negative/66_board_correctness_hazard.cupr` attaches all
five packs on a deliberately-hazardous board; its fixed twin,
`examples/tracks/cuprite/board_correctness_fixed.cupr`, attaches the
same packs on a corrected design. Since WO-87's entity-population
pass (D198), both carry REAL declared topology (`then:` vendor
instances, `nets:` membership, `straps:` bindings), and the packs
fire on it live: the hazard board trips >= 1 rule in every family
with per-entity attribution, the fixed twin renders zero diagnostics
(its only residue is honest realized-tier deferral obligations: cap
placement distance, probe clearance -- WO-24/WO-35 facts). The same
pass un-blocks `std.elec.patterns.decoupling`'s net sweep
(`tests/test_wo87_board_population.py` is the enforcement). Each
rule's `expect:` fixture pair (`regolith rules test`) remains the
per-rule unit evidence. Note the declared-vs-realized line: a board
that declares no `nets:`/`connect:` topology genuinely has no
declared nets (net rules pass vacuously at this tier); the realized
netlist tier re-forms those checks over real nets.

## 5. The post-mortem law

Charter 36 sec. 1: "the catalog grows forever ... every real hardware
bug becomes a rule in the same change that diagnoses it." Any agent
diagnosing a real hardware defect in this project adds the
corresponding `demand:`/`advise:` rule (with its `per:` citation and
`expect:` fixtures) to the relevant `std.board_correctness` pack --
or, if the fact it needs does not exist yet, adds the record field
under the sourcing law and escalates the rule's addition as follow-up
scope rather than inventing the fact.
