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
| `opt_trace_G1.pdf` | 10329 | `sha256:31400389b6b530576e5a6722d65151caf29c8652b24a37c89ad638168abd072e` |
| `opt_trace_G1.svg` | 15146 | `sha256:76198c2c2e0f5064eee9a469eac26db3cd864a90577061016f7ae0e45b3b5fab` |
| `opt_trace_G2.pdf` | 9795 | `sha256:e42faf59dbf026188b4a7d148dfe8dbcf28816b132798f21c8f1b23429a50cbb` |
| `opt_trace_G2.svg` | 14556 | `sha256:90acda0815a95d8dc8a23647f2f4b555ef2623bb5bc0012d8659f8a34746bc37` |
| `plan_schedule.pdf` | 5487 | `sha256:5606227f1ebc0ca91e5e1caef2c4baf110ef7ad435094e496cf6674a64c536d1` |
| `plan_schedule.svg` | 9151 | `sha256:ad21cb6e018403c9b98b5f3f5b0846f09c389c638d0de1e1b66328f4170f3b6e` |
| `regolith.lock` | 348 | `sha256:ee1341e8cd465c6105dc5d5b15f53b5a97eaac06493aaae120407f35faccf7be` |
