# uav_talon -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `commutation_jitter` (no_model): no harness model for claim kind 'commutation_jitter'
- `jitter` (no_model): no harness model for claim kind 'jitter'
- `loading_ok` (no_model): no harness model for claim kind 'loading_ok'
- `clamp_bolts` (unmatched_call_path): call path `mech.bolt.separation_margin` matches no registered route (the landed model registers `mech.bolt.joint_separation`; Class B routing increment -- basis refreshed WO-113)

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.

(section empty since WO-113: the former `makeable` rows moved below.)

## Accepted -- Manufacturability residuals (WO-113 refresh)

The WO-110 DFM channel now ROUTES every `makeable` claim; both of this project's parts are laser-cut sheet:

- `makeable` x2 (mfg.manufacturable_ungrounded_process): the `cut` process family has no record-groundable envelope check in DFM v1 (mill-only, F132.3); sheet physics lives in the WO-28 rule packs.

Retirement: a cut-family DFM envelope check grounded in laser-cutter records (machinery, not data).

## Discharged for real (WO-113/D224 corpus enrichment)

- `tip_defl`: Euler-Bernoulli cantilever tip over the declared gust case -- the WO-70 discharge test's own committed 220N gust tip force derivation, the 900mm declared half-span, the AL7075_T6 record modulus, and the spar section at the worst optimizer depth corner. Carried a D224.3 DESIGN FIX: the spar depth domain was re-specced [3,8]mm -> [52,60]mm (the flat strip VIOLATED by three orders of magnitude; the repo's own tests already modeled the spar 60mm deep -- rationale in airframe.hema).

## Accepted -- Entity-derived bound not literal at lowering

The bound references entity/material properties whose D103 ref resolution on the reduction path is a recorded machinery residual; substituting a literal would fabricate a bound the design does not assert (D195).

- `root_stress` (unresolved_limit): bound 'material.sigma_y / 1.8' not literal

Retirement: D103 ref resolution on the reduction path.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:BatteryBay` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:BatteryPack` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:BoardOutline` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:CardMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:SparCapMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:WingSpar` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:avionics.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:propulsion.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.sheet` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Given-resolution input gaps

The model's required inputs are not resolvable from the declared given set (D97 sec. 8.4); the design does not carry the missing quantities, and inventing them is forbidden.

- `cg_ok` (cg_moment_no_declared_position_data): mech.cg(...) needs per-part mass AND position to form sum(m_i * x_i): mech.mass(...) is not yet wired to any n

Retirement: declare the missing givens with citable sources, or realize them through the realized-fact channel.

## Accepted -- impl/iface conformance edges

An interface-conformance edge (`impl:X`, or the `select:X` candidate-list kind for `impl X by select(...)`) carries no scalar window on either side -- genuinely indeterminate per D195.3, exactly like a bare import. Accepted via the D215 `impl(<Interface>)` waiver spelling, which names the INTERFACE and matches whichever realization kind (impl/extern/select) lowered its edges. Verdicts untouched (INV-2/INV-13).

- `impl:BatteryBay` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:BoardOutline` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:BoomMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:CardBay` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:MotorMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:SparCapMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `select:MotorClass` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: a realized impl (`= todo!` -> real geometry/binding) or, for MotorClass, a resolved `select(...)` choice; the waiver then goes stale and is removed.
