# WO-109 -- Claim routing by call form + probe plugin loading (Class B)

Status: open
Language: Python (orchestrator/translate.py + harness registry +
  plugin loading); Rust ONLY if the lowered claim record genuinely
  lacks the call text (escalate first).
Spec: F130 Class B; F126.1 (the cycle-33 thermo precedent:
  route label-named claims by CALL FORM); F128.2 (the D209
  evaluator already recognizes call forms where geometry exists --
  the translate-time half was deliberately skipped then, landed
  now); D220 (no verdict changes); charter 38 (unchanged).

## Goal

A claim whose right-hand side is a model call -- `payload_ok:
mech.deflection(...)`, `sag: mech.deflection(...)`, `life:
mech.bearing.l10_hours(...)` -- reaches the registered model for
that CALL, regardless of what its author labeled it. "No registered
harness model for label kind 'payload_ok'" dies as a deferral
reason wherever a call form exists; what remains is either a real
model verdict or an honest `*_inputs_missing` deferral naming the
missing inputs.

## Deliverables

1. Translate-time routing: `_match_call_lhs`-family recognition
   generalized so ANY label-named claim with a call expression
   routes by the call's dotted model path (the thermo/within-window
   precedent, applied everywhere). Label-only claims (no call) keep
   their current honest no-model deferral.
2. The routing covers every track's claim surface (hema/cupr/fluo/
   calx) -- audit the label-kind deferrals fleet-wide and enumerate
   which routes light up in the WO close-out.
3. Probe plugin loading: the ship/release probe env loads
   registered plugin packs exactly like CLI builds do -- the 9
   "elec.si lives in the optional feldspar pack, not installed in
   the probe env" deferrals become real model invocations (feldspar
   IS installed; F126.1(a) proved CLI builds load the full
   registry -- find and fix the probe-path divergence).
4. Deferral-reason hygiene: reasons distinguish (a) no call form,
   (b) call form matches no registered model (name the dotted
   path), (c) inputs missing (name them). All three are golden-
   visible.
5. Fixtures per track both ways (routed + honestly-unroutable);
   golden regen reviewed per the E0303 rule (new error-level rows =
   regression).

## Acceptance

- printer_k1 `payload_ok`, arm_a6 `payload_deflection`/
  `housing_deflection` (and the fleet-wide label-kind set) route to
  their called models: each now yields a real verdict or a named
  `*_inputs_missing` deferral -- NOT "no model for label".
- The elec.si claims invoke the feldspar model in the release
  probe.
- No waiver edits in this WO (WO-113 owns burn-down); waiver
  matching still works over the new deferral shapes (stale waivers
  surface in the ship report and are LISTED, not silently dropped).
- `make check` green; census golden regenerated + diff reviewed.

## Escalation

If the lowered claim record does not carry the call text on some
path (so routing cannot see it), escalate the Rust increment to the
coordinator rather than widening scope; do not self-assign D/F
numbers.
