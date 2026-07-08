# Execution Model: Stages, Scopes, Commit

> Regolith spec. HDL-style concurrency for construction: within a scope,
> all statements are concurrent; state advances only at scope boundaries.
> In the elec track this is native (it *is* how hardware description
> works); the mech track adopted it in spec 0.2 and it is one of the
> strongest "feel the same" carriers between the languages.

## 1. Stages

An artifact is built by a pipeline of **stages**, each bound to a process
module with its own capability table and rule pack:

```
# mech: real parts are process sequences
stage cast:     process=die_cast(...)
stage machined: process=cnc_mill(axes=3), from=cast

# elec: a board is also a process sequence
stage bare:      process=pcb_fab(jlc_2l)
stage assembled: process=smt_assembly(...), from=bare
stage programmed: from=assembled          # firmware/bitstream load is a stage
```

- Constructs must come from the stage's process vocabulary.
- Stage boundaries are ownership checkpoints: a later stage may modify
  earlier state (machining a casting; populating a bare board),
  transferring ownership, subject to borrow rules -- interface-bound
  entities stay protected across stages.
- Values and demands are stage-qualified; capability checks run against
  the stage that *finishes* the controlling entity.
- **Imports are stages:** `stage src: import(path) [sealed]` -- foreign
  geometry/netlists enter the pipeline at the realized level, skipping
  construction IR entirely. `sealed` = no later stage may modify (the
  verify-only ladder rung). One form for all import depths.
- **Artifact-position imports:** an import bound directly in a
  system's parts list (`plate: import(path) sealed`) is shorthand for
  an artifact with exactly one import stage, named **`src`** by rule --
  retro-contract impls on it qualify their bindings with `src.`.

## 2. Scopes

Within a stage, construction happens in labeled, optionally region-guarded
concurrent scopes:

```
then [label] [on <region>]:
    a = ...
    b = ...        # a and b are concurrent; text order irrelevant
then:
    c = ...        # sees a and b committed
```

Rules:

1. **Snapshot reads.** Every statement in a scope queries the state at
   scope entry. A statement's exports are visible only in *later* scopes;
   referencing a sibling's exports is a compile error.
2. **Merge at commit.** Effects merge at the scope boundary:
   - *Same-sign overlap* (two cuts on one region; two loads on one net
     within ratings): commutes; merge is automatic. Ownership of the
     contested region must be declared (`merge(a over b)`) only if a later
     query references it -- lazy ordering.
   - *Mixed-sign overlap* (an add and a cut contest a region; two drivers
     contest a net): does not commute -- always a hard error in one scope.
     Resolve by sequencing into separate scopes, explicit
     `merge(a before b)`, or (elec) a declared arbitration construct.
3. **Dependency depth is visible.** Scope nesting depth *is* the
   dependency depth. Shallow designs are the path of least resistance by
   construction.
4. **Borrow checking is per-scope:** set intersection of modified-entity
   sets against the entry snapshot.
5. **Region guards compose with placement.** Inside `then L on R:`,
   placement defaults to R and out-of-region selection is a static error;
   the label feeds diagnostics ("in scope 'seal_prep'").

`seq:` is sequential sugar -- each statement its own commit; a lint nudges
independent statements back into one `then:`.

**Bare statements** [SETTLED, example-driven]: a construction statement
written directly at stage/setup level (outside any `then:`) implies its
own single-statement scope. Very sequential artifacts read linearly
without one-feature `then:` boilerplate; grouping into `then:` remains
the way to state concurrency. (Adopted after `examples/mech/
pillow_block.hema` made the boilerplate visible; formerly a mech
watchlist item.)

There is no `.original` / `.current` distinction (retired): a query means
"at my scope's entry snapshot," full stop. Pre-modification references are
served by datums.

## 3. Elec-specific note: construction vs behavior

The scope/commit model governs **construction** (building the artifact:
instantiating blocks, declaring nets, placing, routing). The elec track
additionally has **behavioral time** (what the circuit does when running),
which is a different axis entirely -- `on <event>:` bodies, continuous relations, and
clock domains live in the behavioral layer (`cuprite/03-behavioral-layer.md`),
not in construction scopes. The regolith deliberately keeps these
separate: construction concurrency is about unambiguous building; behavioral
concurrency is about modeling physics. They share the snapshot-read
mindset but not machinery.
