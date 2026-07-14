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
| `opt_trace_G1.pdf` | 9100 | `sha256:a637e3c72af33ec85aa290000b3608214d8532128c640cd0e0e82a9929a61bb0` |
| `opt_trace_G1.svg` | 13235 | `sha256:b1af9da71f47bc854c94b33e7bf14787e336f26c4bf77b07d49146d52b61e80b` |
| `opt_trace_G2.pdf` | 8567 | `sha256:563525550da296068ac1a1586c4bbeb5409516854c57bbd2934f6ed82072d80e` |
| `opt_trace_G2.svg` | 12654 | `sha256:b2f468e98a7db450421527ca6f0cbe5b11dfc2d1f04631d34fe3eff648d677fd` |
| `plan_schedule.pdf` | 4344 | `sha256:fe9a231b5370e78c7aaa7c14b1a12cf71c2440a42a7df8dbdaf44ea1cc42c63a` |
| `plan_schedule.svg` | 6815 | `sha256:a4ba7476dd36b53c7c78e7a17f053d7207f5a554f8a989b92e7396f5432002fd` |
| `regolith.lock` | 348 | `sha256:ee1341e8cd465c6105dc5d5b15f53b5a97eaac06493aaae120407f35faccf7be` |
