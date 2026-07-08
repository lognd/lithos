# WO-42: Realized-domain IRs (L4 payload schemas + the staged build loop)

Status: in-progress (see "Progress" section below -- scope beyond
the vocabulary/doc slice needs its own dispatch)
Depends: WO-30 (payload store + PayloadRef channel), WO-22 engine
half (the geometry producer to promote), WO-24 engine half (the
layout producer to promote), WO-32 D1/D2 (the flownet payload and
`regolith-lower::extract` are the first in-pipeline consumers).
GATES: WO-32 D4b's end-to-end half (extraction over
realizer-produced geometry instead of hand-authored fixtures), WO-34
(run extraction over real records), WO-25 (IR-derived manufacturing
reports/BOM).
Language: Rust (`regolith-oblig` schemas, `regolith-api`/`regolith-py`
realized-input channel, `regolith-lower` consumption); Python
(realizer promotion in `regolith.realizer.*`, orchestrator staged
loop, regenerated `_schema/`)
Spec: AD-25 (normative; this WO is its machinery) + design-log
2026-07-08-cycle-24 D128; regolith/08 sec. 1 (L4); AD-5/AD-17/AD-18/
AD-22; `../design/22-mech-geometry-realizer.md` (the forward
contract being promoted); `../design/20-solver-abstraction.md`
sec. 8 (the channel + kind vocabulary).

## Goal

The spec's L4 "REALIZED IR" level becomes real: realized geometry
and placed/routed layout are schema-versioned, content-addressed IRs
produced once by the realizers and consumed in-pipeline by lowering
-- so extraction (WO-32/WO-34), rule packs, and backends read typed
IRs cited by digest, never native CAD/EDA files, and a geometry or
layout change invalidates exactly the obligations built on it.

## Deliverables

1. **`RealizedGeometry` schema** (`regolith-oblig`, schemars,
   AD-5/AD-18): WO-22's Python forward contract
   (`regolith.realizer.mech.schema` -- realized-geometry record:
   STEP content hash, mass properties, topology summary) PROMOTED
   into Rust per the AD-22 rule (the hand-written Python version is
   deleted or demoted to a drift check in the same change). Extend
   with the fields the WO-32 extract seam reads (per-segment wetted
   geometry: flow areas, path lengths, bends, roughness class,
   elevation; wall data: E, thickness, diameter) and a per-stage
   structure. Payload kind `geometry.realized` (already in the D96
   vocabulary). One `SCHEMA_VERSION` bump for this WO's schema work
   (coordinate with whatever version is current at dispatch; bump
   ONCE); `make schema`; golden corpus re-keyed.
2. **`RealizedLayout` schema** (`regolith-oblig`): the elec
   placed/routed board content WO-24 produces -- board outline ref,
   placements (footprint, position, rotation, side), routed segment
   list (net, layer, width, length), copper summary, extracted
   parasitic slots, `.kicad_pcb` content hash pin. NEW payload kind
   `layout.realized`: add it to the D96 kind vocabulary in
   `../design/20-solver-abstraction.md` sec. 8 AND note it in the
   feldspar channel contract (feldspar OPEN-2 pins that list --
   record the addition in `../feldspar/docs/feldspar/`
   `09-model-integration.md` sec. 4's kind list in the same change).
3. **The realized-input channel**: `regolith-api::Session` compile
   calls accept realized-IR inputs (digest -> bytes, resolved by the
   caller; AD-17 purity: content-as-input, no IO in the pipeline);
   `regolith-lower` passes them to elaboration so
   `regolith-lower::extract` runs in-pipeline (D128) and extracted
   values carry the source IR digest as citation. The FFI crossing
   is coarse per AD-4 (one map of bytes, marshalled by `regolith-py`,
   reached via `compiler.py`). `regolith debug ir` gains a section
   listing the realized IRs supplied to the build (kind, digest,
   subject).
4. **Realizer promotion** (Python): `regolith.realizer.mech` emits
   `RealizedGeometry` as its primary semantic output (generated
   `_schema/` model), `put` into the WO-30 store; STEP stays a
   pinned side artifact + evidence. `regolith.realizer.elec` emits
   `RealizedLayout` the same way once its layout half runs (its
   KiCad-unavailable deferral stands -- the schema and the emission
   seam land now, exercised by the fixture-driven tests WO-24
   already uses). No pass, pack, or backend parses STEP/`.kicad_pcb`
   after this WO (grep-level reviewer criterion).
5. **The staged build loop** (orchestrator): lower -> realize
   (producing new IRs) -> re-lower with them, to a fixed point;
   termination by content addressing (unchanged IR inputs ->
   byte-identical re-lower, INV-10); every iteration logged with the
   IR digests that changed. Lockfile rows for realized IRs carry
   `cause: realizer(<pack>)` (INV-21).
6. **Docs**: AD-25 marked implemented where landed; regolith/08
   sec. 1 note updated from "decided" to "landed"; design/22's
   forward-contract section marked promoted; WO-22/24/34/25
   amendment notes flipped to point at the landed channel; this WO's
   Status line.

## Acceptance criteria

- The WO-22 fixture part round-trips end to end: the mech realizer
  emits a `RealizedGeometry` into the store; a re-lower consumes it;
  `regolith-lower::extract` values match the hand-computed fixture
  numbers to exact interval bounds and are cited to the IR digest.
- Changing the fixture geometry changes the IR digest and BREAKS the
  dependent payload goldens (the G42 anti-staleness property, proven
  with a second geometry variant).
- Same-source determinism: two staged builds produce byte-identical
  IR digests and payload digests; the staged loop terminates in one
  re-lower when realization adds nothing new (INV-10 test).
- A build whose geometry IR is absent lowers with the
  pre-realization placeholder intact and dependent obligations
  honestly indeterminate, naming the missing IR (D128's placeholder
  rule).
- Schema drift check green (`make schema` no-op after regen); no
  hand-written Python mirror of either schema survives (AD-22
  promotion verified by grep).
- `make check` green.

## Progress (this dispatch)

This pass scoped the whole WO per the dispatch protocol (README.md)
and landed the lowest-risk, no-code-dependency slice so a later
dispatch can proceed without re-deriving scope. Landed:

- **D2's doc half**: `layout.realized` added to the D96 kind
  vocabulary in `../design/20-solver-abstraction.md` sec. 8.3, and to
  the feldspar channel contract kind list
  (`../../feldspar/docs/feldspar/09-model-integration.md` sec. 4),
  in the same change (WO body's explicit requirement). `PayloadRef`
  itself (`crates/regolith-oblig/src/payload.rs`) needs no code
  change for a new kind string -- `kind: String` is unconstrained,
  confirmed by reading the struct.
- This status/progress note.

**Escalation -- scope, not ambiguity.** Deliverables 1, 3, 4, 5 are
each independently substantial (a new schemars-derived Rust schema
promoted from the Python forward contract at
`python/regolith/realizer/mech/interpreter.py::RealizedGeometry` +
`regolith.realizer.mech.model` consumer; a NEW `RealizedLayout`
schema with no existing Python source of truth yet since WO-24's
layout half only has KiCad-unavailable deferral fixtures; the
`regolith-api::Session`/FFI realized-input channel per AD-4's coarse
one-map-of-bytes crossing; `regolith-lower::extract` in-pipeline
wiring per D128; the orchestrator staged fixed-point loop with
INV-10 termination proof; a `SCHEMA_VERSION` bump + `make schema` +
golden corpus re-key). None of these has a design ambiguity blocking
it (AD-25/D128 already answered every open question this dispatch
found) -- the remainder is implementation volume across
`regolith-oblig`, `regolith-api`, `regolith-py`, `regolith-lower`,
`compiler.py`, and three Python realizer/orchestrator modules, each
needing its own hierarchical plan and its own `make check` cycle.
Recommendation for the next dispatch: split by deliverable along the
WO's own numbering (1+4 mech geometry promotion as one unit, 2+4
elec layout schema+emission as a second, 3 the FFI channel as a
third gating both, 5 the staged loop last since it depends on 3).

Remaining (not started, tracked here so nothing is silently
dropped): deliverables 1, 3, 4, 5; deliverable 6's non-vocabulary
doc updates (AD-25 "implemented where landed" flip, regolith/08
sec. 1 "decided" -> "landed", design/22's forward-contract section
marked promoted, WO-22/24/34/25 amendment notes); every acceptance
criterion except the D2 vocabulary note.

## Non-goals

- New realizer capability (feature coverage, KiCad-real runs --
  WO-22/WO-35 territory; this WO promotes what exists).
- Solving anything (pack territory).
- Firmware/ELF map data as an IR (future; enters by the AD-25 rule
  when WO-37 needs it -- record, do not pre-build).
- Parametric geometry descriptors (`geometry.parametric` is a
  DISTINCT existing kind; untouched here).
- Salsa-style incremental re-lowering (the staged loop re-runs the
  whole pure pipeline; artifact-level incrementality via content
  addressing is already the AD-2 risk-register position).
