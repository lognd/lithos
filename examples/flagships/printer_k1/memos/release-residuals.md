# printer_k1 -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `headroom` (no_model): no harness model for claim kind 'headroom'
- `jitter` (no_model): no harness model for claim kind 'jitter'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.

- `rail_v` (unsupported_op): comparator 'require' defers

Retirement: the claim-form lowering increment for the named form (charter 30 sec. 1.3 WO-shaped escalation).

## Accepted -- Manufacturability residuals (WO-113 refresh)

The WO-110 DFM channel now ROUTES every `makeable: manufacturable(...)` claim. BedCarriage's `manufacturable(milled)` discharges for real against the project's declared machine/tool records (`records/shop.toml`). The five laser-cut sheet parts' claims stay honestly deferred with a refreshed basis:

- `makeable` x5 (mfg.manufacturable_ungrounded_process): the `cut` process family has no record-groundable envelope check in DFM v1 (mill-only, F132.3); sheet-process physics lives in the WO-28 rule packs (`mech.sheet.min_bend_radius`), one home.

Retirement: a cut-family DFM envelope check (machine bed size vs sheet, kerf vs feature) grounded in laser-cutter records -- a WO-110-shaped machinery increment, not a data gap.

## Discharged for real (WO-113/D224 corpus enrichment)

- `payload_ok`: Euler-Bernoulli cantilever tip -- boundary payload (30N), the declared plate/bolt-pattern overhang geometry (20mm lever), AL6061_T6 record modulus, declared 3mm sheet gauge (delta = 0.013mm vs the 0.3mm bound).
- `BedCarriage.makeable`: DFM stock/tool fit vs the knee-mill class record + 6mm end mill (records/shop.toml).

## Accepted -- Entity-derived bound not literal at lowering

The bound references entity/material properties whose D103 ref resolution on the reduction path is a recorded machinery residual; substituting a literal would fabricate a bound the design does not assert (D195).

- `travel_x` (unresolved_limit): bound 'build_volume.x' not literal
- `travel_y` (unresolved_limit): bound 'build_volume.y' not literal
- `travel_z` (unresolved_limit): bound 'build_volume.z' not literal

Retirement: D103 ref resolution on the reduction path.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:BaseFrame` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:BedCarriage` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:BoardOutline` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:BuildPlatformMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:CardMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:DirectDriveExtruder` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:EnclosurePanel` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:HeatedBed` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:HotendPocket` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:LeadscrewMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:PanelSeal` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:RailMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:XCarriage` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:controller.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:psu.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.fluorite` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.intents` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.cnc` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.matings` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.mounts` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.sheet` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- impl/iface conformance edges

An interface-conformance edge (`impl:X`, or the `select:X` candidate-list kind for `impl X by select(...)`) carries no scalar window on either side -- genuinely indeterminate per D195.3, exactly like a bare import; the two `conformance_impl_bound_missing` rows additionally have no real impl-side narrowing to author (a mirrored bound would discharge vacuously, D195). Accepted via the D215 `impl(<Interface>)` waiver spelling: RailMount, LeadscrewMount, StepperMount, CardBay, PanelSeal, BoardOutline, FanDrive, HeaterDrive, HotendPocket, HolePattern, FeederThroat, BuildPlatformMount, BedHeater, and select:AddressDecodeGlue. Verdicts untouched (INV-2/INV-13).

Retirement: realized impl-side narrowings or a resolved `select(...)` choice; each waiver then goes stale and is removed.

## Accepted -- fluorite flownet claims (D215)

`flow` (PartCooling, thermal.fluo) lives in the top-level `require
Cooling:` body of a flownet file -- now a harvested, matched waive
position per D215(c). Waived in place (no model for the label kind,
F126.1); the import(std.fluorite) waive moved from the flownet body
(not a harvest position) into the same require body.

Retirement: a registered model for the fluids.mdot route; the waiver
then goes stale.
