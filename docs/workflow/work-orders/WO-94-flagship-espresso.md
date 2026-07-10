# WO-94 -- Flagship wave 2: espresso_machine promotion (the fluid flagship)

Status: todo
Language: corpus authoring + Python (gap-driven)
Spec: D196.1; toolchain/31-flagships.md; WO-70..75 close-outs;
  F115 addendum census (espresso_machine 127 obligations / 3
  discharged); fluorite/ spec + guide 03 (the track this flagship
  fronts -- the fleet has NO fluorite-led flagship).

## Goal

examples/systems/espresso_machine graduates to
examples/flagships/espresso_machine as the fluorite-led flagship:
thermal/hydraulic flownet claims discharging where models exist,
honest walls ledgered where they do not (the WO-92 close-out noted
nine fluid claims now LOWER but discharge `no_model` -- this WO
inventories exactly which fluid harness models are missing and
either lands the closed-form ones with citations or ledgers them),
plus the same flagship bar as WO-93 (optimizer pin, artifact set,
test net, honest census).

## Deliverables

1. The move (same path-spelling discipline as WO-93 deliverable 1).
2. Fluid-model inventory: for each `no_model` fluid claim, name
   the model it needs; land the citable closed-form ones (pressure
   drop / pump duty / thermal reach -- check what harness/models
   already covers and what feldspar exposes before writing
   anything new; NO DUPLICATION with either); ledger the rest.
3. Census-driven gap pass + one optimizer pin (duct/pump select or
   dimension), WO-93 posture.
4. Artifact bar via preview (flownet sheet + contract graph) +
   `regolith test` scenarios.
5. Docs: flagship README to the fleet shape; guide 03 example
   refresh if spellings drifted.

## Acceptance criteria

- Release build discharge count strictly above baseline (3);
  every remaining deferral specific; any new fluid model
  calibrated against a citable reference (the feldspar law).
- One real optimizer pin with trace. Artifact bar met via preview.
- No spec/grammar changes (escalate instead). `make check` green.

## Dependencies

WO-85/92 + preview landed. Independent of WO-93 (different
directories); both serialize with WO-87/WO-90 at integration only
through goldens (regenerate, never hand-merge).
