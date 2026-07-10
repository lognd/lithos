# 33 -- CAM verification (design charter; D175, cycle 31)

> Charter for making regolith/08 sec. 4 rule 3 real: supplied
> manufacturing plans (G-code) verified in CHECK MODE -- reach,
> collision, stock removal, completeness -- against realized
> geometry and machine/tool records. Ledger rule: AD-35
> (00-architecture.md). Machinery: WO-67 (+ std.machines/
> std.tooling records via WO-66). Where this doc and a WO body
> conflict, this doc wins.

## 0. The gap this closes

The spec has always said a supplied plan is verified, never
trusted: `plan: extern("op10.nc", gcode_fanuc)` pins the plan
(cause `extern(<ref>)`), check-mode models discharge its claims,
residue goes `by test` (first article). Planning-as-evidence
(regolith/07 sec. 6) makes the plan an evidence artifact. None of
it was built: today a supplied plan discharges nothing.

## 1. Design decisions (load-bearing)

1. **Check mode only, v1.** Verification of SUPPLIED plans; plan
   GENERATION (full CAM) stays the expensive-tier future with a
   flagship-evidence reopen. Checking is cheap and sound; that
   asymmetry is the whole point (08 sec. 4).
2. **One model-pack family, in-house**: `std.cam` (AD-19 packs;
   deterministic, pure-Python + numpy; no external CAM kernel).
   Models, cheapest first:
   - `cam.parse`: G-code dialect front-ends (`gcode_fanuc`,
     `gcode_marlin` for the FDM flagship) -> a typed toolpath IR
     (moves, feeds, tool changes, offsets). Parse failure =
     INDETERMINATE with the offending line cited, never a crash.
   - `cam.envelope`: every commanded position within the machine
     record's travel + the tool's reach arithmetic. Violation
     names the line + axis + excess.
   - `cam.collision_coarse`: swept-tool-vs-fixture/stock clearance
     on a conservative voxel/AABB tier (rapid moves through
     uncut stock are the classic catch).
   - `cam.removal`: conservative voxel stock-removal simulation:
     final stock vs target RealizedGeometry -> undercut (material
     left where the part demands none) and overcut (part body
     removed) measures against the subject's tolerance surface.
   - `cam.coverage`: every machined feature the FeatureProgram
     declares is touched by some cutting move (completeness).
3. **Conservative or silent -- never optimistic.** Voxel results
   carry their resolution as declared error; a pass at resolution r
   claims only what r supports (margin-driven: a thin margin forces
   the finer tier or stays indeterminate). Surface finish,
   chatter, thermal effects: OUT of scope, `by test` territory,
   listed as declared exclusions in the evidence.
4. **Inputs are records + IRs, only**: machine kinematics/travel/
   spindle from `std.machines`, tool geometry from `std.tooling`
   (both under the AD-34 sourcing law), target geometry by
   RealizedGeometry digest, the plan by extern ref hash. No side
   channels (AD-22); the evidence cites all four.
5. **FDM is a dialect, not a second system**: `gcode_marlin` +
   printer machine records verify flagship-1's print plan with the
   same envelope/coverage models (removal inverts to deposition
   bounds -- the conservative claim is envelope + flow-budget
   sanity, recorded as such).

## 2. What already carries it

The planner-evidence doctrine (07 sec. 6), extern linkage + check
mode (08 sec. 4), model packs + subprocess seam (AD-19), evidence
caching/attestation (AD-18/20), RealizedGeometry (AD-25),
FeatureProgram (WO-51), the parity report (AD-33) which counts a
verified plan as `planner`-class provenance.

## 3. Non-goals (reopen criteria attached)

- Plan generation/optimization: reopen on flagship phase-C evidence
  that check-mode + vendor CAM is insufficient.
- High-fidelity surface/finish prediction, chatter, tool wear:
  `by test` forever until a calibrated model with citations exists
  (feldspar territory then).
- Five-axis kinematics: v1 is 3-axis + FDM; reopen on a real
  five-axis corpus member.
- A G-code EMITTER: L6 serialization of generated plans belongs to
  the future generation tier, not here.

## 4. Acceptance shape (what WO-67 must prove)

A milled corpus part (pillow_block class) with a supplied
`plan: extern(...)` G-code file: envelope + collision + removal +
coverage all discharge with cited evidence; a deliberately-broken
variant of each failure class (out-of-travel move, rapid through
stock, undercut plan, missing feature) yields the named
INDETERMINATE/violated result with line citations; flagship-1's
Marlin dialect parses and envelope-checks against a printer machine
record; all deterministic, all cached by content address, parity
report shows the plan as planner-class provenance.
