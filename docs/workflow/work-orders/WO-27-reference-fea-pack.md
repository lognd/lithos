# WO-27: Reference external FEA pack (feldspar)

Status: honest-partial (lithos-side conformance run against the real
installed `feldspar` distribution, `tests/packs/test_feldspar_
conformance.py`; feldspar-side M1/WO-01..11 built and shipped in the
sibling repo). REMAINING: the PAYLOAD half (`geometry.realized`
end-to-end from a real `.hema` lowering) stays blocked on WO-22's
end-to-end half (feature-program emission from `regolith-lower` is
still the named upstream wall; WO-22's own file is unchanged by this
WO). The CI deliverable (a separate job installing regolith + the pack,
asserting the wheel exclusion) is NOT added in this pass -- scope note
below.
Depends: WO-20 (plugin layer), WO-21 (signing), WO-22 (geometry to
mesh); name CONFIRMED by owner 2026-07-05: **feldspar**
Language: Python, SEPARATE repository (`feldspar`, owner decision
2026-07-05; excluded from the regolith wheel, AD-19/D-F)
Spec: regolith/07 sec. 3 (reduced/full tiers), sec. 2 (swept
obligations, coverage), sec. 5 (corner discipline); design:
`../../spec/toolchain/20-solver-abstraction.md`

## Goal

The first external solver pack, built OUTSIDE the regolith package
against the public pack protocol: a reduced-tier shell/solid FEA
model that discharges stress/deflection claims the closed-form tier
cannot close, signs its evidence, and proves the WO-20/21 contract
from the consumer side. What this WO validates matters more than the
solver's sophistication.

## Deliverables

- The `feldspar` distribution (own repository `feldspar`, own
  `pyproject.toml`): depends on `regolith` (never vice versa),
  exposes the `regolith.model_packs` entry point.
- Solver choice: CalculiX (ccx) driven via the WO-20 subprocess
  adapter -- boring, packaged everywhere, deterministic given a fixed
  mesh. Meshing via gmsh with a FIXED seed/algorithm folded into the
  settings digest (INV-10: the pack is only as deterministic as its
  digest is honest).
- Models: static stress (upper, von Mises) and static deflection
  (upper), reduced tier: signature declares required inputs
  (geometry ref from WO-22's realized record, material, loads/BCs
  from the obligation's given), validity domain (linear elastic,
  small deflection), cost, and a mesh-convergence-derived eps
  (two-refinement Richardson estimate charged into eps -- the margin
  rule stays the ONE discharge rule).
  KIND NAMING (cycle 20, D94): the models register under the
  VOCABULARY kinds (`mech.static_stress`, `mech.static_deflection`)
  and compete with the closed-form tier in one graph; method-named
  kinds (`mech.fea.*`) become a registration lint error when WO-30
  lands (feldspar 06's constructor override is the pre-WO-30
  interim).
  CHANNEL (cycle 20, D96): geometry refs cross as
  `geometry.realized` / `geometry.parametric` payload refs on the
  WO-30 channel. The SCALAR conformance half of this WO (parametric
  ports, corner sweep, signing) is dispatchable BEFORE WO-30; the
  payload half after.
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

## Conformance run (this pass, scalar half)

`tests/packs/test_feldspar_conformance.py` runs against the REAL
`feldspar` distribution (`pip install`ed non-editable from
`../feldspar`, not a fake/synthetic pack): entry-point discovery,
cost-ordered selection, total discharge, a thin-margin
`mech.static_stress` corpus claim discharged through
`orchestrator.build` with a signed + verified (`Valid(certified)`)
attestation and coverage stated, the pack "uninstalled" (no
`load_packs` composition) reverting the same claim to
`harness.no_model`/indeterminate with zero regolith code change,
byte-identical repeat-discharge evidence, and cost-ordered best-path
selection (the real feldspar model registered under a closed-form
model's own claim kind via its documented `claim_kind=` override,
`ModelRegistry.select`'s pure `(cost, model id)` order proven live).
No `ccx`/`gmsh` needed: at these requests' eps budget, feldspar's own
internal planner always finds its closed-form direction sufficient
(checked live, not assumed) -- consistent with feldspar's own posture
that discretized-solve paths need a tooled environment to exercise.

Installing feldspar system-wide also exposed a latent gap in the
existing WO-20 pack-discovery test (`tests/packs/test_pack_protocol.
py::test_load_packs_composes_deterministically_sorted_by_name`): it
built its baseline registry via `default_registry()`, which now also
discovers any REAL installed `regolith.model_packs` distribution, not
only its injected fakes. Fixed to build from `register_all` directly
(the isolation the test always intended); see the same commit series.

CUTS (named, not silently dropped):
- The CI "separate job" deliverable (install regolith + the pack, run
  the pack's tests, assert the wheel excludes `feldspar`) is not added
  in this pass -- `.github/workflows/` changes were judged out of the
  dispatched scope (Python-only conformance run) and are left for a
  follow-up.
- Mesh-convergence Richardson eps and the discretized ccx/gmsh solve
  path are feldspar-side implementation (already built, per feldspar's
  own M1 close-out); this WO's lithos-side tests do not force that
  path since it needs a tooled environment this sandbox lacks.
