# WO-155 -- the cuprite functional simulation gate: source-generic `hdl.sim_assert` (D264)

Status: open (Depends: WO-153 [procio seam, the sim model's tool
  invocation routes through it], WO-154 [ratified spec: the
  stimulus-binding clause, the `signal_table` registry entry, the
  invariant text]; the D256 hash window MUST have merged -- this WO
  touches lowering + goldens, same serialization law as every other
  lithos code WO this cycle)
Language: Rust (`regolith-syntax` grammar extension for the
  stimulus-binding clause, `regolith-lower` obligation emission
  per the plan.rs precedent, `regolith-diag` new E11xx codes) +
  Python (`harness/models/hdl/models.py` generalization, the
  `signal_table` payload consumption, `sim/` artifact emission,
  the content-address cache).
Spec: WO-154's ratified spec deltas (the `by sim(<stimulus-ref>)`
  clause, the `signal_table` registry entry, the coverage-matrix
  flip text -- implement exactly what WO-154 specifies, do not
  re-derive); D264 rulings 2/3/4/5 (gate economics/caching, v1
  auto-emission strength -- declared-stimulus sim plus named-absence
  coverage, NOT a refuse-everything cliff; schema discipline --
  ride WO-147's bump or sequence after it, never a second bump; the
  VCD/signal_table seam with the signal-design track, D263); D260
  ruling 3 (authored evidence posture -- a drawn/typed stimulus is
  authored/asserted tier, can drive a PASS/FAIL verdict but can
  never itself claim model-backed or measured); `scratch_recon_
  cuprite_sim_gate.md` secs. 4a/4b/4c/4d/5 (the full gate design
  this WO implements: claim family, Rust emission pattern, cache
  key shape, artifact family, determinism posture -- not
  re-derived here); D202 (the `hdl.build` source-generic precedent
  this WO repeats for `hdl.sim_assert`,
  `python/regolith/harness/models/hdl/models.py:183`); `crates/
  regolith-lower/src/claims/plan.rs:206-262` (WO-89's auto-emit
  pattern for HDL extern edges -- this WO's Rust emission clones
  it); `python/regolith/harness/models/hdl/models.py:112-118,
  312-454` (today's FIXTURE-ONLY sim model and testbench-build/run
  logic this WO generalizes to source-generic); `python/regolith/
  orchestrator/translate.py:3486` (`_translate_hdl`, already wired
  for `hdl.sim_assert` requests -- this WO is what finally makes
  real fleet requests form, not the translate wiring itself);
  charter 37 sec. 1.4 (the scenario-digest x design-digest cache
  rule this WO's cache key reuses one layer down); `crates/
  regolith-diag/src/code.rs:491-505` (E1101-E1103 assigned; WO-151
  claims E1104 for `bringup_expectation_authored_posture` -- THIS
  WO's new codes take the NEXT FREE slot(s) after WO-151's claim,
  confirmed at implementation time via the generated registry,
  `make codes`; do not assume E1104 is free without checking
  WO-151's landed state first).

## Goal

A behavioral HDL subject that declares a stimulus artifact
discharges `hdl.sim_assert` for real, from an ordinary fleet build
-- source-generic, content-address cached, artifact-complete --
while a subject with no declared stimulus produces a named-absence
coverage row rather than silence or a fabricated pass.

## Deliverables

1. Grammar: the `by sim(<stimulus-ref>)`-shaped clause from WO-154's
   ratified spec, parsed alongside the existing `impl ... by
   extern(ref, <hdl-dialect>)` clause (`regolith-syntax`).
2. Rust emission (`regolith-lower`, the plan.rs pattern): an
   `hdl.sim_assert` obligation is auto-emitted for an HDL extern edge
   WHEN the design names a stimulus artifact for that subject via the
   new clause -- the author cannot forget the claim once a stimulus
   is declared. A behavioral subject with an HDL extern edge but NO
   stimulus clause is enumerated by the coverage producer (WO-157)
   as a named absence, not emitted here as a fabricated obligation.
3. `signal_table` payload port (Python, beside the existing `hdl_src`
   port on the `hdl.sim_assert` `DischargeRequest`): hash-pinned
   directed stimulus/expectation vectors (cycle/time, input
   assignments, expected output windows) per WO-154's ratified
   schema, carrying the provenance/trust-tier fields the D260 seam
   requires (authored tier only for a drawn/typed artifact; no
   constructor path to model-backed/measured for this payload kind
   -- deliverable 6's E-code is the belt to this suspenders).
4. Source-generic sim model (`harness/models/hdl/models.py`): the
   existing fixture-bound `hdl.sim_assert` model (models.py:112-118,
   396-454) generalizes to build a testbench harness FROM the
   `signal_table` vectors (rather than consuming a hand-authored
   testbench file) for ANY subject naming a stimulus, exactly the
   way D202 generalized `hdl.build` from fixture-only to
   source-generic. PASS/ASSERT-FAIL/SIM_OK discipline and the
   failure-count verdict arithmetic (upper bound 0, eps 0) are
   UNCHANGED; tool failure/timeout still maps to `Err(DomainError)`
   (indeterminate), never a silent pass. The 5 existing fixture
   registrations (counter, alu_generic, fifo_cdc, assertions_map,
   fsm_traffic) continue passing unchanged against the new
   source-generic path (they become its first proof, not a parallel
   legacy path).
5. `_translate_hdl` (`orchestrator/translate.py:3486`) gains the
   stimulus port: a fleet build with a real stimulus-binding clause
   now forms a real `hdl.sim_assert` `DischargeRequest`, closing the
   gap the recon named (translate wiring existed; requests never
   formed).
6. New E11xx diagnostic codes (`regolith-diag`, via `make codes` --
   confirm the actual next-free slot against WO-151's landed state):
   - a stimulus artifact carries no provenance/authored-tier record
     (the D260.3 evidence-honesty check on the `signal_table`
     payload itself);
   - a declared stimulus ref does not resolve (mirror of the
     extern-ref-does-not-resolve family, loud at ship).
   Every new code gets a `regolith explain` entry (WO-131 law).
7. Artifacts (`sim/` family, AD-36 registry, per WO-154's charter 38
   table entry): `sim/<subject>/trace.vcd` (verilator `--trace`
   output, hash-pinned by stimulus digest + src digest + tool
   version) and `sim/<subject>/sim_report.json` (vectors, failures,
   tool+version, stimulus provenance, cache key -- shape precedent
   `backends/hdl.py:103-144`'s `tier_report.json`).
8. Content-address cache: cache key = (hdl_src digest x stimulus
   digest x model version, where model version already folds the
   verilator version per the existing AD-19 cache-key law,
   `models.py:127-131`); a sim re-runs only when the HDL bytes, the
   vectors, or the tool version changed. Implemented as a lookup
   keyed ONLY by digests/claim-kind/project-name (F154 compliance --
   never a line number, never a volatile identity).
9. Rust + Python tests: grammar parses the stimulus clause and
   rejects malformed refs; Rust emission fires the obligation exactly
   when a stimulus is declared and does NOT fire when absent; the
   source-generic model discharges a NEW (non-fixture) example design
   end to end; the cache proves a second identical run is a lookup
   hit (no re-invocation of verilator); both new E-codes fire on
   their designed negative fixtures.

## Out of scope

- The coverage/named-absence SWEEP itself (enumerating every subject
  and asserting totality) -- WO-157, which consumes this WO's
  emission machinery.
- Timing closure (`budget kind=timing`, `std.timing` model) -- WO-156,
  a sibling gate, not this WO.
- VCD waveform RENDERING (a gorgeous-artifact figure) -- deferred to
  the signal-design/graphite surface per D264 ruling 5; this WO ships
  the `trace.vcd` data file, not a picture.
- Constrained-random stimulus generation -- v1 is directed vectors
  only (D264 ruling 2); if/when constrained-random arrives, the seed
  becomes part of the stimulus artifact and thus the cache key, by a
  LATER WO.
- Any second manufacturer/vendor concern -- not applicable to this
  WO.
- Fleet corpus adoption (declaring real stimulus artifacts for
  riscv_hart_rv1/sdr_transceiver/mainboard_mx/la_jig8, burning waiver
  rows) -- WO-157.
- The E1105 expected_signals-vs-sim cross-check -- WO-158 (needs a
  real demo subject with both a bring-up pack and a sim trace to
  cross-check against).
- The `signal_table` payload's SCHEMA_VERSION bump, if one turns out
  to be needed: per D264 ruling 4, this WO's implementer MUST check
  whether WO-147 has already landed its cycle-37 bump; if the
  payload needs new wire fields, they ride WO-147's bump (if not yet
  closed) or this WO explicitly declines to add wire-breaking fields
  and records the gap for a future-cycle bump in its close-out --
  under NO circumstance does this WO open a second cycle-37 bump
  (D211/D261.4 one-bump-one-owner).

## Acceptance

- `cargo test -p regolith-syntax -p regolith-lower -k sim_assert`
  green: stimulus-clause parsing, obligation emission on-declared /
  absent-on-undeclared, both proven by test.
- `uv run pytest tests -k hdl_sim -q` green: the 5 existing fixtures
  pass through the generalized source-generic path unchanged, AND at
  least one NEW non-fixture example design discharges
  `hdl.sim_assert` for real from an ordinary build.
- Cache-hit proof: a test asserts a second identical
  (src, stimulus, tool-version) run does not re-invoke verilator
  (mock/count the `procio.run_tool` call, or the project's
  equivalent instrumentation) -- `uv run pytest tests -k
  sim_gate_cache -q` green.
- `regolith explain <code>` prints a real entry for both new E11xx
  codes (no placeholder text); `grep -rn 'SCHEMA_VERSION'
  crates/regolith-syntax/src` still shows exactly one cycle-37 bump
  (WO-147's) unless this WO's close-out explicitly documents landing
  its passenger fields inside that same bump.
- `sim/<subject>/trace.vcd` and `sim/<subject>/sim_report.json` are
  produced by a real fleet-adjacent build (a test project, not
  necessarily a fleet flagship yet -- WO-157 does the fleet
  adoption): `test -f` over a build's dist/ output, or the project's
  existing artifact-presence test pattern.
- `make check` green.

## Escalation

If the `signal_table` payload cannot express the vector shape
WO-154's spec settled on without a wire-schema change AND WO-147 has
already closed its bump, escalate to the coordinator before opening
a second SCHEMA_VERSION bump -- do not silently smuggle the change
in as a non-breaking addition if it is not actually non-breaking.
