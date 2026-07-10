# printer_k1 -- flagship-1, the FDM 3D printer

Phase A (contract-first): `docs/workflow/work-orders/WO-64-flagship-printer.md`.
The whole machine at L0->L2 -- frames, interfaces, budgets, promises,
claims -- with ZERO artifacts realized. Every `impl` binding in this
project is `= todo!`: the contract is concrete, the geometry/circuit/
net body is deferred to phase B (WO-62/63-gated).

## Envelope targets (asserted givens)

These are the machine-class targets the whole contract is built
around. They are literals with a cited source position, not derived
values -- the parity report (`ship --explain`, AD-33) will list them
on the attention list, which is the HONEST outcome for a top-level
product requirement nobody derives from a smaller claim. Source:
`docs/spec/toolchain/31-flagships.md` sec. 2 (flagship-1 charter) +
this file (the machine-class decision, recorded here since the
charter deliberately leaves exact numbers to the authoring agent).

- **Build volume class: 220mm x 220mm x 250mm** (X x Y x Z), asserted
  in `printer_k1.cupr` (`PrinterK1.boundary.build_volume` -- parts
  have no `boundary:` of their own, hematite/03 sec. 5, so the
  envelope lives at assembly altitude) and consumed by
  `xy_gantry.hema`/`z_motion.hema`/`bed.hema`'s travel claims.
- **24V system**, asserted in `psu.cupr` (`Psu24V.boundary.rail`) and
  consumed by every downstream elec/harness current budget.
- **Single direct-drive extruder**, asserted in `extruder.hema`
  (`DirectDriveExtruder`'s absence of a Bowden-tube interface) and
  `thermal.fluo` (one melt-path net, not a multi-tool carriage).

## File map

| file | track | contract |
|---|---|---|
| `contracts.hema` | hematite | shared project-local mech interfaces (mount/rail/bay/pocket contracts every part below binds) |
| `frame.hema` | hematite | base/frame structure: build volume, rail/leadscrew/bay/panel mounts |
| `xy_gantry.hema` | hematite | XY gantry motion: carriages, belts, motor mounts, accel force promises |
| `z_motion.hema` | hematite | Z bed motion: leadscrew + guide rods, motor mount |
| `bed.hema` | hematite | heated bed platform + thermal watt promise |
| `extruder.hema` | hematite | direct-drive extruder + hotend mechanical mount |
| `enclosure.hema` | hematite | enclosure-optional seam (panel interface, no part required) |
| `thermal.fluo` | fluorite | hotend melt path + part-cooling air path, contract level |
| `controller.cupr` | cuprite | electronics bay boundary interface + controller board port contract + EBI decode `by select` |
| `psu.cupr` | cuprite | 24V power supply intent + budget contribution |
| `harness.cupr` | cuprite | harness boundary: declared runs (motors, heaters, thermistors, endstops) |
| `printer_k1.cupr` | cuprite | the top-level `system`: assembly-wide budgets, boundary, claims, the walls-list-governing acceptance surface |

## Walls list

The full list, each with its governing spec citation, lives in ONE
place (not duplicated here): the ledger section of
`docs/workflow/work-orders/WO-64-flagship-printer.md`. Phase A closed
with three recorded walls:

- **W1**: no polymer-melt fluid medium/record exists in `std.fluid`
  (fluorite/02 sec. 1; AD-34 sourcing law) -- the hotend melt path is
  not expressed as a fluorite net; see `thermal.fluo`'s header.
- **W2**: no small DC blower/axial-fan pump-curve record exists in
  `std.fluid` (fluorite/02 sec. 3) -- the part-cooling fan is modeled
  as a promise-driven `Imposer` instead of `Pump`.
- **W3** (soft, not blocking): no prismatic/linear-slide mating
  primitive exists in `std.mech.matings` (hematite/03 sec. 3) --
  `contracts.hema`'s `LinearSlide`/`LeadscrewDrive` use explicit
  `dof: removed=[...]` instead; a std `Prismatic` type would save
  future linear-motion projects the same boilerplate.
