# reaction_wheel -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `bw` (no_model): no harness model for claim kind 'bw'
- `crit_speed` (no_model): no harness model for claim kind 'crit_speed'
- `first_mode` (no_model): no harness model for claim kind 'first_mode'
- `fit_holds` (no_model): no harness model for claim kind 'fit_holds'
- `jitter` (no_model): no harness model for claim kind 'jitter'
- `life` (no_model): no harness model for claim kind 'life'
- `pm` (no_model): no harness model for claim kind 'pm'
- `torque_ripple` (no_model): no harness model for claim kind 'torque_ripple'
- `total` (no_model): no harness model for claim kind 'total'
- `wheel_iz` (no_model): no harness model for claim kind 'wheel_iz'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Entity-derived bound not literal at lowering

The bound references entity/material properties whose D103 ref resolution on the reduction path is a recorded machinery residual; substituting a literal would fabricate a bound the design does not assert (D195).

- `burst` (unresolved_limit): bound 'material.sigma_y / 1.05\n                   given omega = 12000rpm' not literal
- `grade` (unresolved_limit): bound 'iso1940(G2.5)' not literal
- `grms_ok` (unresolved_limit): bound 'material.sigma_y / 1.6' not literal
- `rim_stress` (unresolved_limit): bound 'material.sigma_y / 3.0\n        # G19: stress is monotone-increasing in omega -- the solver\n        # 
- `static_sf` (unresolved_limit): bound "material.sigma_y / 2.0\n\n        # G15: press-fit retention needs the contact{17-4PH, 4140}\n        #

Retirement: D103 ref resolution on the reduction path.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:Flywheel` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:WheelDriver` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.power` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.turned` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Other machinery-deferred obligations

Each row lists its verbatim deferral reason and detail; every one is a recorded machinery/record wall, not a design failure.

- `b10` (mech.bearing.l10_hours_inputs_missing): 'pair=preloaded_707C' is missing inputs ['c_rating', 'p_exponent', 'p_load', 'speed_rpm'] (need ('c_rating', '
- `mount_rise` (thermo.junction_temperature_inputs_missing): 'machined.shell.mount_face)\n                        - thermo.temperature(ambient' is missing inputs ['ambient
- `t_j` (thermo.junction_temperature_inputs_missing): 'br_u.fet_high.junction' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta

Retirement: the per-reason machinery increments named in the detail text.

## NOT ACCEPTED -- impl/iface conformance edges (machinery-blocked)

These obligations carry real subjects but colon-containing claim names (`impl:X`) the waive target grammar cannot spell; the D213 spelling covers only `import(<pkg>)`. They remain refusing until the spelling generalizes (WO-105 ledger escalation).

- `impl:WheelMount` (conformance_impl_bound_missing): the spec side resolved (static <= 25) but the impl asserts no matching bound; to discharge, either declare a `
- `impl:WheelSeat` (conformance_impl_bound_missing): the spec side resolved (radial <= 6) but the impl asserts no matching bound; to discharge, either declare a `r
