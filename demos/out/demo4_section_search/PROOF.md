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
| `opt_trace_G1.pdf` | 10383 | `sha256:54ade9147a09c9a456d19af0aad99219bc86066e4e907a66ddbef1de22d6b8f1` |
| `opt_trace_G1.svg` | 15146 | `sha256:da0aca88ec599e99c5d47dc65278e0d50ba65b81d76d48bb041eb2fb57d31b03` |
| `opt_trace_G2.pdf` | 9849 | `sha256:f73589a898042cf0431abf980ef9aa9143e37ae35508b9775eab28f8f47bd076` |
| `opt_trace_G2.svg` | 14556 | `sha256:e4e3fe5819f57e27b1ba25d8b746ebd1047d302d077b043cd1eb5470880e120a` |
| `plan_schedule.pdf` | 5487 | `sha256:27e8f84709434c6b2c34c7ac4cd9e82be20c021dd19d75ac16dc15195c4f8171` |
| `plan_schedule.svg` | 9151 | `sha256:e6a72db95be83dc85190b3334faafa49f11a91d8eea5010f3812577d3f3a3992` |
| `regolith.lock` | 348 | `sha256:ee1341e8cd465c6105dc5d5b15f53b5a97eaac06493aaae120407f35faccf7be` |
