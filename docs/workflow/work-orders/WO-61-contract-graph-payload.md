# WO-61: ContractGraphPayload + the contract-graph sheet (WO-58 D2 completion)

Status: todo
Depends: WO-55 (integrated first: this WO owns the ONE permitted
follow-up SCHEMA_VERSION bump, D167 -- serialize strictly after
WO-55's; if WO-55 lands 21, this lands 22). WO-58 deliverables
1/3/5-7 (landed: layout helper, backend wiring, audit conventions --
REUSE them).
Language: Rust (`regolith-ir`/`regolith-lower`/`regolith-api`
emission + `regolith-oblig` schema) + Python (the
`diagram.contract_graph` producer WO-58 escalated).
Spec: docs/spec/toolchain/29-interaction-surface.md sec. 1.6
(NORMATIVE), 23-lowering-output-surface.md (AD-22 -- this WO is the
F96-pattern producer completion), 00-architecture.md AD-17/AD-22/
AD-27/AD-31, design-log 2026-07-09-cycle-30 D165/D167, and WO-58's
ledger (the field-by-field gap verification -- read it verbatim).

## Goal

`BuildPayload` gains a readable L2 surface (`ContractGraphPayload`:
interfaces, frames, matings, connections BY NAME, with promise-slot
counts and connection kinds -- the `FlownetPayload` precedent), and
WO-58's escalated `diagram.contract_graph` producer lands on it.

## Deliverables

1. Schema (`regolith-oblig`): `ContractGraphPayload` -- nodes
   (artifact/interface names, kinds, promise-slot counts), edges
   (connection/mating kind labels), stable source-ordered; the ONE
   serialized follow-up bump per D167. `make schema` regenerated.
2. Emission: `regolith-lower` populates it from the contract-IR pass
   (AD-17 pass order; one tracing span); `regolith-api::BuildPayload`
   carries it; FFI/facade untouched beyond the payload field (AD-4
   coarse boundary holds).
3. Producer: `diagram.contract_graph` per WO-58's spec text --
   node-and-edge DrawingModel sheet via the LANDED layout helper
   (`layered_positions`), wired through the same ship-spec
   `"drawings"` block convention (`"track": "contract_graph"`).
4. Golden + audit: one multi-artifact corpus design's contract graph,
   deterministic across two runs, drafting-audit-clean, structural
   assertions (one node per interface/artifact, one edge per
   connection) per WO-58's test conventions.
5. Docs: WO-58 ledger cross-note (D2 completed here), guide sec. 7a
   extension, WO ledger. Flip BOTH Status lines (this WO; WO-58's D2
   mention) in the same change.

## Acceptance criteria

- `regolith debug ir` (or the payload JSON surface) shows the
  contract graph for a corpus design; names are readable, not hashes.
- Sheet byte-identical across two runs; audit rules pass; provenance
  on every rendered name (schema-enforced).
- SCHEMA_VERSION exactly one above WO-55's landed value; `make
  schema` drift check green; `make install` then `make check` green.
