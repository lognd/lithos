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

## Accepted -- impl/iface conformance edges

An interface-conformance edge carries no scalar window on either side, or (the 17 `conformance_impl_bound_missing` rows) a resolved spec-side bound with no real impl-side narrowing to author -- a mirrored bound would discharge vacuously, the INV-13/26 violation D195 forbids. Accepted via the D215 `impl(<Interface>)` spelling: HeaterSeat, ThermoWell, LevelWell, FittingPort, MountPattern, SealFace, BoltPattern, IsoMount, HolePattern. Verdicts untouched (INV-2/INV-13).

Retirement: real impl-side narrowings; each waiver then goes stale.

## Accepted -- fluorite flownet claims (D215)

The BrewPath (pressure/flow/supply_dp/npsh/vented/hammer/ramp/fill_flow/swell/leaks), SteamService (band/recover/rate/single_fault/no_vac), and GroupThermosiphon (flow/stall/regime) claims live in top-level require bodies of flownet files -- harvested, matched waive positions per D215(c); one require body harvests for the whole file. Each waived in place with its wall-citing basis (no model for the kind / claim form outside the scalar lowering surface / dp record chain open).

Retirement: the per-reason machinery increments (kind models, claim-form lowering, record chain closure).

## Accepted -- dotted window halves (D215)

`brew_hold.lo`/`.hi` (junction-temperature inputs missing on regulate_brew.plant) and `steam_hold.lo`/`.hi` (no model for the pressure-band kind), accepted per half via the D215 dotted spelling.

Retirement: thread the junction-temperature inputs / register the band kind.

## Accepted -- hoop claims (floors author-revised per D216)

Both boiler `>= certified` floors were aspirational: each hoop claim's entity-derived bound (material.sigma_y(T_local)/1.8) sits behind the recorded D103 ref-resolution residual, and no certified channel exists for the route today. Per D216(2) the author revised both floors to `community` in the design sources with recorded rationales; the memo-backed deviations then accept at tier honestly.

Retirement: restore each floor when the D103 resolution + a signed channel land.

## Evidence note -- dfm(min_hole_to_bend) on cut.boiler_s_holes (frame_panels.hema)

Proto lot EV-104: hole-to-bend draw-in measured at 0.2mm on the rear flange cluster -- within the flange's flatness allowance; accepted. This memo entry is the `by doc` evidence the waiver cites (WO-105: the formerly evidence-less rung-7 waiver release-gated the whole flagship; the evidence-less posture stays exercised by the waivers.rs suite).

## WO-113 enrichment pass (D224 campaign)

Declared this pass: tap-drill diameters + depths on every boiler
threaded port (ISO 261 values, derivations at the ops), the project
shop [[machine]]/[[tool]] records (records/shop.toml), the
`water_iapws_liquid` std.fluid medium record (IAPWS-95, 318.15K --
the design's own declared hot-tank corner), and [profiles.cost.*]
for every claimed quantity (fixture-tier honesty note in
magnetite.toml). No discharge count change -- each chain instead
advanced to its TERMINAL machinery wall, now named at every waiver:

- boilers' `makeable`: the round-stock (Tube/Bar) weldment realizer
  gap -- no realized geometry for the staged loop (WO113-F5).
- `cost` x6: the escalated Rust bare-form cost_bom marker emission
  gap (profiles + quantity resolve; no quantity basis reaches the
  estimator).
- `supply_dp`: density resolves from the new record; the remaining
  pipe-only declaration is REFUSED (D224.1) because the claim spans
  the flowmeter + 20kPa check valve the single-segment Darcy model
  cannot carry -- needs the component-dp record chain (F132.3).
- `npsh`: the Ulka EX5's NPSH_r curve is unpublished; the pump-curve
  record chain stays honestly open (WO110-F5).
- `group_sag`: the cantilever route exists, but the group service
  load and plate-bending lever are undeclared; a declared spec would
  decide the verdict either way, so it stays deferred pending a
  design-review load spec (candidate D224.3 review: real machines
  visibly nod -- flagged, not hidden).
