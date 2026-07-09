# WO-61: ContractGraphPayload + the contract-graph sheet (WO-58 D2 completion)

Status: done (SCHEMA_VERSION 21 -> 22; ContractGraphPayload +
diagram.contract_graph landed; make check green in the dispatch
worktree, modulo two pre-existing/out-of-scope failures named in the
ledger below)
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

## Ledger (this dispatch)

**Done.**

- D1 (schema): `regolith-oblig/src/contract_graph.rs` --
  `ContractGraphPayload { nodes: Vec<ContractNode>, edges:
  Vec<ContractEdge> }`, domain tag `"contract_graph"`, its own
  `content_digest`. `SCHEMA_VERSION` 21 -> 22 (`regolith-util::canon`,
  re-exported unchanged per AD-18); `make schema` regenerated and
  committed (`python/regolith/_schema/models.py`/`__init__.py`).
- D2 (emission): `regolith-lower::contracts::build_contract_graph_payload`
  projects the EXISTING `ContractGraph` (interfaces + every system's
  matings/parts) in the SAME `lower.contracts` span (factored into
  `run_contracts_pass`, shared by both pipeline functions, AD-17).
  `BuildPayload.contract_graph: ContractGraphPayload` is a SINGLE,
  always-populated (never `Option`) field -- one graph per build, not
  one per named subject like `flownets`/`frames`/`harnesses` (those
  have their own per-file elaboration seam; the contract graph is the
  whole build's L2 surface, matching the WO's own "readable L2
  surface" framing). No FFI/facade change beyond the new payload
  field (AD-4 coarse boundary holds; `regolith-py` untouched).
- D3 (producer): `regolith.backends.drawings.producers.contract_graph`
  -- one symbol entity per node (interface/artifact, annotated with
  name + kind + promise-slot count for an interface), one
  orthogonally-routed polyline per mating edge via the WO-58
  `layered_positions` helper, one edge annotation citing the mating's
  name and its declared-effects-derived kind label. Wired through
  `DrawingsBackend`'s existing `"drawings"` block convention
  (`DrawingSpec(track="contract_graph")`, `BackendInputs.contract_graph`);
  `regolith.backends.ship.ship` derives it from
  `report.final.payload_json`'s `"contract_graph"` key (no
  `PayloadRef` exists for this payload either, same as `harnesses`),
  explicit-argument override supported.
- D4 (golden + audit): `tests/backends/test_drawings.py`'s
  `TestContractGraphProducer` -- deterministic across two runs,
  passes the WO-50 drafting-audit rule pack, one symbol per node / one
  3-segment polyline per edge (structural assertions, this repo's own
  in-code-assertion "golden" precedent per WO-58's D6 note). Corpus
  goldens regenerated (`tests/golden/data/*.json`): every content
  digest folds `SCHEMA_VERSION` (AD-18), so the 21->22 bump changes
  every obligation/snapshot hash even though no lowering BEHAVIOR
  changed -- verified by re-running `test_golden_corpus_is_deterministic`
  and diffing that only hash VALUES (never structure/counts) moved.
- D5 (docs): this ledger; WO-58's own ledger cross-note below; Status
  lines on both WOs flipped in this change.

**Escalations/cuts:** none needed -- WO-58's own D2 gap analysis
(`ContractGraph` has no readable payload) is exactly what D1/D2 above
close.

**Pre-existing, out-of-scope, NOT touched this dispatch** (found while
running `make check`, neither caused by nor fixed by this WO's diff --
verified by inspection: neither touches `regolith-ir`/`regolith-lower`/
`regolith-oblig`/`regolith-api`/`regolith.backends`, this WO's only
surface):

- `cargo test -p regolith-ls`: `workspace::tests::
  falls_back_to_opened_folder_when_no_manifest_found` fails in this
  sandbox (`/tmp` vs a symlink-resolved temp path mismatch) --
  environment-specific, `regolith-ls` untouched by this diff.
- `tests/test_cli_optimize.py::test_optimize_writes_lockfile_with_optimize_cause`
  and `::test_optimize_resume_reuses_a_prior_trace_digest` fail
  (`regolith.lock`/payload-store files not found in `tmp_path` despite
  the CLI's own log lines claiming success) -- lives entirely in
  `regolith.cli.app`/`regolith.orchestrator.optimize` (WO-55/56/57
  territory, explicitly the parallel agents' surface per this
  dispatch's own scope note), not this WO's Rust/backends surface.
