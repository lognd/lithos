# arm_a6 -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `housing_deflection` (no_model): no harness model for claim kind 'housing_deflection'
- `j1_travel` (no_model): no harness model for claim kind 'j1_travel'
- `j2_travel` (no_model): no harness model for claim kind 'j2_travel'
- `j3_travel` (no_model): no harness model for claim kind 'j3_travel'
- `jitter` (no_model): no harness model for claim kind 'jitter'
- `payload_deflection` (no_model): no harness model for claim kind 'payload_deflection'
- `pose_home_j2` (no_model): no harness model for claim kind 'pose_home_j2'
- `pose_load_j3` (no_model): no harness model for claim kind 'pose_load_j3'
- `pose_reach_j2` (no_model): no harness model for claim kind 'pose_reach_j2'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.

- `makeable` (unsupported_op): comparator 'require' defers

Retirement: the claim-form lowering increment for the named form (charter 30 sec. 1.3 WO-shaped escalation).

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:BasePlate` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:JointBore` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:LinkFlange` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:UpperArm` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:WristBase` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:controller.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.cnc` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.matings` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.turned` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Other machinery-deferred obligations

Each row lists its verbatim deferral reason and detail; every one is a recorded machinery/record wall, not a design failure.

- `base_bolts` (mech.bolt.joint_separation_inputs_missing): 'mill.feet' is missing inputs ['f_external', 'f_preload', 'k_bolt', 'k_clamp'] (need ('f_preload', 'f_external
- `j1_bearing` (mech.bearing.l10_hours_inputs_missing): 'pair=dgb_6006' is missing inputs ['c_rating', 'p_exponent', 'p_load', 'speed_rpm'] (need ('c_rating', 'p_load
- `j2_bearing` (mech.bearing.l10_hours_inputs_missing): 'pair=dgb_6004' is missing inputs ['c_rating', 'p_exponent', 'p_load', 'speed_rpm'] (need ('c_rating', 'p_load
- `j3_bearing` (mech.bearing.l10_hours_inputs_missing): 'pair=dgb_6002' is missing inputs ['c_rating', 'p_exponent', 'p_load', 'speed_rpm'] (need ('c_rating', 'p_load

Retirement: the per-reason machinery increments named in the detail text.

## Accepted -- impl/iface conformance edges

An interface-conformance edge (`impl:X`, or the `select:X` candidate-list kind for `impl X by select(...)`) carries no scalar window on either side -- genuinely indeterminate per D195.3, exactly like a bare import. Accepted via the D215 `impl(<Interface>)` waiver spelling, which names the INTERFACE and matches whichever realization kind (impl/extern/select) lowered its edges. Verdicts untouched (INV-2/INV-13).

Retirement: a realized impl or, for JointReduction, a resolved `select(...)` choice; the waiver then goes stale and is removed.

- `impl:BaseFoot` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:JointBore` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:JointMotorMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:LinkFlange` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `select:JointReduction` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
