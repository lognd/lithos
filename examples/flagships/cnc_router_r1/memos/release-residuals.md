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

## Accepted -- dotted window-half claims (D215)

`axial.lo`/`axial.hi` (axis_module stiffness window) and `v48_window.lo`/`v48_window.hi` (power rail window): a `within [lo, hi]` claim defers per half; the D215 dotted-target spelling names each half. No model for either window kind (F126.1).

Retirement: register the window kinds; the waivers then go stale.

## Accepted -- impl/iface conformance edges

An interface-conformance edge carries no scalar window on either side, or (CarriageDeck/SpindleBody's impl-bound-missing rows) a resolved spec-side bound with no real impl-side narrowing to author -- a mirrored bound would discharge vacuously, the INV-13/26 violation D195 forbids. Accepted via the D215 `impl(<Interface>)` spelling: AxisFoot, BeamEnd, BedSeat, BoltPattern, CarriageDeck, ClampBore, DriveChannel, EStopNode, LimitBank, NutSeat, RailFeed, RailTap, ShoulderSeat, SpindleBody, SpindleCmd, SpindleCmdIn, StepDirIn, StepDirOut. Verdicts untouched (INV-2/INV-13).

Retirement: real impl-side narrowings; each waiver then goes stale.

## Accepted -- floored claims (floors author-revised per D216)

The five floored groups (frame Structural, side_plate Structural, gantry_beam Stiffness, z_carriage Clamp: `>= certified`; spindle Runout: `>= catalog`) were aspirational: their claims lower to label kinds with no registered model (twist, sag, grip, round, tir, throat_life) or carry entity-derived bounds behind the recorded D103 residual (weld_static, throat_static), and the catalog evidence channel is the F124 queued residual (tir). Per D216(2) the author revised each floor in its design source with a recorded rationale; the memo-backed deviations then accept at tier honestly.

Retirement: restore each floor when its channel exists (F126.1 routing, D103 resolution, F124 catalog wiring, plus signed evidence).

## Accepted -- machine first_mode (pinned model unmatched)

`first_mode` (machine.hema) pins `model=fea_modal`, which lives in the OPTIONAL feldspar pack; the release environment does not install it (WO-27 uninstalled posture), so the pin is honestly unmatched.

Retirement: install the feldspar pack; the claim discharges at tier.

## Accepted -- fluorite flownet claims (D215)

The ten FloodCoolant claims (flow, balance, jet, margin, npsh, regime, prime, slam, leaks, drain) live in top-level require bodies of the flownet file -- harvested, matched waive positions per D215(c); one require body harvests for the whole file. Each waived in place with its wall-citing basis.

Retirement: the per-reason machinery increments (kind models, claim-form lowering, dp record chain).
