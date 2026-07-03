# Principles

> Substrate spec. Domain-neutral. Status: [SETTLED] unless marked.

## 1. The three mantras

Every design decision in either language is justified against these three,
in this priority order when they conflict:

| mantra | meaning | enforced by |
|---|---|---|
| **Unambiguous** | every reference, choice, and behavior has exactly one valid interpretation | query cardinality typing; single ownership + borrows; orbit-checked `any`; explicit merge ordering; single-driver rules; monomorphization of integer domains; banned `==` on continuous quantities; banned inheritance |
| **Intent-based** | the human declares purpose and boundary truth; the system derives consequences | boundary-only human inputs; the value-source grammar; requirements as claims; contracts before implementations; process-aware construction vocabularies |
| **User-friendly** | the cheapest tier catches each error, constructively, in the user's vocabulary | static-before-structural-before-physical check placement; constructive diagnostics with concrete fixes; margin-driven fidelity (no accuracy knobs); lockfile-visible defaults; `todo!`/`assume!` as honest state |

## 2. The defaults test

A default behavior is permissible iff it is:

1. **conservative** -- the default can cause a spurious failure, never a
   silent pass;
2. **local in effect** -- changing the input that triggered it perturbs
   only nearby results;
3. **lockfile-materialized** -- the resolved value appears in the lockfile
   where a review diff will surface it.

Anything failing any prong must be an explicit declaration in source. This
single law replaces per-feature debates about "smart defaults."
(Compliance is itself audited: INV-26 in `13-invariants.md`, where
every guarantee in this document lives with its mechanism and proof
argument.)

## 3. Design principles

1. **Name intent, not implementation.** No entity indices, no pin numbers,
   no topology hashes in source. All references are semantic queries
   resolved against current design state.
2. **Ambiguity is a compile error.** A reference with multiple valid
   interpretations fails the build with a constructive diagnostic. `.all`,
   `.only`, `.any` are explicit escape hatches with checked semantics.
3. **Single ownership, explicit joins.** Every entity has exactly one
   owner; selecting or acting across ownership boundaries requires explicit
   join syntax.
4. **Promises, not actuals.** System-level computation uses only declared
   contract values. Consuming a computed actual is a named opt-in recorded
   as a dependency edge in the build graph.
5. **Intervals, not points.** Tolerances, component scatter, environment
   ranges, and process corners propagate as intervals; every check is
   evaluated at its own worst-case corner.
6. **Claims need evidence.** Every physical claim ends in exactly one of:
   discharged, violated, indeterminate, or explicitly assumed. "Cannot
   tell" is never conflated with "fails."
7. **Static before structural before physical.** The cheapest tier that
   can catch an error owns it (see `08-lowering-architecture.md`).
8. **Everything is a module.** Process packs, rule packs, materials,
   component catalogs, physics models, and interface libraries are
   versioned imports, not built-in magic.

## 4. The four-component architecture

Each domain's system splits into four components so that each can be
built, tested, and contributed to by someone who understands only that
component:

```
+------------------------------------------------------------+
| QUANTITY CORE          shared vocabulary (the "ABI")       |
|   namespaces, quantities, units, tensor ranks, intervals   |
+--------------+-----------------------------+---------------+
               |                             |
+--------------v--------------+ +------------v---------------+
| MODELING LANGUAGE           | | VERIFICATION HARNESS       |
|  what is CLAIMED            | |  how claims are CHECKED    |
|  entities, ownership,       | |  physics models, validity  |
|  contracts, requirements,   | |  domains, error models,    |
|  constraint graph           | |  solvers, search           |
|                             | |                            |
|  emits: OBLIGATIONS --------+-+--> returns: EVIDENCE       |
+--------------+--------------+ +------------+---------------+
               |                             |
+--------------v-----------------------------v---------------+
| ORCHESTRATOR                                               |
|   optimization loop, caching, lockfile, scheduling,        |
|   the API surface for CLI / CI / future UI                 |
+------------------------------------------------------------+
```

- **Quantity core.** Owned by neither big component; both depend on it.
  Changes to it are breaking changes everywhere. Shared *across domains*:
  `mech.stress` and `elec.voltage` live in one namespace system, which is
  what makes cross-domain contracts expressible later.
- **Modeling language.** Everything semantic. Performs all *non-physical*
  checks itself (ownership, cardinality, units, ledgers, capability-table
  lookups, budget arithmetic). Compiles physical claims into obligations.
- **Harness.** A registry of models -- analytical and numerical -- each
  with a validity domain, error model, and cost. Discharges obligations,
  returns evidence. The boundary is *physics*, not expense: closed-form
  physics lives here too.
- **Orchestrator.** Owns all state and iteration: the free-variable loop,
  evidence caching, the lockfile, parallel discharge. Compiler and harness
  are pure functions; the orchestrator composes them.

The two languages share one quantity core, one obligation/evidence schema,
one orchestrator, and one harness *architecture* (the model registries are
domain-specific packs inside it). Only the modeling languages differ.

## 5. Why text

- Diffable, reviewable, version-controllable.
- Statically checkable without rendering or simulating: a part or block
  can be written and checked against fixed contracts locally. This is what
  makes LLM generation of designs a verifiable loop instead of a leap of
  faith.
- GUI, LSP, previews, and rendered "datasheet" views are projections of
  the text, never a second source of truth.
