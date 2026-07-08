# WO-24: Elec structural realizer (bind -> netlist -> layout)

Status: in-progress (engine half landed cycle 18, `1d69e33`:
allocation-search binding with backjump, netlist emission, KiCad
layout adapter to the WO-20 wire protocol -- KiCad-real run and the
lowering-output -> binding-requirement bridge remain; see "Cuts
recorded this cycle" and WO-29 -- STILL BLOCKED after WO-29's design
pass (cycle 19, D90): the split (Rust emits per-block capability
demands, Python derives candidates from quarry) is decided and
normative, but Rust-side emission needs entities/claims that in turn
need the `parts:`-line parser promotion, cut back this cycle -- see
WO-29's "Cuts recorded this cycle")
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

- One Kestrel board (`examples/systems/cubesat/`, pick the simplest) runs
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

## Cuts recorded this cycle

- **KiCad tooling unavailable in the execution environment** (reopen
  criterion: `kicad-cli` on PATH and the `pcbnew` python module
  importable in the sandbox/CI). Verified: `shutil.which("kicad-cli")`
  is `None`; `import pcbnew` raises `ModuleNotFoundError`. The layout
  adapter (`regolith.realizer.elec.kicad`) is implemented against the
  documented wire shape (wrapper argv -> JSON `LayoutResponse` on
  stdout, same discipline as `regolith.harness.adapter`) and exercised
  with a fake subprocess in tests; it has never run against a real
  KiCad install. The acceptance fixture
  (`tests/realizer/elec/test_kestrel_fixture.py`) proves the DRC-
  evidence mapping and the bind/netlist/hash pipeline end-to-end but
  fakes the wire response for the placement/routing/DRC step itself.
  `extract_from_pcb` (deliverable 4) is an honest
  `Err(ToolUnavailable)` stub for the same reason (needs `pcbnew`).
- **No lowering-output -> binding-requirement bridge.** WO-24 asks for
  the orchestrator-owned allocation-search loop; no Python-side
  translation from a real lowered `.cupr` build's entities/obligations
  into this module's `BlockRequirement`/`ComponentCandidate` input
  shape exists yet (that bridge is WO-19/WO-26 territory: extracting
  block capability demands and registry-candidate capability tables
  from real compiler output). This WO delivers the allocation-search/
  netlist/layout ENGINE against that explicit input model and
  demonstrates it on a hand-built fixture shaped like the Kestrel
  OBC/ADCS boards (`examples/systems/cubesat/kestrel.cupr`), not on a live
  compiled `.cupr` file. Reopen criterion: WO-26 (or a dedicated
  follow-up) lands the entity-DB -> requirement/candidate extraction.
  THAT FOLLOW-UP NOW EXISTS: WO-29 (lowering output surface,
  deliverable 4; design charter `../design/23-lowering-output-surface.md`) --
  its design pass (cycle 19, D90) decided the Rust/Python split but
  the extraction itself is STILL BLOCKED on the `parts:`-line parser
  promotion (WO-29 Q4/D91), recorded as a cut in WO-29 rather than
  closed this cycle.
- **INV-13 xfails: already resolved, not by this WO.** No `xfail`
  marker exists anywhere in `tests/` (grepped repo-wide). WO-19 already
  populated `bound_kinds` end-to-end and both INV-13 fixtures in
  `tests/invariants/test_inv_13_no_dead_uppers.py` run for real
  (verified green in this cycle's `make check`). `TODO.md` sec. 1
  (the note near "the cross-boundary INV-13 fixture stays xfail until
  then") is stale text describing a state that no longer holds; per
  this WO's dispatch instructions the coordinator updates `TODO.md`,
  not this WO directly.
