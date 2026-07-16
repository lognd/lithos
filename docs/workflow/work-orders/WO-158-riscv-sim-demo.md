# WO-158 -- riscv_hart_rv1 sim demo: expected_signals-vs-sim cross-check (D264)

Status: open (Depends: WO-157 [fleet adoption -- the riscv stimulus
  artifacts, the discharged census rows, and the E1105 cross-check
  wiring this demo exercises must exist before the demo can show them
  working]; last WO in the cuprite sim/timing gate track)
Language: demos (`demos/out/` PROOF.md + manifest regeneration,
  `python/regolith` demo-runner script if the project's demo harness
  needs a new entry) + corpus (any additional riscv-specific
  polish the demo narrative needs, strictly within what WO-157
  already landed).
Spec: `scratch_recon_cuprite_sim_gate.md` sec. 6 (the demo tie-in
  this WO executes: "riscv_hart_rv1 earns its census" -- the hart's
  uarch/pc_incr HDL runs a directed instruction-sequence stimulus,
  the build discharges `hdl.sim_assert` for real, the calc book
  carries the sim verdict row and a timing-closure table for one
  interface budget grounded in cited datasheet values, and PROOF.md
  shows the census discharged count RISING with waiver rows burned
  -- the F152 honesty pattern: reclassification is the deliverable;
  the SECOND hook, la_jig8/mainboard_mx bring-up packs' shipped
  `expected_signals.json` windows (D224 provenance,
  `python/regolith/backends/harness_pack.py:207-380`) get their
  loop closed from the OTHER side -- the E1105 cross-check compares
  the SIMULATED trace against the shipped expected-signal windows,
  "the bring-up pack's expectations were watched happening in
  simulation before the board exists," needing no live-capture
  machinery); charter 40 sec. 6 (the live-capture deferral this demo
  answers from the simulation side, not the capture side -- capture
  itself remains deferred, unchanged by this WO); F152 (`docs/
  workflow/design-log/`: the reclassification-is-the-deliverable
  honesty bar every PROOF.md in this repo must meet -- no invented
  evidence, no overclaimed count; F157's own self-correction of an
  earlier overclaim is the cautionary precedent this WO's author
  must re-read before writing PROOF.md's numbers); charter 41 (AD-39,
  the gorgeous-artifact bar every demo's PROOF.md is held to).

## Goal

`riscv_hart_rv1`'s demo materials show, with real numbers, that its
census discharged count rose because a directed-stimulus simulation
now runs for real against its uarch HDL, and that the shipped
`expected_signals.json` bring-up windows for `la_jig8`/`mainboard_mx`
were cross-checked against a simulated trace before any board exists
-- both backed by artifacts a reviewer can open, never narrated
without evidence.

## Deliverables

1. `demos/out/demo<N>_riscv_sim/` (or the project's existing
   riscv-flagship demo directory, if one already exists and this WO
   extends it rather than creating a new numbered demo -- check
   `demos/out/` first and prefer extending over duplicating): a
   PROOF.md that states the BEFORE state (79 obligations, 4
   discharged, 75 accepted deviations, per the recon's own citation
   of the pre-WO baseline) and the AFTER state (WO-157's regenerated
   census numbers for riscv_hart_rv1), with the delta explicitly
   framed as reclassification (waived obligations now discharge for
   real), never as new obligations invented to inflate the count.
2. The manifest/artifact index for the demo includes the real
   `sim/uarch/trace.vcd` and `sim/uarch/sim_report.json` (or the
   actual subject path WO-155/157 produced) so the discharge is
   backed by an openable artifact, not just a narrated number.
3. A calc-book excerpt (or full calc book, if the project's demo
   convention ships the whole thing) showing the sim verdict row
   (vectors, zero failures, tool+version, stimulus citation) and, if
   WO-156 has landed by this WO's dispatch time, one timing-closure
   table for a named interface budget grounded in cited datasheet
   values -- if WO-156 has NOT landed yet, this WO's close-out
   states that plainly and ships the sim-only half as an honest
   partial (per the recon sec. 8's own allowance for a sim-first
   partial).
4. The E1105 cross-check demo beat: a documented run (in PROOF.md,
   with the actual command/output) comparing a `la_jig8` or
   `mainboard_mx` shipped `expected_signals.json` window against the
   corresponding simulated trace, showing agreement (or, if the demo
   deliberately shows the negative case too, a clearly-labeled
   disagreement fixture separate from the positive demo run).
5. `demos/out/.../manifest.json` regenerated to include the new
   artifacts, following the same manifest-update convention the
   existing demo directories use (cf. `demos/out/demo11_board_
   gerbers/manifest.json`, `demos/out/demo17_physical_bringup_pack/
   manifest.json` as format precedents).

## Out of scope

- Any change to the sim/timing gate's implementation, the fleet
  adoption's stimulus authoring, or the census golden -- all WO-155/
  156/157's; this WO only demonstrates what they landed.
- Live-capture hardware-in-the-loop verification -- charter 40 sec.
  6's deferral is UNCHANGED; this demo's cross-check is
  simulation-vs-expectation, not capture-vs-expectation.
- Any new fleet project's coverage -- riscv_hart_rv1 (primary) and
  la_jig8/mainboard_mx (the E1105 cross-check hook) only, per the
  recon's own demo-tie-in scope.

## Acceptance

- `PROOF.md` states BEFORE/AFTER census numbers for riscv_hart_rv1
  that MATCH the actual regenerated `tests/golden/data/
  fleet_census.json` values from WO-157 (a reviewer can diff the
  claimed numbers against the golden file and find them identical --
  the F152 honesty check made mechanically verifiable).
- `test -f demos/out/.../sim/uarch/sim_report.json` (or the actual
  landed path) succeeds -- the discharge claim is backed by a real
  artifact file, not narration alone.
- The E1105 cross-check command in PROOF.md is RUNNABLE and its
  documented output matches a fresh run: re-running the exact command
  PROOF.md quotes reproduces the exit code/summary it claims.
- `demos/out/.../manifest.json` includes the new sim artifacts,
  checkable by `python -m json.tool` parsing + a key-presence
  assertion (or the project's existing manifest-validation test).
- If WO-156 has not landed by dispatch time, PROOF.md contains an
  explicit honest-partial note naming the timing-half deferral (no
  silent omission of the timing table).
- `make check` green; the project's demo-verification target (if one
  exists, e.g. `make demos` or `tools/health/demos.py`) passes for
  this demo directory specifically.

## Escalation

If WO-157's fleet adoption did not reach riscv_hart_rv1 specifically
(e.g. scope was cut to a different project under its own escalation),
escalate to the coordinator before substituting a different flagship
for this demo -- the recon's demo tie-in specifically names
riscv_hart_rv1 for the "earns its census" narrative, and a silent
substitution would misrepresent which project actually improved.
