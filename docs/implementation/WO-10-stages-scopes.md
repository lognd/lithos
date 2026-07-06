# WO-10: Stages, scopes, commit model

Status: done
Depends: WO-07, WO-09
Language: Rust (`regolith-sem`) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: regolith/06 (all); hematite/02 sec. 2-4, 7a (pieces)

## Goal

The execution model: stage pipelines, concurrent scopes with snapshot
reads, commit/merge, bare statements, setups, pieces.

## Deliverables

- Stage graph: `from=` (single parent), `joins=[...]` (multi-piece
  parents), `import(path) [sealed]` entry stages; per-stage process
  binding (capability table lookup stubs -- table data arrives with
  WO-16).
- Scope DAG within stages/setups: `then [label] [on region]:`, `seq:`
  sugar (+ the independent-statements lint), bare statements as
  single-statement scopes.
- Snapshot-read enforcement: sibling-export references = compile
  error naming the later-scope fix.
- Setups: ordered, `hold:` consumption, `flip about` (refixture
  tolerance injection recorded as a stage-level scatter entry),
  omitted-setup = planner-allocated marker.
- `pieces:` unified DB with per-piece provenance; joining-stage
  `align:` records (reusing the mating align AST from WO-05).
- Stage-exit resolution points for impl binding (SEAM-1 rule 1).

## Acceptance

- pillow_block and weldment_frame examples type through L3 statically
  (predicted deltas only, no geometry).
- Sibling-reference and cross-stage-unqualified-name violations produce
  the documented diagnostics.
