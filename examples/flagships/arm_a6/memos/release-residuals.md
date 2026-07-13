# arm_a6 -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `j1_travel` (no_model): no harness model for claim kind 'j1_travel'
- `j2_travel` (no_model): no harness model for claim kind 'j2_travel'
- `j3_travel` (no_model): no harness model for claim kind 'j3_travel'
- `jitter` (no_model): no harness model for claim kind 'jitter'
- `pose_home_j2` (no_model): no harness model for claim kind 'pose_home_j2'
- `pose_load_j3` (no_model): no harness model for claim kind 'pose_load_j3'
- `pose_reach_j2` (no_model): no harness model for claim kind 'pose_reach_j2'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Manufacturability residuals (WO-113 refresh)

The WO-110 DFM channel now ROUTES every `makeable: manufacturable(...)` claim; the five mill-family parts (ShoulderHousing, BearingRetainer, MotorBracket after realization -- plus the two below once their parts realize) discharge for real against the project's declared machine/tool records (`records/shop.toml`) and the tap-drill diameters declared on their hole patterns. Three residuals remain, each a MACHINERY gap (never a data gap):

- `Turret.makeable` (mfg.manufacturable_inputs_missing): lathe ops (Shaft/Shoulder) project no FeatureProgram -- the v1 feature-op set is mill-only (WO113-F1 escalation).
- `UpperArm.makeable` (mfg.manufacturable_inputs_missing): optimizer-bound part (b in [24,40]mm minimize) realizes no geometry in the staged loop; the DFM channel has no bbox (WO113-F2 escalation, the known cycle-34 realization residual).
- `Forearm.makeable` (mfg.manufacturable_inputs_missing): same as UpperArm (b in [18,32]mm minimize; WO113-F2).

Retirement: WO113-F1 (turned-part FeatureProgram projection) / WO113-F2 (minimize-bound part realization).

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

## Discharged for real (WO-113/D224 corpus enrichment)

Former `*_inputs_missing` rows, retired by declaring the inputs a real drawing carries (provenance recorded in-file at each claim site; waivers deleted per D224.2):

- `base_bolts`: VDI 2230 residual clamp -- ISO 898-1 M8 8.8 preload, moment-derived external load, cone-approximated stiffnesses.
- `j1_bearing` / `j2_bearing` / `j3_bearing`: ISO 281 L10 -- std.bearings 6006/6004/6002 record Cr values, pose-arithmetic-derived loads, declared joint speed specs, p=3.
- `housing_deflection` / `payload_deflection` (x2): Euler-Bernoulli cantilever tip -- boundary/pose-derived loads, declared spans, AL6061_T6 record modulus, section-derived I at the worst optimizer corner.

## Accepted -- impl/iface conformance edges

An interface-conformance edge (`impl:X`, or the `select:X` candidate-list kind for `impl X by select(...)`) carries no scalar window on either side -- genuinely indeterminate per D195.3, exactly like a bare import. Accepted via the D215 `impl(<Interface>)` waiver spelling, which names the INTERFACE and matches whichever realization kind (impl/extern/select) lowered its edges. Verdicts untouched (INV-2/INV-13).

Retirement: a realized impl or, for JointReduction, a resolved `select(...)` choice; the waiver then goes stale and is removed.

- `impl:BaseFoot` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:JointBore` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:JointMotorMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:LinkFlange` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `select:JointReduction` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
