# regolith-sem

The semantic layer: entity database, ownership/borrow checking,
symbolic queries, stage/scope execution model, symmetry orbits, the
sketch DOF ledger, and the continuous/discrete converter graph. Runs
entirely on the pre-realization IR using per-construct predicted deltas
(WO-07) -- the anti-ambiguity checks here (WO-08..WO-11) all execute
before any realizer exists. Language-spec semantics are pointed at
rather than restated: `docs/spec/regolith/05-ownership-and-queries.md`,
`docs/spec/regolith/06`, and `docs/spec/regolith/13-invariants.md`
(INV-16) are the normative source; this doc is a symbol-level index
into that design.

## Entity database

<a id="entity-db"></a>
### `entity`

The entity database: the artifact's committed state as a set of
entities with owners, regions, and symmetry orbits (`docs/spec/regolith/
05-ownership-and-queries.md` sec. 1, 3, 5). Entity IDs are internal
only -- never serialized into source-facing output; all source
references resolve through queries (WO-08). The DB is a sequence of
immutable snapshots: a commit produces a new snapshot, never mutates
one in place.

## Ownership and borrowing

<a id="ownership"></a>
### `ownership`

The anti-toponaming machinery: single ownership, borrows, merge signs,
and region conflicts, all evaluated on predicted deltas before any
realizer exists (`docs/spec/regolith/05-ownership-and-queries.md` sec. 3,
`docs/spec/regolith/06` sec. 2). A borrow conflict is reported
bidirectionally, at both the modifier and the borrower (SEAM-1,
hematite/03 sec. 2.1); same-sign overlaps auto-merge, mixed-sign
overlap in one scope is a hard error. The elec binding treats "one
driver per net" as ownership, with `arbitrate` as a declared join.

## Queries

<a id="query"></a>
### `query`

Method-chain queries: static validation and symbolic resolution
against entity-DB snapshots (`docs/spec/regolith/05-ownership-and-queries.md`
sec. 2, 5). Validation runs statically (predicate names, entity kinds,
operand types, cardinality) over the pre-realization IR; resolution is
symbolic against a snapshot. A cardinality mismatch is an E0301-family
diagnostic carrying the matched-entity table; a broken-orbit `.any` is
E0502 with pinning suggestions.

<a id="resolve"></a>
### `resolve`

L1 name/type resolution: for a bare name referenced in an expression,
decides the quantity class of the symbol it resolves to
(`docs/spec/regolith/05-ownership-and-queries.md` sec. 2,
`docs/spec/regolith/02-quantity-core.md` sec. 2 -- `==` on a continuous
quantity is a compile error, INV-17). Deliberately narrow: resolves
only the quantity class of a declaration's own directly-declared
fields; anything unclassifiable comes back `Unknown` and never
triggers the ban, so there are no false positives on discrete values.

## Execution model

<a id="stage"></a>
### `stage`

Stage pipelines, concurrent scopes with snapshot reads, commit/merge,
setups, and pieces (`docs/spec/regolith/06` all, `docs/spec/hematite/02`
sec. 2-4, 7a). Scopes read committed snapshots only: referencing a
sibling scope's exports before it commits is a compile error naming
the later-scope fix. Impl binding resolves at stage exit (SEAM-1 rule
1); per-stage process binding looks up a capability table whose data
arrives with WO-16, so this module currently stubs that lookup slot.

## Profile and sketch ledger

<a id="profile"></a>
### `profile`

Profile static checks (WO-11 ledger half): branch-pin completeness and
the sketch DOF ledger, with no constraint solving
(`docs/spec/hematite/02` sec. 5). The sketch degree-of-freedom ledger is
entity freedoms minus applied constraints; the remainder must be zero
or accounted for by declared free variables (value sources). Exports
are modeled as placeless datums exposed only through an instantiation
context -- referencing an export through the profile value rather than
a feature is an error naming the anchoring rule.

## Symmetry

<a id="symmetry"></a>
### `symmetry`

Symmetry groups and orbits: the machinery behind `x.any`
(`docs/spec/regolith/05-ownership-and-queries.md` sec. 5). The DB tracks
the artifact's symmetry group, computed conservatively from
per-construct declared contributions (the intersection): sound but
conservative, so an undetected true symmetry may cause a spurious
`.any` error, but a false symmetry is never asserted. Later constructs
break symmetry, splitting orbits.

## Net core and converter graph

<a id="net-core"></a>
### `net_core`

AD-23: one net core, per-discipline plugins. The net ledger machinery
(terminal collection, per-net imposer counting, deterministic
traversal) lives once here, parameterized by a discipline that
contributes only a check predicate and diagnostic message. `elec`
(cuprite/03 sec. 2, at most one voltage-imposing terminal) and `fluid`
(fluorite/02 sec. 4, at least one pressure imposer per subnet) are the
two instances riding the same traversal; before this module the elec
check duplicated the same logic in Python (AD-23, D100).

<a id="converter"></a>
### `converter`

The continuous/discrete converter graph and the INV-16 acyclicity
check (`docs/spec/regolith/13-invariants.md` INV-16,
`docs/spec/cuprite/03-behavioral-layer.md` sec. 1a). INV-16: no
algebraic loop crosses the continuous/discrete boundary. Two
independent halves realize the proof: the zero-order-hold delta-by-type
rule (every converter port samples pre-instant and applies post-instant,
so a domain-crossing edge cannot participate in a zero-delay cycle),
and a within-domain acyclicity check over combinational (`=`) networks
inside one clock/continuous domain (a cycle with no delta to break it
is E0105).
