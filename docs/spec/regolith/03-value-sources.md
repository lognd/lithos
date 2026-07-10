# The Value-Source Grammar

> Regolith spec. [SETTLED] as of mech spec 0.3 (was FIX-1). The single
> biggest UX decision in the system: one grammar answers "who decides this
> number?" for every numeric slot in every language.

## 1. The five sources

Every numeric slot -- dimension, tolerance, load, stiffness, trace width,
supply voltage, clock rate, buffer depth -- takes exactly one of five
sources (the sixth row below, `in registry(<family-ref>)`, is the SAME
`in [lo, hi]` bounded-freedom source generalized to a discrete record
domain -- D181, WO-68 -- not a new source):

```
<value-source> ::=
    <literal>                  # the human knows it
  | in [lo, hi] [opt-dir]      # bounded freedom; the optimizer decides
  | in registry(<family-ref>)  # bounded freedom over a catalog family
  | free                       # the process-rule minimum decides
  | derived [(sf=k)]           # a consequence of system analysis; pinned
  | allocated [(policy)]       # a share of a declared budget or a planner output
```

| source | meaning | resolved by | example (mech) | example (elec) |
|---|---|---|---|---|
| literal | asserted truth | -- | `wall = 4mm` | `vdd = 3.3V +- 5%` |
| `in [lo, hi]` | optimizer decides inside hard bounds | eager propagation, then the lazy loop if needed | `radius = in [2mm, 8mm] minimize` | `c_bulk = in [10uF, 100uF] minimize` |
| `in registry(<family-ref>)` | optimizer decides inside a closed, hash-pinned catalog family (D181, WO-68) | discrete section search (the D161 `optimize_discrete` engine) over the declared family's records | `section: in registry(std.civil.w_shape)` | (reserved; no elec discrete-catalog slot uses this yet) |
| `free` | cheapest legal value per process rules | the pack rule carrying `resolves: <field> from free` (DFM / DRC eager propagation) | `bend.radius = free` | `trace.width = free` |
| `derived (sf=k)` | computed from system-level analysis over corners | contract solver at L2 | `loads: radial: derived(sf=1.5)` | `port.i_max: derived(sf=1.5)` |
| `allocated (policy)` | a share of a named budget, or a planner decision | budget allocator / planner | `+- allocated` in a tolerance chain | `noise: allocated` in an error budget |

`in registry(<family-ref>)` names WHERE to search (a closed catalog
family), never WHAT to pick (AD-28's no-auto-substitution rule
unaffected): `free` alone still means "the process-rule minimum
decides, honest indeterminate where no rule resolves it" -- the two
forms are NOT interchangeable and `in registry(...)` is not a
reinterpretation of `free` (D181). calcite's `FrameMember` is the v1
consumer: a searchable member's `section:` field declares
`in registry(std.civil.<family>)`; lowering carries the family into
`FrameMember.section_domain: Option<String>`
(`regolith-lower::frame_lower::section_domain_ref`), leaving `section`
itself at its ordinary `free` placeholder (AD-25) since the domain is
declared, not resolved. An empty `registry()` ref or an `in <expr>`
whose callee is not `registry` degrades to `section_domain: None`
honestly (AD-3: never a guess, never a panic) -- no dedicated
diagnostic exists for either malformed shape yet (a named gap, not
silently swallowed; `crates/regolith-lower/src/frame_lower.rs`'s
`section_domain_ref` doc comment and its unit tests are the record).

Notes:

- **Comparator literals** (`>= 80kN/mm`, `<= 30ns`) are literals: one-sided
  asserted bounds. The two-sided comparator literal is spelled
  `within [lo, hi]` -- a *demanded window* (flexure stiffness that must
  be neither too stiff nor too soft; an oscillator frequency band) --
  distinct from `[lo, hi]`, the *interval value* (scatter/range the
  author asserts). `within` is a registered overload meaning
  containment in all its positions (`within(a, b, tol)`,
  `within <d> after <e>`, `within [lo, hi]`).
- **Comparators in claim position.** In a claim expression the
  comparator is written infix, like any comparison:
  `mech.backlash(mesh) within [0.05mm, 0.15mm]` beside
  `stress < limit`. Never `= within [...]`: `=` in claims means
  discrete equality only, and giving it a second containment meaning
  would make the operator's semantic class depend on its right-hand
  side (decided by grammar experiment, cycle 5, D42). In *slot*
  position the comparator literal follows `:` or `=` like any value
  source (`static: <= 12N`, `k: within [0.8, 1.6] N/mm`).
- **Domains are hard.** A value outside `in [lo, hi]` is unsatisfiable,
  never clamped.
- **Integer domains monomorphize.** `n = in [2, 6]` over integers is
  exhaustively enumerated; every static check runs per-instantiation.
  Source must be valid for the whole domain or the domain must shrink.
- **Optimization direction** (`minimize` / `maximize`) is a secondary
  objective, applied only after all claims are satisfiable. It is
  strictly per-variable and takes no arguments. Global objectives
  (minimize *distinct* component values, total cost, setup count) live
  in `policy:` blocks at system altitude -- resolved [SOPEN-4], see
  `12-overrides-and-hints.md` section 4.

## 2. Resolution and the lockfile

Every non-literal source resolves into the lockfile with its resolving
cause:

```
# hematite.lock / cuprite.lock excerpts
flange.radius = 2.4mm         cause: dfm(sheet.min_bend_radius)
bore.d        = 34.0mm        cause: obligation(housing.seat.stiffness)
seat.runout   = +-0.015       cause: budget(mesh_alignment)
u1.decouple.c = 22uF          cause: obligation(vdd_core.droop)
net.vdd.width = 0.3mm         cause: drc(jlc_2l.current_capacity)
```

A number that changes in review *names why it changed*. This is the
defaults test's third prong made concrete.

## 3. Two-phase resolution policy

1. **Eager.** Process-rule packs (DFM/DRC) and closed-form constraint
   propagation resolve everything they can on the pre-realization IR --
   no geometry kernel, no synthesis, no simulation. The resolver of a
   `free` slot is, concretely, a pack rule declaring
   `resolves: <field> from free` (cycle 18; hematite
   `02-language.md` sec. 10, cuprite `04-structural-layer.md` sec. 4):
   the engine picks the cheapest value satisfying the rule's demand
   and pins it as `cause: dfm(<pack>.<rule>)` / `drc(<pack>.<rule>)`
   -- the causes in section 2 above name their authoring rule.
2. **Lazy.** Only variables eager resolution cannot pin, and only when
   verification of the eager candidate fails, enter the orchestrator loop
   (`07-claims-and-evidence.md` section 6). The eager candidate *is* the
   answer if verification passes -- no loop ever spins up.

## 4. Topology/structure boundaries as domain constraints

If a value crossing some threshold would change the *structure class* of
the design (mech: a fillet consuming an adjacent face; elec: a component
value pushing a regulator between operating modes, a count change that
alters netlist topology), the feasible domain is the declared domain
intersected with the structure-preserving region. The optimizer never
proposes across the boundary. Resolving *pinned against* a boundary emits
a `note:` naming the boundary and the intentional alternative construct.
For **literal** values, crossing a structure boundary is a compile error
raised as early as it is predictable, with constructive options including
conversion to a bounded free variable.

## 5. Deleted vocabulary

This grammar replaced, and permanently retires: `var()`, `rated()`,
`promised()`, bare `margin=` as a multiplier (safety factors are `sf=`
everywhere; `margin` means only the evidence value-to-limit distance).
The *slot* a value sits in (e.g. inside an interface) is what makes it a
promise; no keyword needed.
