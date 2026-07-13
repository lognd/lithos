# WO-108 -- Optimization proof packs: physical artifacts for every optimizer surface (D218)

Status: done (2026-07-13; demos/ live, make demos green, make check green)
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

## Close-out ledger (2026-07-13; coordinator assigns final D/F numbers)

LANDED (committed, `make demos` green, completeness+determinism test
green in `make check`):
- `demos/harness.py` -- the per-demo output tree, content-hashed
  `Manifest` (sha256, deterministic JSON), `PROOF.md` writer, and the
  `gap_proof` honest-gap path.
- `demos/run_all.py` + `make demos` / `make demos-strict` -- the runner
  (live-only green vs. fail-on-any-not-live) in the Makefile house style.
- Demo 1 (`select`/ebi_decode) LIVE: real `compiler.check` ->
  `choice_points` -> `optimize_discrete` -> `winner_lock_row`; emits the
  pinned + policy-flip lockfiles and the opt_trace sheet (SVG+PDF).
- Demo 2 (continuous/printer_k1) LIVE: the landed golden-section
  evaluator over two real minimize dims (bed `a`, carriage `b`), each
  minimizing OCCT-measured mass; before/after STEP + GLB + viewer + both
  opt_trace sheets + the two-row lockfile.
- Demo 3 (removal/ribbed_panel) LIVE: nested discrete-count x
  golden-section-thickness over real OCCT realizations; the ribbed STEP
  solid + part drawing + both opt_trace sheets + the two-row lockfile.
- Demo 4 (section search/footbridge, WO-65) LIVE behind a probe: real
  `orchestrate.build` runs `search_free_section`; emits the two
  `optimize(mass_per_length, ...)` rows, the search-trace sheets (loaded
  from the persisted traces), and the civil plan/member-schedule sheet.
- Demo 6 (fleet showcase/small_office) LIVE: the real two-command
  `build --release` + `ship` CLI flow; small_office's build itself runs
  the free-section search, so the shipped 20-file `dist/` package's own
  lockfile carries two live `optimize(...)` rows.
- Demo 5 (bounded sketch slot, WO-97/D209) LIVE, retargeted per F128.3
  from `uav_talon` WingSpar to `arm_a6` UpperArm (`UpperArmSection.b`,
  [24mm, 40mm]) -- the part that genuinely pins. Drives
  `optimize_sketch.pin_bounded_slot` end to end: golden-section search
  over the bounded width, each candidate realized (OCCT) and discharged
  against the registered `mech.beam.cantilever_deflection` model with
  DECLARED inputs (force 6.87N from `link1.hema`'s `payload_deflection`
  claim, span 300mm from the promoted profile, E=68.9GPa AL6061_T6,
  thickness 20mm). Winner b=24.000mm (limit slack at every candidate);
  a tightened-limit rerun (2e-5m) moves the winner to ~30.5mm, the
  binding-constraint evidence that the search is real, not a rubber
  stamp -- both recorded in `PROOF.md`. Emits the pinned `regolith.lock`
  row, the winning STEP + GLB + viewer, and the opt_trace sheet
  (SVG+PDF). `uav_talon` WingSpar is NOT live through this coupling --
  its governing load is `derived(sf=1.5)` with no declared scalar force,
  so driving it would require fabricating a load (forbidden by D209);
  this honest residual is named in demo 5's `PROOF.md`, not silently
  dropped.
- `tests/test_wo108_demos.py` -- the fleet-gate-style completeness +
  determinism + honest-gap test (wired into `make check`).
- Guide chapter `docs/guide/22-proving-optimizations.md` (+ README row).

PROBE-GATED (none remaining; all 6 demos LIVE as of 2026-07-13):
- (was) Demo 5 bounded sketch slot -- see LANDED above. The general
  `orchestrate.build`-level coupling (a bounded slot pinning inside the
  ordinary build pipeline, as originally scoped against `uav_talon`) is
  still not wired -- demo 5 drives `optimize_sketch.pin_bounded_slot`
  directly rather than through `orchestrate.build`. That build-level
  wiring is a residual, tracked as [PROOF-F4] below, not a demo gap.

FINDINGS (placeholder labels; coordinator numbers/records):
- [PROOF-F1] The civil member-schedule producer (`civil_plan_section`)
  renders each free member's DECLARED domain (`unresolved`) rather than
  writing back the searched winner; demo 4 shows the pinned section
  authoritatively via the lockfile row + opt_trace sheet and names this
  as a WO-65 producer follow-on (out of WO-108's no-machinery-change
  scope). A one-line producer change would let the schedule cell show the
  optimizer-pinned section.
- [PROOF-F2] The `regolith optimize` CLI subcommand consumes only a
  closed-form JSON spec (`discrete_domains_from_spec`); it cannot read a
  compiled `BuildPayload.choice_points` entry, so the real `by select`
  optimize chain (demo 1) is only reachable through the orchestrator
  Python API. A future `optimize` CLI seam that consumes compiled choice
  points would let demo 1 run wholly through the console entry.
- [PROOF-F3] `duct_vane` (named in the WO body for demo 2) is not a
  landed corpus member; printer_k1's real minimize dims are the proven
  substitute (the same substitution `tests/backends/test_parity.py` and
  WO-64 already record). Adding a `duct_vane` fluid exemplar would let
  demo 2 name it directly.
- [PROOF-F4] Demo 5 drives `optimize_sketch.pin_bounded_slot` directly
  (the D209 evaluator) rather than through `orchestrate.build`'s
  ordinary discharge pipeline; the general in-pipeline coupling (a
  bounded slot pinning as a side effect of a plain `build`, with no
  demo-side evaluator call) is not yet wired. `uav_talon` WingSpar
  remains genuinely blocked either way -- its load is
  `derived(sf=1.5)`, never a declared scalar -- so this residual is
  scoped to the wiring path, not a missing model.
