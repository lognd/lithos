# WO-157 -- sim/timing fleet adoption: census flip + coverage sweep + waiver burn (D264)

Status: open (Depends: WO-155 [the sim gate, functional half] for
  the sim-half adoption; WO-156 [timing closure v1] for the timing-
  half adoption -- D264 ruling 7/the recon sec. 8 explicitly allow
  the sim half to land first as an honest partial if WO-156 is not
  yet closed, so long as this WO's close-out says so plainly rather
  than silently shipping only half the coverage sweep)
Language: corpus (declaring stimulus artifacts + timing budgets on
  fleet `.cupr` sources) + Python (the coverage/named-absence sweep,
  the E1105 wiring point if a cross-check subject exists here rather
  than in WO-158, census golden regen) + goldens
  (`tests/golden/data/fleet_census.json`).
Spec: D264 rulings 2/3 (the census discharged-decrease rule --
  `tools/health/fleet.py:30-35` -- becomes the sim/timing gate's
  anti-erosion tripwire automatically once new discharged rows enter
  the census, no new census machinery needed; v1 auto-emission
  strength is declared-stimulus-plus-named-absence, NOT a
  refuse-everything cliff -- this WO's coverage sweep enumerates and
  reports absences, it does not retroactively red every uncovered
  fleet project); F152 (the honesty bar this WO's waiver burn must
  meet: reclassification is the deliverable, never invented
  evidence -- "the reclassification is the deliverable, not the
  count," per the design-log's own F157 correction of an earlier
  overclaim); `scratch_recon_cuprite_sim_gate.md` sec. 8 item 5 (this
  WO's deliverable list: stimulus artifacts + timing budgets for
  riscv_hart_rv1, sdr_transceiver, mainboard_mx, la_jig8; burn the
  corresponding waiver rows; census golden regen; the coverage
  named-absence sweep + E1105 cross-check + the INV-<N> ship-path
  check), sec. 4e (c) (the totality-of-coverage-sweep proof shape
  this WO implements: enumerate subjects from the lowered entity set
  the build used, not from claims that happen to exist -- the
  WO-114 zero-unexplained-rows partition precedent,
  `tools/health/fleet.py:36-40`); WO-154's ratified INV-<N> ledger
  entry (this WO is the enforcing change for leg (c)'s TOTALITY and
  the ship-path check referenced in leg (a)'s proof).

## Goal

The four named fleet projects (riscv_hart_rv1, sdr_transceiver,
mainboard_mx, la_jig8) discharge real `hdl.sim_assert` obligations
(and timing budgets where WO-156 has landed) from declared stimulus
artifacts, the corresponding accepted-deviation/waiver rows are
burned as an honest reclassification, the fleet census golden
reflects the new discharged counts, a fleet-wide coverage sweep
proves every behavioral/clocked subject either has real coverage or
a named-absence row (never silence), and the INV-<N> ship-path check
is wired in as the enforcing code for that guarantee.

## Deliverables

1. Stimulus artifacts (directed vectors per WO-155's `signal_table`
   shape) authored for at least the riscv_hart_rv1 uarch/pc_incr HDL
   subjects; timing budgets (per WO-156, if landed) for at least one
   named interface budget per project touched. sdr_transceiver,
   mainboard_mx, la_jig8 get stimulus artifacts for their existing
   HDL extern edges to the extent their corpus has behavioral
   subjects worth covering (per-project scope is a corpus-authoring
   judgment call, recorded in the close-out, not silently
   maximized or minimized).
2. Waiver/accepted-deviation burn: for each newly-discharged
   `hdl.sim_assert` (and timing) obligation, the corresponding
   accepted-deviation row in the affected project's evidence is
   replaced by the real discharge -- per the F152 bar, this is a
   RECLASSIFICATION (the obligation existed and was waived; now it
   discharges for real), never a fabricated new obligation invented
   to inflate a count.
3. Fleet census golden regeneration (`tests/golden/data/
   fleet_census.json`): the four projects' `{obligations, discharged,
   accepted_deviation, violated, ...}` rows update to reflect the
   real discharges; riscv_hart_rv1's starting point (79 obligations,
   4 discharged, 75 accepted deviations, per the recon sec. 2 item 2)
   is the concrete before-state this WO's close-out cites its
   after-state against.
4. The coverage/named-absence sweep (new check, coordinator's
   placement call -- `tools/health/` sibling to the existing
   consistency checks is the natural home given the WO-114
   precedent it reuses): enumerates every HDL extern edge and every
   `on <clk>` body from the LOWERED entity set of each fleet build,
   and asserts each one either matches a real sim/timing obligation
   or appears as an explicit named-absence row in a coverage report
   -- zero silent/unaccounted subjects, the WO-114
   zero-unexplained-rows partition pattern.
5. The E1105 cross-check wiring point (mirror of the extern-ref
   family; the actual demo instance is WO-158's, but the CHECK
   ITSELF -- comparing a simulated trace against a shipped
   `expected_signals.json` window and firing E1105 on disagreement --
   is this WO's enforcing code, since it is part of the census/
   discharge machinery, not the demo narrative).
6. The INV-<N> ship-path check (the INV-32 tap-agreement pattern,
   charter 40 sec. 3): a ship-time refusal if a `sim/` artifact's
   digests do not re-verify against the payload store -- the
   concrete enforcing code for WO-154's leg (a) proof argument.
7. WO-154's INV-<N> ledger entry updated in this WO's close-out:
   record that leg (c)'s TOTALITY claim and leg (a)'s ship-path
   check are now discharged by this WO's code (in the SAME change,
   per house law).

## Out of scope

- Authoring stimulus/timing coverage for any fleet project beyond
  the four named ones -- a later, separate corpus-growth WO if the
  owner wants broader coverage.
- Promoting the coverage sweep from report to a hard release-block
  on EVERY uncovered subject -- D264 ruling 3 explicitly keeps v1 at
  declared-stimulus-plus-named-absence; a stricter policy flip is a
  later, separate decision (mirrors WO-150's report-only-then-promote
  precedent).
- The riscv PROOF.md narrative itself and the concrete
  expected-signals-vs-sim demo run -- WO-158 (this WO wires the
  CHECK; WO-158 performs the DEMO exercising it).
- Any change to the sim/timing gate's implementation
  (`std.timing`/the source-generic sim model) -- WO-155/156 own
  those; this WO is corpus adoption + census + the sweep/ship-check
  only.

## Acceptance

- `uv run pytest tests/golden -k fleet_census -q` green against the
  regenerated golden; a reviewer diff of `tests/golden/data/
  fleet_census.json` shows riscv_hart_rv1's discharged count RISING
  from its pre-WO baseline (79/4/75, recon sec. 2) with accepted
  deviations correspondingly falling -- the F152 honesty pattern,
  checkable as a literal number comparison in the PR diff.
- `tools/health/fleet.py`'s discharged-decrease rule passes (does NOT
  fire) against the new census -- proves this WO is a net rigor gain,
  not erosion.
- The coverage sweep runs and reports zero silent/unaccounted HDL
  subjects across the four named fleet projects: `uv run python -m
  tools.health.<sweep-name> --check` (or the chosen entry point)
  exits 0 with every subject accounted for as either
  discharged/accepted-deviation/violated or an explicit named-absence
  row -- no subject absent from the report.
- E1105 fires on a designed negative fixture (a sim trace deliberately
  disagreeing with a shipped `expected_signals.json` window) and
  stays silent on a matching pair: `uv run pytest tests -k
  e1105_cross_check -q` green.
- The INV-<N> ship-path check refuses a deliberately-corrupted `sim/`
  artifact (digest mismatch) in a negative fixture test.
- `docs/spec/regolith/13-invariants.md`'s INV-<N> entry close-out
  note updated in this same change.
- `make check` and the fleet leg of `make health` both green (fleet
  leg run manually and its output attached to the close-out, since
  `make check` itself does not run the full fleet).

## Escalation

If a named fleet project's corpus has no behavioral subject worth
covering with a real stimulus (e.g. a project that is pure structural
netlist with no clocked logic), record that as an explicit
zero-applicable-subjects finding in the close-out rather than
inventing a stimulus for a subject that does not need one.
