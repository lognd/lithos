# dune_buggy -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `accel` (no_model): no harness model for claim kind 'accel'
- `ackermann` (no_model): no harness model for claim kind 'ackermann'
- `adc_budget` (no_model): no harness model for claim kind 'adc_budget'
- `ampacity` (no_model): no harness model for claim kind 'ampacity'
- `angle_ok` (no_model): no harness model for claim kind 'angle_ok'
- `arm_life` (no_model): no harness model for claim kind 'arm_life'
- `axle_life` (no_model): no harness model for claim kind 'axle_life'
- `balance` (no_model): no harness model for claim kind 'balance'
- `bead_retention` (no_model): no harness model for claim kind 'bead_retention'
- `bending` (no_model): no harness model for claim kind 'bending'
- `bridge` (no_model): no harness model for claim kind 'bridge'
- `bridge_temp` (no_model): no harness model for claim kind 'bridge_temp'
- `buckle` (no_model): no harness model for claim kind 'buckle'
- `cap_bolts` (no_model): no harness model for claim kind 'cap_bolts'
- `capacity` (no_model): no harness model for claim kind 'capacity'
- `cg_height` (no_model): no harness model for claim kind 'cg_height'
- `clamp` (no_model): no harness model for claim kind 'clamp'
- `clearance` (no_model): no harness model for claim kind 'clearance'
- `collapse` (no_model): no harness model for claim kind 'collapse'
- `coning` (no_model): no harness model for claim kind 'coning'
- `crank_life` (no_model): no harness model for claim kind 'crank_life'
- `crit_speed` (no_model): no harness model for claim kind 'crit_speed'
- `crush_space` (no_model): no harness model for claim kind 'crush_space'
- `decel` (no_model): no harness model for claim kind 'decel'
- `deflection` (no_model): no harness model for claim kind 'deflection'
- `derated` (no_model): no harness model for claim kind 'derated'
- `elongation_life` (no_model): no harness model for claim kind 'elongation_life'
- `face_stress` (no_model): no harness model for claim kind 'face_stress'
- `fade_decel` (no_model): no harness model for claim kind 'fade_decel'
- `film` (no_model): no harness model for claim kind 'film'
- `first_mode` (no_model): no harness model for claim kind 'first_mode'
- `floor_mode` (no_model): no harness model for claim kind 'floor_mode'
- `flotation` (no_model): no harness model for claim kind 'flotation'
- `flow` (no_model): no harness model for claim kind 'flow'
- `fuse_coord` (no_model): no harness model for claim kind 'fuse_coord'
- `gradeability` (no_model): no harness model for claim kind 'gradeability'
- `grip` (no_model): no harness model for claim kind 'grip'
- `hanger_life` (no_model): no harness model for claim kind 'hanger_life'
- `idle` (no_model): no harness model for claim kind 'idle'
- `impact` (no_model): no harness model for claim kind 'impact'
- `inj_clamp` (no_model): no harness model for claim kind 'inj_clamp'
- `insertion` (no_model): no harness model for claim kind 'insertion'
- `isolate` (no_model): no harness model for claim kind 'isolate'
- `kill_confirm` (no_model): no harness model for claim kind 'kill_confirm'
- `lambda_stable` (no_model): no harness model for claim kind 'lambda_stable'
- `latency` (no_model): no harness model for claim kind 'latency'
- `locate` (no_model): no harness model for claim kind 'locate'
- `mass` (no_model): no harness model for claim kind 'mass'
- `mount_stiff` (no_model): no harness model for claim kind 'mount_stiff'
- `no_bind` (no_model): no harness model for claim kind 'no_bind'
- `no_boil` (no_model): no harness model for claim kind 'no_boil'
- `no_drum` (no_model): no harness model for claim kind 'no_drum'
- `no_fade` (no_model): no harness model for claim kind 'no_fade'
- `no_float` (no_model): no harness model for claim kind 'no_float'
- `no_slip` (no_model): no harness model for claim kind 'no_slip'
- `no_surge` (no_model): no harness model for claim kind 'no_surge'
- `ntc_acc` (no_model): no harness model for claim kind 'ntc_acc'
- `oil_latency` (no_model): no harness model for claim kind 'oil_latency'
- `oilp_error` (no_model): no harness model for claim kind 'oilp_error'
- `oilp_noise` (no_model): no harness model for claim kind 'oilp_noise'
- `pad_life` (no_model): no harness model for claim kind 'pad_life'
- `pilot_fit` (no_model): no harness model for claim kind 'pilot_fit'
- `pitting` (no_model): no harness model for claim kind 'pitting'
- `proof_crush` (no_model): no harness model for claim kind 'proof_crush'
- `proof_torsion` (no_model): no harness model for claim kind 'proof_torsion'
- `pull_through` (no_model): no harness model for claim kind 'pull_through'
- `pump_drop` (no_model): no harness model for claim kind 'pump_drop'
- `reserve` (no_model): no harness model for claim kind 'reserve'
- `residual` (no_model): no harness model for claim kind 'residual'
- `rod_buckle` (no_model): no harness model for claim kind 'rod_buckle'
- `sag_ride` (no_model): no harness model for claim kind 'sag_ride'
- `seat_distortion` (no_model): no harness model for claim kind 'seat_distortion'
- `spark_energy` (no_model): no harness model for claim kind 'spark_energy'
- `spindle_life` (no_model): no harness model for claim kind 'spindle_life'
- `spline_fatigue` (no_model): no harness model for claim kind 'spline_fatigue'
- `spline_shear` (no_model): no harness model for claim kind 'spline_shear'
- `springback_ok` (no_model): no harness model for claim kind 'springback_ok'
- `ssf` (no_model): no harness model for claim kind 'ssf'
- `static` (no_model): no harness model for claim kind 'static'
- `strap_life` (no_model): no harness model for claim kind 'strap_life'
- `surge` (no_model): no harness model for claim kind 'surge'
- `thermal_ok` (no_model): no harness model for claim kind 'thermal_ok'
- `thread` (no_model): no harness model for claim kind 'thread'
- `top_speed` (no_model): no harness model for claim kind 'top_speed'
- `torsion` (no_model): no harness model for claim kind 'torsion'
- `tray_buckle` (no_model): no harness model for claim kind 'tray_buckle'
- `vib_ok` (no_model): no harness model for claim kind 'vib_ok'
- `vr_timing` (no_model): no harness model for claim kind 'vr_timing'
- `weld_life` (no_model): no harness model for claim kind 'weld_life'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.

- `boots` (unsupported_op): comparator 'require' defers
- `bump_steer` (unsupported_op): comparator 'require' defers
- `capacity` (unsupported_op): comparator 'require' defers
- `dust` (unsupported_op): comparator 'require' defers
- `fail_safe` (unsupported_op): comparator 'require' defers
- `force_band` (unsupported_op): comparator 'require' defers
- `restrained` (unsupported_op): comparator 'require' defers
- `rollover_seal` (unsupported_op): comparator 'require' defers
- `sound_ok` (unsupported_op): comparator 'require' defers
- `survivable` (unsupported_op): comparator 'require' defers

Retirement: the claim-form lowering increment for the named form (charter 30 sec. 1.3 WO-shaped escalation).

## Accepted -- Entity-derived bound not literal at lowering

The bound references entity/material properties whose D103 ref resolution on the reduction path is a recorded machinery residual; substituting a literal would fabricate a bound the design does not assert (D195).

- `arm` (unresolved_limit): bound 'material.sigma_y / 2.0\n                 given force = boundary.pedal_panic' not literal
- `arm_stress` (unresolved_limit): bound 'material.sigma_y / 1.8\n        # Jump landing: quasi-static envelope case, monotone in load\n        #
- `axle_static` (unresolved_limit): bound 'material.sigma_y / 1.6' not literal
- `baffle_weld` (unresolved_limit): bound 'material.sigma_y / 3.0' not literal
- `bearing_seat` (unresolved_limit): bound 'material.sigma_y / 2.0' not literal
- `bore` (unresolved_limit): bound 'material.sigma_y / 2.0\n                  given p_line = 80bar' not literal
- `brake_torque` (unresolved_limit): bound 'material.sigma_y / 1.8\n                          given torque = brake_peak(1400*m)' not literal
- `ear_stress` (unresolved_limit): bound 'material.sigma_y / 2.0' not literal
- `growth` (unresolved_limit): bound 'material.sigma_y(T_env.hi) / 1.5\n                    given dT = T_gas.hi - T_env.lo' not literal
- `landing` (unresolved_limit): bound 'material.sigma_y / 1.2\n                     given load = landing_envelope(2_drop)' not literal
- `no_cavitate` (unresolved_limit): bound 'fluids.vapor_pressure(oil, T_oil) + 0.5bar' not literal
- `pin_fillet` (unresolved_limit): bound 'material.sigma_y / 1.8' not literal
- `proof` (unresolved_limit): bound 'material.sigma_y / 1.5\n                   given p = 30000' not literal
- `rail_stress` (unresolved_limit): bound 'material.sigma_y / 1.5\n                         given load = boundary.occupant.hi\n                   
- `rail_stress` (unresolved_limit): bound 'material.sigma_y / 2.0\n\n        # G4/LOWER: torsional stiffness is a LOWER-bound claim -- any\n      
- `sealing` (unresolved_limit): bound 'ip67' not literal
- `shear` (unresolved_limit): bound 'material.tau_allow(condition=core) / 1.4' not literal
- `shear_ok` (unresolved_limit): bound 'material.tau_allow / 1.25\n                      given x = 0.18' not literal
- `sheave_burst` (unresolved_limit): bound 'material.sigma_y / 1.1\n                          given omega_in = 11000rpm' not literal
- `shell` (unresolved_limit): bound 'material.sigma_y / 2.5\n                   given p = hydrostatic_envelope(boundary.accel,\n            
- `tooth` (unresolved_limit): bound 'material.sigma_y / 1.6\n                   given torque = wheel_jam(60*m)' not literal

Retirement: D103 ref resolution on the reduction path.

## Accepted -- D102 temporal containment/reduction residuals

Typed temporal containments have no scalar request shape (payload-channel consumption is a recorded residual); entity-derived temporal bounds await the same D103 resolution.

- `dump_ok` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape
- `landing` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape

Retirement: the recorded D102/D103 machinery residuals.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:BodyPanels` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:BrakeCircuits` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:BrakeDisc` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:Coilover` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:Crankshaft` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:CvtPrimary` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:CylinderHead` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:DashUnit` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:EfiEcu` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:EngineCooling` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:Exhaust` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:FrontCorner` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:FuelFeed` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:FuelTank` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:Halfshaft` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:PedalBox` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:PowerSystem` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:RearHub` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:ReductionBox` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:RollCage` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:SeatFrame` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:SpaceFrame` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:SteeringGeometry` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:TrailingArm` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:Wheel` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.digital` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.power` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.sense` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.cast` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.forged` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.formed` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.gear` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.joining` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.sheet` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.spring` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.tube` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.turned` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Other machinery-deferred obligations

Each row lists its verbatim deferral reason and detail; every one is a recorded machinery/record wall, not a design failure.

- `carcass` (thermo.junction_temperature_inputs_missing): 'tire.shoulder' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta'); check
- `face_temp` (thermo.junction_temperature_inputs_missing): 'turned.fixed_sheave.face' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_the
- `fet_t` (thermo.junction_temperature_inputs_missing): 'drv_i.fet.junction' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta'); 
- `hat_soak` (thermo.junction_temperature_inputs_missing): 'hat.bearing_side' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta'); ch
- `lcd_temp` (thermo.junction_temperature_inputs_missing): 'display.panel' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta'); check
- `life` (mech.bearing.l10_hours_inputs_missing): 'pair=tapered_32005' is missing inputs ['c_rating', 'p_exponent', 'p_load', 'speed_rpm'] (need ('c_rating', 'p
- `oil_temp` (thermo.junction_temperature_inputs_missing): 'sump_oil' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta'); checked ca
- `restriction` (fluids.dp_inputs_missing): 'inlet -> engine_side' is missing inputs ['density_kgm3', 'diameter_m', 'friction_factor', 'length_m', 'veloci
- `soak` (thermo.junction_temperature_inputs_missing): 'oil' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta'); checked call kw
- `tank_standoff` (thermo.junction_temperature_inputs_missing): 'FuelTank.tank.shell' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta');

Retirement: the per-reason machinery increments named in the detail text.

## NOT ACCEPTED -- dotted window-half claim names (machinery-blocked)

A `within [lo, hi]` claim defers per window half with a dotted name (`<claim>.hi`); the waive target's trailing-segment match cannot spell a dotted claim name (probed stale both ways). Remains refusing until the spelling generalizes (WO-105 ledger escalation).

- `bias_range.hi` (no_model): no harness model for claim kind 'bias_range.hi'
- `bias_range.lo` (no_model): no harness model for claim kind 'bias_range.lo'
- `camber_band.hi` (no_model): no harness model for claim kind 'camber_band.hi'
- `camber_band.lo` (no_model): no harness model for claim kind 'camber_band.lo'
- `flat_ratio.hi` (no_model): no harness model for claim kind 'flat_ratio.hi'
- `flat_ratio.lo` (no_model): no harness model for claim kind 'flat_ratio.lo'
- `lash.hi` (no_model): no harness model for claim kind 'lash.hi'
- `lash.lo` (no_model): no harness model for claim kind 'lash.lo'
- `pickup_true.hi` (no_model): no harness model for claim kind 'pickup_true.hi'
- `pickup_true.lo` (no_model): no harness model for claim kind 'pickup_true.lo'
- `rate.hi` (no_model): no harness model for claim kind 'rate.hi'
- `rate.lo` (no_model): no harness model for claim kind 'rate.lo'
- `ride_f.hi` (no_model): no harness model for claim kind 'ride_f.hi'
- `ride_f.lo` (no_model): no harness model for claim kind 'ride_f.lo'
- `static_camber.hi` (no_model): no harness model for claim kind 'static_camber.hi'
- `static_camber.lo` (no_model): no harness model for claim kind 'static_camber.lo'

## NOT ACCEPTED -- trust-floored claims (memo evidence cannot meet the floor)

These claims sit in `trust: >=`-floored groups; D207 memo evidence confers community tier and can never meet a tested/certified floor, and CLI builds emit unsigned evidence. They remain refusing until a signing story lands (WO-105 ledger escalation).

- `lap_anchor` (unresolved_limit): bound 'material.sigma_u / 1.0\n                        given load = 13300        # rulebook proof pull' not li
- `shoulder_anchor` (unresolved_limit): bound 'material.sigma_u / 1.0\n                             given load = 13300' not literal
- `tab_tearout` (no_model): no harness model for claim kind 'tab_tearout'

## NOT ACCEPTED -- unlocated claims (tooling could not map the obligation to a source anchor)

Listed for the census; revisit by hand.

- `toe` (non_scalar_claim): claim form ClaimForm7 is not a scalar comparison

## NOT ACCEPTED -- fluorite flownet claims (machinery-blocked)

The `cooling.fluo` flownet claims (`flow`, `npsh`, `stat_snap`) live in
top-level `require` blocks of a flownet-only file with no calcite/mech
`structure`. The D214 waiver-harvest match scope for a structure-less
flownet file is a recorded unmatched position (waivers.rs F126 queue
note), so a `waive` on them cannot match and is not authored -- a
`waive` there was probed stale (E0701) and removed. They remain
refusing (WO-105 ledger escalation). NOTE: `flow` ALSO names a real,
harvestable hema claim in `engine_top_end.hema` (Breathing group),
which IS accepted above; only the flownet triad is unwaivable.
