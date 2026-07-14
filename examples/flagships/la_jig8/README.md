# la_jig8 -- the logic-analyzer tap jig (WO-127, charter 40 sec. 4)

An 8-channel logic-analyzer-class tap jig: it mates a target board's
debug-profile tap header, protects and level-shifts each channel into
an RP2040, and streams the capture to a host over USB-serial.

The point is not the jig. The point is that **the test hardware is
itself a lithos design**, shipped through the same pipeline as the
thing it tests -- census, calc book, complete gerbers, firmware, and
its own bring-up harness pack. Charter 40 promises that after
something is built it is easy to physically TEST it; this project is
the paper proof, and `demos/demo17` is the cross-referenced pack that
ties a target's tap channels to this jig's channels.

## The single-home seam (the whole reason this exists)

The tap header is `vendor(tap_header_2x08_254)` -- a **reference** to
the one published pinout record in `stdlib/std.elec/records/dft.toml`.
The debug emission profile PLACES that record on a target board; this
jig MATES it. Channel ordering, pin numbering, ground interleave, and
keying are never restated here, or in the firmware, or in the harness
pack. If the pinout changes, it changes in one file and both sides of
the seam follow. A second copy of a pinout is a desync bug waiting for
a bad afternoon with a scope.

## What the rule packs caught (and what got FIXED, not waived)

The board_correctness packs earned their keep. The first draft
VIOLATED five rules, every one a real bug:

| Rule | What was actually wrong |
|---|---|
| `interface_protection.tvs_on_exposed_net` | the USB data pair had no ESD clamp |
| `pdn_decoupling.shunt_cap_presence` | **all six** RP2040 power pins had no local bypass |
| `pdn_decoupling.bulk_per_rail_presence` | no bulk reservoir on the 3V3 rail |
| `bringup_config.debug_header_presence` | a *bring-up jig* with no debug header of its own |
| `dft_test_points.test_point_on_critical_net` | no probe pad on the 1.1V core rail |

All five are fixed as **design fixes** (guide 27 rule 3 / D224.3): no
rule touched, no window moved, no waiver added. The draft also hung
DVDD on 3.3V; the datasheet says DVDD is the internal regulator's 1.1V
*output*, and the netlist now says so too.

## What discharged for real

`mcu_junction` -- the RP2040 junction temperature, through the
registered `thermo.temperature` lumped model over three declared
inputs (ambient from the system's own boundary; power from the
bus-power budget allocation; r_theta from the JESD51-3 QFN-56
low-conductivity-board class). Worst corner 67.5 degC against an 85
degC ceiling. Real model, real inputs, real margin, real calc sheet in
`dist/calc/`.

Everything else is honestly waived inside the D220.2 closed classes
and itemized in `memos/release-residuals.md`.

## What the jig CANNOT yet express (the findings)

This exemplar exists to surface gaps. It found six. None is patched
here -- WO-127 authors *around* them and ledgers them.

- **F-WO127-1 -- no level-shift buffer record class.** A logic-analyzer
  front end wants a dual-supply level-shift buffer (the real part is
  the SN74LVC8T245 class). `ti.logic` carries only 74HC glue (gates,
  decoders, comparators); std.elec has nothing. So `LevelShift8`
  carries its full port/spec contract with an honest `todo!` body and
  is NOT declared as a board part. **Consequence: the shipped gerbers
  are for a board with no level shifter on it.** The BOM and the
  netlist are honest about that; the jig as shipped is not yet a
  buildable 5V-tolerant instrument.
- **F-WO127-2 -- no analog front-end models.** The two claims that
  actually govern a probe channel -- input-voltage tolerance and the
  RC edge-rate corner -- are spellable but route to no registered
  model. Their arithmetic is written out at the claim site and is
  checkable by hand; the toolchain cannot check it.
- **F-WO127-3 -- a wrapped net member list silently drops its
  continuation lines.** A `nets:` entry whose parenthesized member list
  spans multiple lines loses every member after line 1, with **no
  diagnostic**. The rule packs then evaluate an incomplete net.
  Reproduced by collapsing two nets from 4 wrapped lines to 1 line
  each with no semantic change: board_correctness violations went
  **8 -> 1**. Here it produced false violations (loud, survivable); the
  same mechanism can just as easily produce a false PASS on a rule
  that should have failed (silent, not survivable). Every net in
  `jig_board.cupr` is therefore written on ONE line, however long.
- **F-WO127-4 -- no replication construct for part instances.** The
  eight channels are copy-pasted eight times. A 32-channel analyzer
  would be unwritable in practice; `parts: ch[0..32]: ChannelFrontEnd`
  has no spelling.
- **F-WO127-5 -- the registered converter models are unreachable from
  design source.** This is the big one. `elec.buck.output_voltage_ripple`,
  `elec.converter.efficiency`, and `elec.converter.settling_time` are
  all registered in the model registry -- and `translate.py` carries no
  source call form for any of them, so a claim spelled at the
  registry's own `CLAIM_KIND` still returns `unmatched_call_path`.
  They are reachable only from Python-side tests, never from a design.
  This is why **every buck rail in the fleet** (mainboard_mx's four
  rails, `buck_converter.cupr`, cubesat's eps) waives its ripple /
  transient / eta claims with the basis *"no registered harness model
  for label kind 'ripple'"* -- and that basis is **wrong**. The model is
  registered; the CALL FORM is missing. A cheap lowering gap has been
  hiding behind an expensive-sounding modelling excuse since F126.1.
  The jig's `ripple` claim is left spelled at the registry kind with
  every input declared, so it will discharge with zero edits to the
  file the day a call form lands.
- **F-WO127-6 -- firmware source cannot be referenced from disk.** The
  firmware family consumes a content-addressed `{filename: content}`
  tree with no path-reference form, so the application source's single
  home is the ship spec's firmware tree. Keeping a readable second copy
  under `firmware/app/` would be exactly the desync trap the repo's
  no-duplication rule forbids, so there isn't one.

## Layout

```
la_jig8.cupr     top-level system: parts, budgets, the discharged thermal claim
front_end.cupr   per-channel protection + level shift (F-WO127-1/2 live here)
power.cupr       USB-VBUS -> 3V3 rail (F-WO127-5 lives here)
jig_board.cupr   the PCB: the tap-header MATE, board_correctness, nets
si.cupr          the USB pair's 90-ohm differential claim (earns the bring-up tap)
ship.spec.json   BOM, board outline, firmware tree, the debug tap block
memos/           release residuals (every waiver's home)
```

## Building it

```
regolith build --release examples/flagships/la_jig8/
regolith ship  examples/flagships/la_jig8/ --spec examples/flagships/la_jig8/ship.spec.json --out dist
regolith ship  examples/flagships/la_jig8/ --spec examples/flagships/la_jig8/ship.spec.json --emit-profile debug --out dist-debug
```

The debug ship emits the jig's OWN harness family -- the jig is a
debuggable design like any other. The recursion stops there: there is
no jig-for-the-jig.
