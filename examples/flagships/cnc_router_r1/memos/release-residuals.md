# cnc_router_r1 -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `accel` (no_model): no harness model for claim kind 'accel'
- `backlash` (no_model): no harness model for claim kind 'backlash'
- `bus_clamp` (no_model): no harness model for claim kind 'bus_clamp'
- `cost` (no_model): no harness model for claim kind 'cost'
- `crit_speed` (no_model): no harness model for claim kind 'crit_speed'
- `deck_parallel` (no_model): no harness model for claim kind 'deck_parallel'
- `dir_setup` (no_model): no harness model for claim kind 'dir_setup'
- `droop` (no_model): no harness model for claim kind 'droop'
- `fets` (no_model): no harness model for claim kind 'fets'
- `field_flat` (no_model): no harness model for claim kind 'field_flat'
- `first_mode` (no_model): no harness model for claim kind 'first_mode'
- `floor` (no_model): no harness model for claim kind 'floor'
- `gantry_moving` (no_model): no harness model for claim kind 'gantry_moving'
- `growth` (no_model): no harness model for claim kind 'growth'
- `headroom` (no_model): no harness model for claim kind 'headroom'
- `idle_floor` (no_model): no harness model for claim kind 'idle_floor'
- `inrush` (no_model): no harness model for claim kind 'inrush'
- `land_straight` (no_model): no harness model for claim kind 'land_straight'
- `pilot_conc` (no_model): no harness model for claim kind 'pilot_conc'
- `pilot_perp` (no_model): no harness model for claim kind 'pilot_perp'
- `plan_deadline` (no_model): no harness model for claim kind 'plan_deadline'
- `pullout` (no_model): no harness model for claim kind 'pullout'
- `rack` (no_model): no harness model for claim kind 'rack'
- `reserve` (no_model): no harness model for claim kind 'reserve'
- `run_cap` (no_model): no harness model for claim kind 'run_cap'
- `shoulder_twist` (no_model): no harness model for claim kind 'shoulder_twist'
- `sink` (no_model): no harness model for claim kind 'sink'
- `square_xy` (no_model): no harness model for claim kind 'square_xy'
- `stack` (no_model): no harness model for claim kind 'stack'
- `step_deadline` (no_model): no harness model for claim kind 'step_deadline'
- `step_edges` (no_model): no harness model for claim kind 'step_edges'
- `time` (no_model): no harness model for claim kind 'time'
- `tram` (no_model): no harness model for claim kind 'tram'
- `wcet` (no_model): no harness model for claim kind 'wcet'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.

- `alive` (unsupported_op): comparator 'require' defers
- `estop_relay` (unsupported_op): comparator 'require' defers
- `kill` (unsupported_op): comparator 'require' defers
- `limit_react` (unsupported_op): comparator 'require' defers
- `makeable` (unsupported_op): comparator 'require' defers
- `ot_react` (unsupported_op): comparator 'require' defers
- `spindle_sto` (unsupported_op): comparator 'require' defers
- `stop_steps` (unsupported_op): comparator 'require' defers

Retirement: the claim-form lowering increment for the named form (charter 30 sec. 1.3 WO-shaped escalation).

## Accepted -- Entity-derived bound not literal at lowering

The bound references entity/material properties whose D103 ref resolution on the reduction path is a recorded machinery residual; substituting a literal would fabricate a bound the design does not assert (D195).

- `fit` (unresolved_limit): bound 'partitions.app.size' not literal
- `screw_l10` (unresolved_limit): bound 'design_life' not literal
- `trucks_l10` (unresolved_limit): bound 'design_life' not literal

Retirement: D103 ref resolution on the reduction path.

## Accepted -- D102 temporal containment/reduction residuals

Typed temporal containments have no scalar request shape (payload-channel consumption is a recorded residual); entity-derived temporal bounds await the same D103 resolution.

- `emissions` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape
- `radiated` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape

Retirement: the recorded D102/D103 machinery residuals.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:axis_carriage.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:axis_module.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:bed_plate.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:contracts.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:contracts.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:controller.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:drives.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:frame.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:gantry_beam.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:power.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:side_plate.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:spindle.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:spoilboard.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.compute` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.buffers` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.families` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.power` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.intents` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.cnc` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.linear` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.matings` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.mounts` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.weld` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:vfd.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:z_carriage.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Other machinery-deferred obligations

Each row lists its verbatim deferral reason and detail; every one is a recorded machinery/record wall, not a design failure.

- `bearing_soak` (thermo.junction_temperature_inputs_missing): 'zones.nose' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta'); checked 

Retirement: the per-reason machinery increments named in the detail text.

## NOT ACCEPTED -- dotted window-half claim names (machinery-blocked)

A `within [lo, hi]` claim defers per window half with a dotted name (`<claim>.hi`); the waive target's trailing-segment match cannot spell a dotted claim name (probed stale both ways). Remains refusing until the spelling generalizes (WO-105 ledger escalation).

- `axial.hi` (no_model): no harness model for claim kind 'axial.hi'
- `axial.lo` (no_model): no harness model for claim kind 'axial.lo'
- `v48_window.hi` (no_model): no harness model for claim kind 'v48_window.hi'
- `v48_window.lo` (no_model): no harness model for claim kind 'v48_window.lo'

## NOT ACCEPTED -- impl/iface conformance edges (machinery-blocked)

These obligations carry real subjects but colon-containing claim names (`impl:X`) the waive target grammar cannot spell; the D213 spelling covers only `import(<pkg>)`. They remain refusing until the spelling generalizes (WO-105 ledger escalation).

- `impl:AxisFoot` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:BeamEnd` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:BedSeat` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:BoltPattern` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:CarriageDeck` (conformance_impl_bound_missing): the spec side resolved (lateral >= 20) but the impl asserts no matching bound; to discharge, either declare a 
- `impl:ClampBore` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:DriveChannel` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:EStopNode` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:LimitBank` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:NutSeat` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:RailFeed` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:RailTap` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:ShoulderSeat` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:SpindleBody` (conformance_impl_bound_missing): the spec side resolved (dissipation <= 180) but the impl asserts no matching bound; to discharge, either decla
- `impl:SpindleCmd` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:SpindleCmdIn` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:StepDirIn` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:StepDirOut` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

## NOT ACCEPTED -- trust-floored claims (memo evidence cannot meet the floor)

These claims sit in `trust: >=`-floored groups; D207 memo evidence confers community tier and can never meet a tested/certified floor, and CLI builds emit unsigned evidence. They remain refusing until a signing story lands (WO-105 ledger escalation).

- `grip` (no_model): no harness model for claim kind 'grip'
- `round` (no_model): no harness model for claim kind 'round'
- `sag` (no_model): no harness model for claim kind 'sag'
- `throat_life` (no_model): no harness model for claim kind 'throat_life'
- `throat_static` (temporal_reduction_unresolved_limit): claim form ClaimForm2 bound 'material.sigma_y / 1.8' is not a literal (an entity-derived bound needs D103 ref 
- `tir` (no_model): no harness model for claim kind 'tir'
- `twist` (no_model): no harness model for claim kind 'twist'
- `weld_static` (unresolved_limit): bound 'w.filler.sigma_allow, sf=2.0\n        # gantry accel reaction: 30 gantry at 5 through 0.4\n        # up

## NOT ACCEPTED -- fluorite flownet claims (machinery-blocked)

The coolant.fluo flownet claims (flow, balance, jet, margin, npsh,
regime, prime, slam, leaks, drain) live in top-level `require` blocks
of a flownet-only file; the D214 match scope for a structure-less
file is recorded unmatched (waivers.rs F126 queue note), so their
waivers cannot match and are not authored. They remain refusing
(WO-105 ledger escalation).

## NOT ACCEPTED -- trust-floored claims

`weld_static` (BaseFrame), `twist`/`sag` (GantryBeam),
`throat_static`/`throat_life` (SidePlate), `tir` (Spindle22, catalog
floor), `grip`/`round` (SpindleMount): each sits in a `trust: >=`
group; D207 memo evidence is community tier and cannot meet the
floor, and CLI builds emit unsigned evidence. They remain refusing
(WO-105 ledger escalation).

## NOT ACCEPTED -- dotted window halves

`axial.lo`/`axial.hi` (spindle preload window) and
`v48_window.lo`/`v48_window.hi`: the waive target grammar cannot
spell dotted claim names (WO-105 ledger escalation).
