# cuprite Overview

> Spec 0.10 (design sketch).

## 1. Vision

A declarative, goal-oriented language for electrical and computer design:

```
Traditional:  Schematic + code -> (manual analysis, lab bring-up) -> "does it work?"
cuprite:         Claims + Contracts -> (solvers, synthesis, provers) -> Netlist + Layout + Logic + Evidence
```

The designer declares **what the system senses, computes, communicates,
and actuates**, **its boundary truth** (supply, environment, lifetime),
and **what each block promises across its ports**. Chip selection, pin
assignment, passives sizing, logic implementation, and layout are derived,
each decision landing in the lockfile with its cause.

The central bet is the same as hematite's: most electrical design errors are
ambiguity and unstated-assumption errors (floating configurations,
level-mismatched interconnects, overloaded rails, timing met only at the
typical corner, the decoupling that worked by luck), and a language that
makes ambiguity a compile error and assumptions ledgered state kills the
bug class rather than the bug.

## 2. Three altitudes, one artifact

cuprite source spans three altitudes, connected by lowering, all in one
language (a design may be written at any altitude and mixed):

1. **Intent layer** (`02-intent-layer.md`): named intents and flows.
   "Sense temperature to +-0.5K at 1/min; decide; report over BLE;
   run a year on 2xAA." No implementation vocabulary exists at this
   altitude.
2. **Behavioral layer** (`03-behavioral-layer.md`): blocks with typed
   ports, behavior as clocked `on <event>:` bodies (RTL-equivalent subset)
   and continuous relations (analog subset). A strict superset of an HDL:
   quantities are physical (voltages with tolerances, currents, energies),
   not abstract logic levels; every value is interval-capable; claims and
   contracts are native.
3. **Structural layer** (`04-structural-layer.md`): bound components,
   packages, pins, placement, routing. Mostly *derived*, but writable
   directly (and this is where verify-only imports of existing designs
   enter).

The computer track (`05-computer-track.md`) is a vocabulary pack over the
same three altitudes: workloads (intent) -> architecture contracts
(behavioral promises: throughput, latency, memory) -> RTL or purchased
silicon (structural binding).

## 3. What cuprite inherits

Everything in `../regolith/` applies unchanged: value sources, contract
model with evidence clauses, entity DB + queries + single ownership +
borrows + datums + orbits, stage/scope construction, claims ->
obligations -> evidence with margin-driven discharge, budgets, lockfile,
diagnostics, build tiers, coherence rules. The domain-binding column for
elec in `../regolith/10-domain-binding.md` is normative for this track.

Three bindings do the heaviest lifting:

- **Single ownership = single driver.** A net has exactly one driver;
  shared drive (buses, open-drain wired-AND) is an explicit arbitration
  construct -- the join syntax of this domain. The FreeCAD-toponaming
  analog here is the silently-contended net and the board spin it costs.
- **Intervals = tolerances + PVT.** Component scatter, supply tolerance,
  and process/voltage/temperature corners are one interval discipline;
  every timing/level/power check runs at its own worst corner. "Met at
  typical" is not a pass.
- **Vendor artifact = chip.** A purchased IC is an interface bundle
  (ports, timing, absolute-max intervals as demands/promises) with
  catalog evidence plus an optional behavioral model registered in the
  harness. Buy-vs-build is contract substitution, not a design rewrite.

## 4. Non-goals (for now)

- IC-internal physical design (we stop at RTL/netlist handoff for custom
  silicon; FPGA bitstreams are in scope via vendor toolchain backends).
- RF/microwave layout synthesis (claims about RF budgets are expressible;
  the harness models and layout machinery are far-future).
- Replacing firmware application development: the computer track sizes
  and verifies the *platform*; application logic beyond declared
  workloads is out of scope -- permanently for design source (EOPEN-6
  closed, cycle 8, D70, by the same rationale as the host-language ban
  D60): deeper content enters `by extern` with evidence.

## 5. Prior art map

Verilog-AMS / VHDL-AMS (mixed discrete/continuous HDL -- the L3 baseline
to exceed: no contracts, no intervals, no evidence) - Modelica (acausal
continuous modeling) - SPICE (the expensive harness model) - static
timing analysis (the cheap harness model; the margin-driven pairing with
SPICE mirrors beam-theory/FEA exactly) - IPC-2221 (rule pack) - IBIS
(vendor behavioral models with catalog evidence) - Chisel/Amaranth
(generator-style HDLs; contrast: generation is our L2->L3 lowering, not a
host-language macro layer) - Bluespec (rule-based semantics; the closest
prior art to claims-adjacent HDL) - contract-based SoC verification
(assume-guarantee; SVA) - Ptolemy (models of computation) - digikey/JLC
capability files (process registries).
