# WO-80: rung-5 model= pinning, wired end to end

Status: todo (SERIALIZE: dispatch after the in-flight translate.py
wiring agent integrates -- both touch the same dispatch table)
Depends: WO-76's escalation record (the audit: parser lexes ModelKw
but never populates Claim.model_pin; gear_reducer/machine corpus
members' `model=` text is swallowed into the comparison RHS;
nothing in discharge/translate/registry honors a pin).
Language: Rust (`regolith-syntax` claim attribute parse ->
`model_pin`; `regolith-lower` plumb) + Python (registry honoring).
NO schema bump (the field already exists in the schema).
Spec: regolith/12 sec. 2 rung 5 (NORMATIVE: "a forced model that
cannot close the margin yields indeterminate, not a pass"),
hematite/04 model= row, WO-76's ledger.

## Deliverables

1. Parser: `model=<ident>` in a claim's trailing attributes ->
   populated `model_pin` (CST/AST/formatter; negative fixture for
   an unknown trailing attr stays whatever it is today).
2. Lowering: model_pin into the obligation (field exists; verify
   keying implications -- a pin changes the obligation content, so
   re-keying is CORRECT per INV-2; account for the two corpus
   members' golden churn).
3. Honoring: `ModelRegistry.select`/translate honors a pin -- skip
   cost order, exact-id lookup, no-match => honest indeterminate
   (`model_pin_unmatched`), NEVER a fallback to another model.
4. Tests: gear_reducer/machine corpus members now carry populated
   pins (goldens regenerated + accounted); a pin-to-wrong-model
   fixture yields indeterminate; WO-76's lug_bracket note updated
   (the exclusivity workaround stays valid, now also pinned for
   real).
5. Docs: regolith/12 cross-note if any wording needs truthing; WO
   ledger.

## Acceptance: pin honored end-to-end via compiler.check + discharge;
"cannot forge a pass" fixture; make install + make check green;
Status flipped.
