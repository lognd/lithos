# cubesat -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `burn_energy` (no_model): no harness model for claim kind 'burn_energy'
- `detumble_in` (no_model): no harness model for claim kind 'detumble_in'
- `dipole` (no_model): no harness model for claim kind 'dipole'
- `dod` (no_model): no harness model for claim kind 'dod'
- `first_mode` (no_model): no harness model for claim kind 'first_mode'
- `fit` (no_model): no harness model for claim kind 'fit'
- `fmax` (no_model): no harness model for claim kind 'fmax'
- `frame_total` (no_model): no harness model for claim kind 'frame_total'
- `headroom` (no_model): no harness model for claim kind 'headroom'
- `mag_floor` (no_model): no harness model for claim kind 'mag_floor'
- `never_flat` (no_model): no harness model for claim kind 'never_flat'
- `no_rattle` (no_model): no harness model for claim kind 'no_rattle'
- `pa_out` (no_model): no harness model for claim kind 'pa_out'
- `rbf_kill` (no_model): no harness model for claim kind 'rbf_kill'
- `safe_floor` (no_model): no harness model for claim kind 'safe_floor'
- `settle` (no_model): no harness model for claim kind 'settle'
- `stack` (no_model): no harness model for claim kind 'stack'
- `torque` (no_model): no harness model for claim kind 'torque'
- `wcet` (no_model): no harness model for claim kind 'wcet'
- `wear` (no_model): no harness model for claim kind 'wear'
- `worst_orbit` (no_model): no harness model for claim kind 'worst_orbit'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.

- `alive` (unsupported_op): comparator 'require' defers
- `fault_safe` (unsupported_op): comparator 'require' defers
- `kick` (unsupported_op): comparator 'require' defers
- `latchup` (unsupported_op): comparator 'require' defers
- `no_contention` (unsupported_op): comparator 'require' defers
- `no_stuck` (unsupported_op): comparator 'require' defers
- `ocp` (unsupported_op): comparator 'require' defers
- `one_shot` (unsupported_op): comparator 'require' defers
- `pattern_clear` (unsupported_op): comparator 'require' defers

Retirement: the claim-form lowering increment for the named form (charter 30 sec. 1.3 WO-shaped escalation).

## Accepted -- D102 temporal containment/reduction residuals

Typed temporal containments have no scalar request shape (payload-channel consumption is a recorded residual); entity-derived temporal bounds await the same D103 resolution.

- `harmonics` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape
- `ovp` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape
- `retention` (temporal_reduction_unresolved_limit): claim form ClaimForm2 bound 'loop.rated_tension / 2.0' is not a literal (an entity-derived bound needs D103 re

Retirement: the recorded D102/D103 machinery residuals.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:../elec/buck_converter.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:adcs.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:antenna.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:comms.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:contracts.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:eps.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:obc.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:payload.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.compute` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.debug` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.buses` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.power` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.protocols` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.intents` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.cnc` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.matings` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.mounts` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.sheet` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:structure.hema` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Other machinery-deferred obligations

Each row lists its verbatim deferral reason and detail; every one is a recorded machinery/record wall, not a design failure.

- `fpga_ceiling` (thermo.junction_temperature_inputs_missing): 'payload.u_fpga.junction' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_thet
- `margin` (given_unresolved): link-budget reference 'antenna.gain' (port 'gain') did not resolve to a value through the entity DB

Retirement: the per-reason machinery increments named in the detail text.

## Accepted -- dotted window-half claims (D215)

A `within [lo, hi]` claim defers per window half with a dotted name (`<claim>.hi`/`.lo`); the D215 dotted-target spelling names each half. Both windows defer because the junction-temperature model is missing its ambient/power/r_theta inputs on the cells (recorded residual). Accepted per half, in the owning decl scope.

- `batt_window.hi` / `batt_window.lo` (thermo.junction_temperature_inputs_missing): 'eps.store.cells' missing ['ambient', 'power', 'r_theta']
- `temp_window.hi` / `temp_window.lo` (thermo.junction_temperature_inputs_missing): 'store.cells' missing ['ambient', 'power', 'r_theta']

Retirement: thread the junction-temperature inputs (the per-reason machinery increment named in the detail text).

## Accepted -- impl/iface conformance edges

An interface-conformance edge (`impl:X`) carries no scalar window on either side -- genuinely indeterminate per D195.3, exactly like a bare import. Accepted via the D215 `impl(<Interface>)` waiver spelling (StackCard included, matched by its interface name). Verdicts untouched (INV-2/INV-13). Retirement: a realized impl-side narrowing; the waiver then goes stale.

- `impl:AntennaPort` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:BoltPattern` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:CardBay` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:PanelSeat` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:PivotBore` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:StackHarness` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:TileCompressor` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:Umbilical` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

## Accepted -- rail_stress (floor author-revised per D216)

`rail_stress` lowers to label kind 'rail_stress', which has no certified evidence channel (no registered model, F126.1; feldspar's FEA kinds enter only via the payload channel), so the original `>= certified` floor was aspirational. Per D216(2) the author revised the floor to `community` in `structure.hema` with the recorded rationale; this memo-backed deviation then accepts at tier honestly.

- `rail_stress` (no_model): no harness model for claim kind 'rail_stress'

Retirement: restore the certified floor when a channel for the kind exists (F126.1 routing or a `by model(...)` pin plus signed evidence); the claim then discharges at tier and the waiver goes stale.
