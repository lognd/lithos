# PROOF: civil free-section search over a declared family (footbridge, WO-65)

- optimized quantity: **mass_per_length** (the lightest section clearing every declared demand -- strength AND the L/360 deflection bound -- under the SAME value+eps margin discharge uses)
- domain: the footbridge girders' declared `section: in registry(std.civil.w_shape)` free-section family
- winners: **G1=w16x40, G2=w8x31** (G1 is deflection-governed -> a heavier shape than the strength-only G2)
- cause rows (verbatim from `regolith.lock`):

```
G1=w16x40    cause: optimize(mass_per_length, trace=blake3:f90c3168617deceb1b02a823bca07e2047b64edc4fe929f48850aa636a2ed938)
G2=w8x31    cause: optimize(mass_per_length, trace=blake3:e849fed2e5ec7b3ab6bf9e69fc9583d1ab1b96ed058166e9917296d805484aaf)
```

## Where a human SEES it

- `opt_trace_G1.svg/.pdf`, `opt_trace_G2.svg/.pdf` -- the real search traces (loaded from the persisted trace store): every w_shape candidate's mass-per-length, feasibility, and the winner.
- `plan_schedule.svg/.pdf` -- the frame plan + member schedule.

### Honest residual (named, no producer edit)

The member-schedule producer currently renders each free member's DECLARED domain (`unresolved`/free) rather than writing back the searched winner; the authoritative pinned section is the `cause: optimize(...)` lockfile row + the trace sheet above. Writing the search winner into the schedule cell is a WO-65 producer follow-on, out of this WO's (no-machinery-change) scope.

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `opt_trace_G1.pdf` | 4367 | `sha256:842886fb30eddab83bf9de66f791880583a2fe7ffb40f51fc7c8d32fd356d18d` |
| `opt_trace_G1.svg` | 5420 | `sha256:4ea8c7d8fa7c793cf2a02886673ca67383bf3661000240822f877819504e47f3` |
| `opt_trace_G2.pdf` | 3834 | `sha256:671ed128cf35ea78c61c7bd292737e18e0028ed0dd2079e62e238dae1153c9c1` |
| `opt_trace_G2.svg` | 4839 | `sha256:4f9ead9403713c90e1a0be2a1fffb629557454ec3972c66ffde8a98694a735b5` |
| `plan_schedule.pdf` | 2244 | `sha256:f4695b0fd07d0118b47a8d271c9a694e7b0a5d94f9bda653ca97e778c000da7e` |
| `plan_schedule.svg` | 2542 | `sha256:ee225dc95a5aef5897da969cda822a735c6de2edd386a3883f05fb445260045b` |
| `regolith.lock` | 348 | `sha256:ee1341e8cd465c6105dc5d5b15f53b5a97eaac06493aaae120407f35faccf7be` |
