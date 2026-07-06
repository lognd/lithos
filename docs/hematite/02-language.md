# The hematite Language: Parts, Features, Profiles, Queries

> Spec 0.13. Canonical syntax after the audit fixes; all forms here are the
> single canonical spelling (retired alternatives listed in
> `04-vocabulary.md` section 4).

## 1. A complete part

```
part IgniterBody:
    material: AISI_316

    stage barstock: process=saw_stock(dia 45mm)

    stage turned: process=cnc_lathe, from=barstock
        then:
            # process vocabulary: lathe ops are Turn/BoreTurn, not
            # CSG verbs (a hematite has Contour/Pocket, never Extrude)
            envelope = Turn(profile=OuterProfile)
            bore     = BoreTurn(profile=FlameTubeBore)
        then seal_prep on envelope.front:
            seal_face = Face(turn+polish)        # Ra from capability; on= defaults to guard

    stage milled: process=cnc_mill(axes=4), from=turned
        then:
            # cross-stage references carry the stage qualifier (path rule)
            ports = PatternOf<SwirlPort>(n=6, circular(dia 14mm),
                        frame=turned.bore.axis.offset(z=18mm)
                                  .tangent_to(dia 14mm, elevation=8deg))
        then:
            plug_port = ThreadedHole(M18x1.5, on=turned.envelope.side)
            # C6 symmetry broken here; ports.any afterward = E0502, correctly

    datum throat_ref = bore.throat_plane         # immutable, borrow-exempt

    impl FlameSeat<dia 24> for self:
        seat = turned.seal_face                  # permanent borrow
```

## 2. Stages

`stage <name>: process=<module>(args) [, from=<stage>]` -- one process
step. Regolith semantics (`../regolith/06-execution-model.md`) apply:
per-stage capability table and DFM pack, ownership checkpoints at
boundaries, stage-qualified dimensions, capability checked against the
finishing stage.

- **Imports are stages:** `stage src: import(path) [sealed]`. Geometry
  enters at L4 with a measured entity DB; `sealed` forbids later
  modification. The import ladder is purely "how many stages follow."
- **Artifact-position imports.** An import bound directly in an
  assembly's `parts:` (`plate: import("baseplate_rev2.step") sealed`)
  is shorthand for a part with exactly one import stage, whose name is
  **`src`** by rule. Retro-contract impls and datum captures on such a
  part qualify with it: `holes = src.holes.where(...)` inside
  `impl ... for plate:`; from outside, `plate.faces.where(...)` as
  usual.
- **Path rule** (was FIX-6): within a stage, bare names; cross-stage
  references require the stage qualifier (`turned.seal_face`); impl
  blocks sit outside stages and always qualify. Rust module-path
  intuition.

## 3. Setups and workholding

Machining stages contain ordered `setup` blocks -- workholding states:

```
stage milled: process=cnc_mill(axes=3), from=cast
    setup A:
        hold: cast.base.sides
        datum A = cast.base.bottom          # GD&T letter bound to fixturing
        then: ...
    setup B:
        flip about X                         # injects refixture tolerance
        hold: milled.boss.od
        then: ...
```

- `hold:` names the gripped geometry (trade term; `fix:` retired for the
  `fit` collision).
- Omitted setups are planner-`allocated`; `sequence: a before b` pins
  manufacturing order when the human must.
- Refixture error comes from the process capability table and enters
  tolerance stackups automatically.

## 4. Scopes and features

Regolith scope/commit semantics, with the mech feature vocabulary:

```
then [label] [on <region>]:
    holes  = Pierce(circle(5mm), pattern=grid(2,3,25mm))   # on= defaults to guard
    flange = Bend(edge=blank.top, angle=90deg, radius=free)
```

- Features come from the stage's process module
  (`from processes.sheet_metal import Blank, Bend, Pierce`); each feature
  class declares its predicted entity-DB delta (creates/modifies/consumes)
  and its symmetry contribution.
- Feature exports are named filtered views (`boss.side`, `boss.base_edge`)
  plus virtual geometry (`boss.axis`) -- never raw topology.
- `seq:` for genuinely sequential chains; lint nudges independent features
  back to `then:`.
- Overlap merge rules, `merge(a over b / a before b)`, `rebind()`: per
  regolith.

## 5. Profiles (the sketch layer)

A `profile` is a 2D constraint system -- a *value* (borrow-exempt), not
topology. The topology/metric split is the core design:

```
profile FlameTubeBore:
    walk:                          # topology + ALL discrete choices
        from inlet_plane
        line down                  # a       (direction words are uniqueness-
        arc tangent, bulge=right   # b        checked hints, never approximations)
        line angled                # c
        arc tangent, bulge=left    # d
        line down                  # e
        close via axis             # revolve centerline closure
    constraints:                   # metrics: orderless, declarative
        a.length = 8mm
        c.angle = 30deg from axis
        d.radius = in [1.5mm, 4mm]
        e.diameter = dia 6mm H9
        inlet_plane to throat_plane = 22mm +- allocated
    exports:
        throat_plane: datum
```

Rules:

- The walk pins **every discrete branch** (`bulge=left/right` chord-wise
  in the +normal view, `tangent`/`perpendicular` joins). Unpinned solver
  branches are compile errors -- the sketch-level analog of ambiguous
  queries.
- The sketch DOF ledger must close, or remaining freedoms must be
  declared free variables.
- `hole <name>:` declares a named inner loop (one nesting level);
  `regions:` names area expressions (`interior - holes`, `between(...)`)
  consumable by features.
- Curves are `from_table(...)` or `from_fn(...)`; freehand splines do not
  exist.
- A profile may be externally linked: `profile Outline:
  extern("outline.dxf", dxf)` -- a transparent format elaborates into
  the sketch layer with the full static tier (regolith
  `08-lowering-architecture.md` section 4); the industrial-design
  handoff path.
- Constraint solving drives an existing engine (SolveSpace). The
  constraint vocabulary is a closed v1 set equal in power to the
  SolveSpace constraint kinds (coincident, distance, angle,
  radius/diameter, tangent, perpendicular, parallel,
  horizontal/vertical in the profile frame, equal, symmetric,
  midpoint, on_entity) [SETTLED, cycle 8, D65 -- closes OPEN-5];
  solver interaction detail is implementation-owned (WO-11, Phase C).
- **Export anchoring** [SETTLED, cycle 1]: a profile is a placeless
  value; its exported datums acquire 3D existence only through an
  instantiating feature and are addressed feature-first
  (`body.mid_plane`, never `BodyOutline.mid_plane` once placed).
  Referencing a profile's export where a placed datum is needed is a
  compile error naming the instantiating feature(s). This also closes a
  snapshot loophole: a sibling statement cannot launder a dependency on
  a feature's placement through the profile value.

## 6. Queries and datums

Regolith machinery with mech predicates:

```
body.edges.where(adjacent=top, dir=Z)
edges.at_intersection(slot, base.top)      # explicit cross-owner join
pattern.instances.nearest(throat_ref)
pattern.instances.any                      # orbit-checked
q.all / q.only                             # cardinality intents
body.cavity(inlet=bore.inlet).wetted_faces # derived void entity
left_ref = blank.left_edge.as_datum()      # capture out of the borrow system
```

Derived cavity entities (`.cavity(inlet=...)`: `wetted_faces`, `volume`,
`min_section`) are computed at L4 and queryable like any entity set.

## 7. Zones [SETTLED] (was SEAM-4)

Zone-valued quantities (`thermal: zones(tip: [700K, 950K], ...)`) index
named regions declared in a `zones:` block on the part (or, in
interfaces, relative to roles):

```
zones over turned.envelope.faces:
    tip:  .where(between=(throat_ref, exit_ref))
    base: remainder
```

Rules:

1. The declared zones must **partition** the referenced entity set
   (cover + disjoint) -- predicted at L3, verified on real geometry at
   L4. `remainder` names the complement exactly once.
2. Zone boundaries automatically become datums
   (`zones.tip.boundary`), usable like any datum.
3. A zone-valued quantity must supply a value for every zone of its
   target, or a `default:`.
4. In obligations, a zone map serializes as a content-addressed
   piecewise field over the realization snapshot -- no obligation-schema
   change, resolving the old freeze concern.
5. Zone extents are owned regions (regolith
   `05-ownership-and-queries.md`): a later feature that erases a zone's
   extent conflicts with whatever borrowed the zone (e.g. a thermal
   boundary condition).

## 7a. Multi-piece parts (weldments) [SETTLED, cycle 2]

A weldment is *one part* (one BOM line; machined as a unit after
joining) built from several pieces, each with its own stock and
material -- expressible by neither a single-stock part nor a stageless
assembly. Shape (worked in `examples/mech/weldment_frame.hem`):

```
part MachineFrame:
    pieces:
        rail_l: stock RectTube(60mm x 40mm x 3mm, l=600mm), material: S355
        gusset: import("gusset_rev1.step") sealed, material: S355

    stage welded: process=mig_weld(er70s_6), joins=[rail_l, gusset]
        align:
            gusset.face.frame = rail_l.web.frame (contact)
        then:
            w1 = FilletWeld(between=(gusset.edges.all, rail_l.web), leg=4mm)

    stage machined: process=cnc_mill(axes=3), from=welded
```

Rules:

1. `pieces:` entries are stocks, part references, or imports; each
   carries its own material. A part with `pieces:` has no part-level
   `material:`.
2. A joining stage names its inputs with `joins=[...]` and places them
   with the *same `align:` vocabulary as matings* -- a weldment is an
   assembly frozen into a part. Weld features create joint entities;
   leg/throat sizes are capability-checked against the weld process
   pack.
3. After the joining stage the entity DB is unified with per-piece
   provenance (`welded.rail_l.bottom`); later stages machine across
   piece boundaries freely -- that is the point.
4. **Weld vocabulary** [SETTLED in shape, cycle 2; models remain
   OPEN-13]:
   - Taxonomy: `FilletWeld`, `GrooveWeld(prep=...)`, `SpotWeld`,
     `PlugWeld` -- feature classes declared per weld process module
     like any other feature.
   - Each weld feature creates a **`weld` joint entity** with measures
     (kind, leg / effective throat, effective length, process record
     ref), queryable like any entity set: `welded.welds.all`,
     `.where(kind=fillet)`.
   - Distortion enters the entity DB as position scatter on the joined
     pieces, from the weld process capability table -- it then flows
     into tolerance stackups with zero new machinery.
   - Claim form: `mech.weld_stress(w, under=...)`. [SETTLED, cycle 3;
     closes OPEN-13] The harness pack `std.mech.weld` (two-halved)
     provides signature `weld_line_state` (inputs: weld-set measures +
     joint load resultants; outputs: throat stress components;
     `domain:` rigid-plate, elastic) implemented by the line-weld
     (welds-as-lines) method as the cheap tier and a shell-FEA node as
     the expensive tier -- margin-driven selection as everywhere.
   - Weld DFM rules (eager, per weld process module): torch access
     (approach cone vs surrounding geometry), leg-vs-thinner-wall
     limits, joint-prep compatibility (`GrooveWeld(prep=)` vs plate
     thickness), minimum weld-to-edge distance.

## 7b. Variants [SETTLED, cycle 3; closes OPEN-1]

`variant <name>: {a, b}` declares an **externally-chosen** discrete
config axis: the orderer picks, not the optimizer, so *every* variant
must verify (contrast `in {..}` domains, which the optimizer resolves).
Construction may branch with a `when <variant> = <value>` statement
guard; instantiation sites choose (`clip: CableClip(hand=left)`); the
lockfile carries per-variant sections. Cross-variant evidence sharing
is the swept-obligation machinery verbatim (SEAM-3): the compiler
emits one obligation carrying the variant domain (`sweep: hand in
{left, right}`); a model that declares mirror/permutation equivalence
between points discharges one and extends (the symmetry machinery);
otherwise it sweeps with per-point caching, so geometry shared across
variants is shared evidence by content address. Worked in
`examples/mech/molded_clip.hem`.

## 8. Manufacturing claims (CAM as obligation)

Manufacturability, cost, and cycle time are ordinary claims discharged
by planner models (regolith `07-claims-and-evidence.md` section 6):

```
require Manufacture:
    makeable: manufacturable(milled)
    cost:     mfg.unit_cost(qty=100) <= 30 USD
    time:     mfg.cycle_time(milled) <= 20 min
```

Eager DFM rules are the cheap conservative tier; the CAM planner
(reach, collision, fixturing over the declared setups) is the expensive
tier, engaged only when rule-pack margins are thin. The plan is the
evidence; the L6 G-code backend serializes it. Omitted setups being
planner-`allocated` and `sequence:` pins are this same machinery from
the source side.

**Supplied plans** [SETTLED in shape, cycle 3]: a proven shop program
may be linked instead of generated --
`plan: extern("op20.nc", gcode_fanuc) by test(fai_207)` at stage or
setup granularity (the plan *obligation* stays per stage per OPEN-12;
supplied and generated setups compose). The planner runs in **check
mode** over supplied plans -- verifying reach/collision/completeness
of a given program is cheaper than planning -- and residue is
discharged by first-article evidence. Regolith `08` section 4.

## 9. Materials

`material: AISI_4140` binds a registry record: interval-valued `f(T)`
properties, `condition(annealed | quench_temper(...))` variants, fatigue
data with provenance (`sn_curve(ref=mil_hdbk_5j, R=-1,
surface=per_finishing_stage)`). Friction and contact facts live in
`contact { A, B }` pair records selected by connection `lubrication:`
state. Overrides require evidence. See regolith `02-quantity-core.md`
section 6.
