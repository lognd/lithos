# calcite -- fluid circuits for lithos (DRAFT v0)

Status: PROPOSED spec, drafted 2026-07-07 from the feldspar
stress-test finding G25 (`20-solver-abstraction.md` sec. 7 item 6;
reproduction case
`../feldspar/examples/lithos/regen_engine/feed_lines.hem`). Enters
the normative set when a design cycle adopts it; until then nothing
depends on it and the sec. 7 ask stays open.

calcite is the third lithos language track: hematite describes
solids, cuprite describes electrical intent/structure, calcite
describes INTERNAL FLOW TOPOLOGY -- feed systems, coolant loops,
hydraulics, pneumatics, lubrication, HVAC. Name: calcite (CaCO3),
the mineral that dissolves and precipitates -- the one that FLOWS
through the rock; extension `.calc`.

The gap it closes: flow circuits today are inexpressible (hematite
pockets are secretly manifolds; cuprite `nets:` are electrical), so
hydraulic obligations cannot be lowered from design intent, givens
are hand-asserted, and feldspar's entire fluids catalog has no
source of truth to consume.

Reading order:

1. `01-overview.md`  -- scope, personas, seams, non-goals
2. `02-language.md`  -- media, fluid ports, components, flownets,
                        states, claims
3. `03-lowering.md`  -- elaboration rules, obligation shapes, the
                        flownet payload, feldspar/harness seam,
                        cross-track couplings
4. `04-open-questions.md` -- COPEN list

House rules apply verbatim: quantity core is shared (regolith/02),
claims say WHAT never HOW (regolith/07 sec. 1), evidence/margin
machinery unchanged, ASCII only.
