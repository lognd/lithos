# 04 -- Open questions (COPEN ledger)

Elaboration disposition (cycle 27, D139): the charter opened no
COPENs and the elaboration opened none -- every discretionary point
was either decided by the charter, resolved by an existing regolith
mechanism (the F90 discipline), or is listed below as
deferred-with-reopen-criteria (charter sec. 7 restated with the
cycle-27 amendments). The open queue is EMPTY; each deferral names
the exact evidence that reopens it, and anything short of that
evidence must not reopen the item.

- **Geometry/BIM authoring or IFC export**: v1 has grids/levels and
  declared areas/lengths only. Drawing SHEETS are now IN SCOPE via
  the D140 documentation surface (toolchain/25, WO-50) -- derived
  output, not authored geometry. REOPEN the authoring/IFC half only
  when a consumer needs coordinated 3D geometry across trades; the
  AD-25 producer seam is where it would land (a BIM import becomes a
  realized-IR producer, never a second frame schema).

- **Construction cost estimation**: CLOSED by D147 (cycle 27) -- the
  owner supplied the demand this deferral's reopen criterion named.
  Cost is a claim over a project-declared profile
  (toolchain/27-costing.md; quantity takeoff = the L6 schedules x
  profile unit-cost records; machinery WO-54). Construction
  SCHEDULING (durations, sequencing) remains deferred: REOPEN on a
  real scheduling use case; the `mfg` time namespace is the landing
  zone.

- **Rebar/connection detailing**: transfer classes carry capability
  envelopes, not detailed designs. REOPEN when a fabricator-facing
  backend is asked for; the detailing pack would be `std.civil`
  content over the existing connection records, plus a WO-50 sheet
  family.

- **Soil mechanics beyond declared bearing/frost records**: geotech
  reports stay `by test` records with trust tiers. REOPEN on a
  foundation-design use case (settlement/consolidation claims); the
  solver home would be a feldspar namespace, never calcite surface.

- **Zoning/site-plan law**: building-code-shaped (rule packs) but
  jurisdiction data is unbounded. REOPEN when a real jurisdiction
  pack is contributed.

- **HVAC air-side (duct networks)**: no longer blocked on gas-medium
  maturity -- D141 closed FOPEN-2 (compressible delivery is a
  discharge tier), so low-velocity duct networks are expressible
  TODAY as fluorite gas-medium subnets with `std.fluid` air records.
  What remains deferred is calcite-side convenience vocabulary
  (diffuser/register classes, air-change claims). REOPEN with a
  duct-network corpus example that the fluorite surface makes
  awkward; expected resolution is `std.fluid.circuits` pattern
  content (D144), not calcite surface.

- **Occupant simulation (evacuation modeling)**: L2 egress checks
  are prescriptive-code arithmetic. Performance-based design
  (evacuation simulation evidence) REOPENS only when a real
  performance-based submission needs it; the mechanism is already
  present (an obligation discharged by a simulation-tier pack with
  declared coverage) -- it is registry content, not language.
