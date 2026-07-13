# WO-115 -- Feature proof packs: demos v2 (D222)

Status: done

## Close-out ledger (cycle 35)

LANDED (green: make check full gate + demos gate 16/16 + health-smoke):
- Demos 7-16, one per user-facing feature family, all LIVE, each a
  runnable script driving the REAL pipeline over REAL fleet designs
  with a hashed committed manifest + PROOF.md (WO-108 harness reused,
  no second harness):
  7 drawings (printer_k1 HLR sheets + small_office civil plan);
  8 BOM/cost/schedule (cnc_router_r1 real-mass BOM, timber_pavilion
    member schedule + WO-101 cost sheet over the build's own
    persisted ItemizedEstimate);
  9 assembly instructions (arm_a6 ShoulderJointAssembly through the
    real ship --spec assemblies channel; mate-ordered steps + views);
  10 3D (cnc GLBs + viewer.html verified standalone, AD-31);
  11 boards (mainboard_mx real kicad-cli gerber/drill/pos set;
     fake-tier board pin labeled; real-tool timestamp rows labeled
     deterministic=False -- documented manifest churn);
  12 firmware + HDL (espresso BrewCtl pinmux->WO-37 tree with the
     honest no-ELF surface; riscv discharged verilator tier + named
     netlist absence);
  13 test runner (4-language corpus net, cold-miss/warm-hit cache
     proof);
  14 preview (spec-less set: 3D byte-parity with ship, drawings
     differing by exactly the D197 stamp);
  15 calc book + audit (arm_a6: all 54 rows walked to a disposition,
     every sheet chain digest independently recomputed);
  16 doctor/config (host toolenv report + ui.port precedence ladder).
- run_all.DEMOS covers the union; make demos / demos-strict / the
  health demos leg (D219) run all 16; the WO-108 gate test
  generalizes (feature packs: cause_row n/a + stated pipeline path;
  completeness re-hashed against the on-disk manifest so labeled
  nondeterministic rows verify honestly).
- Docs: guide 22 (feature-pack table), guide 23, guide README.

BUG FIXED AT ROOT CAUSE (in-slice):
- WO115-F3: `regolith test` expectation grammar (`[\w.]+`) predated
  WO-68's forall expansion, so expanded claims (`strength[G1]`) were
  unaddressable and bus_shelter's design test rotted red. One shared
  _CLAIM_PATH now backs every expectation regex
  (python/regolith/orchestrator/test_expect.py); the bus_shelter
  expectation names the pinned member's claim.

FINDINGS (named gaps, artifacts NOT fabricated over them):
- WO115-F1: no fleet package emits the `cost/` dist family --
  `cost_summary_sheet` has no ship-side caller (WO-101 Status:
  in-progress) and no persisted estimate subject matches a BOM row
  fleet-wide (timber's is `all`); demo8 drives the real producer over
  the real resolved estimate and names the gap.
- WO115-F2: no lowering pass derives `FirmwareDesign` from
  `computer`/`bind` declarations (WO-37 input is caller-supplied by
  design), and only the stm32g0 reference family pack exists (the
  cubesat OBC's stm32l496 has none) -- fleet firmware ships only
  through the caller channel demo12 exercises.
- Environment note: the WO-118 feldspar self-heal misses from a
  worktree (Makefile FELDSPAR_DIR ?= ../feldspar is relative to the
  checkout, and worktrees live under .claude/worktrees/); linked
  manually via `make feldspar-link FELDSPAR_DIR=<abs>`.
Language: Python (demos/ scripts + harness; no product-code changes
  except real bugs found, which are fixed at root cause).
Spec: D222; WO-108 (the harness, manifest, PROOF.md idiom --
  REUSE, never a second harness); D219 (health demos leg covers
  the union).

## Goal

Every user-facing feature family has a runnable physical proof:
a script that drives the REAL pipeline on a REAL fleet design and
leaves inspectable physical artifacts (files a human opens) plus a
hashed manifest and a PROOF.md explaining what was proven and how
to re-run it.

## Deliverables (one demo each, extending demos/ 7..N; survey
`regolith --help` + charter 38's artifact families and cover them
ALL -- the list below is the known floor)

1. Drawings: projected multi-view SVG/PDF sheets (real HLR views,
   dimensions visible) for a mech part + a civil plan sheet.
2. BOM + cost + schedule: derived BOM with real masses + cost
   columns + member schedule, CSV/PDF forms.
3. Assembly instructions: mate-ordered steps with per-step views.
4. 3D: deterministic GLB + the offline viewer.html (proof opens
   standalone).
5. Boards: real KiCad gerber set from a BoardOutline (kicad-cli
   where resolvable, fake-tier fallback labeled).
6. Firmware + HDL: shipped ELF/netlist evidence (or the named-
   absence surface) for the computer-track projects.
7. Test runner: `regolith test` over a corpus net with the cache
   proving incremental replay.
8. Preview: spec-less `regolith preview` artifact set vs ship
   byte-parity where designed.
9. Calc package + audit index (after WO-114 merges): the calc book
   for one project, with the audit walk demonstrated (every
   obligation row resolves).
10. Doctor/config/toolenv: environment report + config precedence
    demonstration (text artifacts are fine here).
11. run_all.py + make demos + the health demos leg cover the new
    set; each demo's manifest is content-hashed and committed.

## Acceptance

- `make demos` green with every pack live; artifacts regenerate
  byte-identically where the underlying family is deterministic
  (label the honestly-nondeterministic ones with why).
- PROOF.md per demo states: feature proven, pipeline path
  exercised, artifact inventory, re-run command.
- `make check` + health green.

## Escalation

A feature that CANNOT produce a physical artifact end-to-end is a
finding (placeholder number) -- report it, do not paper over it
with a synthetic artifact.
