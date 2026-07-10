# 34 -- Topology-class geometry optimization and the FEA loop (design charter; D184/D185, cycle 32)

> Charter for the erosion/topology optimization class and for
> FEA-decided variables. Two-phase by design: declared removal
> vocabularies first (all existing machinery), density-field
> synthesis second (feldspar solver capability, gated). Ledger
> rules: D184/D185 (design-log 2026-07-10-cycle-32); charter 30
> sec. 3's non-goal is REVISED by this charter exactly along its
> own named reopen route. Machinery: WO-76 (FEA loop demo), WO-77
> (phase-1 vocabulary); phase 2 gets its own WO only after both.

## 1. FEA-decided variables (D184): doctrine, not mechanism

A value "determined by FEA" is `in [lo, hi] minimize|maximize`
whose feasibility claims discharge through an FEA-class model:
the engine walks the domain, FEA draws the feasible boundary, the
winner pins with its trace. Rung 5 (`model=<fea-impl>`) forces the
expensive path when cheap-tier screening must not decide.
Everything is landed; WO-76 is the demonstration + cost accounting
(per-evaluation wall time, cache-hit incrementality, budget
honesty). FEA-authored `derived` values ride the SensitivityHook
seam if ever needed -- reopen criterion: a real case the
boundary-finding form cannot express.

## 2. Phase 1 (WO-77): declared material-removal vocabularies

> LANDED (cycle 33, WO-77/D200): the vocabulary below is live --
> grammar/validation in `regolith-lower::removal` (misuse surface
> E0451), DFM reference packs in
> `examples/tracks/hematite/std_removal.hema`, exemplar + optimizer
> pin-proof in `examples/tracks/hematite/ribbed_panel.hema` and
> `tests/orchestrator/test_wo77_removal.py`, spec entry in
> hematite/07 sec. 2a. This section's text is the charter of record,
> unchanged.

The honest erosion: the author DECLARES a removal family; the
optimizer explores its parameters; the feature chain realizes it;
FEA-class discharge verifies it; parity attributes it.

- Vocabulary (hematite, spec cycle inside WO-77 -- grammar goes
  through the ordinary elaboration discipline): pattern-shaped
  feature ops over a target region -- `ribs(count in [..], pitch
  in [..], thickness in [..])`, `pocket_grid(...)`, `shell(t in
  [..])`, `lattice(cell in {...}, density in [..])` -- each
  lowering to ordinary FeatureProgram ops (the coverage ledger
  grows accordingly; an unsupported cell family is a named skip).
- The optimizer needs NOTHING new: pattern parameters are ordinary
  bounded/discrete slots; mass/stiffness objectives are ordinary
  budgets + claims; the staged evaluator already realizes each
  candidate.
- Manufacturability is not optional: every explored candidate
  passes the DFM tier like any authored geometry (a lattice a
  process cannot make is infeasible, not clever).

## 3. Phase 2 (gated): density-field synthesis as a solver capability

SIMP/BESO-class optimization enters as a feldspar solver: design
domain + load cases + volume/compliance target in; optimized
density field + EXTRACTED candidate geometry out. Constitution:

- The output is a PROPOSAL: a candidate RealizedGeometry + its
  trace-class evidence (iterations, compliance history, seed,
  mesh/filter parameters -- all content-addressed). Adoption is a
  source edit by the author (AD-28 sovereignty verbatim: synthesis
  proposes, never silently substitutes). An adopted candidate is
  then verified like ANY import: full FEA discharge + DFM tier on
  the extracted body -- the extract-to-manufacturable step is
  phase 2's honesty risk, and DFM discharge is the gate that keeps
  it real (a smoothed blob that cannot be made fails loudly).
- Feldspar-side law applies: cited formulation (SIMP per
  Bendsoe/Sigmund; filters cited), calibration against published
  benchmark cases (the MBB beam class), validity predicates,
  deterministic seeding.
- GATES: WO-76 landed (the FEA loop is the inner engine), WO-77
  landed (the cheap alternative exists so phase 2 is chosen on
  merit), and an owner check-in on the compute-budget class
  (density-field runs are orders costlier than anything the
  harness schedules today).

## 4. Non-goals (reopen criteria attached)

- Generative "AI-suggested" geometry outside the two forms above
  (no provenance = no entry).
- Shape-derivative/level-set methods in v1 of phase 2: SIMP-class
  first; reopen on a benchmark phase 2 cannot pass.
- Multiphysics topology (thermal-structural coupled) until the
  structural loop is proven.
