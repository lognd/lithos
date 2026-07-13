# small_office -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.


Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.


Retirement: the claim-form lowering increment for the named form (charter 30 sec. 1.3 WO-shaped escalation).

## Accepted -- Entity-derived bound not literal at lowering

The bound references entity/material properties whose D103 ref resolution on the reduction path is a recorded machinery residual; substituting a literal would fabricate a bound the design does not assert (D195).

- `feeder` (unresolved_limit): bound 'HeatingLoop.pump.electrical_demand\n                     + HeatingLoop.boiler.electrical_demand, sf=1.2

Retirement: D103 ref resolution on the reduction path.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:hydronics.fluo` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.civil` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.fluorite` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.intents` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Calcite frame-chain walls

Per-claim frame walls (WO-74 single-bay modelling, WO-85/D194 pressure-only members, WO-65 registry-section coverage): the demand or section data the model needs is not in the modelled scope, and fabricating it is forbidden (D195).

- `drift` (no_frame_model): civil.story_drift has no closed-form harness model yet (covered forms: civil.utilization/mech.deflection (WO-4
- `strength[Br1]` (frame_section_unresolved): section 'hss127x127x8' names no std.civil section record
- `strength[C_A]` (frame_section_unresolved): section 'w250x73' names no std.civil section record
- `strength[C_B]` (frame_section_unresolved): section 'w250x73' names no std.civil section record
- `strength[Deck2]` (frame_section_incomplete): section 'comp_deck_140mm''s record carries no area_mm2/i_mm4 field this resolver reduces (a per-metre strip se
- `strength[DeckR]` (frame_section_unresolved): section 'steel_deck_38mm' names no std.civil section record

Retirement: the named frame-model/record increments.

## Accepted -- Other machinery-deferred obligations

Each row lists its verbatim deferral reason and detail; every one is a recorded machinery/record wall, not a design failure.


Retirement: the per-reason machinery increments named in the detail text.

## Accepted -- impl/iface conformance edges

An interface-conformance edge (`impl:Feeder`) carries no scalar window on either side -- genuinely indeterminate per D195.3, exactly like a bare import. Accepted via the D215 `impl(<Interface>)` waiver spelling. Verdicts untouched (INV-2/INV-13).

- `impl:Feeder` (conformance_windows_unresolved)

Retirement: a real impl-side narrowing or realized-fact discharge; the waiver then goes stale and is removed.

## Accepted -- fluorite flownet claims

`balance`, `fill`, `margin`, `npsh`, `regime` (hydronics.fluo) live in
the top-level `require Hydronics:` body of a flownet-only file -- now a
harvested waive position per D215 (flownet-file claims join the D214
harvest/match scope). Each is waived in place with its wall-citing
basis (dp inputs missing on the riser Pipe records; no model for the
flow_imbalance/npsh_margin kinds; the reynolds window and settles()
forms outside the scalar lowering surface). The import(std.fluorite)
waive moved from the flownet body (not a harvest position) into the
same require body.

Retirement: the per-reason machinery increments (record chain closure,
kind models, claim-form lowering).

## Note on the Structure group's `trust: >= tested` floor

The frame-claim acceptances above ride the RECORDED F124.1 gap: a
calcite require-group `trust:` directive does not lower into the
member claims' own floor field yet, so the gate binds no floor here.
When that wiring lands, these community-tier acceptances will fail
the floor and this memo's deviations must be re-evaluated (tested
evidence or floor re-posture) -- recorded, not hidden.
