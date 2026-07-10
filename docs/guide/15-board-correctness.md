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

Two additive stdlib records feed these packs' `per:`-cited facts
(sourcing law, `32-stdlib-depth.md` sec. 1):

- `stdlib/std.elec/records/crystals.toml` (new): `cl_pf` (specified
  load capacitance) on each crystal component, feeding
  `clock_discipline`'s load-cap sizing rules.
- `stdlib/std.elec/records/connectors.toml`: `exposure_class` field
  added to every wire-to-board connector record, feeding
  `interface_protection`'s exposed-connector sweep.
- `examples/registry/{rp2040,atsamd21,stm32g0}.cupr`: each MCU
  record's `demands:` block gains `debug_header:` and
  `reset_supervisor:` fields, cited to the part's own datasheet
  section, feeding `bringup_config`'s bring-up rules.

## 4. The hazard fixture board

`examples/negative/66_board_correctness_hazard.cupr` attaches all
five packs on a deliberately-hazardous board; its fixed twin,
`examples/tracks/cuprite/board_correctness_fixed.cupr`, attaches the
same packs on a corrected design. Both files' own header comments
record the current, honest limitation: the domains these rules
quantify over (`power_pins`, `config_straps`, `exposed_connectors`,
`crystals`, `critical_nets`) are `EntityKind::Other` and are not yet
populated by any landed lowering pass for a `board` decl (the WO-29
entity-population remainder -- the same gap `jlc_2l`/
`std.elec.patterns.decoupling` already carry). Until that lands, the
actual per-family "trips/passes" evidence lives in each rule's
`expect:` fixture pair, exercised by `regolith rules test`; the
hazard/fixed pair of `.cupr` files demonstrates the ATTACHMENT shape
today and will demonstrate live per-entity firing once the entity
layer catches up (named growth, WO-79 close-out).

## 5. The post-mortem law

Charter 36 sec. 1: "the catalog grows forever ... every real hardware
bug becomes a rule in the same change that diagnoses it." Any agent
diagnosing a real hardware defect in this project adds the
corresponding `demand:`/`advise:` rule (with its `per:` citation and
`expect:` fixtures) to the relevant `std.board_correctness` pack --
or, if the fact it needs does not exist yet, adds the record field
under the sourcing law and escalates the rule's addition as follow-up
scope rather than inventing the fact.
