# espresso_machine -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `adc_floor` (no_model): no harness model for claim kind 'adc_floor'
- `cost` (no_model): no harness model for claim kind 'cost'
- `gasket_b` (no_model): no harness model for claim kind 'gasket_b'
- `gasket_s` (no_model): no harness model for claim kind 'gasket_s'
- `group_sag` (no_model): no harness model for claim kind 'group_sag'
- `headroom` (no_model): no harness model for claim kind 'headroom'
- `heat_bank` (no_model): no harness model for claim kind 'heat_bank'
- `kick` (no_model): no harness model for claim kind 'kick'
- `mains_fit` (no_model): no harness model for claim kind 'mains_fit'
- `recover` (no_model): no harness model for claim kind 'recover'
- `split` (no_model): no harness model for claim kind 'split'
- `standby_floor` (no_model): no harness model for claim kind 'standby_floor'
- `usable` (no_model): no harness model for claim kind 'usable'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.

- `cut` (unsupported_op): comparator 'require' defers
- `fill_bounded` (unsupported_op): comparator 'require' defers
- `makeable` (unsupported_op): comparator 'require' defers
- `open_on_brew` (unsupported_op): comparator 'require' defers
- `recover` (unsupported_op): comparator 'require' defers
- `vent_on_stop` (unsupported_op): comparator 'require' defers

Retirement: the claim-form lowering increment for the named form (charter 30 sec. 1.3 WO-shaped escalation).

## Accepted -- Entity-derived bound not literal at lowering

The bound references entity/material properties whose D103 ref resolution on the reduction path is a recorded machinery residual; substituting a literal would fabricate a bound the design does not assert (D195).

- `life` (unresolved_limit): bound 'design_life, scatter_factor=4' not literal
- `static` (unresolved_limit): bound 'w.filler.sigma_allow, sf=2.5' not literal

Retirement: D103 ref resolution on the reduction path.

## Accepted -- D102 temporal containment/reduction residuals

Typed temporal containments have no scalar request shape (payload-channel consumption is a recorded residual); entity-derived temporal bounds await the same D103 resolution.

- `crown` (temporal_reduction_unresolved_limit): claim form ClaimForm2 bound 'material.sigma_y(T_local) / 2.0' is not a literal (an entity-derived bound needs 

Retirement: the recorded D102/D103 machinery residuals.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:brew_boiler.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:contracts.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:control_board.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:fittings.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:frame_panels.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:group_head.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:reservoir.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.intents` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.cnc` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.matings` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.molding` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.mounts` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.seals` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.sheet` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.weld` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:steam_boiler.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Other machinery-deferred obligations

Each row lists its verbatim deferral reason and detail; every one is a recorded machinery/record wall, not a design failure.

- `surface` (thermo.junction_temperature_inputs_missing): 'cut.blank' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta'); checked c

Retirement: the per-reason machinery increments named in the detail text.

## Accepted -- Rule-pack rows deferred at this tier

The named dfm/drc/erc rules carry no engine input at RELEASE (realized-fact-gated rule surface); the rule-pack waive target spelling is the designed acceptance channel for them.

- `drc(jlc_2l.annular_ring)` (no_model): no harness model for claim kind 'drc(jlc_2l.annular_ring)'
- `drc(jlc_2l.bus_length_match)` (no_model): no harness model for claim kind 'drc(jlc_2l.bus_length_match)'
- `drc(jlc_2l.drill_size)` (unresolved_limit): bound 'capability.min_drill' not literal
- `drc(jlc_2l.trace_width)` (unresolved_limit): bound 'capability.min_trace' not literal

Retirement: the realized-fact feeds the rules await.

## NOT ACCEPTED -- dotted window-half claim names (machinery-blocked)

A `within [lo, hi]` claim defers per window half with a dotted name (`<claim>.hi`); the waive target's trailing-segment match cannot spell a dotted claim name (probed stale both ways). Remains refusing until the spelling generalizes (WO-105 ledger escalation).

- `brew_hold.hi` (thermo.junction_temperature_inputs_missing): 'regulate_brew.plant' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta');
- `brew_hold.lo` (thermo.junction_temperature_inputs_missing): 'regulate_brew.plant' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta');
- `steam_hold.hi` (no_model): no harness model for claim kind 'steam_hold.hi'
- `steam_hold.lo` (no_model): no harness model for claim kind 'steam_hold.lo'

## NOT ACCEPTED -- impl/iface conformance edges (machinery-blocked)

These obligations carry real subjects but colon-containing claim names (`impl:X`) the waive target grammar cannot spell; the D213 spelling covers only `import(<pkg>)`. They remain refusing until the spelling generalizes (WO-105 ledger escalation).

- `impl:BoltPattern` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:FittingPort` (conformance_impl_bound_missing): the spec side resolved (leak <= 0.02) but the impl asserts no matching bound; to discharge, either declare a `
- `impl:HeaterSeat` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:HolePattern` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:IsoMount` (conformance_impl_bound_missing): the spec side resolved (static <= 25) but the impl asserts no matching bound; to discharge, either declare a `
- `impl:LevelWell` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:MountPattern` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:SealFace` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:ThermoWell` (conformance_impl_bound_missing): the spec side resolved (thermo.lag <= 2) but the impl asserts no matching bound; to discharge, either declare 

## NOT ACCEPTED -- trust-floored claims (memo evidence cannot meet the floor)

These claims sit in `trust: >=`-floored groups; D207 memo evidence confers community tier and can never meet a tested/certified floor, and CLI builds emit unsigned evidence. They remain refusing until a signing story lands (WO-105 ledger escalation).

- `hoop` (temporal_reduction_unresolved_limit): claim form ClaimForm2 bound "material.sigma_y(T_local) / 1.8\n        # boundary.brew_pressure's 14 bar ceilin
- `hoop` (temporal_reduction_unresolved_limit): claim form ClaimForm2 bound 'material.sigma_y(T_local) / 1.8\n        # T_local worst corner here is saturatio

## NOT ACCEPTED -- fluorite flownet claims (machinery-blocked)

The brew_water/steam_service/thermosiphon flownet claims (pressure,
flow, supply_dp, npsh, vented, hammer, ramp, fill_flow, swell, leaks,
rate, band, single_fault, no_vac, stall, regime) live in top-level
`require` blocks of flownet-only files; the D214 match scope for a
structure-less file is recorded unmatched (waivers.rs F126 queue
note), so their waivers cannot match and are not authored. They
remain refusing (WO-105 ledger escalation).
