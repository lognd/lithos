# PROOF: bounded sketch-segment slot sized by a real margin search (arm_a6 UpperArm, WO-97/D209)

- optimized quantity: **UpperArm.UpperArmSection.b** (the bounded sketch-segment width, [24mm, 40mm])
- domain: arm_a6 UpperArm's cantilever-deflection margin search (Euler-Bernoulli, end point load, `beam_bending.py`'s `mech.beam.cantilever_deflection` model), driven by DECLARED inputs -- force 6.87N (`link1.hema` payload_deflection claim), span 300mm (promoted profile run), E=6.890e+10Pa (AL6061_T6), thickness 20mm (Blank record)
- winner: **b=24.000mm** (the 1.5mm limit is slack at every candidate, so the minimizer converges to the lower bound, 24mm)
- cause row (verbatim from `regolith.lock`):

```
x=0.02400024969178664    cause: optimize(declared_objective, trace=blake3:6085c5ed55cb7ee592c2ca1a6e60ecd816a5006b69baba3156a416af1f0ffc2b)
```

## Binding-constraint evidence (the search is real)

Re-running the SAME coupling with the deflection limit tightened to 0.020mm (below the deflection at 24mm, above it at ~40mm) moves the winner OFF the lower bound: **b=30.462mm** (termination=converged, feasible=True). A rubber-stamp evaluator would land on 24mm regardless of the limit; this one does not.

## Honest residual: uav_talon WingSpar stays deferred

`uav_talon`'s WingSpar carries the same `SegmentLength::Bounded` slot shape, but its governing load is `derived(sf=1.5)` -- there is no declared scalar force to hand the cantilever model, only a safety-factor derivation. Driving it through this coupling would require fabricating a load, which WO-97/D209 forbids; it stays honestly `optimizer_evaluator_deferred` (demo5 was retargeted to arm_a6 UpperArm, the part that genuinely pins -- F128.3). No demo in this pack claims WingSpar is live.

## Where a human SEES it

- `upper_arm_section.step` / `.glb` / `.viewer.html` -- the realized solid at the winning width; open the viewer in a browser.
- `opt_trace_b.svg` / `.pdf` -- the real search trace: every candidate width, its feasibility, and the winner.
- `regolith.lock` -- the pinned `cause: optimize(...)` row.

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `opt_trace_b.pdf` | 12811 | `sha256:c92d820e7c08c0fdd7036469e859a3aef3b7cb23c595b20dc36680ee4ad7a02f` |
| `opt_trace_b.svg` | 18333 | `sha256:c567998a9d58ff24007f511d0b8ad298cd5b57cc72950d78cc17bb3ccee19804` |
| `regolith.lock` | 223 | `sha256:6e2fd9e8196becc14dd04bb0dfb49bf1b29e474247b0722c88c94637e92404e6` |
| `upper_arm_section.glb` | 836 | `sha256:40ccaf283693e715c23302fc6f18cc62f6e0c4765bb4ea04df0dd9ac1c78b850` |
| `upper_arm_section.step` | 15701 | `sha256:455aa1373acce92dd4de297064184c3ec9d86987c560caf8a918f6af4d65aebf` |
| `upper_arm_section.viewer.html` | 10600 | `sha256:2a69e09037d1fe23617a6455117f7a68fade18c009225f84b353540b23dd5b54` |
