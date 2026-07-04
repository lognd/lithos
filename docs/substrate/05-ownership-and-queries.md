# Ownership, Queries, Datums, Symmetry

> Substrate spec. The anti-ambiguity machinery. Mech binding: topology
> (faces/edges/vertices) and the toponaming problem. Elec binding: nets,
> instances, ports, layout regions, and the multiple-driver problem.

## 1. The entity database

After each committed construction step, the artifact's state is an entity
database. Entity IDs are internal only -- never written in source. All
source-level references are **queries** against this database.

| column (generic) | mech | elec |
|---|---|---|
| id | face/edge/vertex id | net/instance/port/region id |
| origin | creating feature | creating statement (instantiation, net regolith) |
| owner | feature that last modified it | driving block / owning layout region |
| kind + measures | planar/cylindrical, normal, area, length | direction, domain, width, layer, fanout |
| tags, sym_orbit | user tags, symmetry orbit | bus membership, orbit (identical instances) |

## 2. Queries

References compose from semantic predicates; validation is static
(predicate names, entity kinds, operand types, and expected cardinality
are checked before any expensive realization runs):

```
shell.edges.where(parallel_to=Z, adjacent_to=shell.top)     # mech
edges.at_intersection(slot, base.top)                       # explicit join
pattern.instances.nearest(throat_ref)                       # instance addressing
nets.where(domain=vdd_core, kind=clock)                     # elec
u_drv.ports.where(direction=out) & bus_a.members            # elec join
decouple.instances.any                                      # orbit-checked
```

Canonical form is the method chain; there is no bracket sugar (retired,
was FIX-3).

**Cardinality typing.** A query is one of:

- `Entity` -- exactly one; over/under-match is a compile error;
- `Set[Entity; n]` -- cardinality tied to an integer variable; consumers
  must be cardinality-polymorphic;
- `Set[Entity]` -- dynamic; consumers must accept `.all`.

Cardinality intents: `.all` (explicitly everything), `.only` (exactly
one), `.any` (orbit-checked representative, section 5). Instance
addressing is semantic (`nearest`, `where`), never positional index.

## 3. Ownership and borrows

1. **Single ownership.** Every entity has exactly one owner: the
   construct that most recently created or modified it. Modification
   transfers ownership. Elec: every net has exactly one driver; shared
   buses require a declared arbitration construct (the explicit-join
   analog for drive).
2. **Selections are borrows.** A construct consuming a query holds an
   immutable borrow on the resolved entities for the remainder of its
   stage. A later construct modifying borrowed entities is a **borrow
   conflict** -- a compile error with suggested resolutions (reorder or
   rescope, narrow the query, `rebind()` after the modifier).
3. **Interface bindings are permanent borrows.** Role-bound entities are
   protected for the artifact's lifetime, across all stages.
4. **Cross-owner selection requires joins** (`&`, `at_intersection`).
5. The full check runs on the pre-realization IR using per-construct
   predicted effects; a post-realization pass verifies the predictions
   (constructs with data-dependent effects must declare so and are checked
   there).

**Regions are first-class owned entities.** [SETTLED] Beyond point-like
entities (faces, nets), an owner may hold a *region* -- a spatial or
resource extent with an exclusion or arbitration policy: elec courtyards,
keepouts, and impedance-controlled route corridors; mech guarded scope
regions, fixture access volumes, and zone extents (see zones,
`02-quantity-core.md`). Placing or routing into an owned exclusion
region, or a later feature cutting into a fixture access volume, is the
same borrow conflict as modifying a borrowed face -- caught by the
ownership checker, not by a post-hoc rule pass. Region overlap where both
policies permit is an explicit-join declaration.

## 4. Datums

Immutable reference geometry/state, captured explicitly, outside the
borrow system by construction -- the only mechanism for referencing
since-consumed state, and the anchor for frames, tolerance/timing
references, and instance addressing.

- Mech: planes, axes, points; GD&T datum letters bound to fixturing.
- Elec: reference nodes (ground), voltage-domain and clock-domain frames,
  board outline/keepout reference geometry, timing reference events
  (a clock edge as the "datum" of a timing budget).

```
datum throat_ref = bore.throat_plane          # mech
datum t0 = clk_sys.rise                       # elec timing reference
```

## 5. Symmetry and `any`

The entity database tracks the artifact's symmetry group, computed
conservatively from per-construct declared contributions (a circular
pattern declares Cn; an n-bit bus declares its permutation-of-identical-
bits orbit; the artifact group is the intersection). Conservative but
sound: an undetected true symmetry may cause a spurious `any` error; a
false symmetry can never be asserted.

`x.any` -- "choose one, without loss of generality" -- is legal iff all
candidates lie in one orbit of the *current* group. Later constructs can
break symmetry (mech: an off-pattern hole; elec: assigning bit 0 of a bus
a special role), splitting orbits; an `any` after the break is an error
with pinning suggestions. `any` resolves to a canonical representative
recorded in the lockfile (bit-reproducible builds).

Symmetry flows into obligations as hints: a Cn body and load licenses
sector FEA models; an orbit of identical channels licenses
verify-one-instantiate-n discharge in the elec harness.

## 6. Diagnostics

Errors are constructive and stated in the user's vocabulary: show the
query, the matched entities with origin and measures, and 2-3 concrete
fixes. Stable substrate-wide error code families (`09-build-and-lockfile.md`
section 4).
