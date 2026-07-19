# cuprite -- Declarative Electrical and Computer Design

> Spec 0.12 (design sketch). NAMED **cuprite** (`.cupr`) in cycle 9
> (D78). 0.10 -> 0.11 (cycle 18, WO-28 spec cycle): the `drc:`/`erc:`
> rule grammar and the discipline boundary landed
> ([04-structural-layer.md](04-structural-layer.md) sec. 4, [07-vocabulary-sketch.md](07-vocabulary-sketch.md)
> sec. A2). 0.11 -> 0.12 (cycle 23, D120): the HDL coverage matrix
> ([09-hdl-coverage.md](09-hdl-coverage.md)) makes the "HDL superset" banner precise and
> testable. This track is
> deliberately younger than the mechanical one: the regolith is
> proven against mech first, and this directory's job is to
> demonstrate that the same machinery carries electrical and computer
> design without deformation -- and to flag where it does not.

cuprite is the electrical instantiation of the regolith (`../regolith/`).
It covers two coupled sub-tracks:

- **Circuit track:** boards and analog/mixed-signal design -- from named
  intents down to gerbers.
- **Computer track:** computation as a first-class design object -- from
  workload intents down to RTL you synthesize or silicon you buy.

At the highest level there are **no chips, no pins, no nets** -- only
named intents, flows between them, and boundary truth. Implementation is
derived, the same way hematite derives geometry from claims.

| doc | contents |
|---|---|
| [01-overview.md](01-overview.md) | vision; how the two sub-tracks relate; inheritance from the regolith |
| [02-intent-layer.md](02-intent-layer.md) | the top: named intents, flows, boundary, budgets |
| [03-behavioral-layer.md](03-behavioral-layer.md) | the HDL superset: blocks, ports, processes, continuous relations, single-driver ownership |
| [04-structural-layer.md](04-structural-layer.md) | binding to real components, packages, pins, layout; DRC/ERC; PVT corners |
| [05-computer-track.md](05-computer-track.md) | workloads -> architecture contracts -> implementation (buy or build) |
| [06-lowering.md](06-lowering.md) | the elec L0-L6 stack and checks per level |
| [07-vocabulary-sketch.md](07-vocabulary-sketch.md) | draft keyword tables mapped to the regolith |
| [08-open-questions.md](08-open-questions.md) | the EOPEN list |

Status: the core is [SETTLED] as of 0.10 -- the boundary/interior
intent rule, the event-bounded hybrid semantics (03 sec. 1a), the
analog net discipline, host binding, the component record schema, and
the computer track's realization ledger were each settled by worked
examples (16 single-file designs plus the ten-file Kestrel project),
and the EOPEN queue is empty ([08-open-questions.md](08-open-questions.md)). What keeps this
track honestly younger than mech: it has not been implemented against,
and its vocabulary tables (`07`) remain a sketch in layout though not
in substance. Naming (EOPEN-1) is the one open decision.
