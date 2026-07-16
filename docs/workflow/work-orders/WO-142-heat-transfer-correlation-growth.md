# WO-142 -- heat-transfer correlation growth (feldspar-side + thin lithos pad checks) (F158/F159)

Status: open (Depends: WO-138; parallel with WO-139/140/141/143 --
  does not gate or get gated by them)
Language: feldspar repo (its own conventions: Rust core + Python
  pack, calibration-first) for the correlation directions; Python
  (lithos harness) ONLY for a thin pad-check model, and ONLY if a
  demo claim (WO-144) needs pack-free discharge.
Spec: F159 sec. 1.5/d1 (feldspar today has Dittus-Boelter HEATING
  only, `feldspar:python/feldspar/heat/closed_form.py:205`; the
  missing directions this WO adds); AD-37 ruling 1 (the shared
  boundary rule: closed forms needing no numeric solve MAY live on
  either side; a coupled/conjugate solve is feldspar-only, certified
  tier per INV-14); `docs/spec/toolchain/20-solver-abstraction.md`
  sec. 7 (feldspar-recorded asks); feldspar spec 12 (the boundary
  rule, shared verbatim between repos, same citation WO-135 uses);
  D258's licensing table (`scratch_recon_thermo_fluids.md` sec. 3)
  for each correlation's citation posture.

## Goal

The heat-transfer correlation set feldspar exposes widens from one
branch (Dittus-Boelter heating) to the set the fleet's HX/thermal
claims actually need, each transcribed from its primary paper (or an
acceptable textbook restatement where the primary is paywalled, per
the standing house rule `fluid_pressure_drop.py:83` already uses);
coupled/conjugate problems are named as a recorded wall, not
attempted.

## Deliverables (feldspar half -- its own repo, its own WO)

1. Gnielinski 1976 (Gnielinski, V., Int. Chem. Eng. 16(2):359-368):
   f-coupled Nu correlation, 3000 < Re < 5e6 -- consumes the
   friction factor from WO-139's model, the natural pairing the
   recon names (Nu depends on f).
2. Dittus-Boelter COOLING branch (n = 0.3; Dittus & Boelter 1930,
   Univ. Calif. Publ. Eng. 2:443, reprinted Int. Comm. Heat Mass
   Transfer 12 (1985) 3-22) -- completes the existing heating-only
   implementation.
3. Laminar fully-developed Nu constants: 3.66 (constant T_wall), 4.36
   (constant q'') -- Incropera & DeWitt, Fundamentals of Heat and
   Mass Transfer, Table 8.1 lineage.
4. Churchill & Chu 1975 natural convection: horizontal cylinder
   (Int. J. Heat Mass Transfer 18:1049-1053) and vertical plate
   (18:1323-1329).
5. NTU-effectiveness relations per flow arrangement (Kays & London,
   Compact Heat Exchangers, 3rd ed., 1984; restated Incropera Table
   11.4) -- algebraic closed forms composing UA -> NTU ->
   effectiveness -> outlet temperatures under an error budget, the
   feldspar route-planner's natural territory.
6. Each direction cites its primary paper (or textbook restatement
   where paywalled, named explicitly as such); calibration tests
   follow the benchmarks-memo pattern
   (`docs/workflow/research/2026-07-08-benchmarks-and-datasets.md`
   sec. 3).

## Deliverables (thin lithos pad check -- CONDITIONAL)

7. A `thermo.htc` (or hx-outlet) pad-check harness built-in lands
   ONLY IF WO-144's demo needs pack-free discharge for a claim
   neither existing lithos thermal model
   (`thermo.junction_temperature`, node-temperature claims) covers.
   If the demo does not need it, record "not needed" in the
   close-out rather than pre-building unclaimed surface (the AD-41
   F145 lesson: no surface without a consumer).

## Out of scope (recorded wall, D258/F159 sec. 1.5/d3)

- Conjugate/coupled problems: any solve where flow and heat are
  mutually dependent (the thermosiphon buoyancy loop: HxSegment zone
  <-> wall temperature fields) is feldspar `CoupledGroup` territory,
  already named at `docs/spec/fluorite/03-lowering.md:114-124`. This
  WO does NOT attempt it -- name it as its own future feldspar slice,
  do not promise it in this wave.
- Full conjugate CFD-class solving -- AD-30's "packs, never in-tree",
  certified tier per INV-14; not this WO's territory at all.

## Acceptance

- feldspar `make check` (its own gates) green; each new correlation
  has a calibration test against a published worked example, cited
  by source + edition + example/table number in the test itself.
- Each direction's docstring/citation names its primary paper; where
  the primary is paywalled (Gnielinski, Churchill-Chu), the citation
  explicitly states the textbook-restatement basis (Incropera &
  DeWitt) rather than silently citing only the textbook.
- The conjugate/coupled wall is recorded in the close-out with an
  explicit pointer to `03-lowering.md:114-124` -- not silently
  dropped, not attempted.
- If deliverable 7 (the lithos pad check) is built: its citation is
  present and printed on its calc sheet, and a fleet claim actually
  reaches it (build-report evidence in the close-out). If not built:
  the close-out states "not needed" and names which demo claim was
  checked against.
- `make check` green on the lithos side (only touched if deliverable
  7 lands).

## Escalation

If a demo claim needs something that turns out to be conjugate/
coupled, do not attempt a shortcut solve -- name it as hitting the
d3 wall and hand it to a future feldspar slice; this is the honest
outcome the recon anticipated, not a WO failure.
