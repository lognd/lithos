# The Value-Source Grammar

> Regolith spec. [SETTLED] as of mech spec 0.3 (was FIX-1). The single
> biggest UX decision in the system: one grammar answers "who decides this
> number?" for every numeric slot in every language.

## 1. The five sources

Every numeric slot -- dimension, tolerance, load, stiffness, trace width,
supply voltage, clock rate, buffer depth -- takes exactly one of five
sources:

```
<value-source> ::=
    <literal>                  # the human knows it
  | in [lo, hi] [opt-dir]      # bounded freedom; the optimizer decides
  | free                       # the process-rule minimum decides
  | derived [(sf=k)]           # a consequence of system analysis; pinned
  | allocated [(policy)]       # a share of a declared budget or a planner output
```

| source | meaning | resolved by | example (mech) | example (elec) |
|---|---|---|---|---|
| literal | asserted truth | -- | `wall = 4mm` | `vdd = 3.3V +- 5%` |
| `in [lo, hi]` | optimizer decides inside hard bounds | eager propagation, then the lazy loop if needed | `radius = in [2mm, 8mm] minimize` | `c_bulk = in [10uF, 100uF] minimize` |
| `free` | cheapest legal value per process rules | DFM / DRC eager propagation | `bend.radius = free` | `trace.width = free` |
| `derived (sf=k)` | computed from system-level analysis over corners | contract solver at L2 | `loads: radial: derived(sf=1.5)` | `port.i_max: derived(sf=1.5)` |
| `allocated (policy)` | a share of a named budget, or a planner decision | budget allocator / planner | `+- allocated` in a tolerance chain | `noise: allocated` in an error budget |

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
   no geometry kernel, no synthesis, no simulation.
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
