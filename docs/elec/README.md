# cuprite -- Declarative Electrical and Computer Design

> Spec 0.10 (design sketch). NAMED **cuprite** (`.cupr`) in cycle 9
> (D78). This track is
> deliberately younger than the mechanical one: the substrate is
> proven against mech first, and this directory's job is to
> demonstrate that the same machinery carries electrical and computer
> design without deformation -- and to flag where it does not.

cuprite is the electrical instantiation of the substrate (`../substrate/`).
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
| `01-overview.md` | vision; how the two sub-tracks relate; inheritance from the substrate |
| `02-intent-layer.md` | the top: named intents, flows, boundary, budgets |
| `03-behavioral-layer.md` | the HDL superset: blocks, ports, processes, continuous relations, single-driver ownership |
| `04-structural-layer.md` | binding to real components, packages, pins, layout; DRC/ERC; PVT corners |
| `05-computer-track.md` | workloads -> architecture contracts -> implementation (buy or build) |
| `06-lowering.md` | the elec L0-L6 stack and checks per level |
| `07-vocabulary-sketch.md` | draft keyword tables mapped to the substrate |
| `08-open-questions.md` | the EOPEN list |

Status: the core is [SETTLED] as of 0.10 -- the boundary/interior
intent rule, the event-bounded hybrid semantics (03 sec. 1a), the
analog net discipline, host binding, the component record schema, and
the computer track's realization ledger were each settled by worked
examples (16 single-file designs plus the ten-file Kestrel project),
and the EOPEN queue is empty (`08-open-questions.md`). What keeps this
track honestly younger than mech: it has not been implemented against,
and its vocabulary tables (`07`) remain a sketch in layout though not
in substance. Naming (EOPEN-1) is the one open decision.
