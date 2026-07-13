# sdr_transceiver -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `agc_deadline` (no_model): no harness model for claim kind 'agc_deadline'
- `bad_sum` (no_model): no harness model for claim kind 'bad_sum'
- `bad_sum_neg` (no_model): no harness model for claim kind 'bad_sum_neg'
- `bram` (no_model): no harness model for claim kind 'bram'
- `cal_cost` (no_model): no harness model for claim kind 'cal_cost'
- `enob` (no_model): no harness model for claim kind 'enob'
- `fit` (no_model): no harness model for claim kind 'fit'
- `floor_chan` (no_model): no harness model for claim kind 'floor_chan'
- `floor_nyq` (no_model): no harness model for claim kind 'floor_nyq'
- `fmax_bus` (no_model): no harness model for claim kind 'fmax_bus'
- `fmax_samp` (no_model): no harness model for claim kind 'fmax_samp'
- `h2_abs` (no_model): no harness model for claim kind 'h2_abs'
- `h2_rel` (no_model): no harness model for claim kind 'h2_rel'
- `harmonics` (no_model): no harness model for claim kind 'harmonics'
- `headroom` (no_model): no harness model for claim kind 'headroom'
- `hot_switch_never` (no_model): no harness model for claim kind 'hot_switch_never'
- `image_rej` (no_model): no harness model for claim kind 'image_rej'
- `insertion` (no_model): no harness model for claim kind 'insertion'
- `isolation` (no_model): no harness model for claim kind 'isolation'
- `jitter_snr` (no_model): no harness model for claim kind 'jitter_snr'
- `keep_up` (no_model): no harness model for claim kind 'keep_up'
- `rejection` (no_model): no harness model for claim kind 'rejection'
- `rise_rx` (no_model): no harness model for claim kind 'rise_rx'
- `rise_tx` (no_model): no harness model for claim kind 'rise_tx'
- `rx_floor` (no_model): no harness model for claim kind 'rx_floor'
- `rx_leak` (no_model): no harness model for claim kind 'rx_leak'
- `settled` (no_model): no harness model for claim kind 'settled'
- `sfdr` (no_model): no harness model for claim kind 'sfdr'
- `snr` (no_model): no harness model for claim kind 'snr'
- `stack` (no_model): no harness model for claim kind 'stack'
- `total` (no_model): no harness model for claim kind 'total'
- `tx_burst` (no_model): no harness model for claim kind 'tx_burst'
- `usb_buf` (no_model): no harness model for claim kind 'usb_buf'
- `wcet` (no_model): no harness model for claim kind 'wcet'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.

- `alive` (unsupported_op): comparator 'require' defers
- `cal_entry` (unsupported_op): comparator 'require' defers
- `cal_exit` (unsupported_op): comparator 'require' defers
- `fault_rx` (unsupported_op): comparator 'require' defers
- `no_drop` (unsupported_op): comparator 'require' defers
- `no_underrun` (unsupported_op): comparator 'require' defers
- `por` (unsupported_op): comparator 'require' defers
- `rx_ready` (unsupported_op): comparator 'require' defers
- `tr_order` (unsupported_op): comparator 'require' defers
- `tx_entry` (unsupported_op): comparator 'require' defers
- `tx_exit` (unsupported_op): comparator 'require' defers

Retirement: the claim-form lowering increment for the named form (charter 30 sec. 1.3 WO-shaped escalation).

## Accepted -- Entity-derived bound not literal at lowering

The bound references entity/material properties whose D103 ref resolution on the reduction path is a recorded machinery residual; substituting a literal would fabricate a bound the design does not assert (D195).

- `fit` (unresolved_limit): bound 'partitions.appA.size' not literal
- `no_clip` (unresolved_limit): bound 'p1db - 3dB\n                     during agc = stepped' not literal
- `ref_stability` (unresolved_limit): bound '+-0.5ppm\n                           forall op\n\n# The LO: a fractional-N synthesizer on its own domai
- `rx_closes` (unresolved_limit): bound 'capture.sensitivity + 12dB\n                       during op = rx\n        # Reported margin is dB (a r

Retirement: D103 ref resolution on the reduction path.

## Accepted -- D102 temporal containment/reduction residuals

Typed temporal containments have no scalar request shape (payload-channel consumption is a recorded residual); entity-derived temporal bounds await the same D103 resolution.

- `eye` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape
- `mask_ok` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape
- `order` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape
- `pa_ramp` (temporal_containment_unmodeled): claim form ClaimForm6 lowered to a typed D102 containment, but its mask acceptance has no scalar request shape

Retirement: the recorded D102/D103 machinery residuals.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:adc_chain.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:board.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:clock_tree.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:contracts.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:dds_core.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:dsp_core.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:firmware.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:sdr_ctl.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.compute` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.debug` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.buses` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.families` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.elec.power` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.intents` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.cnc` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Other machinery-deferred obligations

Each row lists its verbatim deferral reason and detail; every one is a recorded machinery/record wall, not a design failure.

- `local_ambient` (thermo.junction_temperature_inputs_missing): 'board.RfDeck.local_env' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta
- `pa_junction` (thermo.junction_temperature_inputs_missing): 'board.u_pa.junction' is missing inputs ['ambient', 'power', 'r_theta'] (need ('ambient', 'power', 'r_theta');
- `tx_closes` (given_unresolved): link-budget reference 'radiate.pa_out' (port 'pa_out') did not resolve to a value through the entity DB

Retirement: the per-reason machinery increments named in the detail text.

## NOT ACCEPTED -- impl/iface conformance edges (machinery-blocked)

These obligations carry real subjects but colon-containing claim names (`impl:X`) the waive target grammar cannot spell; the D213 spelling covers only `import(<pkg>)`. They remain refusing until the spelling generalizes (WO-105 ledger escalation).

- `extern:DdsCore` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:AntennaFeed` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:Ddc` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:DdsCore` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:DeckBay` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:Duc` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:IfDigitizer` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:IfReconstructor` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
