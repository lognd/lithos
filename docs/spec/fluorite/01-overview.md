# 01 -- Overview (RATIFIED v1, cycle 20 / D93)

One sentence: fluorite declares what a fluid system must DO -- carry
these flows between these components within these pressures,
temperatures, and transients -- as a relational circuit over typed
fluid ports, and lowers it to obligations the harness discharges
through ordinary solver packs.

## Why a third track (and why not extend the other two)

- hematite owns wetted GEOMETRY (a channel's cross-section, a tube's
  bends) but has no concept of what flows through it or how circuits
  compose. Geometry is the SOURCE of hydraulic parameters, not the
  circuit itself.
- cuprite `nets:` are the right SHAPE (relational, conservation per
  node, reference reachability) but the wrong physics: fluid edges
  are nonlinear (dp ~ mdot^2), media carry properties and state
  (T, quality), and components have wetted geometry on the mech
  side. Bolting fluid semantics onto elec nets would fork both.
- The through/across discipline generalizes cleanly: current/voltage
  (cuprite) :: mdot / (p, T) (fluorite). fluorite copies the NET
  DISCIPLINE, not the electrical vocabulary.

## Personas

1. **The circuit author** writes media, components, and flownets --
   topology and intent, never solver names (regolith/07 sec. 1
   verbatim: no `fluids.colebrook` in a claim, ever).
2. **The lowering** elaborates geometry + topology into a serialized
   flownet payload plus scalar-interval givens -- the thing solver
   packs (feldspar's fluids/prop namespaces) actually consume.
3. **The harness** is UNCHANGED: same obligations, same margin rule,
   same evidence. fluorite adds a language and a payload kind, zero
   harness machinery.

## Seams (one-way arrows, as always)

- fluorite -> regolith: lowers to obligations + payload refs;
  quantity core shared (fluids.*, thermo.* namespaces exist there).
- hematite -> fluorite: a part's wetted features implement FluidPort
  interfaces; the realizer's geometry record is where hydraulic
  parameters (areas, lengths, roughness) come from. fluorite never
  re-declares geometry.
- cuprite -> fluorite: actuation crossing only -- a valve's commanded
  state is a cuprite signal; the binding is an event/config-domain
  shared through the one quantity core (see 02 sec. States).
- feldspar (or any pack) <- regolith: discharges fluorite-lowered
  obligations; consumes the `flownet` payload through the
  generalized ref channel (D96, 20-solver-abstraction sec. 8).

## v1 scope and non-goals

In: steady incompressible networks (liquids, low-Mach gases as
incompressible-with-rho(p,T) corners), component pressure-drop
models, pumps/regulators/valves/orifices/plena, NPSH/cavitation
screening, flow distribution over orbits, quasi-steady line-up
states, water-hammer TRANSIENT CLAIMS (the claim vocabulary exists;
the discharging tier is the pack's problem), heat-exchange coupling
to hematite zones.

Out (v1, recorded not forgotten): compressible network solving
(choking as a screening claim only), two-phase flow beyond
cavitation margins, medium mixing, free-surface/slosh, CFD anything.
