# WO-93 -- Flagship wave 2: cubesat promotion

Status: todo
Language: corpus authoring + Python (gap-driven)
Spec: D196.1 (the promotion ruling); toolchain/31-flagships.md
  (the flagship bar + parity posture); WO-70..75 close-outs (the
  fleet pattern: phases, honest walls, optimizer pins); F115
  addendum census (cubesat 91 obligations / 7 discharged -- the
  strongest system).

## Goal

examples/systems/cubesat graduates to examples/flagships/cubesat
at the flagship bar: every honest gap either closed or ledgered as
a named wall, at least one optimizer pin proven from the compiled
design, its feldspar-reachable claims discharging, and the D196.2
artifact bar met (`preview` produces its sheet/graph set stamped;
`ship` refuses only on the honestly-unresolved remainder).

## Deliverables

1. The move (directory + goldens/deferral dicts + path references
   -- grep for BOTH string-joined and Path-joined spellings; the
   small_office graduation missed two Path-joined test refs).
2. Deferral-census-driven gap pass: classify all ~84 unresolved
   obligations by reason; close what landed machinery already
   supports (record refs, load paths, conformance impl bounds --
   D195's teaching deferrals name exactly what each impl owes);
   ledger the rest as named walls in the WO file, fleet-style.
3. At least one `by select`/dimension optimizer pin from the
   compiled design (`cause: optimize(...)` in the lockfile), the
   WO-70..75 posture.
4. Artifact set: `preview --out` sheets + contract graph committed
   as CI-checked expectations (the test asserts artifact
   presence + stamp, not pixel equality); `regolith test` corpus
   net extended (a .test.<ext> scenario per track the design
   spans).
5. Docs: flagship README updated to the fleet table shape.

## Acceptance criteria

- Release build discharge count strictly above the census baseline
  (7), with every remaining deferral carrying a specific reason.
- One real optimizer pin with trace. Artifact bar met via preview.
- No spec/grammar changes in this WO (escalate instead).
- `make check` green.

## Dependencies

WO-85/92 + preview landed (all merged). Serializes with WO-87 at
integration if its board entities change cubesat's elec counts
(re-census after merging, do not fight it).
