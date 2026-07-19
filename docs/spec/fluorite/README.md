# fluorite -- fluid circuits for lithos

Status: RATIFIED v1 (design cycle 20, 2026-07-07, D93). Drafted
2026-07-06 as `calcite`/`.calc` from the feldspar stress-test finding
G25 (`20-solver-abstraction.md` sec. 7 item 6; reproduction case
`feldspar:examples/lithos/regen_engine/feed_lines.hema`); ratified
after the adversarial read against the four demand fixtures
(feed_lines + the dune-buggy circuits, feldspar G39) with the F98
fixes folded in and the name changed (D93: `calcite`/`.calc` read as
a calculation package and are now dead names).

fluorite is the third lithos language track: hematite describes
solids, cuprite describes electrical intent/structure, fluorite
describes INTERNAL FLOW TOPOLOGY -- feed systems, coolant loops,
hydraulics, pneumatics, lubrication, HVAC. Name: fluorite (CaF2), the
mineral named for flowing (Latin `fluere`: it flows as a smelting
flux, and it named both flux and fluorine) -- the ore-mineral scheme
continues (hematite/iron/mech, cuprite/copper/elec). Extension
`.fluo`, registered in the ONE extension registry module in
`crates/regolith-syntax` (WO-31).

The gap it closes: flow circuits were inexpressible (hematite pockets
are secretly manifolds; cuprite `nets:` are electrical), so hydraulic
obligations could not be lowered from design intent, givens were
hand-asserted, and feldspar's entire fluids catalog had no source of
truth to consume.

Reading order:

1. [01-overview.md](01-overview.md)  -- scope, personas, seams, non-goals
2. [02-language.md](02-language.md)  -- media, fluid ports, components, flownets,
                        states, claims
3. [03-lowering.md](03-lowering.md)  -- elaboration rules, obligation shapes, the
                        flownet payload, feldspar/harness seam,
                        cross-track couplings
4. [04-open-questions.md](04-open-questions.md) -- FOPEN ledger (all deferred items carry
                        reopen criteria; the open queue is empty,
                        F90 discipline)

House rules apply verbatim: quantity core is shared (regolith/02),
claims say WHAT never HOW (regolith/07 sec. 1), evidence/margin
machinery unchanged, ASCII only.

Implementation: WO-31 (front end + the AD-23 generalized net core),
WO-32 (lowering + the `flownet` payload + the realized-geometry
extraction seam).

Naming note (cycle 26): the retired draft name `calcite` was later
reassigned to the CIVIL track (D133, `docs/spec/calcite/`, files `.calx`);
`.calc` stays dead. References to calcite in this README's history
lines mean the fluid draft only.
