# WO-108 -- Optimization proof packs: physical artifacts for every optimizer surface (D218)

Status: open
Language: Python (demo scripts + small glue); consumes every
  landed emission family; NO verdict-machinery changes
Spec: D218.1 (the directive); AD-30 (one optimization engine);
  charter 38 (the artifact families); WO-55/56/57/77 ledgers (the
  landed surfaces); WO-65 + WO-97/D209 (the two surfaces landing
  in parallel -- consume them if merged, else record the honest
  gap and wire the script to pick them up).

## Goal

`demos/` contains one runnable script per optimization surface.
Each script runs the REAL pipeline end to end and emits PHYSICAL
artifacts -- drawings (SVG + PDF), STEP, GLB + offline viewer,
BOM, gerbers where elec -- into `demos/out/<demo>/` with a
manifest of content hashes, plus a `PROOF.md` narrating what was
optimized, the pinned winner, and where each artifact shows it.
A committed runner (`make demos`) executes all of them; a test
asserts each demo's manifest is complete and deterministic.

## The surfaces (one demo each)

1. `select` discrete choice: ebi_decode (WO-56) -- the
   `cause: optimize(...)` pin rendered on its sheet; policy-flip
   variant shows the winner change.
2. Continuous staged evaluator: duct_vane (WO-57) -- two minimize
   dims pinned; before/after geometry (STEP + GLB) and the
   opt_trace sheet.
3. Removal vocabulary pins: ribbed_panel (WO-77) -- count/
   thickness pins; STEP with the ribs, drawing with cited pins.
4. Section search (WO-65): a civil design's `section_domain`
   family searched; plan + member-schedule sheets with
   optimizer-pinned sections and the search trace.
5. Bounded sketch slot (WO-97/D209 coupling): WingSpar (or the
   first coupled part) -- STEP whose profile dimension carries
   `cause: optimize(...)` from a REAL margin search, drawing with
   the pinned value cited.
6. Fleet showcase: one full `regolith ship` package (a green
   fleet project) copied/linked into the demo tree -- the
   complete dist/ with index, ledgers, drawings, 3d, bom.

## Rules

- Scripts run the real CLI/pipeline (no bespoke evaluators, no
  fixture-only paths); deterministic outputs (two runs
  byte-identical for every deterministic format).
- A surface whose machinery is not yet merged emits an HONEST
  `PROOF.md` gap note and exits nonzero from `make demos-strict`
  (never a fabricated artifact); the runner prints which demos
  are live.
- ASCII everywhere; outputs under demos/out/ are gitignored
  EXCEPT each demo's manifest + PROOF.md (committed evidence of
  shape, not bytes).

## Acceptance criteria

- `make demos` runs every live demo green from a clean checkout;
  each emits its physical artifact set and manifest; PROOF.md per
  demo names the optimized quantity, winner, cause row, and
  artifact files.
- Demos 1-3 + 6 live at landing; 4-5 live the moment WO-65 /
  WO-97-coupling merge (wired, tested behind availability probes).
- `make check` green; a fleet-gate-style test keeps demo
  manifests deterministic.
