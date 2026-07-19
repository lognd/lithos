# WO-167 -- dwelling/house wiring program (D268 item 4)

Status: open (Depends: T-0007..T-0011 [WO-132..137, the power track:
  cuprite power vocabulary, power lowering, power models, cuprite-
  calcite tandem, factory flagship -- ALL must be done, this program
  rides the completed track per D268 sequencing item 5: "house wiring
  ... rides power track WO-132..137 completion"], WO-164 [capability
  registry])
Language: Python + Rust per whichever of WO-132..137's own patterns
  this program extends (circuits/panels are a cuprite-calcite tandem
  concern, same split as WO-136); this WO does not introduce a new
  language split, it extends the landed power track's.
Spec: `docs/spec/toolchain/44-boundary-charter.md` sec. 5 (AD-47);
  `docs/workflow/design-log/2026-07-19-cycle-38.md` D268 item 4 (the
  licensing posture, verbatim-binding) and D250 sec. 3 (breaker/panel
  catalog sourcing gate); `docs/workflow/work-orders/WO-132-power-
  front-end.md` through `WO-137-factory-flagship.md` (the track this
  program extends -- read all six before starting, they define the
  cuprite power vocabulary and cuprite-calcite tandem this program's
  circuits/panels/schedules sit on top of).

## Goal

Circuits, panels, cable schedules, and panel schedules for a
dwelling, built on the WO-132..137 power track's existing cuprite
power vocabulary + cuprite-calcite tandem siting -- NOT a new
electrical language, an application of the landed one to residential
branch-circuit/panel/service scope.

## Licensing posture (D250/D268 -- verbatim, do not relitigate)

Representation-first: rule MODELS (e.g. circuit-loading arithmetic,
wire-gauge-vs-ampacity-vs-length voltage-drop calculations) with
cited public-domain or owner-verifiable sources -- reuse whatever
`std.power`'s ALREADY-LANDED WO-134/134B NEC/Eaton-catalog citations
established (grep `std.power` records for the citation pattern
before writing any new one). NO transcription of NEC tables beyond
what those existing citations already cover. Refusals stay NAMED:
if a circuit/panel rule needs a specific NEC table this program does
not already have a landed citation for, refuse it explicitly in the
record/check's own citation field rather than inventing a number.
Breaker/panel catalog CONTENT remains gated on verifiable offline
sourcing per D250 sec. 3 -- do not add new breaker/panel part records
without a citable source; if the owner has not supplied one, the
capability's `process_records` field (WO-164) may reference EXISTING
`std.power` catalog records only, and the registration's DFM checks
may reference circuit-loading rules only, naming the panel-catalog
gap as a deferred item rather than fabricating parts.

## Deliverables

1. Circuit declaration surface: branch circuits (load, wire gauge,
   breaker size, length) as a cuprite-domain construct extending the
   power vocabulary WO-132 landed -- reuse existing constructs (nets,
   loads) before adding new grammar; escalate to design-log if a
   genuinely new construct is needed.
2. Panel siting: reuse the cuprite-calcite tandem (WO-136) to place a
   panel/subpanel within a calcite dwelling model.
3. Cable schedule + panel schedule artifacts: tabular emission
   (reuse the existing schedule-backend machinery from
   `docs/workflow/work-orders/WO-50-` era drawings/schedules backends
   if it already generalizes; otherwise a new but narrow schedule
   renderer following its pattern).
4. DFM/ERC-class checks: circuit loading (breaker size vs. total
   connected load vs. NEC-cited derating, using ONLY existing cited
   values), voltage drop over cable run length (a real closed-form
   calc, cited).
5. `RealizerCapability` registration (WO-164): `process_records`
   points at existing `std.power` records only (per the licensing
   gate above); if population needs exceed what's landed, name the
   gap in this WO's close-out as a follow-up ticket rather than
   blocking or fabricating.
6. Demo: a small dwelling (a handful of rooms/circuits, reusing
   WO-137's factory-flagship pattern scaled down, or a fresh small
   fixture if the factory flagship's scale is a poor fit) with a
   real cable schedule + panel schedule artifact, committed under
   `demos/out/`.

## Non-goals

- No new NEC-table transcription of any kind.
- No panel/breaker part CATALOG growth beyond what WO-134/134B
  already landed, absent a new owner-supplied source.
- No commercial/industrial wiring scope (dwelling only, per D268's
  literal framing).

## Acceptance

- Circuit/panel/schedule constructs exist and are exercised by a
  demo with real cable + panel schedule artifacts.
- Every numeric threshold used in a DFM/ERC check cites its source
  (grep-checkable: each check's citation field is non-empty and
  points at an existing `std.power` citation or a newly-added one
  with an equally real source -- no bare numeric literal without a
  citation comment).
- `RealizerCapability` registration for the dwelling-wiring domain
  passes WO-164's refusal rule.
- `make check` green.
</content>
