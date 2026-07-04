# cuprite Lowering Stack

> cuprite spec 0.10. The elec binding of the generic stack
> (`../substrate/08-lowering-architecture.md`). Level numbers align with
> hematite's on purpose; the capability-based definitions of L3/L4 are what
> make the alignment principled rather than cosmetic.

## 1. The stack

```
L0  SOURCE        .cupr text + stdlib (components, families, fabs, matings,
 |                protocol packs) + imports
 |    parse, format-normalize
L1  TYPED AST     names resolved; quantity/unit checking; value-source
 |                grammar; ==-ban; behavior (process/continuous) parsed
 |    lower contracts
L2  CONTRACT IR   <- "contracts live here" -- IMPLEMENTATION-FREE
 |      graph of: intents + flows, domains (voltage/clock) as frames,
 |      interfaces (port roles/promise slots), connections (net matings,
 |      crossings, buses), boundary truth, budgets, claims, config space
 |      checks/solves: flow ledger (fed/consumed/rate-compatible) -
 |      driver/load and domain-crossing ledgers on promises - power
 |      budget arithmetic - schedulability arithmetic - worst-case
 |      timing over promised delays - level-compatibility (fit)
 |      lookups - derived-contract authoring over corners - budget
 |      arithmetic - contract-first verification
 |    per-artifact lowering (intent allocation -> blocks)
L3  BEHAVIORAL IR the HDL-superset layer: blocks, ports, processes,
 |                continuous relations, block-diagram connection
 |      checks: port/query typing and cardinality - single-driver
 |      ownership/borrows - arbitration joins - clock/power-domain
 |      membership and crossing checks (CDC/ERC as type system) -
 |      monomorphization sweep (bus widths, channel counts) - symmetry
 |      orbits - structure-boundary domains - eager rule packs (derating,
 |      IPC-2221 -> resolves `free`) - T1 conformance
 |    realization (synthesis, component binding, place-and-route)
L4  STRUCTURAL IR bound netlist + packages/pins + placed/routed layout +
 |                synthesized logic; extracted parasitics = measured
 |                entity DB (imports enter HERE, skipping L3)
 |      checks: post-realization prediction verification (E-series
 |      snapping, pin-mux results, route classes) - T2 conformance -
 |      extraction - DRC - derived entities (coupled-net pairs, thermal
 |      copper regions)
 |    emit proof work
L5  OBLIGATIONS   <- "proofs live here" -- same schema as mech, same
 |      harness architecture, elec model packs:
 |      static timing / worst-case DC / IPC-2221 / utilization bounds
 |      (cheap) -> IBIS SI, lumped thermal, switching loss (mid) ->
 |      SPICE, EM field solve, gate-level sim (expensive)
 |      margin-driven selection; PVT corner discipline; evidence cache
 |      orchestrator: lazy loop (component values, route budgets) over
 |      (eager-feasible AND structure-preserving) space
L6  BACKENDS      gerber/drill, pick-and-place, BOM (vendor refs),
                  netlists, bitstreams, firmware images, fab drawing,
                  rendered "datasheet" views, evidence ledger report
```

## 2. Construct x level matrix

| construct | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|
| intent + flow | typed regolith | flow ledger; contract skeletons | allocated to blocks | -- | intent-level claims | traceability report |
| value (any source) | typed qty | -- | constraint node; eager resolution; structure domain | E-series/concrete value | sensitivity target | BOM value |
| port | typed role | promise/demand slots | driver ownership; domain membership | pin assignment | port-level obligations | pinout table |
| net / connection | regolith | mating: align (domains), ledger entries | single-driver check; arbitration | routed geometry; extraction | SI/timing obligations | netlist |
| clock/voltage domain | regolith | frame; crossing ledger | membership typing | tree synthesis; plane assignment | skew/droop obligations | constraints out |
| `on` body (RTL) | parsed | -- | synthesizable check; ownership | synthesized gates | -- | HDL export |
| continuous relation | parsed | -- | DAE well-formedness | component binding | harness model source | -- |
| block | regolith | interface bundle | instantiation; orbits | placement group | T3 obligations | -- |
| workload / schedule | typed regolith | schedulability arithmetic | -- | binary/bitstream size | deadline obligations | firmware image |
| budget | regolith | closure arithmetic | -- | contributor measurement | corner evaluation | report |
| claim (`require`) | expr | attach to graph | -- | -- | obligation; evidence | ledger |
| vendor component | ref | interface bundle (datasheet intervals) | behavioral model instance | footprint + pins | catalog evidence | BOM line |
| abstract block (`spec:`) | regolith | functional contract | impl selection (`by spec/composing/circuit/vendor`) | synthesized/bound realization | equivalence + promise obligations | -- |
| firmware image | regolith | realizes schedule contract | -- | toolchain-realized; map/stack/WCET measured | resource/timing obligations | image file |
| event / mask | typed regolith | window/corner sets | -- | -- | transient/noise obligation givens | test specs |
| target overlay | regolith | reserve accounting | added blocks | added placement (reserved regions only, INV-8) | added obligations | per-target outputs |
| import (sealed stage) | path+hash | retro-contracts | **skipped** | measured netlist/layout | obligations | -- |
| `extern` (impl/image) | ref+hash+format | contract binding | transparent (Verilog): elaborated blocks | opaque (netlist/ELF/IP): measured/evidenced | equivalence + promise obligations | linked as-is |
| `waive` / `policy:` | parsed | rule/claim matching; forbid = domain cuts | scope queries; prefer = search order | -- | acceptance records | ledger; lockfile annotations |
| `realizes` / host binding | regolith | realization ledger; demand implication via flow budgets | -- | hosting + IO-bank assignment | -- | traceability report |

## 3. Notes on alignment with mech

- The **eager/lazy split is identical**: rule packs (DRC/ERC/derating =
  DFM) resolve `free` and validate the candidate cheaply; the
  orchestrator loop runs only when verification of the eager candidate
  fails (e.g. droop claim fails -> loop proposes bulk capacitance within
  its bounded domain, guided by sensitivities).
- **Two on-ramps, same as mech:** contract-first (an architecture of
  unbound interfaces + budgets verifies with zero implementation) and
  verify-only import (an existing KiCad/netlist design enters at L4 and
  gets claims retrofitted).
- The main asymmetry: elec L4 realization contains *search* (synthesis,
  placement, routing) where mech L4 is mostly *evaluation* (the kernel
  computes what features dictate). Consequence: elec relies more on the
  planner/`allocated` machinery and its lockfile causes. This is a
  difference in degree, not architecture -- mech setups/op-ordering are
  already planner-allocated, and both use the substrate's conflict-
  driven allocation search (greedy descent + cheap screens + lazy
  verification + blame-set backjumping with learned nogoods; substrate
  `07-claims-and-evidence.md` section 7). The lazy loop runs over
  pre-layout variables only; layout is realize-once-verify [SETTLED,
  cycle 8, D69 -- closes EOPEN-5]. An incremental-reroute protocol is
  a deferred orchestrator optimization with a stated reopen criterion
  (`08-open-questions.md` sec. 1a).
