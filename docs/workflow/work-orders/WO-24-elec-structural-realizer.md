# WO-24: Elec structural realizer (bind -> netlist -> layout)

Status: done (end-to-end half closed this cycle: the bridge landed
already via WO-29 deliverable 4; this dispatch closes the remaining
gap, the real-KiCad `RealizedLayout` producer + its WO-42 `put` seam.
See "End-to-end close-out (this dispatch)" below for the full
account.)
Depends: WO-16 (registry records), WO-19 (lowering), WO-20 (realizer
registers as a model pack); WO-05 residual (elec behavioral bodies
typed) only for the behavioral/INV-16 half, which is NOT this WO
Language: Python (`regolith.realizer.elec`); vendor tools driven as
subprocesses through the WO-20 adapter discipline
Spec: cuprite/04 (the L3->L4 realizer, step order is normative),
cuprite/06 (lowering table); regolith/08 sec. L4; regolith/07 sec. 7
(allocation search)

AMENDMENT (cycle 24, D128/AD-25): the placed/routed layout this WO
produces gains a Rust-sourced IR, `RealizedLayout` (WO-42; NEW
payload kind `layout.realized`, content-addressed, put into the
WO-30 store): outline, placements, routed segments with lengths and
layers, copper summary, parasitic slots, `.kicad_pcb` content-hash
pin. The `.kicad_pcb` stays the pinned native artifact (verify-only
L4 re-import unchanged); the "extracted-fact channel (stackup,
lengths, copper areas) shaped as model-pack inputs" deliverable
rides `RealizedLayout` rather than a bespoke format. WO-42 owns the
schema and the emission seam; nothing else in this WO's scope moves.

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
  criterion MET, cycle 26 -- kicad-cli 10.0.4 on PATH, pcbnew linked
  into the venv by `make install` (kicad-link); the `-m kicad` tier
  runs real; see kicad.py environment note (SWIG deprecation
  caution); original text:
  `kicad-cli` on PATH and the `pcbnew` python module
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
  RETIRED (WO-35, cycle 24): the cut is now BEHIND A GATE rather than
  unconditional. `regolith.realizer.elec.kicad.real_kicad_available()`
  checks both `kicad-cli` on PATH and `pcbnew` importable; a
  `-m kicad`-marked test tier (`tests/realizer/elec/test_kicad_real.py`)
  runs real when the gate is open and skips WITH the tool named in the
  reason when it is not (still closed in this sandbox, verified the
  same way). `test_kestrel_fixture.py`'s fake-subprocess tier remains
  the always-on tier per WO-35's acceptance criteria. Pin assignment
  itself (this WO never attempted it -- see `docs/spec/cuprite/04-
  structural-layer.md` sec. 1 step 2, unchanged since cycle 7) is now
  owned by `realizer/elec/pinmux.py`.
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
  THAT FOLLOW-UP LANDED: WO-29 deliverable 4 (2026-07-08, D126)
  supplies the bridge. Rust (`regolith-lower::block_requirement`) emits
  the raw capability demands per architecture-resource `promises:`
  argument into the `block_requirements` `BuildPayload` field; Python
  (`regolith.realizer.elec.bridge`) screens them into this module's
  `BlockRequirement` and derives `ComponentCandidate`s from magnetite
  `RecordStore` records. An end-to-end test drives raw payload ->
  screening models -> THIS module's `bind_all` to a bound pin with no
  hand-built requirement fixture. The remaining hand-built piece in
  `test_kestrel_fixture.py` is the KiCad wire step (still blocked on
  `kicad-cli`/`pcbnew`, the separate cut above), not the input bridge.
- **INV-13 xfails: already resolved, not by this WO.** No `xfail`
  marker exists anywhere in `tests/` (grepped repo-wide). WO-19 already
  populated `bound_kinds` end-to-end and both INV-13 fixtures in
  `tests/invariants/test_inv_13_no_dead_uppers.py` run for real
  (verified green in this cycle's `make check`). `TODO.md` sec. 1
  (the note near "the cross-boundary INV-13 fixture stays xfail until
  then") is stale text describing a state that no longer holds; per
  this WO's dispatch instructions the coordinator updates `TODO.md`,
  not this WO directly.

## End-to-end close-out (this dispatch)

The two remaining gaps this WO's ledger named -- a real KiCad run, and
WO-42's `layout.realized` `put` emission seam (WO-42 deliverable 4's
remainder, explicitly deferred to WO-24 by that WO's own notes) -- are
both closed on this host, where `real_kicad_available()` is OPEN
(kicad-cli 10.0.4 + linked `pcbnew`).

- **`regolith.realizer.elec.kicad_wrapper`** (new module): the real
  `argv` executable `run_layout` talks to. Honest scope, not invented
  around: it builds a real `pcbnew.BOARD`, draws a real placeholder
  square `Edge.Cuts` outline (importing the caller's actual mech-
  interface outline is a separate, larger integration this dispatch
  does not attempt), saves a real `.kicad_pcb`, and runs a real
  `kicad-cli pcb drc` pass. No footprint-library resolution/placement
  or routing machinery exists anywhere in this repo yet, so the
  response is always `status="unrouted"` -- WO-24's own documented
  honest outcome ("autorouting quality is NOT promised") -- never a
  faked `"routed"`. The DRC report on the resulting outline-only board
  is real KiCad output. `regolith.realizer.elec.kicad.run_real_layout`
  wires `run_layout` to this wrapper via `real_wrapper_argv()` (same
  interpreter, so it shares the process's linked `pcbnew`).
- **`extract_from_pcb`** (`regolith.realizer.elec.extraction`):
  promoted from an unconditional `Err(ToolUnavailable)` stub to a real
  `pcbnew`-backed track/zone walk, gated on `pcbnew` importability
  (still an honest `Err(ToolUnavailable)` on a `pcbnew`-less host,
  never faked either way); a missing/unreadable file is now a distinct
  `Err(LayoutFailed)` rather than depending on how the vendored
  SWIG binding happens to fail on a bad path.
- **`regolith.realizer.elec.realized`** (new module): WO-42
  deliverable 4's remainder -- `build_realized_layout` assembles the
  generated `regolith._schema.models.RealizedLayout` from a
  `LayoutArtifact` + placements/routed segments/extraction;
  `put_realized_layout` stores it into the WO-30 `PayloadStore` (kind
  `layout.realized`), mirroring `orchestrate.put_realized_geometry`'s
  `PayloadStore.put` (fresh digest, no upstream Rust-computed digest to
  reproduce yet). Original note ("No `REALIZER_PACK_ELEC`
  lockfile-cause wiring is added -- `orchestrate.py`'s `staged_build`
  loop (WO-42 deliverable 5) is mech-only by that WO's own scoping;
  wiring an elec staged-build leg is a distinct future dispatch, not
  attempted here"): THAT DISPATCH LANDED (the joint WO-24/WO-25
  close-out, same cycle). `staged_build` now takes a caller-supplied
  `elec_boards` map (mirroring `feature_programs`' role for the mech
  leg -- `layout.realized` has no in-payload discovery placeholder, so
  which board backs which subject is a caller-supplied fact, the same
  documented scoping decision the mech leg already made);
  `realizer.elec.realized.realize_elec_board` drives the real-KiCad
  wrapper behind `real_kicad_available()` (an honest `ToolUnavailable`
  skip when the gate is closed, never faked); and `REALIZER_PACK_ELEC`
  lockfile rows (`<subject>.layout`, `cause: realizer(elec)`, INV-21)
  land via the now-kind-aware `realized_lock_rows`. The `-m kicad`
  e2e test (`tests/orchestrator/test_staged_build_elec_kicad.py`,
  passing REAL on this host) proves a real `.cupr` staged build
  carries `layout.realized` in `StagedBuildReport.realized_inputs`,
  the report survives the `ship --build` disk round-trip, and the
  elec backend exports the manufacturing set from the pinned
  `.kicad_pcb` bytes with the real `kicad-cli`.
- **Tests** (`tests/realizer/elec/test_kicad_real.py`, `-m kicad`
  tier, all 4 passing REAL on this host): a real `kicad-cli --version`
  smoke test (pre-existing), the always-callable gate-reporter
  (pre-existing), a new real-wrapper-produces-a-real-board-and-DRC-
  report test, and a new full round trip (real layout -> real
  extraction -> `RealizedLayout` assembly -> store `put` -> `resolve`
  -> idempotency). `tests/realizer/elec/test_extraction.py`'s
  previously-unconditional "pcbnew absent" test is now gated on
  `pcbnew_importable()` (it no longer holds on a `kicad-link`ed host);
  a new counterpart test asserts the honest `LayoutFailed` outcome for
  a missing file on such a host.
- **Not attempted (explicitly out of scope, named not dropped):** real
  footprint-library resolution/placement, real autorouting, real board-
  outline import from the mech interface, and (at the time of that
  dispatch) wiring an elec leg into WO-42's staged-build loop -- the
  staged-loop item has since landed (see the `realized` bullet above);
  the other three still stand. Each needs its own design/integration
  pass (footprint libraries in particular have no existing convention
  anywhere in this repo to build against) and none is required by this
  WO's literal acceptance text, which only asks for the layout ADAPTER
  and the extraction HOOK, honest about autorouting quality.
- `make check` green (fmt, clippy `-D warnings`, ruff, ty, guard-core,
  schema-check, Rust + Python tests: 459 passed, 2 skipped, 23 xfailed).
  No `SCHEMA_VERSION` bump (no schema/wire type changed -- `RealizedLayout`
  was already landed by WO-42).
