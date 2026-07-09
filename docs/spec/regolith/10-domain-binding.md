# Domain Binding Table

> Regolith spec. Concept-by-concept: what each abstract regolith concept
> means in the mechanical and electrical languages. This table is the
> contract between the regolith and the domains -- when designing a new
> construct in either language, first find (or add) its row here.

## 1. The big table

| regolith concept | mech (hematite) | elec (cuprite) |
|---|---|---|
| artifact | `part` | `board`, `chip`/`block` (synthesized), `computer` |
| system | `assembly` | `system` |
| process pipeline | cast -> machine; cut -> bend -> weld | fab -> assemble -> program; synthesize -> place -> route |
| stage rule pack (eager) | DFM (bend relief, tool access, min radius) | DRC (trace/space, annular ring) + ERC (drive/load, domain crossings) |
| capability table | IT grades, Ra, position per process | fab classes (min trace, drill), assembly (component sizes), logic family specs |
| entity | face, edge, vertex, body | net, instance, port, layout region, clock/voltage domain member |
| entity ownership | feature that last modified topology | driver of a net; owner of a layout region (courtyard, keepout) |
| borrow conflict | later feature eats a selected face | later statement re-drives a consumed net; placement violates a bound keepout |
| explicit join | `at_intersection(a, b)`, `&` | bus arbitration, declared multi-drive (open-drain wired-AND), region overlap declaration |
| datum | plane/axis/point; GD&T letters | reference node (gnd), domain frames, board-outline refs, timing reference events |
| frame (contract context) | datum reference frame | voltage domain + clock domain + reference node |
| symmetry orbit | pattern instances (Cn bolt circle) | identical channels, bus bits, decoupling sites |
| profile (2D constraint value) | sketch: walk + constraints | parameterized waveform/mask templates (`from_fn`/`from_table`; settled D46 -- no solved segment-constraint system; elec `03` sec. 7) |
| tolerance | GD&T on dimensions | component tolerance (1% R), PVT corners, timing margins |
| fit (standard expansion) | ISO 286 `H7/g6` | logic-level compatibility (VOH/VIH margins), impedance matching classes |
| budget | tolerance chain, deflection budget | error budget (ADC chain), power budget, timing budget, noise budget |
| interface roles | geometric slots (bore, shoulder) | ports (pins-as-intent), regions |
| interface demands | GD&T, Ra, fit class | max load capacitance, edge rate, impedance, decoupling demands |
| interface promises | loads, stiffness, thermal | drive strength, timing (setup/hold/prop), power, protocol conformance |
| connection (`mating`) | bolted flange, press fit, bearing mount | net binding, connector mating, bus attach, domain-crossing (level shift, CDC) |
| `align:` | frame coincidence in space | domain compatibility (same voltage/clock domain, or through a declared crossing) |
| `dof:` ledger | rigid-body freedoms; Gruebler | driver/load ledger; domain-crossing ledger; bus arbitration slots |
| `couples:` | gear ratio, cam law | protocol lockstep, clock ratios (PLL mult/div) |
| `preload:` (internal state) | bolt preload with scatter | bias point, termination, pull-up value with tolerance |
| `effects:` model refs | joint diagram, Lame contact pressure | IBIS driver model, thermal dissipation into enclosure, EMI source model |
| connection `capability:` | transmittable shear/axial | current capacity, bandwidth, data rate |
| boundary truth | applied loads, pressures, temps, life | supply source, ambient, EMC environment, duty cycles, design life |
| config variable | mechanism angle (`pivot.theta`) | operating mode (`pm.mode`), clock frequency selection |
| vendor artifact | bearing, bolt (catalog evidence) | IC, module, connector (datasheet evidence + behavioral model) |
| import at L4 | STEP file with retro-contracts | foreign netlist/layout, encrypted vendor IP block |
| realizer (L3->L4) | geometry kernel (OCCT) | synthesis + component binding + place-and-route |
| measured entity DB | B-rep measures, mass properties | extracted parasitics, actual lengths/skews, utilization |
| cheap harness models | beam theory, joint diagrams | static timing, Ohm/RC, IPC-2221, worst-case DC |
| expensive harness models | volumetric FEA, contact | SPICE, EM field solve, gate-level simulation |
| structure boundary (of a value domain) | fillet consumes a face | regulator mode change; count change alters netlist topology |
| eager `free` resolution | DFM minimum (bend radius) | DRC minimum (trace width for current) |
| claim examples | max stress, deflection, fatigue life | droop, setup/hold, BER, battery life, thermal rise |
| event (time datum) | shock onset, mechanism state change | supply.on, clock edge, load step, mode entry |
| mask (envelope) | shock response spectrum, vibration profile | eye mask, power-sequencing mask, emissions limit |
| abstract contract w/ `spec:` | ratio law, spring F(x) law | functional block (mux, filter, executor) |
| equivalence evidence (T3 on spec) | (light use: couples laws) | formal LEC, simulation w/ coverage, AC analysis |
| planner model (plan = evidence) | CAM: setups, toolpaths, cycle time, cost | assembly planning, pin-mux solve, route budgets |
| target overlay + reserves | fixturing features, prototype bosses; spare mass/volume | debug LEDs, test points, SWD header; spare GPIO/power/area |
| owned region | fixture access volume, zone extent | courtyard, keepout, route corridor, memory partition |
| named partition of an extent (`remainder` rule, boundary datums) | `zones over <set>:` | `partitions:` on an `image`; plane splits |
| multi-piece artifact (`pieces:` + joining stage) | weldment (weld joins, then machine as one part) | module-on-carrier / hybrid assembly (castellated module soldered to a carrier). Panelization is deliberately NOT this row: production multiplication (panels, nests, casting trees) is planner territory, plan = evidence |
| config-variable exposer | connection (`pivot.theta`) | connection, block instance (`pm.mode`), system (`op`) |

## 2. What a new domain must provide

To instantiate the regolith for a new domain (e.g. software systems,
optics, hydraulics):

1. **Quantity namespaces** for its physics in the quantity core.
2. **Entity kinds and measures** for its entity database, plus predicted-
   effect declarations for each constructive statement class.
3. **An ownership story**: what "one owner" means, what modification is,
   what the explicit-join constructs are.
4. **A process/rule-pack model**: capability tables and eager rules.
5. **Interface block bindings**: what frames, roles, demands, and
   promises mean.
6. **A ledger**: the conservation/completeness check that runs on
   contracts alone at L2.
7. **A realizer** and the measured representation at L4.
8. **Harness packs**: signatures + models with domains, error models,
   costs.

Everything else -- value sources, claims/obligations/evidence, budgets,
lockfile, diagnostics, build tiers, coherence rules -- is inherited
unchanged.

## 3. Cross-domain contracts

Because both languages share one quantity core and one contract schema, a
single interface may carry roles from two domains: a PCB mounting
interface has geometric roles (hole pattern, board outline: mech) and
electrical roles (chassis ground continuity: elec); a power module's
thermal promise (`thermal: dissipation <= 3W`) is a boundary input to the
enclosure's mech claims. The binding rule: the interface lives in one
home language; foreign-domain roles are expressed purely in quantity-core
vocabulary and bind through the other language's normal impl machinery.

Settled by the two worked examples (`examples/tracks/xdomain/`, cycles 1-2):

1. **Reference form** [SETTLED]: cross-language artifact reference is
   the ordinary `import` statement -- a `.hema`/`.cupr` path imports
   that file's top-level declarations; the extension selects the
   front-end; contract-level content is regolith IR and composes with
   no bridge syntax. There is no `artifact(...)` special form.
2. **Joint-obligation ownership** [SETTLED in shape]: the system that
   *declares* a connection owns the obligations it generates; imported
   artifacts keep their own artifact obligations in their own build
   graphs; content-addressed evidence makes the split cheap.
3. **Boundary subsumption** [SETTLED in shape]: an imported artifact is
   verified under its own declared `boundary:`. For every boundary
   quantity both systems declare, the enclosing context must be
   contained in the imported assumption (enclosing.ambient a subset of
   imported.ambient), checked at L2, else an error naming both
   declarations. Promises-not-actuals, applied to environments.
4. **Mixed-domain vendor records** are ordinary: a `parts`-kind record
   (a motor) may bundle interfaces from several quantity namespaces;
   each consumer binds the roles its language understands.
5. **Cross-track matings**: a system may instantiate matings from
   either track's packs; ledgers are domain packs keyed by the
   mating's kind (the driver ledger runs over a mech-home assembly's
   elec connections; the DOF ledger over its mech ones).
6. The choice of home language for a mechatronic top artifact
   (`assembly` vs `system`) is stylistic -- both bind the same
   regolith concept; pick the language of the integrating concern.

[SOPEN-2] remaining residue: T2 conformance *tooling* for
foreign-domain roles (running the mech kernel's measurements inside an
elec artifact's build, and vice versa) -- an orchestrator/toolchain
question, no longer a schema question. The interface schema is no
longer held open for this.

## 3a. The geom role kit

[SETTLED, cycle 7; closes SOPEN-6 -- the Kestrel contract pack (F76)
was the requirements list.] "Foreign-domain roles are expressed purely
in quantity-core vocabulary" needs that vocabulary to exist. The
**geom role kit** is a small closed set of domain-neutral geometric
role predicates in `std.quantities`' `geom` namespace:

| predicate | declares | T2 measures |
|---|---|---|
| `geom.point(at=?)` | a located reference point | position vs frame |
| `geom.axis` / `geom.plane` | oriented reference elements | direction, position |
| `geom.plate(w x h, t=)` | a planar body outline with thickness | outline extents, thickness, flatness |
| `geom.region(shape)` | a 2D extent (keepout, courtyard, land) | containment, area |
| `geom.hole_pattern(dia\|tapped=, n, layout)` | n like holes in a layout | per-instance position, size, thread class |
| `geom.boss_pattern(tapped=, n, layout)` | n like bosses/standoffs | position, height, thread |
| `geom.envelope(w x h x d)` | a bounding volume | realized extents inside it |

Rules:

1. **Contract vocabulary only.** Kit predicates appear in `roles:` and
   `demands:` of interfaces; they are never construction features --
   impls bind them to native entities (mech faces/patterns; elec board
   outline, mounting holes, courtyards).
2. **Each predicate is a declared-measures + T2-measurement pair**,
   evaluable by either realizer on its realized artifact (B-rep or
   board geometry). Domain neutrality is exactly this: both sides can
   *measure* the same predicate.
3. **Layouts are the shared layout constructors** (`rect`, `circular`,
   `grid`, `along`) -- the same ones patterns use in both languages.
4. **Derived datums**: kit roles export `.center`,
   `.pattern_center`, `.plane`, `.normal` for use in `frame:` blocks
   and demands.
5. **Anchoring**: any role (including native elec/mech ones) may carry
   an `at=geom.point(...)` anchor relative to the frame -- the same
   `at=` as boundary load application points.
6. The kit is versioned registry content; domains extend it by
   publishing (computed semver), never by forking -- coherence rules
   apply.
