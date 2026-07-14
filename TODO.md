# TODO -- the live queue

## START HERE (note to a fresh instance)

You are (probably) reading this with no memory of earlier cycles.
Orientation, in order:

1. `docs/README.md` -- what this project is (four declarative
   engineering languages over one shared regolith + the toolchain).
2. `docs/spec/regolith/` 01 -> 13; `13-invariants.md` is the ledger of
   every guarantee (INV-1..30) with its proof argument -- normative.
3. The language tracks: `docs/spec/hematite/` (mech, `.hema`),
   `docs/spec/cuprite/` (elec/computer, `.cupr`), `docs/spec/fluorite/`
   (fluid, `.fluo`, ratified cycle 20), `docs/spec/calcite/`
   (civil/architectural, `.calx`, chartered cycle 26, ELABORATED
   cycle 27 -- 02/03/04 + corpus exist, awaiting owner
   ratification).
4. `docs/spec/toolchain/00-architecture.md` -- NORMATIVE (AD-1..39);
   wins over any WO body it conflicts with. Charters 25 (drawings +
   quality audit), 26 (pattern libraries), 27 (costing) are the
   cycle-27 additions; 28 (optimization engine) and 29 (interaction
   surface: config/TUI/GUI) are cycle 30's; 30 (geometry depth),
   31 (flagships + parity bar), 32 (stdlib depth, cross-repo), and
   33 (CAM verification) are cycle 31's; 34-37 (topology, signal
   integrity, board correctness, design testing) are cycles 32-33's;
   38 (emission + release) is cycle 34's; 39 (stdlib organization)
   is cycle 35's; 40 (debug + bring-up) and 41 (artifact
   presentation) are cycle 36's.
5. `docs/workflow/README.md` -- ground rules + the DISPATCH
   PROTOCOL every agent follows + the WO dependency graph.
6. `docs/workflow/design-log/` -- dated ledgers of every finding (F1..) and
   decision (D1..); THE project history. Nothing here is re-decided
   without new evidence.
7. `examples/` -- the spec pressure corpus and golden workload.
8. SIBLING REPO `feldspar` (github.com/lognd/feldspar; locally
   checked out beside this repo) -- the external solver pack
   (M1 + symbolic core DONE through its WO-11). Its regolith-side
   contract asks live in
   `docs/spec/toolchain/20-solver-abstraction.md` sec. 7.

NAMES (settled; do not re-litigate): hematite / cuprite / fluorite /
calcite the languages; **magnetite** the package manager
(`magnetite.toml`; quarry + lodestone are RETIRED names, cycle 26
D132); **regolith** the toolchain/CLI/import name; **lithos** the
umbrella brand; **feldspar** the sibling solver pack. Dead names
(`mill`, `loom`, `dcad`, `deda`, `quarry`, `lodestone`, and
calcite's old life as the fluid draft with `.calc`) appear verbatim
only in `docs/workflow/design-log/` history and negative tests.

House rules that are easy to violate accidentally: ASCII only
(repo-wide, no exemptions); one word one idea (hematite/04 sec. 1);
every decision argued against the mantras (Unambiguous >
Intent-based > User-friendly); every cycle gets a dated design log;
version-bump the track headers you materially change; new
guarantees enter the invariant ledger WITH a proof argument in the
same change; extension strings live in EXACTLY ONE registry module
(`regolith-syntax`); schemas are single-sourced in Rust (`make
schema`, never hand-edit `_schema/`); only `compiler.py` imports
`regolith._core`; errors are DATA (diagnostics / typani Results);
stdout is data, logs to stderr; `make check` green before any WO
closes, flipping its `Status:` line in the same change. `make health`
(WO-106/D219) is the whole-repo bar -- one command, four legs (check +
fleet + demos + consistency), run it at cycle close to prove everything
still ships, every optimization still has a physical proof, and the
docs/goldens/waivers still agree (guide 23-health-gate.md).

Current state in one line: cycles 1-35 are CLOSED -- the whole
static core + all four tracks + optimization + emission v2 (every
fleet project ships release-clean, 15/15) + the cycle-35 rigor
flip (71 model-backed discharges, QA-verified, calc-book audit
trail, demos 16/16, graphite v0.2.0, feldspar pack 32) are done;
cycle 36 (owner directive 2026-07-15) is OPEN: hardware bring-up
(debug profile + taps + harness + jig, charter 40/AD-38) and
artifact presentation (charter 41/AD-39) -- the live queue is the
cycle-36 block below.

## DISPATCH QUEUE (the one live queue; structural constraints in workflow/README)

QUEUE STATE (2026-07-15, cycle 36 OPEN -- hardware bring-up +
presentation quality, owner directive w/ full autonomy + push
authority): cycle 35 closed (F134). Design corpus: design-log
2026-07-15-cycle-36 (F135, D236..D240), charters
40-debug-and-bring-up.md (AD-38) + 41-artifact-presentation.md
(AD-39). Law of the cycle: D238 (presentation standard gating +
coordinator VISUAL proof), D237 (debug augments emission, never
verdicts), D240 (fuzz campaigns are a coordinator leg; crashes
become committed regressions), D239 (zero schema bumps default;
the one candidate window bundles taps + WO112-F4 vias, coordinator
adjudicates). Implementation agents are SONNET, non-recursive.

Cycle-36 queue (dependency order; WO files exist for all):

- [ ] FUZZ CAMPAIGN (D240): 15 min/target over
      fuzz_lexer/fuzz_parser/fuzz_cbor_decode, seeded from
      examples/; record in the cycle log; crashes -> minimized
      committed regressions + debugger dispatches. RUNNING.
- [ ] **WO-123** artifact presentation v2: sheet layout engine,
      dimension entities, ruled tables, real charts, calc-sheet
      typesetting, GATING drafting audit + INV-31 -- wave 1.
- [ ] **WO-124** complete board fab set: silkscreen (refdes +
      polarity + identity) / mask / paste / drill + map, both
      legs, set-completeness check -- wave 1.
- [ ] **WO-125** debug emission profile + signal taps: --profile
      debug, tap deriver + spec-block taps, tap header record,
      board/firmware/HDL augmentation, INV-32 -- wave 1.
- [x] **WO-126** bring-up harness pack: harness/ family, tap map +
      expected signals w/ D224 provenance, bringup.md, sigrok
      capture configs + doctor row -- after WO-125.
- [x] **WO-127** logic-analyzer jig exemplar (la_jig8): custom
      test hardware as a lithos design, fleet enrollment (15->16),
      demo17 physical bring-up pack -- after WO-125/126.
      Landed at examples/flagships/la_jig8 (D242 routed it to
      flagships/, not systems/). Gate clean (0 violated, 1 real
      discharge, waivers all in D220 closed classes); debug-clean;
      demo17 live. Findings F-WO127-1..6 -- the big one is -5: the
      three registered converter models are UNREACHABLE from design
      source (translate.py has no call form), so the fleet's buck
      ripple/eta waivers have been blaming a missing MODEL when the
      real gap is a missing LOWERING form. F-WO127-3: a wrapped
      net member list silently drops its continuation lines.
- [ ] Docs/README currency sweep (coordinator): post-F134 reality,
      charters 40/41 + AD-38/39 + guide 30 cross-refs, stale
      range strings (AD-1..35 etc.) -- rolling, closes with cycle.
- [ ] COORDINATOR VISUAL ACCEPTANCE record (D238.3) at WO-123 +
      WO-124 integration -- the cycle does not close without it.
- [ ] Cycle-36 seed queue from F133/F134 stays QUEUED (not
      dispatched this directive) except WO112-F4 if the D239
      window opens: WO117-F1 pin-unmatched indeterminate
      (adjudicate FIRST if touched -- verdict-adjacent);
      WO113-F1/F2/F3/F5; WO110-F3; WO112-F5; WO111B-F1;
      WOG1-F2/F3/F5, WOG3-F1, WOG6-F1; WO118-F1/F2; WO122-F1/F3;
      WO117-F2; F131.1 temporal charter; demo11/16 manifest churn.
- [ ] Owner-gated (unchanged): memo signing (D216.3); conformance
      windows (D195/F90 queue).

QUEUE STATE (2026-07-12, cycle 34 OPEN -- emission v2 + fleet ship
campaign, owner directive w/ delegated design authority): cycle 33
closed (F120). Design corpus: design-log 2026-07-12-cycle-34
(F120/F121, D206..D211), charter 38-emission-and-release.md, AD-36.
Law of the cycle: D206 (ship-green = proven or explicitly accepted;
verdict math untouchable), D211 (ONE schema bump, 28->29, owned by
WO-104).

Cycle-34 queue (dependency order; WO files exist for all):

- [x] **WO-98** release-gate acceptance ledger DONE (merged): gate
      consumes the WaiveLedger; deviations pass LISTED; memo
      evidence (D207); acceptance_ledger.json in the package.
      Residuals -> F124 (trust-floor lowering, match-set lockfile;
      residuals-bundle dispatch).
- [x] **WO-99** emission registries + package layout DONE-partial
      (merged; D6 canonical digests + D7 style-renderer half in
      the residuals-bundle dispatch): registries, plugin kind
      `renderer`, dist/ layout, native-byte persistence.
- [x] **WO-104** geometry+schema wave MERGED (SCHEMA 29 landed;
      RectTube weldment half landed via the F122 slice -- 11
      corpus pieces real STEP; Status in-progress on ONE residual:
      GantryBeam tangent-arc closure solve, F123, Rust increment).
- [x] **WO-100** real projected views + 3D DONE (merged): OCCT HLR
      front/top/right+iso, deterministic GLB, offline viewer.html,
      per-step instruction views; bbox stand-in survives only as
      the loudly-annotated fallback.
- [x] **WO-101** derived BOM v2 + cost/schedule sheets DONE-partial
      (merged; D212 pinned-topology-volume ruling; cost threading
      + corpus goldens in the residuals-bundle dispatch);
      mass_hint-as-area REMOVED.
- [x] **WO-102** firmware + HDL backends (after 99) -- done: `FirmwareBackend`/
      `HdlBackend` (`python/regolith/backends/firmware.py`/`hdl.py`), wired
      into `ship`'s spec blocks (`"firmware"`/`"hdl"`) + `BackendInputs`;
      package what the WO-37 realizer/WO-82 tiers already proved, never
      invokes a compiler/synthesizer at ship time; the ELF/netlist are
      named absences (with reasons) when no application source/synthesis
      tier exists for a design, never fabricated. See WO-102's own
      close-out note for the scope call on the "realized ELF" wording.
- [x] **WO-103** real KiCad outline + gerber export DONE (merged):
      LayoutRequest carries the outline (placeholder square
      deleted); real-leg gerbers PROVEN on-host (305x244 Edge.Cuts
      traced exactly); boards/ family, honest unrouted label.
- [x] **WO-97** bounded sketch-segment optimize DONE-partial
      (promotion + D209 coupling merged; arm_a6 UpperArm.b pins
      ~24mm from a real binding search; residue: Rust
      Bounded->Pinned literalization + preview STEP surfacing,
      WingSpar under-declared load -- see F128).
- [x] RESIDUALS BUNDLE DONE (merged): trust-floor from source,
      match-set lockfile, tagged digests + charter amendment,
      StyleRecord through all renderers, BOM cost threading +
      corpus goldens.
- [x] **WO-105** fleet ship campaign DONE (merged): 15/15 fleet
      projects release_ok=true + clean-gate ship; tracks 51/53
      (2 intended-behavior exclusions); D213/D214/D215/D216
      machinery landed en route; census in the WO file.
- [x] **WO-106** DONE (merged): `make health` -- check + fleet +
      demos + consistency, census golden, design_hash determinism
      fix; HEALTH: PASS verified on master.
- [x] **WO-107** log readability + color DONE (merged, D217).
- [x] **WO-108** optimization proof packs DONE (merged): demos 6/6
      LIVE (`make demos`), physical artifacts + PROOF.md each.
QUEUE STATE (2026-07-13, cycle 35 OPEN -- simulation rigor + audit
trail, owner directive w/ full autonomy + push authority both
repos): cycle 34 closed (F129). Design corpus: design-log
2026-07-13-cycle-35 (F130, D220..D229; owner addenda: D227 stdlib
organization/AD-37/charter 39, D228 graphite progress, D229
VS Code parity). Law of the cycle: D220
(every modelable claim discharges through a real model over real
declared inputs; waivers shrink to the closed classes; verdict
math/D195/D206 untouchable), D224 (enrichment provenance rules --
no fabricated inputs, same-change waiver burn-down, honest
failures fix the DESIGN), D225 (zero schema bumps by default).
Baseline (F130): 1,089 obligations / 45 discharged (4%) / 929
accepted; seven projects discharge zero.

Cycle-35 queue (dependency order; WO files exist for all):

- [ ] **WO-109** claim routing by call form + probe plugin loading
      (Class B; F126.1 general half) -- wave 1, no gates.
- [ ] **WO-111** feldspar model growth (WO-24 remainder + Class C
      solver half; feldspar repo, pushes) -- wave 1, no gates.
- [ ] **WO-114** calc package + audit index (D221) -- wave 1, no
      gates.
- [ ] **WO-116** cycle-34 residue burn-down (F123 arc closure ->
      WO-104 done; WO-97 Rust literalization + preview STEP;
      PROOF-F2; PROOF-F3; HEALTH-F4) -- wave 1, no gates.
- [ ] **WO-110** built-in model depth + manufacturability channel
      (Class C lithos half) -- after WO-109.
- [ ] **WO-112** lowering-surface expansion (Class E: non-scalar
      predicates, D103 bounds, D102 containment, fluid chain, rule
      inputs) -- wave 2, independent of 109 but merged after it.
- [ ] **WO-113** corpus enrichment + waiver burn-down (Class D,
      fleet-wide, per-project slices; D216 trust-floor pass) --
      after 109/110/111/112.
- [x] **WO-115** feature proof packs, demos v2 (D222) -- DONE on
      wo115-feature-proofs: demos 7-16 live (16/16), run_all /
      make demos / health demos leg cover the union; findings
      WO115-F1 (cost/ dist wiring still open, WO-101), WO115-F2
      (FirmwareDesign lowering gap), WO115-F3 (test-runner
      expectation grammar -- FIXED in-slice).
- [ ] **WO-118** stdlib-organization alignment + enforcement
      (D227/AD-37: charter 39 + feldspar spec 12, shared boundary
      rule, health checks) -- after 110/111 merge.
- [ ] **WO-119** progress event channel, PRODUCER half (D228,
      reframed D234.3: typed events off the D217 log stream in
      regolith; graphite consumers moved to its repo's WO-G5/G7)
      -- after waves 1-3; before 117 and before graphite WO-G5.
- [x] graphite EXTRACTED (D233/D234) + SHIPPED v0.2.0: sibling
      repo github.com/lognd/graphite; WO-G1..G8 all done there
      (web + TUI over one body); guide 12 refreshed.
- [x] **WO-120** VS Code extension parity DONE (merged): progress
      tasks, calc-book claim hovers (WO-38 residual closed),
      go-to-artifact, rigor census view.
- [x] **WO-121** docs refresh + guide expansion DONE (merged):
      READMEs to cycle-35 reality, guides 26-29 + guide-12
      rewrite, docs-agreement sweeps (7 consistency sweeps).
- [x] CYCLE 35 CLOSED (F134, 2026-07-15): rigor flip 45->71
      model-backed w/ zero QA disagreements; graphite v0.2.0;
      demos 16/16; every waiver in a closed class. Cycle-36 opens
      from the F133+F134 seed queue: WO117-F1 pin-unmatched
      indeterminate (adjudicate FIRST, verdict-adjacent);
      WO113-F1/F2/F3/F5 realizer + cuprite threading; WO110-F3
      Rust cost marker; WO112-F4 vias + F5 bus grammar (next
      schema window); WO111B-F1 fea_modal routing; WOG1-F2/F3 +
      WOG3-F1 public report models; WOG1-F5/WOG6-F1 config
      list --json; WO118-F1/F2 stdlib content debt; WO122-F1/F3
      qty units; WO117-F2 calc numerics; F131.1 temporal charter;
      demo11/16 manifest churn.
- [x] **WO-117** verification + health v2 + census flip DONE on
      wo117-verification-close: D226 QA harness (tests/qa/, 20
      families, 100 samples, zero disagreements), census v2
      per-class golden + rigor regression gate, calc_books +
      demos_coverage consistency legs, make check + all health
      legs green foreground; findings WO117-F1 (pin-unmatched
      indeterminate double-count -- accounting fixed, discharge.py
      root cause to cycle 36), WO117-F2 (sheets lack resolved
      numerics; QA captures at the harness boundary).
- [ ] Owner-gated (unchanged): memo signing (D216.3); conformance
      windows (D195/F90 queue).

Cycle-33 history below (all closed).

QUEUE STATE (2026-07-10, cycle 33 OPEN, F114/D191/D192): cycle 32
closed (F111/D183..D190/F112, SCHEMA_VERSION 26, master green).
Cycle 33 opened same day (design-log 2026-07-10-cycle-33) from
F112's consolidated queue + the owner's directives (installs,
docs refresh, TTY colors, release-build sweep, external-tool
gating). Sweep finding F114: CLI builds pass NO record search
paths (fleet-wide discharged=0) -> WO-84. Host env fixed:
feldspar re-installed editable into the venv; gmsh via conda-forge
(no arm64 apt/pip path); ngspice/ccx apt commands handed to owner.

Cycle-33 support wave: INTEGRATED 2026-07-10, master green after
each serial merge gate:

- [x] SIMPLE docs refresh DONE (D191.1): README four languages +
      calcite/feldspar rows, AD-1..35/INV-1..30/WO-01..83, real
      CLI verbs, graphite section + apps/graphite README.
- [x] SIMPLE TTY ANSI colors DONE (D191.2): regolith-diag palette,
      --color auto|always|never + NO_COLOR at the CLI edge;
      goldens byte-identical with color off.
- [x] SIMPLE external-tool registry DONE (D191.3):
      python/regolith/toolenv.py, `regolith doctor` [--json],
      guide 18-external-tools.md; kicad/verilator/ghdl sites
      refactored through it.
- [x] **WO-84** record-path resolution DONE (D192):
      `regolith.magnetite.stdlib_resolve`, staged_build gained
      frame/plan record paths, build/ship/test wired;
      timber_pavilion discharge 0/7 -> 4/7 verified end to end.
- [x] SIMPLE test-runner cache full-shape replay fix + wo76
      environment-audit de-snapshotting (F114 fallout).
- [x] SIMPLE small_office graduated to examples/flagships/.
- [x] SIMPLE repo hygiene: CLAUDE.md/FINDINGS* untracked +
      gitignored (owner directive).

Cycle-33 queue (WO files draft as each dispatches; F112 source):

- [x] **WO-85** DONE (2026-07-10): load vocabulary v2 (unit-
      dimension kinds, member@station, E0211), per-member
      .members.all expansion, civil.embedment end-to-end, column
      axial demand; SCHEMA_VERSION 27 (D194). Fleet census F115
      addendum: 41 discharges fleet-wide from zero at cycle open.
- [x] **WO-92** DONE (2026-07-10): fluid comparator-after-call
      lowers structurally; D195 spec-side windows +
      conformance_impl_bound_missing teaching deferral (F116).
- [x] feldspar pack-exposure wave DONE (12 models exposed) +
      **WO-25** DONE (7 SI directions, pack at 19; diff_pair_z cut
      w/ reopen criteria). WO-24 remainder (welds, fatigue, drive
      sizing, Roark) still open -- honest not-attempted.
- [x] SIMPLE astm_a500_grb material record (WO-85 close-out gap;
      hydro columns discharge).
- [x] **WO-86** CG/moment-budget claim kind DONE (merged 2026-07-11,
      honest deferral D204): keystone finding = the mass-budget
      numeric precedent does not exist yet (close_budget wired with
      empty contributions; no evaluator resolves mech.mass(...)) and
      uav declared no CG claim. Added a CGEnvelope claim
      (mech.cg(members=[...]) via the existing generic call form, no
      new grammar) + translate-only handler that defers with
      cg_moment_no_declared_position_data naming both missing inputs.
      uav census 28->29 obligations (new cg_ok, deferred). Escalated:
      real discharge needs close_budget contribution wiring +
      declared part-position data (D204, WO-70 W2 reopen sharpened).
      No schema bump; zero fleet regression.
- [x] **WO-87** elec entity-population pass + rule-eval registry
      dereference DONE (merged; F117/D198): registry.records
      channel, 15 E0601 on hazard board, decoupling un-blocked, F118.
- [x] **WO-88** ConverterGraph execution FFI DONE (merged):
      graph on the payload, buck topology consumer, SCHEMA_VERSION 28.
- [x] **WO-89** DONE (merged): declared-vs-undeclared table
      (3 of 4 asks undeclared -> cycle-34 queue with evidence);
      by-extern HDL edges emit hdl.build; riscv 77/0 -> 79/1 (first
      behavioral discharge through live verilator).
- [x] **WO-90** multi-line opaque-require capture + bare-plural
      forall trap diagnostic DONE (merged): bracket line-join
      capture (E0450); dune_buggy unsupported_op 51->10,
      reaction_wheel 0.
- [x] **WO-91** DONE as the D203 memo: the machinery is already
      unified (five domains, one engine); cycle-34 authoring item
      = mech registry-domain adoption.
- [x] **WO-77** material-removal vocabulary DONE (2026-07-10): four
      family verbs (Ribs/PocketGrid/Shell/Lattice) through the one
      claim-scope traversal into ordinary FeatureOps, E0451 misuse
      surface, std.removal DFM packs, ribbed_panel exemplar +
      optimizer count/thickness pin proof; NO schema bump; lattice =
      honest named realizer skip (see the WO's close-out ledger)
- [x] **WO-78** SI machinery -- DONE (F119: records + claim routing + width pin + stackup select + SI sheet; flagship censuses 31/0->37/3, 74/0->77/3)
- [ ] feldspar WO-24 remainder (welds, fatigue, drive sizing,
      Roark) -- DISPATCHED 2026-07-10 (feldspar repo)
- [x] SIMPLE `regolith preview` verb DONE (2026-07-10): D197's shared
      producer set (ship/preview both call `derive_producer_inputs` +
      `model_for_spec`), honesty stamp applied through `DrawingModel`
      (`stamp_model`), `gate_summary.json` (reuses `GateCounts`),
      `--spec`-less auto-derivation. ship byte-identical (139 backend/
      flagship tests green).
- [x] SIMPLE civil.bearing_pressure model DONE (merged): honest
      residuals queued below.
- [x] **WO-96** assembly instructions DONE (merged): steps JSON +
      markdown document via preview/ship "assemblies" spec block;
      honest gaps ledgered (no mate edges in wire schema yet; no
      torque-producing model -- discharged quantity + hash shown).
- [x] SIMPLE frames into spec-less preview DONE (merged): civil
      plan sheets render spec-less (timber_pavilion 11 files).
- [x] SIMPLE docextract labeled-field truncation DONE (merged):
      Field::full_value_text() in regolith-syntax; every wrapped
      field in the doc golden now whole.
- [x] SIMPLE bearing follow-ups DONE (from its close-out): (a)
      `resolve_embedment_site_bound` now also literalizes
      `civil.bearing_pressure` bounds -- an interval site datum
      (`site.soil.bearing = [150kPa, 210kPa]`) resolves to its
      conservative endpoint by comparator sense (lo for `<=`), and a
      site-NAME-prefixed path (`ShopFloor.soil.bearing`) resolves like
      a `site.`-prefixed one; (b) std.civil `BasePlate<..., bearing:
      area>` gains an optional plate-area param threaded onto the
      existing `FrameTransfer.tributary` field (no schema bump),
      declared on small_office (2.25m2) + hydro_press (1.0m2). Fleet:
      every `civil.bearing_pressure` claim moves off `unresolved_limit`
      to a narrower named deferral (`frame_reaction_unresolved` where
      the column-to-footing reaction chain stops at the one-hop wall,
      `footing_area_undeclared` where no plate area is declared) -- the
      column-reaction chaining is the remaining wall, out of scope.
- [x] **WO-93** cubesat promotion DONE-honest-partial (fleet
      precedent): move + walls W1-W5 ledgered + optimizer pin +
      artifact bar + test net; discharge unchanged at 7 (every
      residual is genuinely model/translate-blocked, see WO note).
- [x] SIMPLE thermo claim-form recognition DONE (merged): 13
      misrouted label-named thermo claims fleet-wide now defer BY
      NAME with input lists; batt_window residual needs claims.rs
      (its within-window split drops the call text) -- queued.
- [x] SIMPLE batt_window-style within-window thermo claims DONE: the
      `within [lo, hi]` split now carries the full call expression as
      each half's LHS (claims.rs `within_window_bounds` returns the
      leading expr), so translate's `_match_call_lhs` routes it to the
      thermo model -- batt_window/temp_window (cubesat) + brew_hold
      (espresso) move from false-`lowered` (label-named, no_model at
      discharge) to honest `deferred thermo.junction_temperature_
      inputs_missing` with named inputs.
- [x] **WO-94** espresso promotion DONE: the fluid flagship
      (Darcy dp model calibrated vs feldspar byte-for-byte,
      126/3 -> 126/4, copper-tube pin, 21 stamped preview
      artifacts incl. the flownet preview fix, fleet's first
      discharged test expectation). Escalations queued below.
- [x] SIMPLE fluid givens threading DONE (merged): quantity-valued
      claim-suffix givens reach given.loads; regime selectors
      honestly excluded; espresso `vented` un-blocked.
- [ ] Cycle-34 design item: fluorite edge-parameter select
      (in registry(...) is calcite-only -- WO-94 escalation 2).
- [x] SIMPLE stdlib growth DONE: composites starter (6 rows,
      Jones/Barbero-cited), crystals 3->5, connectors 8->11;
      config-strap rows honestly cut (no citable source).

SIMPLE open queue (consolidated 2026-07-10, post-merge rewordings
absorbed some items -- this list is authoritative):

- [x] SIMPLE pack sources via [depends] DONE (merged 2026-07-11,
      D201): the D192 resolver now also contributes rule-pack
      sources to the compile set; attachment stays explicit.
- [x] SIMPLE empty-project release guard DONE (merged 2026-07-11):
      a source-less compile set is refused with a constructive
      "no source files found" diagnostic instead of a vacuous pass.
- [x] SIMPLE column-to-footing reaction chaining DONE (merged
      2026-07-11): frame_resolve now walks the column reaction
      transitively to the footing, so civil.bearing_pressure claims
      get real verdicts instead of stalling at
      frame_reaction_unresolved.
- [x] SIMPLE hdl.build source-generic DONE (merged 2026-07-11,
      D202): verilate request bytes + request-carried top module
      threaded; fixture-bound build models retired; sim/equiv keep
      fixtures.
- [ ] Cycle-34 design queue (D202 note): CSR bit-field legality,
      memory-model primitive, parts: generic deref (WO-89 table =
      the F90 reopen evidence), fluorite edge-parameter select.

Cycle-32 fleet detail:

- [x] **WO-70** uav_talon DONE-honest-partial (4/4 demos)
- [x] **WO-71** mainboard_mx DONE-honest-partial (VRM thermal discharged)
- [x] **WO-72** cnc_router_r1 DONE-honest-partial (CAM self-hosting 5/5)
- [x] **WO-73** hydro_press_h30 DONE-honest-partial (section search #2)
- [x] **WO-74** timber_pavilion DONE (search x2 + sheets + schedule + cost)
- [x] **WO-75** arm_a6 DONE-honest-partial (motion walls ledgered)
- [x] **WO-76** FEA-in-the-loop demonstration (D184; done -- honest
      partial: the rung-5 `model=` source pin is a pre-existing
      `crates/` parsing gap escalated to "main", forcing proven via
      claim-kind exclusivity instead; see WO file + guide 11)
- [x] **WO-77** declared material-removal vocabulary DONE (charter 34
      phase 1; cycle-33 queue -- close-out ledger in the WO file)
- [x] **WO-81 phase A** DONE (extension catalog complete; B un-gated by WO-82)
- [x] **WO-82** DONE (build/sim/equiv tiers, honest table)
- [x] **WO-83** DONE (two slices): `regolith test` -- test grammar
      (.test.<ext>, SCHEMA_VERSION 26) + runner (five expect forms
      vs the real pipeline, content-address cache, rule-pack
      unification, per-track corpus + printer_k1 starter net);
      Resolution slot-path gap recorded (F112 queue).
- [x] Fleet asks CONSOLIDATED into F112's cycle-33 design queue
      (design-log 2026-07-10-cycle-32, final section) -- the
      cycle-33 opener drafts from it.

F110's cycle-31 residual inventory stands -- reopen deliberately.
History: design-log cycle ledgers.

Cycle-31 waves:

- [ ] **WO-62** slice A LANDED (closure solve E0447, gauge source
      E0448 -- WO-22 flipped DONE -- coverage ledger + drift check);
      slice B dispatched (RealizedAssembly + mate solve + exemplar +
      composition proof; owns bump 23->24 + the D176
      FramePayload.transfers fold).
- [x] **WO-63** DONE (cycle 31): parity ledger + gate summary in
      `ship --explain [--json]`; literal source-position attribution
      escalated (D170-a, loud report caveat, reopen criterion).
- [x] **WO-64** flagship-1 printer phase A contract-first (B/C
      gated on WO-62+63). Wave A.
- [x] **WO-66** DONE (cycle 31): tools/stdlib generation framework
      + drift check + 471 records; shapes ratified D177-D180
      (renumbered at integration); omissions honest, grep-auditable.
- [x] **WO-67** DONE (cycle 31): std.cam pack (parse/envelope/
      collision/removal/coverage x fanuc+marlin), broken-variant
      fixtures, fuzz; follow-ups recorded: Rust `plan:` grammar
      emission (own WO), stdlib record swap-in, FDM coverage fixture.
- [x] feldspar **WO-23** DONE (merged on feldspar main): tributary
      resolution + demand extraction + H1 utilization, calibrated;
      escalations became D176 + WO-24 deliverable 0.
- [x] **WO-68** DONE (2026-07-10): forall-combo obligation emission
      (a parser-level gap, `SyntaxKind::ForallSweepClaim` -- every
      track's `forall <var> in <domain>:` BLOCK claims were silently
      unreachable, not just calcite's) + `in registry(<family-ref>)`
      domains (no grammar change needed) + FrameMember.section_domain
      (bump 24->25, D181). Five corpus designs updated to declare
      families; `make check` green.
- [ ] **WO-65** un-gated (WO-68 landed both blockers). What remains:
      the section-search EVALUATOR itself (`optimize_discrete` over
      the now-declared `section_domain` family) -- not landed by
      WO-68, which stopped at making the family declarable/reachable.
- [ ] feldspar **WO-24** PARTIAL (3 dispatches): F2/E3 capacity
      forms, benchmarks memo consolidated in-repo, VDI 2230 bolted
      joints + Euler buckling; remaining: welds, bearing life,
      fatigue, thermal transient, drive sizing, Roark completion.
- [x] **WO-64 phase B** DONE-partial (cycle 31): XY gantry realizes
      placed (RealizedAssembly + deterministic STEP), 6/25 todo!
      sites realized, optimizer pins (2 dims + the select) from the
      compiled flagship, fan Pump record wired (W2 closed); parity
      baseline attention(128); NEW walls W4 (E0448 milled misfire --
      fix dispatched), W5 (pump duty derating), W6 (contract-graph
      overlap at scale, xfail).
- [ ] **WO-64 phase C** -- ship --release parity-grade; dispatch
      after W4 + WO-65 reopen land.
- [x] **WO-69** plan: linkage lowering (WO-67's recorded follow-up) --
      done 2026-07-10, bump-free; see its own ledger.

Pre-cycle-31 history: checked boxes below + the design-log cycle
ledgers.

Cycle-30 waves (structural constraints in workflow/README's graph):

- [x] **WO-55** DONE (cycle 30): both drivers + trace/resume +
      `regolith optimize` + INV-30 (proof argument landed);
      SCHEMA_VERSION 21. Recorded escalation in the WO ledger:
      objective/domain extraction from real `policy:`/`by select`
      surfaces is caller-supplied (documented seam) until WO-56
      replaces the `--spec` placeholder (`discrete_domains_from_spec`).
- [x] **WO-58** wave-A slice LANDED (elec_blocks producer, layout
      helper, wiring, audit, guide): deliverable 2 escalated into
      **WO-61** per AD-22/D167 (BuildPayload has no readable L2
      surface); deliverable 4 (opt_trace sheet) still gated on WO-55.
- [x] **WO-60** DONE (cycle 30): ti.logic/microchip.cpld/st.mcu
      component packages (WO-56 demo refs in the WO ledger), std.civil
      +45 rows (imperial AISC families; corpus metric keys left
      honestly unresolved -- see ledger), std.fluid batch,
      mechanisms remainder.
- [x] **WO-61** DONE (cycle 30): ContractGraphPayload +
      diagram.contract_graph + diagram.opt_trace (closing WO-58 D2/D4;
      WO-58 fully done); SCHEMA_VERSION 22.
- [x] **WO-56** landed-with-accepted-residuals (cycle 30, F108):
      select end-to-end (grammar -> choice_points -> optimize ->
      cause: optimize(...) pin) proven by ebi_decode + policy-flip
      test; SCHEMA_VERSION 23 (final, D168). Accepted residuals in
      the WO ledger: the five-design section-search corpus flip
      (gates on tributary-transfer load-path analysis -- the
      recorded WO-48/WO-54 post-v1 exclusion; the WO's flagship
      criterion is corrected by F108, not silently relaxed) and the
      per-candidate monomorphization-sweep remainder. Reopen with
      that analysis, not before.
- [x] **WO-57** DONE (cycle 30): staged evaluator behind the WO-55
      seam, duct_vane exemplar (2 minimize dims), budget/interrupt/
      resume + incrementality proven; recorded decisions in the WO
      ledger (direction-objective branch; ok/release_ok feasibility).
- [x] **WO-59** DONE (cycle 30): `regolith config` doctrine
      (4-level precedence, source-attributed `where`) + apps/graphite
      (textual TUI; localhost GUI, zero-external-request viewer);
      guide 12-graphite.md; `make check` gains test-graphite.

The cycle-29 audit (FINDINGS-cycle28.md scratch, both repos, 0 HIGH
/ 7 MEDIUM / 3 LOW) is fully fixed and merged.

Wave 0 -- owner, blocking:

- [x] **Ratify the calcite elaboration** -- DONE (D149, cycle-27
      log addendum): adversarial read clean, six folds applied,
      WO-46 Status flipped, WO-47/48 un-gated.

Wave 1 -- independent, dispatchable NOW, any order:

- [x] **WO-43** DONE (cycle 28): `regolith build [--release]` +
      `ship --build DIR`; two-command demo proven by subprocess
      test; WO-25 blocker cleared.
- [x] **WO-44** DONE (cycle 28): the one `regolith.plugins` seam;
      feldspar migrated to it in the same cycle (its lazy MANIFEST +
      the stderr logging fix -- a root [root]+stdout config in a
      plugin had hijacked host stdout).
- [x] **WO-49** DONE (cycle 28): FluidPort medium binding lands as
      E0210 (renumbered from the branch's E0204 at integration --
      ratified calcite owns E0204-E0209); WO-32 flipped done;
      compatibility-record positive case CUT (no spec shape exists;
      needs a design-log entry first).
- [x] **WO-51** DONE (cycle 28, three dispatches + D150/D151/D152):
      walk labels (E0442), lower.programs pass, cavity->flow_paths
      (E0443-E0445), coolant_gallery exemplar, SCHEMA_VERSION 17;
      fixtures 57-59. WO-22 honestly NOT flipped (sheet_bracket STEP
      needs the close-edge closure-solve + a sheet-gauge source --
      recorded on WO-22's Status line).
- [x] **WO-27** DONE (cycle 28): real-feldspar conformance run green
      (signed Valid(certified) discharge, uninstall reverts to
      indeterminate, byte-identical evidence hash). Cut, recorded in
      the WO file: CI separate-job leg; discretized ccx/gmsh path
      (planner resolves via cheaper closed-form at tested budget).
- [x] **WO-28 engine remainder** DONE (cycle 28): rule engine
      (E0601/E0603/E0604, resolves: with INV-21 causes), `rules
      test|try` CLI, reference packs, guide WORKING, INV-29 + proof;
      fixtures landed as 55/56 (renumbered at integration); honest
      residuals in the WO ledger (aggregates, elec static tier,
      realized-fact discharge rides WO-22/24).
- [x] **WO-34 D2-D6** DONE (cycle 28): harness elaboration +
      HarnessPayload (SCHEMA_VERSION 16), wiring_harness golden,
      fixtures 52-54 (renumbered); E0306 cross-net stays EXPECT-TODO
      (no cuprite net-membership seam into regolith-lower).
- [x] **WO-26 remainder** DONE (cycle 28): D102 typed temporal
      forms (E0435/E0436), D103 link budget e2e (E0437), D105a sweep
      domains + buck/transient packs, D105b numeric base, D105c
      planner shape, D105d schema half (growth-diff pass out per
      ledger). StaysWithin window field = recorded residual awaiting
      a schema slot.
- [x] SIMPLE DONE (cycle 28): `docs/guide/03-fluorite-guide.md`
      (five D122 examples, current spellings).
- [x] SIMPLE DONE (cycle 28): MCU registry verified against real
      datasheets; DS12232 rev citation FIXED (rev6 does not exist ->
      rev5). Tier deliberately NOT upgraded: INV-14 makes tiers
      above community earned by signature over content hash, not by
      text cross-check -- verification notes recorded in-file.
- [x] SIMPLE (Rust, real bug -- F103, cycle 27): the layout pass
      breaks on CRLF sources (a `\r\n` blank line before a top-level
      declaration kills the next declaration's parse). Windows is
      first-class (AD-12): accept `\r\n` uniformly in the lexer OR
      reject with a constructive encoding diagnostic; fixtures both
      ways; found via feldspar's autocrlf working tree.
      DONE: `\r\n` accepted uniformly (the lexer's `Newline` token is
      now `\r\n|\n`, so a CRLF source yields an IDENTICAL layout token
      stream to its LF twin); a lone `\r` (classic-Mac) is pinned to a
      constructive E0195 encoding diagnostic. Fixtures both ways in
      `crates/regolith-syntax/src/layout.rs` tests.
- [x] SIMPLE DONE (cycle 28): manifold + dune_buggy enrolled in
      golden + deferral corpus dicts (flagship sets only per the
      AD-11 tradeoff; goldens regenerated, not hand-edited).
- [x] SIMPLE DONE (cycle 28, owner-confirmed): symlink removed;
      12 stale worktrees + branches pruned (9 verified subsumed by
      merge-base; stress-cnc-router/stress-espresso/wo32-d3456 were
      superseded WIP drafts of work later completed on master --
      unique-commit content inspected before deletion). Verification
      folded into the cycle's rolling `make check` gates from the
      real path.

Wave 2 -- after their named gates:

- [x] **WO-45** DONE (cycle 28): stdlib/ std.* catalog + TOML
      record loader + de-phantoming test; benchmark-memo datasets
      cited in-record; D153 rules std.compute/std.fluorite
      compiler-owned builtins.
- [x] **WO-52** DONE (cycle 28): Mixer edge kind + declared-outlet
      E0210 exemption (no laundering; fixture 51), gn2_purge golden,
      FOPEN-1 CLOSED in fluorite/04.
- [x] **WO-25 remainder** DONE (cycle 28, Status: done): backend
      framework + CLI + real-kicad-cli export; residuals in the WO
      ledger.
- [x] **WO-24 end-to-end half** DONE (cycle 28, Status: done): the
      lowering->BlockRequirement bridge + real-KiCad RealizedLayout
      producer landed; the `-m kicad` tier runs real.
- [x] **WO-50** ALL CONTENT LEGS LANDED (schema/mech/fluid/elec-BOM/
      quality audit cycle 28; civil plan/section + member schedule
      cycle 29 after WO-48 slice B). Accepted residuals in the WO
      ledger: DXF/PDF sibling renderers, `ship --explain` flag.
- [x] **WO-47** DONE (cycle 28): `.calx` end-to-end at L0-L1, all 5
      corpus designs zero-diagnostic, goldens enrolled; E0204/E0208
      + terminal-half-of-E0209 wired via Circulation/LoadPath
      disciplines. Escalated to WO-48: E0205/E0206/E0207 + the
      tributary half of E0209 (need net_core reachability traversal
      / quantity eval); `assembly` CST left generic (homonym).
- [x] **WO-40** landed cycle 28 (code lints + `check --watch`);
      accepted residuals in the WO ledger: scope-graph lints,
      expert-ladder tier, disclosed corpus lint hits (L0801/L0803).
- [x] **WO-38** landed cycle 28 (LSP navigation/completion/tiered
      diagnostics); accepted residuals in the WO ledger:
      artifact-hover (needs persisted registry_version -- an
      architecture decision), registry-id completion.
- [x] **WO-39** landed cycle 28 (grammar generation + VS Code
      extension); accepted residuals in the WO ledger: bundled
      binaries (first release run), electron e2e.

Wave 3 -- the tail:

- [x] **WO-48** DONE (cycle 29, three slices B/C/A + the
      frame-chain follow-up below; cuts in the WO ledger). Un-gated
      and since landed: WO-50 civil
      leg, WO-54 civil estimator, feldspar's frame-consumer WO.
- [x] **WO-48 frame-chain-completion follow-up** DONE (branch
      `frame-chain`, worktree `.claude/worktrees/frame-chain`):
      `regolith.orchestrator.frame_resolve` resolves a `FramePayload`
      member's name-only `section`/`material` `RecordRef`s against
      `std.civil`'s `sections.toml`/`materials.toml` (SI-unit
      reduction, INV-22-style pinning); wired into `translate.py`
      (`_translate_frame`/`_translate_civil_utilization`/
      `_translate_mech_deflection`) for the `civil.utilization`/
      `mech.deflection` frame-referencing claim forms (calcite/03
      sec. 5), threaded through `discharge.py`/`loop.py`/
      `orchestrate.py` exactly like `CostContext` (`frame_context`,
      `Ok(None)` for a frames-less build). ARCHITECTURAL FINDING (why
      no five-design-corpus claim moves to a real numeric verdict,
      recorded rather than assumed away): EVERY one of the five
      ratified corpus designs' `civil.utilization` group subject /
      `mech.deflection` member target names a member whose `section:
      free` is an unresolved L3 section-search variable (footbridge
      G1/G2, bus_shelter G1, pole_barn T1, small_office
      G2_AB/GR_AB) -- genuinely indeterminate, NOT a missing
      `std.civil` record (D58 does not apply; no section-search
      solver exists, out of SCHEMA_VERSION-preserving scope).
      Separately, a resolved member's own bending demand cannot be
      extracted from the v1 `FramePayload.loads` field for any girder
      whose load arrives through a `Bearing(tributary=...)` transfer
      rather than a direct `on [...]` literal target -- the SAME
      exclusion WO-54's `civil_takeoff_estimate` close-out already
      names for this payload surface (`frame_load_untargeted`, new
      deferral reason). retaining_wall's `sliding` claim names
      `heel_sg`, not a frame member (`frame_member_not_found`) -- a
      geotech-stability quantity outside beam-model scope. Every
      deferral above replaced the PRE-existing blanket
      `unsupported_op` (a frame predicate's comparator sits after a
      call expression, which `_split_comparator` could not parse)
      with a specific, actionable reason -- verified via the new
      `deferral_{footbridge,bus_shelter,pole_barn,retaining_wall,
      small_office}.json` goldens (zero churn to any other corpus's
      golden). End-to-end discharge over a SYNTHETIC fully-resolved
      frame (fixed section+material+direct load) proves the seam
      works when every field IS resolvable
      (`tests/orchestrator/test_frame_resolve.py`, 12 cases). NOT
      attempted (recorded cuts): `dof: kept=` -> `releases`/`fixity`
      transfer-record resolution (a separate registry-IO consumer
      than section/material -- deferred again this slice); an L3
      section-search solver; tributary-transfer load-path analysis
      feeding girder demand. feldspar's `mech.struct` direct-stiffness
      consumption of the `frame` payload remains the feldspar-side
      residual (WO-21 close-out) -- NOT implemented here (feldspar
      checkout is read-only reference for this dispatch).
- [x] **WO-53** DONE (cycle 28 seeds; cycle-29 content addendum:
      std.elec.patterns Batch A + std.mech.mechanisms Batch B, 11
      packs, fixtures + catalog rows; Batch C/fluid/civil = recorded
      growth).
- [x] **WO-54** DONE (cycle 29, two dispatches: schema slice took
      SCHEMA_VERSION 19->20, the LAST bump, folding the WO-26
      StaysWithin `window` rider; remainder landed grammar E0438,
      profiles, orchestrator resolution w/ expiry deferrals, 3
      estimators, small_office end-to-end, fixture 63). Recorded cut:
      mech plan estimator (no landed consumer surface).
- [x] SIMPLE DONE (cycle 28): `docs/guide/04-calcite-guide.md`
      (worked corpus tour, cross-track MEP section; guide README
      numbering settled 01-04 = track order).
- [x] Cross-run nogood cache DONE (cycle 28, EOPEN-13/D75:
      `orchestrator/nogood_cache.py`, keyed on consumed catalog
      record revisions).
- [ ] Core-residual xfails (recorded, honest; RE-ASSESSED cycle 29:
      no cycle-28/29 landing enables un-xfailing any -- the blocking
      surfaces below are each still absent): WO-12's
      cross-boundary INV-13 fixture (needs entity-DB bound_kinds
      end-to-end), WO-11's cross-boundary INV-15 fixture (needs
      populated walks through the FFI), INV-19's escalation-edge
      clause (needs escalation-edge lowering, WO-12 family), INV-12
      match-set growth over the lockfile diff (WO-26 D105 family),
      INV-04 givens-invariance half (discharging model side).
      Each lives beside its WO; none blocks anything else.
- [x] Firmware realizer follow-up DONE (cycle 28): `on_events`
      crosses the FFI; `events_from_on_blocks` builds EventDecl from
      the real typed OnBlock CST (pin/interrupt facts stay
      caller-supplied -- WO-35 territory, not CST data).
- [x] WO-33 optional slices formally CUT (2026-07-09 record in the
      WO file; reopen criteria stand).

## WO-124 execution checklist (complete, professional board fab set)

Leaves mapped against WO-124's deliverables/acceptance (charter 41
sec. 3, F135.4):

- [x] L1: `elec_fabset.py` (new) -- shared required-layer constants
      (charter 41 sec. 3 list), a deterministic hand-rolled Gerber
      X2 writer (header/footer, one round aperture, line draws,
      flash pixels), a compact 3x5 stick/pixel font (A-Z 0-9 space
      `: . - _ /`) for silkscreen board-identity + refdes text, an
      Excellon writer (empty-but-valid, PTH/NPTH split), a drill-map
      writer, and the fab-set completeness checker (job file vs
      emitted vs charter list -- named error, not warning). [D3, D4]
- [x] L2: real-KiCad leg (`backends/elec.py`) -- extend the gerbers
      export with the full `--layers` list (copper/mask/paste/silk/
      fab/courtyard/edge/margin F+B), extend drill export with
      `--generate-map --map-format gerberx2 --excellon-separate-th`;
      job file (`.gbrjob`) ships as-is (kicad-cli auto-emits it once
      layers are passed). [D1]
- [x] L3: fake-KiCad tier board authoring (`fake_kicad.py`) -- full
      standard KiCad layer table (today only F.Cu/B.Cu/Edge.Cuts,
      which silently drops mask/paste/silk/fab from real-leg
      re-export per on-host verification) + `gr_text` board-identity
      block (name, design short-hash from netlist_hash; REV labeled
      `n/a` -- no revision concept exists in the realized surface,
      escalated as a finding, never fabricated) + refdes text hook
      for any supplied placements (empty today, seam only). [D2]
- [x] L4: real-pcbnew leg (`kicad_wrapper.py`/`kicad.py`) -- same
      identity text via `pcbnew.PCB_TEXT`, threaded through two new
      OPTIONAL `LayoutRequest` fields (`board_name`, `design_hash`;
      Python-only wire protocol, not the AD-5 schema -- no
      SCHEMA_VERSION bump, no D239 trigger). [D2]
- [x] L5: `ElecBackend.produce` -- when `not self._available()`,
      drive the new fake-tier exporter instead of an honest cut
      (manifest-identical to the real leg: same relative paths under
      `gerbers/`, `drill/`, `pos/`); run the completeness checker on
      BOTH legs' output before returning `Ok`. [D1, D3, D4]
- [x] L6: escalation -- ledger a design-log finding (placeholder
      F-number) for the named absences: no pad-stack/courtyard/
      polarity data in `Placement` (mask/paste apertures and
      polarity marks are therefore honestly empty/absent, never
      fabricated), no design-revision concept (silkscreen REV field
      is `n/a`). No schema bump taken -- D239 STOP not triggered
      (Placement's existing fields cover refdes/position/side; the
      missing facts are footprint-registry-shaped, not a
      RealizedLayout slot).
- [x] L7: tests -- fake-tier export test (manifest match, silkscreen
      contains identity text, completeness checker green); negative
      test (today's 4-layer set fails the completeness checker);
      real-leg test extended for the new layers (skip-if-unavailable
      keeps the existing discipline).
- [x] L8: docs -- `guide/15-board-correctness.md` full-set table;
      regenerate `demo11_board_gerbers`.
- [x] L9: close-out -- `make check` green; WO-124 `Status:` flipped;
      close-out ledger in the WO file.

## DISPATCH RULES (unchanged, load-bearing)

- Every dispatch follows `docs/workflow/README.md`'s protocol
  VERBATIM-BY-REFERENCE in the prompt; agents never spawn their own
  subagents; single-slice work goes to a plain agent type, not an
  orchestrator type.
- Dispatched agents work ONLY in their isolated worktree -- never
  cd to or operate on the shared repo path, including for
  self-correction. Coordinator re-verifies every "landed"/"green"
  claim from its own checkout (`git branch -v` first -- collect
  tools can silently move HEAD).
- Verify a worktree agent's branch point (`git merge-base BRANCH
  master`) before trusting its diff; rebase stale bases, keep both
  sides on conflict, regenerate (never hand-merge) generated files
  (`make schema`, goldens).
- After any merge touching Rust or SCHEMA_VERSION: `make install`
  before `make check` (stale `_core` otherwise).
- New `examples/negative/` fixtures: check filename-number
  collisions against master's CURRENT state (numbering does not
  git-conflict).
- Findings from corpus/stress agents promote per D124's rules
  (cycle-23 log).
- GOLDEN REGENERATION REVIEW (cycle-33 lesson, the E0303 incident):
  regenerating goldens is never hand-editing, but the DIFF still
  gets reviewed -- specifically any diagnostic_multiset row ADDED
  at error level is a regression until proven intended. "Verdicts
  unchanged" does not cover diagnostics.

## WATCH (unchanged conditions, do not re-litigate)

- F79 (computer at intent altitude) -- only if a real team splits
  ownership there.
- Reopen-criteria ledgers, thinned by cycle 27: fluorite/04 is
  fully decided (FOPEN-1 answered/D142, FOPEN-2 closed/D141);
  hematite/07 sec. 2a's cavity item is SCHEDULED (WO-51, D143);
  cuprite/08 sec. 1a re-reviewed, dispositions stand; calcite/04
  carries the civil deferrals (drawings non-goal revised by D140;
  construction cost closed by D147). Each remaining entry names the
  exact evidence required; nothing less counts. The technical open
  queue is EMPTY by design (F90).
- AD-26's non-goal (tracks as plugins) -- reopen only on a real
  third-party track attempt preserving AD-24.

## Deferred / explicitly cut (project-level)

- `avoid` (soft negative preference): only if an example produces
  an unexpressible preference.
- Multi-FPGA floorplanning / partial reconfiguration (EOPEN-17 v1
  cut).
- Registry HOSTING service (server side): out of client scope
  (regolith/11 sec. 10 stands; publish-side semver re-check is
  server work).
- Post-1.0: Rust migration of remaining hot paths; statistical
  allocation pack (D63); wasm hosts as new `regolith-api`
  consumers. (A UI, formerly this list: SUPERSEDED by the owner's
  2026-07-09 directive -- D163/AD-31, `graphite`, WO-59.) (Kinematics packs, formerly this list: SCHEDULED by
  D144 -- the mechanism-library halves ride WO-53 + feldspar's
  dynamics phase.)
- History: every completed cycle's ledger is in `docs/workflow/design-log/`;
  completed WO details are in each WO file's close-out. This file
  carries NO history by design (D137).
