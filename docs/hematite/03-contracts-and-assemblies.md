# hematite Contracts: Interfaces, Matings, Assemblies, Tolerances

> Spec 0.13. Mech bindings of the regolith contract model
> (`../regolith/04-contracts.md`). Regolith semantics are not restated.

## 1. Interfaces

```
interface BearingSeat<d: length, depth: length>:
    frame:
        origin: bore.axis & shoulder.plane
        z: bore.axis                          # x,y free => Cinf declared
    roles:
        bore:     cylindrical(d=d, depth >= depth), internal
        shoulder: planar, normal=+z, annular(od >= d + 8mm)
    tolerances:
        bore:     tol_class(H7), cylindricity(0.008mm)
        shoulder: perpendicularity(0.01mm, to=z), Ra 0.8
    loads:
        radial: derived(sf=1.5)
        axial:  derived(sf=1.5), structure: inherit
    stiffness:
        radial: allocated
    thermal:
        zones(seat: derived)                  # zone-valued; see 02-language.md sec. 7
```

- The frame is the contract's coordinate system: all tolerances,
  alignment, and loads are expressed in it; assembly positioning is frame
  alignment; stackups are frame-to-frame transform chains. Undeclared
  frame axes declare symmetry.
- Promise slots (`loads:`, `stiffness:`, `thermal:`) take value sources;
  `structure:` declares load time structure (`static` default,
  `alternating(R=, f=)`, `spectrum(ref)`).

## 2. Impls and conformance

```
impl BearingSeat<d=30mm, depth=10mm> for Housing:
    bore     = machined.main_bore.wall        # stage-qualified (outside stages)
    shoulder = machined.main_bore.floor

impl MountPattern<M8, 4> for Housing = todo!  # contract concrete, proof deferred
```

**Impl naming** (example-driven): a part's impl is referenced by its
interface name (`block.BearingSeat`) when the part implements that
interface once; implementing the same interface twice requires `as`
aliases (`impl BearingSeat<30,10> for self as front_seat`) and all
references must use them -- the ordinary
unique-most-specific-or-declare rule.

T1 static (construction kinds, parameter match -- binding may pin a free
variable -- capability vs demands per finishing stage), T2 geometric
(post-build predicates: depths, annular material, no role-violating
intrusions; also the import path), T3 physical (promise obligations).
Role binding is a permanent borrow.

### 2.1 Role binding rule [SETTLED] (was SEAM-1)

Contracts are about the *finished* surface, so impls never read scope
snapshots:

1. **Impls resolve at stage exit.** A role reference
   `turned.seal_face` resolves against stage `turned`'s exit state,
   after all its scopes commit. Intra-stage scope order is irrelevant to
   binding -- a polish op in a later scope of the same stage is simply
   part of what the binding means.
2. **The named stage must finish the surface.** If any later stage
   modifies the bound entity, that is the borrow conflict `E0302`,
   reported bidirectionally: at the impl ("bound at 'turned' but
   'ground' finishes this face -- qualify the binding to 'ground'") and
   at the offending op ("modifies a surface permanently borrowed by
   FlameSeat").
3. **Refining ops.** Feature classes may be declared `refining`
   (Ream, Polish, Grind, light FaceMill): geometry-class-preserving and
   tolerance-tightening by construction. Refining ops in the finishing
   stage compose into the binding naturally (rule 1). A refining op in a
   *later* stage still triggers rule 2 -- the fix is re-qualifying, which
   is one token and keeps the contract honest about which stage's
   capability backs the demands.
4. **Capability checks** run against the last op of the bound surface's
   finishing chain (unchanged, now well-defined by rules 1-3).

### 2.2 Pattern binding rule [SETTLED] (was SEAM-2)

1. A `PatternOf` feature commits as one statement in one scope,
   producing an instance set with its declared symmetry orbit.
2. A `PatternOf<I, n, layout>` interface is implemented by binding the
   whole set at once: `holes = milled.mounts.instances`. Cardinality,
   parameters, and layout are checked statically (per-instantiation when
   `n` is an integer variable).
3. **Verify one, instantiate n:** if the orbit is intact at binding
   resolution (stage exit, per 2.1), T2/T3 run on one canonical
   representative and extend across the orbit; the swept-obligation
   machinery covers variable `n`. A broken orbit falls back to
   per-instance checks.
4. The permanent borrow covers the whole instance set; a later feature
   touching any bound instance is a conflict against the pattern
   contract as a unit.
5. Binding a *single* instance out of a pattern to a separate scalar
   interface (`holes.nearest(inlet_ref)`) is legal and **splits the
   orbit for contract purposes** -- conservative by design: subsequent
   `any` over the remainder follows the ordinary orbit rules.

## 3. Matings

```
mating BoltedFlange<n: int, bolt: BoltSpec, circle: length>:
    between: a: FlangeFace, b: FlangeFace     # named sides, always
    align:   a.frame = b.frame (z anti-parallel, contact)
    dof:     removed=[all]
    preload: torque: 25N*m -> P0, scatter=[0.75, 1.25]
    effects:
        model<joint_diagram>(k_bolt, k_members(frustum), phi)
            applies -> a, b: clamp_pressure(P0_max*n, over=contact_annulus)
            applies -> bolts: static(P0_max + phi*F_ext_max), alternating(phi*F_alt)
    capability:
        shear: mu_min * P0_min * n
        axial: per joint diagram
    require State:
        no_separation: P0_min - (1-phi)*F_ext_max > 0, sf=1.5
        no_slip:       mu_min * (P0_min*n - F_ax) > F_shear, sf=1.3

mating GearMesh<ratio>:
    between: a: GearFace, b: GearFace
    couples: a.theta = -ratio * b.theta       # kinematic coupling

mating CompressionSpring:
    between: a: SpringSeat, b: SpringSeat     # named sides, always (FIX-2)
    k: allocated
    preload: at theta=0deg, scatter=[0.9, 1.1]
```

- Alignment is the **only** positioning mechanism; under-located parts
  are compile errors.
- `effects:` declares physics as signature references with `applies ->`
  load routing; the harness evaluates, the orchestrator injects results
  into each part's verification load set at the correct worst-case
  corners.
- Symmetric matings may declare `between: symmetric(FlangeFace)` to waive
  side naming.
- Escalations (`model=fea_contact`, `stiffness=measured`) are declared,
  build-graph-visible opt-ins.

## 4. Assemblies

```
assembly TorchIgniter:
    parts:
        boss:   IgniterBoss                   # native
        body:   IgniterBody
        nozzle: IgniterNozzle
        plug:   vendor(ngk_me8)               # catalog evidence
        base:   import("chamber_rev3.step")   # enters at L4
    boundary:                                 # the ONLY human-asserted physics
        chamber_pressure: [0, 25bar], structure: spectrum(cycles_ref)
        chamber_wall_temp: zones(body.zones.tip:  [600K, 900K],
                                 body.zones.base: [300K, 420K])
        ambient: [-20degC, 95degC]
        design_life: 5000 cycles
        # boundary loads may carry `at=<datum>` application points
    connect:
        # side bindings name IMPLS (interface names, or `as` aliases
        # when duplicated) -- never raw features
        mount: BoltedFlange<4, M6, dia 42>(a=body.FlangeFace,
                                           b=boss.FlangeFace)
        pivot: Revolute(a=boss.PivotBore, b=nozzle.HubPivot)
                   exposing theta: angle in [0deg, 95deg]
        rear:  BearingMount(a=nozzle.TailJournal, b=base.RearBore)
                   redundant(axial)           # declared indeterminacy
        seal:  FaceSeal(a=body.SealFace, b=boss.SealFace)
                   lubrication: dry
    require Seal:
        leak: leak(seal) < 1e-3 scc/s
        # no point-condition suffix: corner discipline evaluates the
        # claim at the worst corner of chamber_pressure (25 bar)
    require Function:
        closing: forall pivot.theta: closing_torque(pivot.theta) > 0.05 N*m
        rest:    equilibrium(pivot.theta=0deg): stable
    require Fatigue:
        life: mech.life(all, under=boundary.chamber_pressure)
                  >= design_life, scatter_factor=4
    budget seal_stack: kind=tolerance
        require: flatness_chain(seal) <= 0.02mm
        members: [body, boss]              # the explicit blast radius
        allocate: cost_optimal
        locked: body.seal_face.flatness: 0.008mm
```

(For a deflection-kind budget in anger -- `mesh_alignment` across a
housing and two shafts -- see `examples/tracks/hematite/gear_reducer.hema`.)

Assembly computation uses promises only (regolith principle 4):

1. **DOF ledger** (+ Gruebler): removed/free freedoms per part must sum
   to zero (statics) or the declared free set (mechanisms). Double axial
   fixation and under-location are both `E0420`-family errors before any
   geometry exists.
2. **Rigid statics** on the connection graph = the free-body diagram;
   reactions per interface checked against rated envelopes.
3. **Stiffness network** from promised stiffnesses + connection models +
   masses: deflection chains and first-mode estimates, conservative by
   construction. The network solver is the default; rigid statics is its
   determinate fast path. `redundant(<dof>)` routes the load path through
   the compliance solve and couples tolerance misfit into loads.
4. **Connection state + generated loads** at interval corners including
   environment corners ("the press fit that spins when hot" fails at the
   hot corner, at compile time).
5. Config variables are namespaced by their exposer -- usually a
   connection in mech (`pivot.theta`); see regolith
   `04-contracts.md` section 5. `forall` quantifies claims over their
   domains.
6. **Part claims and `boundary.`**: a part claim may reference
   `boundary.` names, which resolve against *each enclosing assembly*
   (the part re-verifies per context). A part designed standalone
   routes loads through interface envelopes
   (`under=interface_envelope(<Interface>)`) whose literal promises are
   its asserted truth -- parts never carry `boundary:` blocks.
   **The same resolution rule covers config domains** [SETTLED,
   cycle 6, F75]: a sub-artifact claim may quantify over an enclosing
   system's exposed config variable (`during deploy = stowed`,
   `forall op:`) -- the name resolves per enclosing context exactly
   like `boundary.`, and a sub-artifact with no context supplying it
   is a constructive error naming the missing exposer.

## 5. Tolerances, fits, budgets

- **Toleranced dimensions.** `length` is nominal + tolerance; the
  tolerance slot is usually unwritten and allocated by the compiler into
  the lockfile. Explicit forms: `5mm +- 0.1`, `dia 30 H7`,
  `position(+-0.05, to=frame)`.
- **Capability tables.** Processes export what they can hold per stage
  (`bore(d<20mm): IT9`; `bore(..., ream): IT7`; `face: +-0.05mm`;
  refixture error per setup flip). Capability lookup is static (`E0410`).
- **Fits.** ISO designations between mating roles (`H7/g6`) expand to
  limit deviations from ISO 286 tables, capability-checked, with
  constructive options on failure (add finishing op, add stage, loosen
  fit). Interferences/clearances are intervals consumed by connection
  models.
- **Allocation.** Local by default (loosest process-capable tolerances
  that close each requirement, per connection, no cross-part flow). When
  local allocation cannot close a chain: `E0432` naming the chain and
  worst contributors. Cross-part rebalancing exists only inside a named
  `budget` with explicit `members:` (blast radius), `allocate:` policy,
  and human `locked:` entries. **Allocation policies are pack-provided
  budget math** (cycle 8, D63 -- the D49 pattern; closes OPEN-2): std
  ships `worst_case` (default) and `rss`; a `statistical(cpk=)` policy
  is one pack away, needing distribution-valued process capability
  data (evidence-tiered registry content), never new syntax.
