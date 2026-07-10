# WO-69: `plan:` linkage lowering (supplied plans reach std.cam)

Status: todo
Depends: WO-67 (std.cam pack, landed -- its close-out ledger's
"Follow-up" paragraph IS this WO's spec-in-brief), WO-68 (landed;
its ForallSweepClaim work touched the same claims lowering area --
read its ledger first). Owns the next serialized SCHEMA_VERSION
bump 25->26 ONLY IF a payload field proves necessary (the WO-67
ledger expects the D96 payloads channel to suffice -- verify before
bumping; a bump-free landing is the preferred outcome).
Language: Rust (`regolith-syntax` `plan:` production,
`regolith-lower` cam obligation emission) + Python (orchestrator
staging of plan/machine/tool/target payload refs, mirroring
`regolith.orchestrator.costing`'s staged-doc precedent).
Spec: regolith/08 sec. 4 (extern plans + check mode -- the
doctrine), regolith/07 sec. 6 (planning as evidence),
33-cam-verification.md sec. 1.4 (inputs are records + IRs only),
WO-67's close-out ledger (the extern-seam findings: what exists,
what does not), regolith/11 (formats kind).

## Goal

`plan: extern("op10.nc", gcode_fanuc)` in source lowers to one
obligation per applicable `cam.*` claim kind, with payload refs for
the plan bytes (hash-pinned), machine record, tool records, and the
target RealizedGeometry digest -- discharged end-to-end by the
landed std.cam models; lockfile cause `extern(<ref>)`.

## Deliverables

1. Grammar: the `plan:` field production (per regolith/08 sec. 4's
   table row); CST/AST; formatter; negative fixtures (unknown
   dialect name; missing ref).
2. Lowering: emit `cam.parse`/`cam.envelope`/`cam.collision_coarse`/
   `cam.removal`/`cam.coverage` obligations for a plan-carrying
   subject, keyed per INV-1, payloads map populated per the WO-67
   ledger's expectation.
3. Orchestrator staging: resolve the extern ref to pinned bytes,
   the subject's machine/tooling record refs (source-declared --
   decide the spelling from the existing `process=` argument
   conventions, escalate if a new argument form is genuinely
   needed), and the target geometry digest; `cause: extern(<ref>)`
   lockfile row.
4. End-to-end corpus proof: the WO-67 fixture plan attached to a
   real corpus part discharges all five models through
   `regolith build`; the broken variants produce their named
   results through the REAL pipeline (not just pack-level tests).
5. Parity: the plan's values class as planner/extern provenance in
   the WO-63 report (the recorded cross-note closes).
6. Docs: guide 14-cam-verification.md gains the source-level
   walkthrough; WO-67 ledger cross-note; this WO's ledger.

## Acceptance criteria

- Source with `plan:` emits exactly the five obligations (keyed
  distinctly); removing the plan field removes them; the corpus
  regression net (WO-68's) stays green.
- End-to-end: good plan discharges Valid x5 with evidence citing
  all four digests; each broken variant surfaces its named result
  via `regolith build --json`.
- Bump-free if possible; if not, exactly 25->26 with the D168 train
  note in the design log (a dated addendum, next free D integer).
- `make install` + `make check` green; Status flipped.
