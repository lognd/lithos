# hydro_press_h30 -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- No registered harness model for the label kind

F126.1 (F125-E1 verdict): a bare-label claim (`sag:`, `twist:`, ...) lowers to a claim kind equal to its label; no model registers these kinds, and feldspar's kinds enter only via the payload/FEA channel. Genuinely unbounded at BUILD.


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

## Accepted -- impl/iface conformance edges

An interface-conformance edge (`impl:X`) carries no scalar window on either side -- genuinely indeterminate per D195.3, exactly like a bare import. Accepted via the D215 `impl(<Interface>)` waiver spelling. Verdicts untouched (INV-2/INV-13).

- `impl:CylinderMount` (conformance_windows_unresolved)
- `impl:PlatenGuide` (conformance_windows_unresolved)

Retirement: a real impl-side narrowing or realized-fact discharge; the waiver then goes stale and is removed.

## Accepted -- floored claims (floors author-revised per D216)

Both '>= certified' floors in corners.hema were aspirational: `clamp` lowers to label kind 'clamp' (no registered model, F126.1) and `weld_static` carries the entity-derived bound 'filler.sigma_allow' behind the recorded D103 ref-resolution residual -- no certified channel exists for either route today. Per D216(2) the author revised both floors to `community` in the design source with recorded rationales; the memo-backed deviations then accept at tier honestly.

- `clamp` (no_model): no harness model for claim kind 'clamp'
- `weld_static` (unresolved_limit): bound 'welded.w_corner.filler.sigma_allow, sf=2.0' not literal

Retirement: restore each floor when its channel exists (F126.1 routing / D103 resolution plus signed evidence); the claims then discharge at tier and the waivers go stale.

## Accepted -- fluorite flownet claims (D215)

`rated`, `relief_holds`, and `hammer` (PressCircuit, all no_model per
F126.1) live in top-level `require` bodies of a flownet-only file --
now a harvested, MATCHED waive position per D215(c) (flownet origins
join the match scope). Each is waived in place with its wall-citing
basis. WO-105 posture note on WO-73's "none waived" ledger line: the
demand STANDS (the claims remain release-gated obligations); the
campaign records them as memo-backed accepted deviations rather than
silent deferrals, and the posture change is recorded in the WO-105
close-out.

Retirement: registered models for the fluids.pressure/peak-within
routes; the waivers then go stale and WO-73's original all-discharged
posture is restored.

## Discharged this campaign (not deviations)

`bearing_l`/`bearing_r` were VIOLATED at the checkpoint (134.3kPa over
the asserted 1.0m2 pads vs the 100kPa soil-test low corner). The pad
area is the design's own sizing choice, so this was a legitimate
authoring fix (D206 discharge-first), not a waiver: each upright now
bears on a 1.5m2 half of a shared 3.0m x 1.0m strip mat
(134.3kN / 1.5m2 = 89.6kPa <= 100kPa). Both claims now DISCHARGE
through footing_bearing_pressure@1.
