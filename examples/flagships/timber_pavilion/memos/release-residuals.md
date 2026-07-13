# timber_pavilion -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:std.civil` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- Other machinery-deferred obligations

Each row lists its verbatim deferral reason and detail; every one is a recorded machinery/record wall, not a design failure.

- `bearing` (frame_reaction_unresolved): footing 'FA' has no resolvable incoming gravity load path in this frame's transfers (Pinned/Moment/BasePlate) 
- `strength[Purlin]` (frame_load_untargeted): member 'Purlin' carries no directly-targeted literal distributed/line/point load in this frame's `loads`, no r

Retirement: the per-reason machinery increments named in the detail text.
