# WO-116 -- Cycle-34 residue burn-down (F129's named-open list)

Status: open
Language: mixed -- Rust (arc closure, Bounded->Pinned) + Python
  (CLI seam, exemplar, status vocabulary); no schema bump without
  D225 escalation.
Spec: F123 (tangent-arc closure ruling + reopen criterion); F128.4
  (PROOF-F2/F3, WO-97 deliverable-6 remainder); F129 (HEALTH-F4);
  WO-104 + WO-97 ledgers (the exact residuals).

## Goal

The five inherited residuals close, flipping WO-104 to done and
retiring F129's non-owner-gated open list.

## Deliverables

1. F123: Rust tangent-arc walk-closure solve beside `close_walk` --
   compute each arc's endpoint from tangent continuity + radius,
   verify closure, emit the resolved outline + arcs into the
   profile the emission pass reads; `GantryBeam`
   (`saw_stock(extrusion(BeamSection, l=820mm))`) emits real STEP
   end to end; flip WO-104 Status to done (its acceptance sentence
   completes).
2. WO-97 remainder: Rust `SegmentLength::Bounded -> Pinned`
   literalization after a successful bounded-slot search + preview
   STEP surfacing (the optimizer-pinned arm_a6 UpperArm.b geometry
   becomes a visible preview/ship artifact).
3. PROOF-F2: `regolith optimize` gains the compiled choice_points
   seam (replacing the `--spec` placeholder path where the WO-55
   ledger documented the caller-supplied seam).
4. PROOF-F3: duct_vane corpus exemplar enrolled (the continuous
   staged-evaluator demo gets a corpus twin).
5. HEALTH-F4: WO Status-line vocabulary normalized (one enumerated
   set; the health consistency leg already parses them -- align the
   stragglers and pin the vocabulary in workflow/README).

## Acceptance

- GantryBeam STEP + census enrollment; WO-104 done.
- A bounded-slot search leaves pinned IR + a preview STEP artifact.
- `regolith optimize` runs a compiled design's choice_points
  without hand-supplied domains (subprocess test).
- duct_vane in the corpus test net; demos/demo2 optionally points
  at it.
- `make check` + health green after `make install`.

## Escalation

Each deliverable is independent; land serially, commit per piece.
If the arc solve needs numerics beyond a closed-form/Newton step,
escalate rather than importing a solver dependency.
