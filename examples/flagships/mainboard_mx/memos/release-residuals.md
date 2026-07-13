# mainboard_mx -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `eta` (no_model): no harness model for claim kind 'eta'
- `jitter` (no_model): no harness model for claim kind 'jitter'
- `ripple` (no_model): no harness model for claim kind 'ripple'
- `transient` (no_model): no harness model for claim kind 'transient'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.

- `mcu_1v1` (unsupported_op): comparator 'require' defers
- `mcu_1v8` (unsupported_op): comparator 'require' defers
- `mcu_3v3` (unsupported_op): comparator 'require' defers
- `mcu_5v` (unsupported_op): comparator 'require' defers
- `v12_to_5v` (unsupported_op): comparator 'require' defers
- `v3v3_to_1v1` (unsupported_op): comparator 'require' defers
- `v3v3_to_1v8` (unsupported_op): comparator 'require' defers
- `v5_to_3v3` (unsupported_op): comparator 'require' defers

Retirement: the claim-form lowering increment for the named form (charter 30 sec. 1.3 WO-shaped escalation).

## Accepted -- D102 temporal containment/reduction residuals

Typed temporal containments have no scalar request shape (payload-channel consumption is a recorded residual); entity-derived temporal bounds await the same D103 resolution.

- `sag` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape

Retirement: the recorded D102/D103 machinery residuals.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:connectors.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:mcu.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:power_tree.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Rule-pack rows deferred at this tier

The named dfm/drc/erc rules carry no engine input at RELEASE (realized-fact-gated rule surface); the rule-pack waive target spelling is the designed acceptance channel for them.

- `erc(dft_test_points.test_point_probe_clearance)` (no_model): no harness model for claim kind 'erc(dft_test_points.test_point_probe_clearance)'
- `erc(interface_protection.vbus_inrush_protection)` (no_model): no harness model for claim kind 'erc(interface_protection.vbus_inrush_protection)'

Retirement: the realized-fact feeds the rules await.

## NOT ACCEPTED -- dotted window-half claim names (machinery-blocked)

A `within [lo, hi]` claim defers per window half with a dotted name (`<claim>.hi`); the waive target's trailing-segment match cannot spell a dotted claim name (probed stale both ways). Remains refusing until the spelling generalizes (WO-105 ledger escalation).

- `usb_diff_z0.hi` (si_differential_unexposed): differential impedance has no exposed feldspar model (the WO-25 diff_pair_z named cut: no independently verifi
- `usb_diff_z0.lo` (si_differential_unexposed): differential impedance has no exposed feldspar model (the WO-25 diff_pair_z named cut: no independently verifi

## NOT ACCEPTED -- impl/iface conformance edges (machinery-blocked)

These obligations carry real subjects but colon-containing claim names (`impl:X`) the waive target grammar cannot spell; the D213 spelling covers only `import(<pkg>)`. They remain refusing until the spelling generalizes (WO-105 ledger escalation).

- `impl:BoardOutline` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:PowerInConn` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:Rail1V1` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:Rail1V8` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `select:AddressDecodeGlue` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `select:CarrierStackup` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `select:Rail3V3` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `select:Rail5V` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
