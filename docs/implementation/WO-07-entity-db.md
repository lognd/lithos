# WO-07: Entity database + predicted deltas

Status: done
Depends: WO-05, WO-06
Language: Rust (`regolith-sem`) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/05 sec. 1, 3, 5; hematite/02 sec. 4; substrate/06

## Goal

The entity DB both domains bind: entities, ownership, regions,
symmetry orbits, and per-construct predicted deltas.

## Deliverables

- `Entity` (internal id -- NEVER serialized into source-facing output,
  origin construct, owner, kind, measures dict, tags, orbit id) and
  `EntityDb` (immutable snapshots; a commit produces a new snapshot).
- `Region` entities with exclusion/arbitration policy (substrate/05
  regions rule).
- `PredictedDelta` (creates / modifies / consumes / regions touched /
  symmetry contribution) -- the declaration every feature/statement
  class supplies; a `data_dependent: bool` flag routes to
  post-realization verification.
- Symmetry: group representation (Cn, Cinf, permutation orbits),
  conservative intersection on commit, orbit splitting on
  symmetry-breaking deltas.
- Content addressing: snapshot hash stable under key order.

## Acceptance

- Scenario tests: pattern commit produces one orbit; off-pattern
  feature splits it; `any` legality queries answer per substrate/05
  sec. 5 (via a temporary direct API; the query engine lands in
  WO-08).
- Snapshot immutability enforced (mutation attempts are programmer
  errors).
