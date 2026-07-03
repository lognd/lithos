# mill Lowering Stack

> Spec 0.13. The mech binding of the generic stack
> (`../substrate/08-lowering-architecture.md`).

## 1. The stack

```
L0  SOURCE        .mill text + stdlib (materials, processes, matings) + imports
 |    parse, format-normalize
L1  TYPED AST     names resolved; quantity/unit checking; value-source and
 |                tolerance grammar; ==-ban; profile walks parsed
 |    lower contracts
L2  CONTRACT IR   <- "contracts live here" -- GEOMETRY-FREE
 |      graph of: frames, interfaces (roles/promise slots), matings (align,
 |      dof, couples, effects-as-model-refs), boundary conditions, budgets,
 |      claims, config space
 |      checks/solves: DOF and Gruebler ledger - capability/fit lookups -
 |      rigid statics + promise stiffness network (incl. redundancy/misfit) -
 |      derived-contract authoring (envelopes over config and environment
 |      corners) - budget arithmetic - interface-first verification
 |    per-part lowering
L3  FEATURE IR    stages, setup order, scope DAG, features as predicted
 |                entity-DB deltas
 |      checks: query typing/cardinality - ownership/borrows/merge-signs -
 |      monomorphization sweep - symmetry groups/orbits - sketch DOF
 |      ledgers and branch-pin completeness - topology-boundary domains -
 |      DFM eager propagation (resolves `free`) - T1 conformance
 |    kernel evaluation (only now does OCCT run)
L4  GEOMETRY IR   B-rep per stage; measured entity DB (imports enter HERE,
 |                skipping L3)
 |      checks: post-geometry prediction verification - T2 conformance -
 |      mass properties - meshes - cavity derivation
 |    emit proof work
L5  OBLIGATIONS   <- "proofs live here" -- self-contained, serializable
 |      from L2 (assembly/connection/state claims) and L4 (part claims,
 |      T3, manufacturability/cost via planner models -- the CAM plan is
 |      evidence)
 |      harness: margin-driven model selection -> EVIDENCE -> cache
 |      orchestrator: lazy loop over (eager-feasible AND topology-
 |      preserving) space, sensitivity-guided; conflict-driven allocation
 |      search for setups/process planning; lockfile authorship
L6  BACKENDS      STEP/AP242+PMI (allocated tolerances ON the model),
                  drawings, G-code (serialized CAM-plan evidence, never
                  computed here), BOM (vendor refs), ledger report
```

Structural payoffs: **interface-first = running L0->L2 only** (a full
system architecture verifies with zero parts); **verify-only import =
entering at L4** (zero feature machinery needed).

## 2. Construct x level matrix

| construct | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|
| dimension (any source) | typed qty | -- | constraint-graph node; eager resolution; topology domain | concrete value | sensitivity target | PMI on model |
| tolerance / fit | grammar | capability check; budget allocation; interval expansion | -- | T2 measurement | misfit loads; corner inputs | PMI, drawings |
| profile | walk+constraints AST | -- | sketch DOF ledger; branch check; solve | evaluated curve | -- | -- |
| feature | -- | -- | entity-DB delta; ownership; DFM | B-rep op; prediction check | -- | toolpath hint |
| setup / `hold:` | decl | -- | order check; refixture tolerance injection | fixture frames | -- | setup sheets |
| query | typed expr | -- | cardinality + orbit check; symbolic resolve | re-resolve/measure | -- | -- |
| datum | name | frame element | borrow-exempt ref | concrete frame | obligation frames | drawing datums |
| interface | decl | frame+roles+promise slots; semver unit | T1 conformance; permanent borrows | T2 conformance | T3 obligations | -- |
| mating | decl | align/DOF/couples; effects -> model refs; capability | -- | contact geometry (escalation) | state-claim obligations; effect-load evaluation | assembly drawing |
| assembly | decl | ledger; statics; network; derived contracts; budgets | -- | -- | claim obligations | BOM |
| boundary | typed qty | corner sets; spectra | -- | -- | obligation `given` | report |
| config var (`pivot.theta`) | typed var | Gruebler; envelope-over-domain | -- | swept instances | `forall` domains | motion docs |
| claim (`require`) | expr | attach to graph | -- | -- | obligation; evidence | ledger |
| `todo!` / `assume!` | mark | promises still solve | skip conformance | -- | unbacked-evidence ledger | release gate |
| material / contact | ref | f(T), mu intervals into models | DFM params | density -> mass | model inputs | BOM specs |
| import stage | path+hash | retro-impl contracts | **skipped** | measured entity DB | obligations | -- |
| vendor part | ref | interface bundle | -- | envelope solid only | catalog evidence | BOM line |
| `pieces:` / joining stage | decl | -- | piece placement (`align:`), weld deltas, distortion scatter | unified multi-piece B-rep | weld obligations | weld symbols, BOM |
| `variant` | typed axis | contracts per point | monomorphized construction branches | per-variant realization | swept obligation over the axis | per-variant outputs |
| `waive` | parsed, basis checked | claim/rule matching | scope query resolution | -- | acceptance record on evidence | ledger + report |
| `policy:` | parsed | forbid = domain cuts | prefer = search order | -- | -- | lockfile annotations |
| `extern` (impl/profile/plan/image) | ref+hash+format | contract binding | transparent: elaborated IR | opaque: measured/evidenced entry | conformance obligations; plan check mode | serialized as-is |

## 3. Coherence against the mantras

- **Unambiguous:** every construct has exactly one home level per
  semantic job (contracts L2, ownership L3, measurement L4, proof L5).
- **Intent-based:** the value-source grammar makes "who decides and why"
  the literal syntax of every number; `boundary:` is the only place
  humans assert physical truth; L2-before-L3 ordering is
  intent-before-geometry.
- **User-friendly:** check placement = cheapest tier wins; the two
  on-ramps (contract-first, import-at-L4) are pipeline shortcuts, not
  modes.
