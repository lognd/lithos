# WO-24: Elec structural realizer (bind -> netlist -> layout)

Status: todo
Depends: WO-16 (registry records), WO-19 (lowering), WO-20 (realizer
registers as a model pack); WO-05 residual (elec behavioral bodies
typed) only for the behavioral/INV-16 half, which is NOT this WO
Language: Python (`regolith.realizer.elec`); vendor tools driven as
subprocesses through the WO-20 adapter discipline
Spec: cuprite/04 (the L3->L4 realizer, step order is normative),
cuprite/06 (lowering table); regolith/08 sec. L4; regolith/07 sec. 7
(allocation search)

## Goal

A `.cupr` board design realizes to a bound netlist and a placed/routed
layout: component binding against registry records, netlist emission,
and a layout adapter with KiCad as the v1 reference backend. After
this WO the Kestrel boards have real layouts; manufacturing outputs
are WO-25.

## Deliverables

- Component binding: the allocation-search loop (regolith/07 sec. 7,
  orchestrator-owned) binds abstract blocks/parts to registry records
  (stm32g0/atsamd21/rp2040 + passives), screened by capability
  arithmetic; every binding is lockfile-pinned with cause `planner`.
  Nogoods stay solver state (D75).
- Netlist emission: bound design -> a neutral netlist model ->
  KiCad netlist writer. The netlist is derived L4 data, content-
  addressed; the single-driver/arbitration checks (cuprite/06) run
  before emission.
- Layout adapter (`realizer.elec.kicad`): drive KiCad (kicad-cli +
  pcbnew python API where required) as a subprocess pack: footprint
  resolution from registry records, board outline from the mech
  interface (the Kestrel PC/104 outline import path), placement +
  routing invocation, DRC run. The DRC REPORT is evidence
  (discharged/violated per rule severity); the layout file is a
  content-addressed, lockfile-pinned artifact (INV-22 hash-pin).
  Autorouting quality is NOT promised: an unroutable/failed route is
  honest indeterminate on the layout obligation, and a hand-edited
  layout re-enters as a pinned import (regolith/08 verify-only L4).
- Extraction hook: post-route extraction surface (net lengths,
  copper areas) shaped as model-pack inputs so layout-dependent
  claims (IPC-2221 current capacity first) can discharge post-route;
  full SI extraction stays a later pack.
- EXPLICIT CUTS (recorded, reopen criteria named): FPGA synthesis /
  bitstream path and the two-bank flow (needs a corpus target
  demanding bitstream evidence); firmware ELF measured-DB ingestion
  beyond hash-pinning; analog SPICE extraction.

## Acceptance

- One Kestrel board (`examples/cubesat/`, pick the simplest) runs
  bind -> netlist -> placed/routed .kicad_pcb -> DRC-clean, fully
  pinned in `regolith.lock`; re-running with an unchanged lockfile
  is a no-op (cache hit on every artifact).
- A binding that violates a budget claim backjumps and lands on a
  feasible record (allocation-search fixture with a rigged nogood).
- A deliberately DRC-violating design yields violated evidence
  citing the DRC rule; a route failure yields indeterminate.
- `make check` green; the two INV-13 cross-boundary xfails that
  waited on `bound_kinds` end-to-end population (TODO sec. 1) are
  revisited: un-xfail if binding now feeds them, else the blocker
  note is updated truthfully.
