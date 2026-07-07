# 03 -- Lowering (DRAFT v0)

One sentence: elaboration turns geometry + topology into a
serialized, content-addressed `flownet` payload plus scalar-interval
givens, and every fluid claim lowers to an ordinary obligation
carrying that payload ref -- the harness and margin rule are
untouched.

## 1. Elaboration (compile-time, deterministic)

- **Hydraulic parameter extraction**: every `Pipe(from=part.role)`
  edge reads its wetted geometry from the implementing part's
  realized record (WO-22 lineage): flow area(s), length, bend
  angles/radii, roughness from the process capability table (a
  laser-cut channel and a drawn tube differ), elevation change.
  Extraction is part of lowering, cited to the geometry snapshot
  hash -- calcite never re-declares geometry (NO DUPLICATION).
- **Vendor/datasheet edges** (valves, pumps, filters) resolve their
  curve records by ref (hash-pinned registry objects).
- **Net checks** (02 sec. 4 discipline) run here; failures are
  compile diagnostics, not solve failures.
- **State expansion**: line-up config domains stay symbolic (ONE
  swept obligation per claim, regolith/07 sec. 2), never enumerated
  into obligation copies.

## 2. The flownet payload

One schema-versioned, Rust-sourced record (AD-5 precedent), the
newest payload KIND in the generalized ref channel
(`20-solver-abstraction.md` sec. 7 item 3):

```
FlownetPayload {
  medium: MediumRef,                    # property-record refs
  nodes: [NodeId],
  reference: { node, p, T },
  edges: [ { id, kind,                  # pipe|orifice|valve|pump|...
             a, b,                      # node ids (positive sense)
             params: {..} | GeomExtract # scalars or geometry-derived
             curves: [RecordRef] } ],
  states: [ { edge, var, domain } ],
}
```

Content-addressed like every payload; the obligation's inputs stay
`Mapping[str, Interval]` (boundary conditions: tank pressure,
ambient, commanded states) plus this ref. Solver packs (feldspar's
`fluids`/`prop` namespaces) consume the payload and solve the
network -- series/parallel reduction, Hardy-Cross/Newton, component
dp models -- entirely pack-side, at whatever tier the margin forces.

## 3. Obligation shapes

| claim form | obligation carries |
|---|---|
| `fluids.dp(a -> b)` | flownet ref + path spec + boundary givens |
| `fluids.flow_imbalance(orbit)` | flownet ref + orbit binding (INV-4 givens-invariance applies: a symmetric manifold with asymmetric feed does NOT license verify-one) |
| `fluids.npsh_margin(pump)` | flownet ref + pump record + pv(T) record |
| `peak(p, within d after e)` | flownet ref + event + the transient claim vocabulary (regolith/02 sec. 5) unchanged |
| `fluids.reynolds(edge) in [...]` | regime screening; discharging model reports which correlation-domain tags hold (feeds other models' Domain tags) |

## 4. Cross-track couplings

- **Thermal (hematite zones)**: `HxSegment(zone=...)` couples an
  edge's absorbed heat to a zone's flux. The coupling is declared in
  calcite, and the COUPLED SOLVE is pack territory (feldspar
  CoupledGroup, its 09 sec. 4b) -- the language only guarantees both
  sides name the same zone datum. This is the regen-jacket case made
  lowerable (the chamber.hem G23 residual: computed zone fields
  remain sec. 7 item 7).
- **Actuation (cuprite)**: valve state variables bind to cuprite
  signals via shared events; sequencing claims live where the
  commander lives (cuprite), fluid consequences where the fluid
  lives (calcite); one event ledger.
- **Structural (hematite)**: pressure/hammer results feed mech
  claims as ordinary derived quantities (`peak pressure` -> vessel
  stress givens), the same promise-chain mechanism as dissipation.

## 5. Trust, evidence, determinism

Nothing new: obligations discharge through the model registry;
evidence is content-addressed, signable, coverage-stating; payload
determinism = geometry snapshot hash + record refs (all existing
mechanisms). The `flownet` payload rides the SAME channel awaited by
geometry refs -- calcite adds demand for item 3, not a second
channel.
