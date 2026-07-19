# WO-165 -- perf-board routing capability program (D268 item 3)

Status: open (Depends: WO-163 [board-shaped realized_kind seam],
  WO-164 [capability registry])
Language: Python (realizer + backends + stdlib records); Rust only if
  a new front-end verb is needed in `regolith-syntax`/`regolith-lower`
  for a perf-board substrate declaration (evaluate against the
  existing cuprite board-declaration surface first -- prefer reusing
  it with a `substrate: perfboard` variant over adding new grammar;
  escalate to the coordinator if the existing grammar cannot express
  a fixed-grid substrate without a new construct).
Spec: `docs/spec/toolchain/44-boundary-charter.md` sec. 5 (AD-47);
  `docs/workflow/design-log/2026-07-19-cycle-38.md` D268 items 1-2
  (registry-first rule, sequencing: perf-board is the smallest
  board-shaped win, exercises the new seams end to end before EDM);
  `docs/spec/cuprite/` (existing board/netlist/placement spec -- read
  the current board-declaration and placement front end before
  adding anything, this program is substrate variance on top of
  existing elec machinery, not a new language).

## Goal

Given a netlist/placement already resolvable by the existing elec
chain, produce, for a FIXED-GRID PERF-BOARD SUBSTRATE (no copper
etching, no autorouter): a jumper/wire assignment (which grid holes
each net's connections route through, point-to-point, no copper
plane), a human-followable WIRING MAP artifact, and a CUT LIST
artifact (board size, any board-edge trims). Registered as a
`RealizerCapability` (WO-164) with real `process_records`/
`dfm_checks`/`claim_kinds`, not a one-off code path.

## Deliverables

1. `substrate: perfboard` (or equivalent) variant on the existing
   board declaration -- fixed hole pitch (0.1in/2.54mm standard,
   cite the physical constant, do not invent a number), board
   dimensions in holes.
2. Perf-board realizer: consumes the existing netlist/placement
   payload (same L3 program IR mech/elec already produce -- reuse,
   do not re-derive), emits a jumper/wire ASSIGNMENT: for each net,
   an ordered path of grid coordinates a physical wire/jumper would
   follow, point to point (no routing-around-obstacles solve required
   for v1 -- straight point-to-point per net is an honest v1 scope;
   name any net-crossing/collision handling explicitly as in-scope
   or deferred, do not silently ignore crossings).
3. `RealizedInput`/`realized_kind` payload per WO-163's generalized
   seam (this IS the first real consumer of that seam).
4. Two artifact families (WO-161-registered): a WIRING MAP (a
   rendered, human-followable diagram -- reuse the existing
   drawing/rendering backend machinery, e.g. `backends/drawings/`,
   rather than inventing a new renderer) and a CUT LIST (board
   dimensions + trim instructions, text/CSV or similar -- pick the
   simplest honest format, do not over-engineer). Both stamp WO-160
   provenance (`tier=deterministic` unless a real tool is invoked).
5. `std.process` perf-board-assembly DFM checks (coordinate with
   WO-170, which owns population of the actual PCB/perf-board
   process-record family -- this WO's DFM checks may be stubs that
   WO-170 fills in with real, sourced values, but the CHECK-SET
   CONTRACT and at least one real check, e.g. "no two jumpers occupy
   the same hole," must land here so the capability registration is
   non-empty per WO-164's refusal rule).
6. Capability registration via WO-164's `register_capability`.
7. **Honest demo target**: a small (e.g. 8-hole-by-12-hole or
   similar modest size -- pick a size that keeps the wiring map
   legible and the demo runtime small) perf-board circuit (reuse an
   existing small cuprite demo circuit if one exists at the right
   complexity, e.g. a simple LED-resistor-switch circuit; do not
   invent a new circuit design from scratch if an existing one
   fits) realized end to end: netlist -> jumper assignment -> wiring
   map + cut list artifacts, committed under `demos/out/` following
   the existing `PROOF.md`/`manifest.json` convention (D265 posture).

## Non-goals

- No copper-board/etching path (that is the existing KiCad chain).
- No autorouting/obstacle-avoidance solve for jumper paths in v1.
- No new process-record population beyond the one stub DFM check
  named in item 5 -- WO-170 owns the real population.

## Acceptance

- New demo directory under `demos/out/` with a PROOF.md showing the
  wiring map + cut list artifacts, provenance tier stamped
  `deterministic`, classified via WO-161's registry (no hand
  dispatcher entry added for these two new families).
- `RealizerCapability` for perf-board registers successfully against
  WO-164's refusal rule (all seven fields populated, at least one
  real DFM check, not a stub-only registration masquerading as
  complete).
- A unit test constructs a small netlist, drives the jumper-
  assignment realizer, and asserts the resulting assignment covers
  every net exactly once (no net left unassigned, no net assigned
  twice) -- this is the closest thing to an INV-style completeness
  guarantee for this program and should be written as a real test,
  not just exercised by the demo.
- `make check` green.
</content>
