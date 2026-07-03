# The Lowering Architecture

> Substrate spec. The generic seven-level stack. Each domain binds L3 and
> L4 to its own representations; L0-L2 and L5-L6 are shared shapes with
> domain-specific content. MLIR is the architectural prior art.

## 1. The generic stack

```
L0  SOURCE          text + stdlib (registries, processes, connections) + imports
 |    parse, format-normalize
L1  TYPED AST       names resolved; quantity/unit checking; value-source and
 |                  tolerance grammar; ==-ban; domain-specific surface parsing
 |    lower contracts
L2  CONTRACT IR     <- "contracts live here" -- IMPLEMENTATION-FREE
 |      graph of: frames, interfaces (roles/promise slots), connections
 |      (align, ledger entries, couples, effects-as-model-refs), boundary
 |      truth, budgets, claims, config space
 |      checks/solves: ledgers - capability lookups - static system solve
 |      on promises - derived-value authoring over corners - budget
 |      arithmetic - contract-first verification
 |    per-artifact lowering
L3  DESIGN IR       the domain's constructive representation, pre-realization
 |      mech: feature graph (stages, scope DAG, predicted entity deltas)
 |      elec: behavioral/structural blocks (the HDL-superset layer)
 |      checks: query typing/cardinality - ownership/borrows/merge -
 |      monomorphization sweep - symmetry orbits - rule-pack eager
 |      propagation (DFM/DRC/ERC; resolves `free`) - T1 conformance
 |    realization (only now do expensive engines run)
L4  REALIZED IR     the concrete artifact model, measured
 |      mech: B-rep per stage (geometry kernel); measured entity DB
 |      elec: bound netlist + placed/routed layout + synthesized logic;
 |            extracted parasitics as the measured entity DB
 |      imports enter HERE, skipping L3
 |      checks: post-realization prediction verification - T2 conformance -
 |      mass/parasitic extraction - derived entities (cavities; coupled nets)
 |    emit proof work
L5  OBLIGATIONS     <- "proofs live here" -- self-contained, serializable
 |      from L2 (system/connection/state claims) and L4 (artifact claims, T3)
 |      harness: margin-driven model selection -> EVIDENCE -> cache
 |      orchestrator: lazy loop over feasible space; lockfile authorship
L6  BACKENDS        fabrication and documentation outputs
        mech: STEP/AP242+PMI, drawings, G-code, BOM, ledger report
        elec: gerber/drill, pick-and-place, netlists, bitstreams,
              firmware images, BOM, datasheet render, ledger report
```

## 2. The check-placement law

**Static before structural before physical.** Every check lives at the
cheapest level that can catch its error class, and nothing expensive runs
until everything cheaper has passed:

- L1: types, units, grammar.
- L2: contract consistency, ledgers, budgets -- before any artifact
  exists.
- L3: reference validity, ownership, rule packs -- before any kernel,
  synthesizer, or router runs.
- L4: predicted-vs-actual verification -- before any physics runs.
- L5: physics, with the cheapest adequate model.

A large class of errors is caught without computing a single boolean
operation or running a single simulation step.

## 3. Structural payoffs (visible only at this altitude)

- **Contract-first = running L0->L2 only.** A full system architecture
  verifies with zero artifacts implemented. This is the team and LLM
  work-breakdown mechanism.
- **Verify-only import = entering at L4.** Foreign geometry / netlists
  get contracts retrofitted and verified with zero construction machinery.
  The adoption wedge is literally a pipeline shortcut.
- **Incremental verification falls out of content addressing.** Promise-
  backed system obligations survive artifact edits; only obligations whose
  subject snapshot changed re-run.

## 4. Manual lowering and external linkage [SETTLED in shape, cycle 3]

The stack is not derive-only. At every lowering edge the human may
**hand-write the lower level** or **link foreign content**, and the
system's job collapses from *deriving* the lower level to *checking
conformance* of the supplied content against the upper level's
contract. Deriving is expensive and heuristic; checking is cheap and
sound. This is the compiler/linker model: the contract is the header,
the foreign content is the object file, and the boundary is checked.

**Two mechanisms, deliberately distinct:**

- `stage <s>: import(path) [sealed]` -- foreign data **merges** into
  this artifact's pipeline: it becomes this artifact's realized state,
  gets a measured entity DB, and later stages may modify it (unless
  sealed). `#include` for artifacts.
- `by extern(<ref>, <format>)` -- a foreign artifact **links** against
  a contract and stays foreign: own hash, own lifecycle, possibly
  opaque (encrypted vendor IP). The fifth impl strategy, beside
  `by spec / composing / circuit / vendor`. `extern` symbols for
  artifacts.

**Entry points per level:**

| level | hand-write (in-language) | external link | the boundary check |
|---|---|---|---|
| L2 | interfaces + promises (normal authoring) | `vendor(ref)` -- this always was L2 linkage | evidence clauses, trust tiers |
| L3 | the design languages themselves; explicit setups, explicit structural authoring | `by extern` on *transparent* formats: Verilog/VHDL for a block, SPICE netlists for a circuit, DXF outlines for a `profile` | elaborated into design IR; full static checks run; conformance to `spec:` is the ordinary equivalence obligation |
| L4 | elec structural layer (writable directly); mech: none -- geometry only via kernel or import | `import(path)` stages; `by extern` on *opaque/realized* formats: compiled netlists, prebuilt firmware (`image fw: extern("fw.elf", elf)` -- map data becomes the measured DB), encrypted IP | T2 measurement where measurable; what cannot be measured must be covered by evidence clauses or the ladder (12) |
| L5 | -- | `by test(ref)`: supplied evidence is extern-at-L5, named as such | trust tiers; declared error models |
| L6 | plan pins (`sequence:`, explicit setups) | supplied plans: `plan: extern("op10.nc", gcode_fanuc)` | the planner runs in **check mode** -- verifying a given plan (reach, collision, completeness) is cheaper than generating one; residue discharged `by test` (first article) |

**Rules:**

1. **No dead uppers.** When both levels are written, the lower must
   conform to the upper: a hand-written realization that contradicts
   its `spec:` is a *failing equivalence obligation*, never a silent
   spec-shadow. If only the lower level is written, contracts are
   authored at that level (the brownfield posture) -- there is no
   requirement to write levels you do not want.
2. **Transparent vs opaque is the format's declaration.** Transparent
   formats elaborate into design IR and get the full static tier;
   opaque ones enter measured-or-evidenced. Format readers ship as
   packages (`formats` kind, `11-packages-and-stdlib.md`),
   hash-pinned, so linkage is reproducible.
3. **Check mode is a first-class planner obligation.** A supplied plan
   is pinned like any planner output (lockfile cause:
   `extern(<ref>)`); its claims are discharged by check-mode models or
   by test evidence -- never by the fact of having been supplied.
4. Everything here composes with the expert ladder
   (`12-overrides-and-hints.md`): an opaque extern whose promises
   cannot be measured or evidenced yet is carried by `assume!`/`waive`
   -- visible state, release-gated.

## 5. What "the same level" means across domains

L3 is defined by *capability*, not representation: the level where the
artifact's construction/behavior is fully specified and statically
checkable, but no expensive realizer (geometry kernel; synthesis, place
and route, component binding) has run. L4 is defined by: the realizer has
run, the result is measured, and predictions are verified. This
capability-based definition is what lets the construct x level matrices of
the two languages line up row for row (`10-domain-binding.md`).
