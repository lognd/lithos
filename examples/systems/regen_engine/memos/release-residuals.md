# regen_engine -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `abort_fast` (no_model): no harness model for claim kind 'abort_fast'
- `coil_ok` (no_model): no harness model for claim kind 'coil_ok'
- `cstar` (no_model): no harness model for claim kind 'cstar'
- `distribution` (no_model): no harness model for claim kind 'distribution'
- `isp` (no_model): no harness model for claim kind 'isp'
- `life` (no_model): no harness model for claim kind 'life'
- `no_spike` (no_model): no harness model for claim kind 'no_spike'
- `sense` (no_model): no harness model for claim kind 'sense'
- `start_ok` (no_model): no harness model for claim kind 'start_ok'
- `starts` (no_model): no harness model for claim kind 'starts'
- `thrust` (no_model): no harness model for claim kind 'thrust'
- `wall_hot` (no_model): no harness model for claim kind 'wall_hot'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.

- `lead` (unsupported_op): comparator 'require' defers
- `mode_sep` (unsupported_op): comparator 'require' defers
- `rated` (unsupported_op): comparator 'require' defers

Retirement: the claim-form lowering increment for the named form (charter 30 sec. 1.3 WO-shaped escalation).

## Accepted -- Entity-derived bound not literal at lowering

The bound references entity/material properties whose D103 ref resolution on the reduction path is a recorded machinery residual; substituting a literal would fabricate a bound the design does not assert (D195).

- `creep` (unresolved_limit): bound 'design_life' not literal
- `proof_stress` (unresolved_limit): bound 'material.sigma_y(T_ambient) / 1.1\n                          given pc = 33bar, coolant = flowing' not l
- `throat_stress` (unresolved_limit): bound 'material.sigma_y(T_local) / 1.4' not literal

Retirement: D103 ref resolution on the reduction path.

## Accepted -- D102 temporal containment/reduction residuals

Typed temporal containments have no scalar request shape (payload-channel consumption is a recorded residual); entity-derived temporal bounds await the same D103 resolution.

- `chill_ok` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape

Retirement: the recorded D102/D103 machinery residuals.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:EngineController` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:FuelFeedTube` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:InjectorHead` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:Liner` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.power` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.sense` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.cnc` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Other machinery-deferred obligations

Each row lists its verbatim deferral reason and detail; every one is a recorded machinery/record wall, not a design failure.

- `fet_t` (thermo.junction_temperature_inputs_missing, WO113-F3): the thermal inputs are sourceable but the cuprite claim lowering drops both inline kwargs and claim-suffix givens (verified live on reaction_wheel's twin claim) -- a Class E lowering gap, not a data gap
- `stiffness_fuel` (fluids.dp_inputs_missing): 'fuel_path) / thermo.pressure(chamber' is missing inputs ['density_kgm3', 'diameter_m', 'friction_factor', 'le

Retirement: the per-reason machinery increments named in the detail text.

## NOT ACCEPTED -- unlocated claims (tooling could not map the obligation to a source anchor)

Listed for the census; revisit by hand.

- `wall_T` (non_scalar_claim): claim form ClaimForm7 is not a scalar comparison

## WO-113 classification note (D224 campaign)

Surveyed for Class D (inputs-missing-with-model-existing) enrichment:
this project has NO honestly-declarable Class D claim. Every residual
is machinery: the prop/acoustics/fatigue call paths are Class C model
growth (feldspar/lithos), the expression-form claims (`fluids.dp(x) /
thermo.pressure(y)`, `stays_within`, timing forms) are Class E
lowering surface, `material.sigma_y(...)` needs the property-curve
record family (Class C/E), and `fet_t` is the WO113-F3 cuprite
kwarg/given threading gap. regen_engine's zero-discharge status is
escalated as WO113-F4: it cannot be flipped by data authoring alone.
