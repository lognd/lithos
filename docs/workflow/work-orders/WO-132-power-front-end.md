# WO-132 -- The power net discipline + cuprite power vocabulary (D248/AD-42, charter 43 secs. 1-2)

Status: open
Language: Rust (`regolith-syntax` grammar/CST, `regolith-sem` net
  core discipline plugin). Schema: a PowerNetPayload slot is WO-133's
  business -- this WO is front-end only. No schema bump here.
Spec: charter 43 secs. 1-2 (NORMATIVE); AD-42; AD-23 (ONE net core,
  parameterized by `NetDiscipline` -- you add the fourth, you do NOT
  fork the core); D248; cuprite/03 sec. 2 (the elec discipline's
  settled checks -- your model); fluorite/02 sec. 4 (the fluid
  discipline -- the closest analogue: conserved flow + potential);
  cuprite/04 (structural layer, where the vocabulary lands);
  regolith/09 (diagnostic families; new codes go through WO-131's
  registry -- coordinate, do not fork).

## Goal

An engineer can DECLARE a factory's power system in cuprite --
service, transformers, switchgear, feeders, motors, loads -- and the
net core checks it with the same ledger machinery it already runs for
elec nets, fluid circuits, and civil load paths.

## Deliverables

1. The **power** `NetDiscipline` in `regolith-sem` (AD-23's fourth;
   parameterize, never fork the core): nodes are BUSES, edges are
   sources/transformers/feeders/protective devices, flow is current
   (kVA), potential is voltage. Reuse the terminal ledger, reference
   reachability, and imposer counting the core already provides.
2. Discipline rules as diagnostics (charter 43 sec. 1):
   (a) at least one source imposer per energized subnet -- an
   unsourced load is a diagnostic, never an assumption;
   (b) exactly one source path per bus unless a TIE is explicitly
   declared -- undeclared parallelism is a diagnostic (this rule
   exists because accidental parallelism destroys equipment);
   (c) a declared protective device at every ampacity transition;
   (d) every load reachable from a source.
3. Vocabulary (charter 43 sec. 2), as ordinary cuprite artifacts with
   power roles -- one word one idea, every one a name an electrical
   engineer already uses: `service`, `generator`, `transformer`,
   `switchgear`, `panelboard`, `mcc`, `feeder`, `busway`, `breaker`,
   `fuse`, `relay`, `motor`, `load`. Grammar + typed CST.
4. Claim FORMS parse and reach lowering as recognized (routing and
   discharge are WO-133/135): `elec.power.demand_load`,
   `voltage_drop`, `ampacity`, `fault_current`, `withstand`,
   `transformer_loading`, `motor_start_dip`, `coordination`,
   `arc_flash`, `grounding`, `power_factor`, `harmonics`,
   `working_clearance`.
5. Corpus: negative fixtures for each discipline rule (unsourced
   load; undeclared parallel path; unprotected ampacity transition;
   unreachable load), and one positive multi-file power design that
   parses zero-diagnostic.
6. Docs: a cuprite spec section for the power layer (the track's own
   `docs/spec/cuprite/` numbering; version-bump the track header);
   guide section deferred to WO-137's flagship.

## Acceptance

- The four discipline rules each FAIL their negative fixture with a
  named, coded diagnostic and PASS the positive design.
- The extension-string rule holds (no new file extension: power is
  cuprite, `.cupr`).
- `make check` green; zero regression in the elec/fluid/civil
  disciplines (their fixtures byte-identical).

## Escalation

If the net core genuinely cannot express a power rule without a core
change (rather than a discipline parameterization), STOP and report
-- AD-23 says the core is ONE, and changing it is a coordinator
decision. Diagnostic codes: coordinate with WO-131 (which owns the
registry and is adding families); do not mint a parallel code space.
