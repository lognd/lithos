# Contracts: Interfaces, Implementations, Connections

> Regolith spec. The unit of composition, team decomposition, ecosystem
> packaging, and buy-vs-build in both languages.

## 1. Interfaces

An interface is a contract an artifact offers at one of its boundaries:

```
interface <Name> <params>:
    frame:        # the reference context all contract content is expressed in
    roles:        # named structural slots with predicates
    demands:      # precision/quality requirements on roles relative to the frame
    promises:     # what the implementor guarantees (loads, stiffness, timing, drive)
```

The four blocks bind per domain:

| block | mech | elec |
|---|---|---|
| `frame:` | datum reference frame (origin, axes); undeclared axes declare symmetry | reference context: ground/reference node, voltage domain, clock domain |
| `roles:` | geometric slots (`bore: cylindrical(d=d), internal`) | ports (`scl: open_drain, sink >= 3mA`), regions (keepouts, courtyards) |
| demands | GD&T on roles (`cylindricity(0.008mm)`, `Ra 0.8`), fit classes | signal integrity demands (max capacitive load, edge-rate limits, impedance) |
| promises | `loads:`, `stiffness:`, `thermal:` | `drive:`, `timing:`, `power:`, `protocol:` |

Promise values use the value-source grammar: a literal bound, `derived
(sf=k)` from system analysis, or `allocated` from a budget.

**Two parameter mechanisms.** [SETTLED, cycle 1] `<Params>` (angle
brackets) are **caller-chosen**: they select *which* contract
(`BearingSeat<d=30mm>`, `Mux<6, 64>`) and monomorphize when discrete.
A `params:` block declares **impl-chosen** variables: internal design
freedom, existentially quantified in `spec:` (any implementation picks
values; resolution is lockfile-caused). A thermistor frontend's divider
resistance is `params:`; its output range is `<...>` or fixed in the
contract. [SETTLED, cycle 8, D62 -- was LEANING D54] Caller-chosen
params may also be **artifact-typed** (`board ObcPcb<fw: image>:` ...
`firmware = load(fw)`; bound at instantiation, `obc: ObcPcb(fw=
flight_fw)`) -- the mechanism that lets an artifact declared at one
altitude be consumed by another's construction without an upward
import. Settled on D54's own criterion: the corpus holds two organic
uses (`examples/cubesat/`: firmware into `ObcPcb<fw: image>`, F83; an
FPGA bitstream into `PayloadPcb<bits: image>`, F88), and the
alternative -- the board importing the integrating system's artifact
-- inverts the dependency graph that contract-first decomposition
relies on. Discipline (what keeps this injection, not templating): an
artifact-typed param binds a *whole artifact by reference* -- the
callee holds a permanent borrow, may consume its contract, measured
DB, and content hash (`load(fw)` pins it), and can never modify or
introspect its construction. No new machinery: binding, cardinality,
and lockfile rules are the ordinary caller-chosen-param rules.

**Behavioral specifications.** [SETTLED] A contract may additionally
carry a `spec:` block -- relations over its roles/ports that any
implementation must satisfy. This is what makes an *abstract block*
(elec: a 6->64 mux with enable, a filter transfer function; mech: a
transmission's ratio law, a spring's force-deflection law) a contract
rather than an implementation. Conformance of a concrete realization to
a `spec:` is a T3 **equivalence obligation**: discharged by formal
equivalence checking (discrete logic), analytic or simulation comparison
with declared coverage (continuous behavior), or catalog evidence (a
vendor part sold as implementing the function). Insufficient coverage is
`indeterminate`, never a pass. The elec track leans on this heavily
(`../cuprite/03-behavioral-layer.md`); mech uses it lightly (`couples:` laws
in matings are spec fragments).

**Evidence clauses.** Every promise carries provenance:
`by analysis` (default -- becomes a harness obligation), `by catalog(ref)`
(datasheet, hash-pinned), `by test(ref)` (lab report). This single
mechanism makes designed, purchased, and lab-tested components one
verification model.

## 2. Implementations and conformance

`impl <Interface> for <Artifact>` binds roles to concrete entities.
Conformance is checked in three tiers:

- **T1 static** -- role kinds by construction, parameter match (binding
  may *pin* a free variable), capability-table checks against demands.
- **T2 structural** -- post-realization measurement: geometric predicates
  on the built model / extracted netlist and layout measurements. Also the
  entry path for imported foreign designs.
- **T3 physical** -- survive the promise set; lowered to obligations,
  discharged by the harness.

Role binding is a **permanent borrow** (`05-ownership-and-queries.md`):
bound entities are protected from later modification for the artifact's
lifetime. "A later operation destroyed the contract surface" is a compile
error naming the interface as borrower.

`impl ... = todo!` defers conformance *proof*, never the contract:
parameters and promises stay concrete so system-level work proceeds.

**Systems and assemblies implement interfaces too** [SETTLED, cycle 6,
F82]: a composite artifact may `impl` an interface whose role entities
are drawn from *several* of its parts (a card bay whose four posts
come from four different rails). Bindings are ordinary queries over
the composed entity DB; the permanent borrow lands on each
contributing part's entities, so a later change to any one part that
destroys the contract surface is the ordinary `E0302` naming the
composite's impl as borrower.

**Inline promise refinement.** [SETTLED, cycle 1] An impl may carry a
`promises:` block that *narrows* the interface's promises (a tighter
dissipation ceiling, a lower mass) -- `refines` semantics spelled
inline, one-way checked like any refinement. Consumers binding that
impl see the refined values; consumers of the bare interface see the
base. This is also how vendor records supply datasheet values into
generic contracts.

## 3. Composition: bundling and refinement only

- **Bundling.** Interfaces contain interfaces
  (`PilotedFlange = Pilot + PatternOf<ThreadedHole<M6>, n, circle(bc)>`;
  elec: `I2CPort = SCL + SDA` over one domain). A bundle adopts a
  sub-interface's frame.
- **Refinement.** `refines` narrows an existing contract: tighter demands,
  wider promises. Refined impls are substitutable for the base, one-way,
  checked.
- **No inheritance, no overriding.** Substitutability would be
  unenforceable.

**Semver from contract diffs:** widening promises or loosening demands is
a minor version; the reverse is major. This is computed from the contract
itself, not declared. Community interface packs (NEMA mounts, ISO flanges;
logic families, connector pinouts, bus standards) are the ecosystem unit.

## 4. Connections

A connection contract joins complementary interfaces (mech: `mating`;
elec: nets, buses, and connector matings). Five contract kinds, shared
shape:

```
mating <Name> <params>:
    between: a: <Interface>, b: <Interface>    # named sides, always
    align:   <frame coincidence rules>         # the ONLY positioning mechanism
    dof:     <freedoms removed/kept>           # feeds the system ledger
    couples: <config-variable coupling>        # gear ratio; protocol lockstep
    preload: <internal state, with scatter>    # bolt preload; bias point, termination
    effects: model<sig>(...) applies -> role   # declared physics, routed loads
    capability: <what it can transmit>         # worst-case corners
    require <Group>: <state claims>            # no-slip; no bus contention; setup/hold met
```

- Connections *declare* physics via signature references; they never
  compute. The harness evaluates `effects:` models and injects generated
  loads into each implementing artifact's verification set.
- **Corner discipline:** each check consumes its own worst-case interval
  end (part stress at max interference; transmitted capability at min;
  timing setup at slow corner, hold at fast corner).
- Escalations are declared opt-ins (`model=fea_contact`,
  `stiffness=measured`; elec: `model=spice_extracted`) and recorded as
  cross-artifact dependency edges in the build graph -- the system-test
  tier, versus the promise-backed unit-test tier.
- Connection stdlibs ship in two co-versioned halves: declarations
  (modeling side) and model nodes (harness side).
- **Orbit connections are regolith vocabulary** [SETTLED, cycle 6,
  D53 -- previously stated only in the elec track]: *broadcast*
  (`scalar -> set.role`), *zip* (`pairwise(set_a, set_b)`), and
  *flatten* connect instance sets with static cardinality checks in
  either language. Where the connection needs a full contract (mech),
  the zip takes it: `pairwise(a_set, b_set) by <Mating>` instantiates
  one mating per element pair, in shared layout order
  (`examples/cubesat/structure.hema`).

## 5. Systems

The top-level artifact (mech: `assembly`; elec: `system`) contains
artifact bindings, connections, boundary truth, budgets, and claims.
System-level computation uses **promises only**:

1. **The ledger.** Sum removed/kept freedoms per artifact; must equal the
   declared free set. Mech: rigid-body DOF, over/under-constraint. Elec:
   driver/load ledger per net (exactly one driver unless explicitly
   arbitrated), domain-crossing ledger (every clock/voltage domain
   crossing must be through a declared crossing connection).
2. **Static system solve on promises.** Mech: rigid statics + promised
   stiffness network. Elec: static power budget + nominal operating point
   + worst-case timing over promised delays.
3. **Interval evaluation at environment corners** including cross-domain
   ones (differential expansion; PVT corners).
4. **Budgets:** cross-artifact allocation happens only inside an
   explicitly declared, named budget with explicit `members:` (the blast
   radius), an `allocate:` policy, and human `locked:` entries. Allocation
   is otherwise strictly local per connection (the defaults test). Domain
   examples: tolerance chains and deflection budgets (mech); power,
   timing, noise, and error budgets (elec). **Budget `kind=` names a
   pack-provided budget math** [SETTLED, cycle 6, D49 -- like intent
   verbs, kinds are packages, not compiler built-ins]: std ships
   `tolerance`, `deflection`, `power`, `timing`, `noise`, `error`,
   and -- added by the Kestrel example -- `mass` and `energy`; members
   may span domains (a mass budget over boards AND structure is one
   budget).

5. **Config variables** are namespaced by the construct that *exposes*
   them: a connection (`pivot.theta`), a block instance (`pm.mode`),
   or the system itself (`exposing op: {sleep, run, fault}`).
   `forall` and `during <var> = <value>` quantify claims over their
   domains.

6. **Boundary subsumption** [SETTLED in shape, cycle 2]: an imported
   artifact arrives verified under its *own* declared `boundary:`.
   For every boundary quantity both systems declare (ambient, supply
   window, life), the enclosing system's interval must be contained
   in the imported artifact's assumption, or L2 errors naming both
   declarations. Containment is uniformly the safe direction because
   boundary entries are, by definition, *tolerated envelopes* -- what
   the artifact was proven under -- never point conditions (INV-7).
   This is what makes evidence transfer across contexts sound: no
   artifact is silently used outside the envelope it was proven in.

**Contract-first workflow:** a system of *unbound* interfaces plus
connections plus boundary truth is fully checkable before any artifact
exists. Artifacts then implement load-annotated / signal-annotated
contracts independently -- the work-breakdown unit for teams and LLM
generation alike. In lowering terms: run the pipeline L0->L2 only.

## 6. Targets and reserves

[SETTLED in shape] A system may declare named build **targets** --
additive overlays for non-product concerns (debug instrumentation, test
fixtures, bring-up aids):

```
system Thermostat:
    reserves:
        gpio:  4
        power: 50mW avg
        area:  400mm2

target debug of Thermostat:
    intents:
        heartbeat: indicate(decide.status)
        console:   debug_access(swd, uart_log)
    draws: reserves
```

Rules:

1. A target may only **add** artifacts, intents, connections, and
   claims; it may not modify base contracts or weaken base claims.
   **Contract-level** base evidence therefore remains valid under
   every target.
2. Targets consume only declared **reserves** -- budget-like set-asides
   (spare drive, power, area, GPIO count, mass/volume in mech) in the
   base design. Exceeding a reserve is `E0432`-family, naming the
   target. The release target is the base itself; `build --release`
   additionally verifies reserves are genuinely spare (nothing base
   depends on them).
3. **Realization-level** base evidence is a sharper story (INV-8;
   additivity alone is NOT sufficient -- an added debug LED that
   perturbed base routing would perturb extracted parasitics): target
   content *realizes only inside reserved regions*, with the base
   realization reused verbatim; base evidence keys then match by
   content addressing. Where a target genuinely perturbs the base,
   the changed snapshot forces re-verification of exactly the touched
   subjects -- reuse is never silent.
4. Target-added artifacts get their own obligations; shared evidence is
   reused via content addressing.

Mech binding: sacrificial fixturing features, prototype-only inspection
bosses, engraved debug markings -- same overlay+reserve mechanism.
Genuinely *alternative* designs (different topology per variant) remain
`variant` territory (mech OPEN-1), not targets: targets add, variants
choose.

## 7. Vendor artifacts

`vendor(ref)` binds a purchased artifact as an interface bundle whose
promises are discharged `by catalog` -- internals are never modeled.
Mech: bearings, bolts, springs. Elec: chips, modules, connectors -- a
vendor IC is an interface bundle (ports, timing, absolute-max intervals)
plus, optionally, a behavioral model registered in the harness for
system-level simulation. Buy-vs-build is therefore not a mode switch:
a synthesized block and a purchased chip satisfy the same contract with
different evidence.
