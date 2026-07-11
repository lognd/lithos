# WO-86 -- CG/moment-budget claim kind

Status: todo
Language: Rust (regolith-ir budgets) + Python (translate/model) +
  corpus (uav_talon)
Spec: F112 ("CG/moment budget kind (uav)", verbatim); the uav_talon
  corpus (grep its sources for the CG/moment commentary -- the ask
  originated as its fleet escalation, the inline comments are the
  primary evidence, the WO-85 pattern); regolith/05-class budget
  arithmetic (mass budgets are the landed precedent -- READ how
  `mech.mass(all)` budgets lower and discharge before designing
  anything); hematite/03 (claim forms).

## Goal

A center-of-gravity / moment budget is mass-budget arithmetic with
a position weight: sum(m_i * x_i) over declared part masses and
positions, compared against a declared envelope. The uav's flight
stability ask needs the CG position claim to discharge from the
same declared data its mass budget already consumes.

## Deliverables

1. VERIFY FIRST (keystone, the WO-89 pattern): what the uav
   sources actually declare (the claim spelling they want), and
   what the landed mass-budget machinery already computes.
   Undeclared spellings are escalations with recommendations --
   do NOT invent grammar; if the existing budget forms cover the
   ask with a weighted-sum extension at the translate/model layer
   ONLY, prefer that (no grammar change).
2. The lowering/translate/model path for the declared form; part
   positions come from declared data (placements/mounts), never
   realized geometry in v1 (that is the realized-fact channel's
   future).
3. uav census before/after; goldens; tests; docs.

## Acceptance criteria

- The uav CG claim forms an obligation and discharges or defers
  with a specific named-input reason; zero fleet regression;
  no SCHEMA_VERSION bump (escalate if forced); make check green.

## Dependencies

None hard (WO-85/92 landed). Serializes with WO-88 at integration
only through goldens.
