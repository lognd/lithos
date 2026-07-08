# WO-32: Fluorite lowering (flownet payload + the extraction seam)

Status: todo

DEMAND NOTE (from WO-31 D3 close-out): two fluid-discipline compile
checks are NOT front-end decidable and are deferred to this WO --
(1) FOPEN-1 mixed-medium rejection (needs edge->component->medium
binding), fixture `examples/negative/40_fluo_medium_mismatch.fluo`;
(2) the transient/volume-budget "neither compliance record nor
extractable wall" diagnostic (fluorite/03 sec. 1), fixture
`examples/negative/43_fluo_transient_no_compliance.fluo`. Both fixtures
are currently `# EXPECT-TODO: WO-32`; flip them to real `# EXPECT: Exxxx`
when this WO wires the checks over the lowered flownet payload.

Depends: WO-31 (front end), WO-30 (payload channel), WO-22 engine
half (realized-geometry records to extract from); the WO-29
remainder is upstream of LIVE-DESIGN extraction fixtures but NOT of
this WO's machinery (hand-authored realized records are legitimate
fixtures here -- the flownet payload itself is new production, not a
consumer side channel; AD-22 is satisfied because THIS WO is the
producer). GATES the feldspar fluids catalog having anything to
consume, and WO-34 (routed runs share deliverable 2's seam).
Language: Rust (`regolith-lower` fluid passes, `regolith-oblig`
FlownetPayload type); Python (regenerated `_schema/`, orchestrator
payload production wiring)
Spec: `docs/fluorite/03` (RATIFIED v1 -- normative for every rule
here); `../design/20-solver-abstraction.md` sec. 8.3 (the channel);
regolith/07 sec. 2; AD-5/AD-17/AD-18/AD-22/AD-23;
design-log 2026-07-07-cycle-20 D93/D96/D99 (the seam).

## Goal

`.fluo` sources lower to ordinary obligations carrying a
content-addressed `FlownetPayload` ref plus scalar-interval givens,
with hydraulic/compliance parameters EXTRACTED from realized
geometry through one shared routed-geometry extraction module --
after this WO, `fluids.*` claims are real obligations any pack can
discharge, and hand-asserted hydraulic givens become unnecessary.

## Deliverables

1. **FlownetPayload schema** (`regolith-oblig`, fluorite/03 sec. 2
   verbatim): medium ref, nodes, reference, edges (kind, sense pair,
   params-or-GeomExtract, compliance-or-null, curve refs), states
   (edge params and net-level state variables). Schemars-derived;
   rides the WO-30 `SCHEMA_VERSION` line (bump once here if WO-30
   already shipped). Content address via the AD-18 encoder.
2. **The routed-geometry extraction seam** (D99/F102; ONE module,
   `regolith-lower::extract`): given a realized-geometry record ref
   and a path/role selector, produce typed extraction results --
   flow areas, length, bend angles/radii, roughness class, elevation
   change, and (from wall records: E, thickness, diameter) wall
   compliance + Korteweg wave speed. Pure and IO-free (AD-17): the
   record CONTENT is an input (the orchestrator resolves refs via
   the WO-30 store and passes bytes in); every result is cited to
   the geometry snapshot hash it came from. This module is shared
   verbatim by WO-34 (wire runs) -- design its result type with a
   segment list + per-segment environment slot now, used by fluid
   edges as a single segment run.
3. **Fluid lowering passes** (`regolith-lower`): elaborate flownets
   per fluorite/03 sec. 1 -- extraction for `from=` edges, record
   refs for curve/compliance params, promise-chain givens for
   `driven_by=` imposers, net checks via the AD-23 core (WO-31),
   symbolic state expansion (ONE swept obligation per claim;
   discrete axes into the WO-30 coverage/sweep encoding). Every
   fluid claim form lowers per the 03 sec. 3 table; the
   compliance-missing compile diagnostic (03 sec. 1) fires when a
   transient/volume-budget claim names an edge with neither record
   nor extractable wall.
4. **Payload emission**: `BuildPayload` gains
   `flownets: IndexMap<FlownetName, FlownetPayload>` (AD-4: payload
   field, not side artifact -- the D89 precedent); obligations
   reference flownets by content digest; the orchestrator `put`s the
   serialized payload into the WO-30 store at build time so
   discharge-time `resolve` works.
5. **Golden corpus**: the WO-31 `examples/fluid/` corpus lowers to
   golden obligation sets + payload JSON (snapshot-updatable);
   determinism test (same source twice -> identical payload
   digests, INV-10); INV-4 fixture: a symmetric manifold orbit with
   ASYMMETRIC feed refuses verify-one (givens-invariance).
6. **Docs**: fluorite/03 marked implemented where landed;
   `../design/23-lowering-output-surface.md` gains a one-line note that
   fluorite lowers with no OpaqueIsland debt (the F96 lesson applied
   forward); regolith/08 lowering-architecture table row for the
   fluid track.

## Acceptance criteria

- `regolith check examples/fluid/coolant_loop.fluo` (name per
  corpus) emits obligations whose `payloads` carry a resolvable
  `flownet` ref; `regolith debug ir` shows the elaborated net.
- Extracted parameters match hand-computed values for a fixture
  tube record (area, length, two bends, compliance) to exact
  interval bounds; the citation carries the geometry snapshot hash.
- A `driven_by=` imposer obligation's givens carry the promise ref
  (the cross-track chain is traceable end to end in the lockfile).
- Same-source determinism: byte-identical payload + obligation
  hashes across two builds.
- The dual-circuit `forall` fixture produces ONE obligation with a
  discrete axis (two enumerated points), not two obligations.
- No second extraction implementation exists (WO-34's reviewer
  criterion starts here: `extract` is the only module reading
  realized-record internals in `regolith-lower`).
- `make check` green; schema drift check green.

## Non-goals

- Solving networks (pack territory: feldspar fluids/prop).
- HxSegment COUPLED solving (the language guarantees shared zone
  datum names; the coupled solve is feldspar M8).
- Computed zone/config fields (WO-33).
- Wire-run extraction consumers (WO-34; the seam only, here).
- FOPEN-1/FOPEN-2 (compile-rejected upstream).
