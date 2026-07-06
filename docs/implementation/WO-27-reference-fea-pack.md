# WO-27: Reference external FEA pack (working name: feldspar)

Status: todo
Depends: WO-20 (plugin layer), WO-21 (signing), WO-22 (geometry to
mesh); name is OWNER'S CALL before first publish
Language: Python, SEPARATE distribution in `packs/feldspar/`
(excluded from the regolith wheel, AD-19/D-F)
Spec: regolith/07 sec. 3 (reduced/full tiers), sec. 2 (swept
obligations, coverage), sec. 5 (corner discipline); design:
`20-solver-abstraction.md`

## Goal

The first external solver pack, built OUTSIDE the regolith package
against the public pack protocol: a reduced-tier shell/solid FEA
model that discharges stress/deflection claims the closed-form tier
cannot close, signs its evidence, and proves the WO-20/21 contract
from the consumer side. What this WO validates matters more than the
solver's sophistication.

## Deliverables

- `packs/feldspar/` distribution: own `pyproject.toml`, depends on
  `regolith` (never vice versa), exposes the
  `regolith.model_packs` entry point.
- Solver choice: CalculiX (ccx) driven via the WO-20 subprocess
  adapter -- boring, packaged everywhere, deterministic given a fixed
  mesh. Meshing via gmsh with a FIXED seed/algorithm folded into the
  settings digest (INV-10: the pack is only as deterministic as its
  digest is honest).
- Models: `mech.fea.static_stress` (upper, von Mises) and
  `mech.fea.static_deflection` (upper), reduced tier: signature
  declares required inputs (geometry ref from WO-22's realized
  record, material, loads/BCs from the obligation's given), validity
  domain (linear elastic, small deflection), cost, and a mesh-
  convergence-derived eps (two-refinement Richardson estimate charged
  into eps -- the margin rule stays the ONE discharge rule).
- Corner discipline: interval givens swept at declared worst corners;
  swept obligations report coverage `corners`/`grid(k)` per
  regolith/07 sec. 2.
- Evidence signing (WO-21): the pack ships a key; the conformance
  suite verifies `Valid(tier)` under a designated key set.
- Conformance: the pack runs the `tests/packs/` suite green from its
  OWN test session (the protocol's outside-consumer proof); plus
  known-answer tests (cantilever vs Euler-Bernoulli within eps;
  thick-wall cylinder vs Lame within eps -- the closed-form packs are
  the oracles).
- CI: a separate job installs regolith + the pack and runs the
  pack's tests (the wheel exclusion is asserted: `regolith` wheel
  contains no `feldspar` module).

## Acceptance

- A thin-margin corpus stress claim that the Lame/beam closed-form
  tier leaves indeterminate is DISCHARGED by the FEA pack through
  `orchestrator.build`, with signed evidence, coverage stated, and
  the cheaper tier still selected first when margins are fat
  (best-path ordering asserted).
- Uninstalling the pack returns that claim to honest indeterminate
  (`harness.no_model`) -- no regolith code change.
- Same request twice -> byte-identical evidence hash (determinism
  through mesh + solver, via the settings digest).
- Pack tests + regolith `make check` both green.
