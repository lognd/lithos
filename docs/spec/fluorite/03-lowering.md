# 03 -- Lowering (RATIFIED v1, cycle 20 / D93)

Implementation status (WO-32, cycle 24 close-out): LANDED end to end
against hand-authored realized-geometry fixtures -- sec. 1 elaboration
(extraction, compliance/wave-speed, vendor/imposer edges, net checks,
symbolic state expansion), sec. 2 the `FlownetPayload` schema, sec. 3
every claim form's obligation shape, sec. 5 payload determinism (see
`examples/tracks/fluorite/` + `tests/golden/test_golden_corpus.py`'s
flownet-digest determinism test). The sec. 1 compliance-missing
compile diagnostic is E0203, wired and corpus-covered
(`examples/negative/43_fluo_transient_no_compliance.fluo`).
Extraction over REAL realizer-produced `RealizedGeometry` IR LANDED
with WO-51 (cycle 28): `lower.programs` emits `FeatureProgram`s with
cavity-derived `flow_paths` from real `.hema` source (D151/D152),
`staged_build` promotes them into the realizer contract with no
caller-supplied program, and the extraction seam resolves the
`GeomExtract` placeholder to concrete scalars over the staged loop
(see `examples/tracks/hematite/coolant_gallery.hema` + the
`test_staged_build_realizes_the_exemplar_with_no_caller_program`
acceptance test) -- the hand-authored-fixture era is over (they
remain a legitimate override/test channel, AD-22). Still NOT landed:
the sec. 3 `flow_imbalance` row's INV-4 givens-invariance check
(model/solver territory, same honest residual as the mech track --
see `examples/negative/44_fluo_asymmetric_feed_verify_one.fluo`).

One sentence: elaboration turns geometry + topology into a
serialized, content-addressed `flownet` payload plus scalar-interval
givens, and every fluid claim lowers to an ordinary obligation
carrying that payload ref -- the harness and margin rule are
untouched.

## 1. Elaboration (compile-time, deterministic)

- **Hydraulic parameter extraction**: every `Pipe(from=part.role)` /
  `Hose(from=part.role)` edge reads its wetted geometry from the
  implementing part's realized record (WO-22 lineage): flow area(s),
  length, bend angles/radii, roughness from the process capability
  table (a laser-cut channel and a drawn tube differ), elevation
  change. Extraction is part of lowering, cited to the geometry
  snapshot hash -- fluorite never re-declares geometry (NO
  DUPLICATION). The extraction module is the SHARED routed-geometry
  seam (D99/F102): wire runs (WO-34) read the same module.
  [Clarified cycle 24, D128/AD-25: "part of lowering" is literal --
  extraction runs IN-PIPELINE over the `RealizedGeometry` IR
  supplied to `lower()` as a compile input; the payload's
  `GeomExtract` selector is only the pre-realization placeholder
  (dependent obligations honestly indeterminate until the IR
  exists), never a discharge-time mechanism.]
- **Compliance and wave speed** (D93, closes the former COPEN-5):
  when an edge's implementing part carries a wall record (E,
  thickness, diameter), lowering extracts wall compliance and the
  Korteweg wave speed alongside the hydraulic parameters, cited to
  the same snapshot hash. Record-bound compliance
  (`Hose(compliance=registry(...))`) takes precedence over
  extraction; an edge with NEITHER a record nor an extractable wall,
  named in a transient or volume-budget claim, is a compile
  diagnostic (the claim would be undischargeable -- fail at compile,
  not at solve).
- **Vendor/datasheet edges** (valves, pumps, filters) resolve their
  curve records by ref (hash-pinned registry objects).
- **Imposer edges** lower their value expression through the ordinary
  derivation machinery: a `driven_by=` promise becomes a given
  carrying the promise-chain ref, exactly like dissipation promises.
- **Net checks** (02 sec. 4 discipline) run here; failures are
  compile diagnostics, not solve failures.
- **State expansion**: line-up config domains stay symbolic (ONE
  swept obligation per claim, regolith/07 sec. 2), never enumerated
  into obligation copies; discrete axes ride the structured coverage
  encoding (D95).

## 2. The flownet payload

One schema-versioned, Rust-sourced record (AD-5 precedent), a payload
KIND in the generalized ref channel (D96,
`20-solver-abstraction.md` sec. 8):

```
FlownetPayload {
  medium: MediumRef,                    # property-record refs
  nodes: [NodeId],
  reference: { node, p, T },
  edges: [ { id, kind,                  # pipe|orifice|valve|pump|
                                        # imposer|...
             a, b,                      # node ids (positive sense)
             params: {..} | GeomExtract # scalars or geometry-derived
             compliance: {..} | null,   # wall compliance + wave speed
             curves: [RecordRef] } ],
  states: [ { target, var, domain } ],  # edge params AND declared
                                        # net-level state variables
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
| `fluids.reynolds(edge) in [...]`, `choked(edge)` | regime screening; discharging model reports which correlation-domain tags hold (feeds the D97 regime channel) |
| `fluids.volume_consumed(edges, at=p)` | flownet ref (compliance fields) + the budget machinery (E0432 family) |
| `fluids.leak_total(subnet)` | budget over fitting/seal contributors; component seal promises enter as givens via the promise chain |

## 4. Cross-track couplings

- **Thermal (hematite zones)**: `HxSegment(zone=...)` couples an
  edge's absorbed heat to a zone's flux. The coupling is declared in
  fluorite, and the COUPLED SOLVE is pack territory (feldspar
  CoupledGroup, its 09 sec. 4b) -- the language only guarantees both
  sides name the same zone datum. Computed zone FIELDS (a regen
  chamber computing its own wall temperatures) are D98/WO-33
  (`regolith/02-quantity-core.md` sec. 4a; the `compute <name>: ...
  over <zones>` claim form); `examples/tracks/hematite/regen_chamber.hema`
  exercises the coupling shape end to end (grammar + lowering only --
  no field-producing model yet, so the coupling stays honestly
  indeterminate).
- **Actuation (cuprite)**: valve state variables bind to cuprite
  signals via shared events; sequencing claims live where the
  commander lives (cuprite), fluid consequences where the fluid
  lives (fluorite); one event ledger.
- **Structural (hematite)**: pressure/hammer results feed mech
  claims as ordinary derived quantities (`peak pressure` -> vessel
  stress givens), the same promise-chain mechanism as dissipation.
  The reverse direction (mech force -> pressure) is the `Imposer`
  component (02 sec. 3).

## 5. Trust, evidence, determinism

Nothing new: obligations discharge through the model registry;
evidence is content-addressed, signable, coverage-stating; payload
determinism = geometry snapshot hash + record refs (all existing
mechanisms). The `flownet` payload rides the D96 channel shared with
geometry/spectra/field refs -- fluorite adds a payload kind, not a
second channel.
