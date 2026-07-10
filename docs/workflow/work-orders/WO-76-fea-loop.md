# WO-76: FEA-in-the-loop optimization (demonstration + cost accounting)

Status: todo
Depends: WO-55/57 (engine + staged evaluator), WO-27/feldspar
(the FEA-class discharge tier proven by its conformance run), rung
5 (`model=`, landed since the harness spine). NO new mechanism
(D184: a second FEA-variable channel is the AD-22 side channel);
NO schema bump; no crates/ changes.
Language: Python (exemplar + tests + any thin wiring the
composition genuinely lacks -- escalate anything thicker).
Spec: docs/spec/toolchain/34-topology.md sec. 1 (NORMATIVE),
design-log 2026-07-10-cycle-32 D184, 28-optimization.md (budget/
resume/trace law), regolith/12 rung 5, feldspar WO-08/WO-27
close-outs (what FEA tier ACTUALLY runs in this environment --
read before planning; the discretized ccx/gmsh leg was a recorded
WO-27 cut).

## Goal

One exemplar dimension optimized where feasibility is discharged
by the most expensive FEA-class model that actually runs here:
`in [lo, hi] minimize` mass against a stress/deflection claim
carrying `model=<fea-impl>` (rung 5), through the staged evaluator,
under a declared budget, with the trace showing the expensive
evaluations and a resume run proving cache-hit incrementality.

## Deliverables

1. Environment audit FIRST: which feldspar FEA-class tier
   discharges in CI here (the WO-27 conformance path)? Record it;
   if only closed-form tiers truly run, force the most expensive
   RUNNABLE tier and record the discretized-leg residual again
   (unchanged from WO-27) -- the demonstration is about the LOOP
   COMPOSITION and cost accounting, not about which solver brand
   runs.
2. Exemplar: a bracket-class hematite member (extend duct_vane or
   add `examples/tracks/hematite/lug_bracket.hema`) with one
   `in [lo, hi] minimize` dim, a stress claim carrying `model=`
   forcing, corpus-enrolled.
3. The runs, as tests: budgeted optimize converges; the trace's
   per-candidate evidence cites the forced model id; interrupted +
   `--resume` re-evaluates nothing cached; per-evaluation wall time
   recorded in the trace/ledger (the cost accounting D184 asks
   for).
4. Docs: guide 11-optimization.md gains the FEA-loop section
   (including the honest cost table); charter cross-refs; WO
   ledger.

## Acceptance criteria

- The winning pin's trace shows the forced FEA-class model
  discharging each candidate's claim; same-seed reruns
  byte-identical (INV-30); resume performs zero re-discharges of
  cached candidates.
- Budget exhaustion honest; no waivers; parity classes the pin as
  optimize-with-trace.
- `make check` green; Status flipped (or honest partial naming the
  environment ceiling).
