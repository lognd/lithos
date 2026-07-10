# 31 -- The flagship program (design charter; D172, cycle 31)

> Charter for designing real machines end-to-end inside the corpus:
> the pressure-test method scaled from parts to products, with the
> D170 parity bar as the finish line. Ledger rule: AD-33
> (00-architecture.md). Machinery: WO-63 (parity report), WO-64
> (flagship-1). Where this doc and a WO body conflict, this doc wins.

## 0. Why flagships

Every abstraction in this repo was validated by corpus pressure
(examples/ is a build input, AD-11). The owner's directive --
machinery designed declaratively at hand-parity -- cannot be
validated by parts. A flagship is a complete machine, authored
declaratively by an agent, driven to `ship --release`, whose every
wall becomes a recorded finding: the walls ARE the deliverable as
much as the machine.

## 1. The parity bar (D170, normative here)

A flagship phase is DONE when its parity report is clean:

1. Zero unattributed values (every resolved number carries a cause
   class; literals carry their source position).
2. Every decision-shaped value is engine-pinned (optimize/dfm/
   budget/planner cause + trace) or expert-asserted with a named
   ladder rung and basis.
3. All demands discharged or deviation-recorded (release
   semantics); assumes/waives visible, counted, and justified.
4. The report is part of `regolith ship --explain` (WO-50's audit
   surface extended, ONE report mechanism): per-subject counts by
   provenance class, the decision ledger, and the "attention list"
   (asserted literals a reviewer should eyeball -- the honest
   replacement for optimality claims, AD-30).

The bar deliberately claims ATTRIBUTION, not optimality: what the
compiler wins is that nothing is arbitrary and nothing is forgotten
-- the same reason compiled code beats hand assembly at scale.

## 2. Flagship-1: FDM 3D printer (`examples/flagships/printer_k1/`)

Chosen to exercise every track in one machine: mech (frame
extrusions, brackets, gantry, leadscrew motion), thermal-fluid
(hotend melt path as the fluorite exemplar it already resembles;
part-cooling air path), elec (a controller board -- MCU + drivers +
EBI-decoded peripherals, reusing the cycle-30 `by select` decode
demo shape), harness (steppers/endstops/thermistors -- the WO-34
surface), firmware (the WO-37 realizer's contract header + BSP),
plus drawings, BOM, cost, and the parity report.

Phases (each a WO slice with its own acceptance; a phase's walls
are recorded findings BEFORE the next phase dispatches):

- **A -- contract-first (dispatchable now)**: the whole machine at
  L0->L2: frames, interfaces, budgets (mass, cost, wall power, 24V
  rail current, hotend watts), promises, claims; `regolith check`
  clean with ZERO artifacts; the architecture is the deliverable
  and its diagnostics ledger is empty by construction, not by
  waiver.
- **B -- realize (gated on WO-62/63)**: parts realize to STEP, the
  motion assembly realizes placed (RealizedAssembly), the board
  lowers through the elec chain, the harness routes, optimizer
  passes pin the declared free dims/selects.
- **C -- ship (gated on B)**: `ship --release` emits drawings, BOM,
  cost, firmware image, gerber-chain outputs; the parity report is
  clean; goldens pin the whole machine.

## 3. Flagship-2/3 (gated, NOT chartered in detail)

Planes (an RC/UAV airframe class, exercising aero solver packs and
mass/CG budgets) and motherboards (a dense multi-rail board,
exercising DRC depth and SI budgets) follow ONLY after flagship-1's
close-out; each gets its charter written from flagship-1's recorded
walls. Ambition without evidence is how corpora rot.

## 4. Rules of engagement

- Flagships are corpus members: enrolled in goldens/deferral dicts,
  zero-diagnostic at their phase gate, regenerated never hand-edited.
- A flagship agent that hits a toolchain wall STOPS on that leaf and
  records the finding (AD-22 discipline, the F96 pattern) -- the
  flagship WO is never the place to grow a side channel.
- Solver depth gaps route to feldspar (D173's precedent); language
  gaps route to a design-log entry + WO, exactly like every cycle.

## 5. Acceptance shape

Phase A: `regolith check` clean over the full printer architecture;
budgets sum; every interface two-sided; the contract-graph sheet
renders it legibly (the WO-61 producer's first machine-scale test).
Phase B/C: per the phase gates above, parity report clean, goldens
pinned, every wall a design-log finding.
