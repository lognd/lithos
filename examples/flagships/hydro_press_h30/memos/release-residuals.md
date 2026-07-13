# hydro_press_h30 -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.

- `hammer` (no_model): no harness model for claim kind 'hammer'
- `rated` (no_model): no harness model for claim kind 'rated'
- `relief_holds` (no_model): no harness model for claim kind 'relief_holds'

Retirement: route label-named claims by call form (the F126.1 queued follow-on) or register a model for the kind; the waiver then goes stale and is removed.

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:HeadPlate` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:Ram` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:hydraulics.fluo` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.civil` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.fluorite` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:std.mech.weld` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Other machinery-deferred obligations

Each row lists its verbatim deferral reason and detail; every one is a recorded machinery/record wall, not a design failure.

- `strength[RamPad]` (frame_section_unresolved): section 'ram_bearing_plate_25mm' names no std.civil section record

Retirement: the per-reason machinery increments named in the detail text.

## NOT ACCEPTED -- impl/iface conformance edges (machinery-blocked)

These obligations carry real subjects but colon-containing claim names (`impl:X`) the waive target grammar cannot spell; the D213 spelling covers only `import(<pkg>)`. They remain refusing until the spelling generalizes (WO-105 ledger escalation).

- `impl:CylinderMount` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `impl:PlatenGuide` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

## NOT ACCEPTED -- trust-floored claims (memo evidence cannot meet the floor)

These claims sit in `trust: >=`-floored groups; D207 memo evidence confers community tier and can never meet a tested/certified floor, and CLI builds emit unsigned evidence. They remain refusing until a signing story lands (WO-105 ledger escalation).

- `clamp` (no_model): no harness model for claim kind 'clamp'
- `weld_static` (unresolved_limit): bound 'welded.w_corner.filler.sigma_allow, sf=2.0' not literal
