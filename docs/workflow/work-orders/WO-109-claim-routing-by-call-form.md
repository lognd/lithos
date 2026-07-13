# WO-109 -- Claim routing by call form + probe plugin loading (Class B)

Status: done
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

## Close-out ledger (2026-07-13, wo109-claim-routing)

No Rust escalation needed: the lowered record carries the call text
on every path audited (`form.lhs` for single-line claims, `form.rhs`
for the `op="require"` wrapped shape).

Landed:

1. Routing (deliverable 1): non-frame `mech.deflection(...)` ->
   `mech.beam.cantilever_deflection` (both the require-op and
   comparator-lhs shapes; `beam_bending.INPUTS` exported for the
   named deferral); bare `mfg.unit_cost(...)` -> `mfg.cost` (honest
   `cost_subject`-missing deferral); the generic fallback keys the
   DischargeRequest by a whole dotted-call LHS instead of the label
   (so ANY call-form claim routes by path; a registered kind
   discharges, an unregistered one defers naming the path).
2. Track coverage (deliverable 2): the router is track-agnostic
   (one serialized obligation shape). Routes that light up
   fleet-wide: printer_k1 `payload_ok`, arm_a6 `payload_deflection`
   x2 + `housing_deflection`, gantry_carriage/sheet_bracket `sag`-
   family (6 corpus rows) -> cantilever inputs-missing (named);
   16 `cost` rows -> `mfg.cost_inputs_missing`; 12 `unsupported_op`
   + label-kind rows (crit_speed/first_mode/npsh/headroom/wcet/...)
   -> `unmatched_call_path` naming the dotted path; label kinds in
   goldens replaced by real call paths (elec.power, fluids.npsh_
   margin, info.wcet, mech.fatigue.damage, ...).
3. Probe plugin loading (deliverable 3): the divergence was NOT a
   code path -- CLI builds and the probe share `default_registry()`
   -- but feldspar's editable install being a manual step no target
   reproduced (any `uv sync` evicts it). `make feldspar-link`
   (kicad-link's degrade-gracefully precedent) installs the sibling
   checkout idempotently; `health`/`health-fleet` depend on it.
   With it, mainboard_mx discharges 3 elec.si claims and
   riscv_hart_rv1 3 more (census 0->3 / 1->4); the remaining
   feldspar-basis waives are PINNED FEA models (fea_modal,
   fea_static_stress, gear contact) -- Class C model gaps
   (WO-110/111), not loading.
4. Reason hygiene (deliverable 4): (a) `no_model` + "label-only
   claim: no model call form"; (b) `unmatched_call_path` naming the
   dotted path AND the label (both at translate time for wrapped
   predicates and at discharge time for routed-but-unregistered
   kinds); (c) `<kind>_inputs_missing` naming the missing inputs.
   All three golden-visible (deferral corpus).
5. Fixtures (deliverable 5): `wo109_cantilever_deflection_fixture.
   hema` covers routed-and-discharged, routed-inputs-missing,
   unmatched-call-path, label-only, and bare-cost; existing
   per-track call-form suites (wo94 fluo, wo95 cupr, SI cupr,
   frame calx) exercise the same seam. Goldens regenerated via
   REGOLITH_UPDATE_GOLDEN=1 (deferral corpus 13 files + fleet
   census); no error-level rows added.

Verdict math untouched (D220.1): every change is deferral-reason
reclassification or a real model invocation; release_ok unchanged
fleet-wide; waivers keep matching by claim name (mainboard's 39
stay `matched`, 0 stale, 0 refusals).

Findings for the coordinator (placeholder labels, no self-assigned
numbers):

- WO109-F1: the fleet census golden now ENCODES the feldspar-loaded
  probe (mainboard 3 / riscv 4 discharged). A checkout without the
  sibling ../feldspar will mismatch the census on a full
  health-fleet run (feldspar-link degrades to a note by design).
  If CI runs health-fleet without the sibling checkout, it needs
  the WO-27 CI-job posture (install the pack) or a documented
  exemption.
- WO109-F2: `makeable: manufacturable(<process>)` claims stay on
  `unsupported_op` (bare undotted predicate, deliberately excluded
  from dotted-call routing) -- the 40-row manufacturability
  channel is WO-110's Class C deliverable, confirmed untouched.
- WO109-F3: waivers whose claims now DISCHARGE (mainboard refclk
  x3, riscv x3) stay `matched` shadowing debt per D224.2 --
  WO-113's same-change burn-down rule owns deleting them; listed
  here so they are not silently forgotten.
