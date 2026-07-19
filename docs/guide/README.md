# The lithos guide

Learning-path documentation for the four design languages and their
toolchain. Read in order:

| doc | what you learn |
|---|---|
| [00-getting-started.md](00-getting-started.md) | install, write a first part, run `regolith check`, read a diagnostic |
| [01-hematite-guide.md](01-hematite-guide.md) | the mechanical language, by example, with the full vocabulary |
| [02-cuprite-guide.md](02-cuprite-guide.md) | the electrical/computer language, same treatment |
| [03-fluorite-guide.md](03-fluorite-guide.md) | the fluid-circuit language, same treatment |
| [04-calcite-guide.md](04-calcite-guide.md) | the civil/architectural language, same treatment |
| [10-writing-dfm-rules.md](10-writing-dfm-rules.md) | authoring DFM/DRC/ERC rule packs (for manufacturing experts too) |
| [11-optimization.md](11-optimization.md) | `regolith optimize`: the discrete/continuous search engine, trace, resume, pinning |
| [12-graphite.md](12-graphite.md) | `regolith config` doctrine + graphite (now a sibling repo, D233/D234): install pointer, what ships today, honest in-flight pointers |
| [13-parity-report.md](13-parity-report.md) | `regolith ship --explain`: the D170 parity ledger (provenance classes, decision/demand tables, the honest attention-list caveat) |
| [14-cam-verification.md](14-cam-verification.md) | verifying a supplied G-code plan (`std.cam`): parse, envelope, collision, removal, coverage |
| [15-board-correctness.md](15-board-correctness.md) | the encoded board-review checklist (`std.board_correctness` `erc:` packs, WO-79) |
| [16-hdl-verification.md](16-hdl-verification.md) | verifying digital logic (`std.hdl`): verilator build/sim_assert/equiv_directed over the cuprite/09 fixture corpus |
| [17-design-testing.md](17-design-testing.md) | `regolith test`: `test` declarations, `.test.<ext>` discovery, the runner and its cache |
| [18-external-tools.md](18-external-tools.md) | the optional external tools (verilator, ghdl, ngspice, kicad-cli, ccx, gmsh, feldspar): what each unlocks, install + troubleshooting, `regolith doctor` |
| [19-signal-integrity.md](19-signal-integrity.md) | calculated impedance windows over fab stackup records, sized termination claims, the stackup `by select`, and the SI table sheet (WO-78, charter 35) |
| [20-emission-and-packaging.md](20-emission-and-packaging.md) | the `dist/<project>/` release package layout, `[artifacts] formats` selection, and extending emission with a producer/renderer plugin (WO-99, charter 38) |
| [21-reading-build-output.md](21-reading-build-output.md) | the two-stream split (stdout is data, stderr is the log stream), the readable/colorized default log view, and `-v`/`-q`/`--color`/`NO_COLOR` (WO-107, D217) |
| [22-proving-optimizations.md](22-proving-optimizations.md) | the `demos/` proof packs: `make demos`, physical artifacts (drawings/STEP/GLB/BOM) per optimizer surface AND per user-facing feature family (WO-108/WO-115, D218/D222), the content-hashed manifest + PROOF.md, and the completeness/determinism gate |
| [23-health-gate.md](23-health-gate.md) | `make health` (D219): the check/consistency/demos/fleet legs, the standardized `LegSummary` row shape, and what each leg actually gates versus reports |
| [24-calc-package.md](24-calc-package.md) | the `calc/` calc book + audit index: per-discharged-obligation calc sheets (inputs with provenance pins, model/citation, margin, evidence hash chain) and the total obligation accounting that maps every obligation to one disposition (WO-114, D221) |
| [25-manufacturability-and-models.md](25-manufacturability-and-models.md) | the `manufacturable(<process>)` realized-geometry channel ([[machine]]/[[tool]] grounded envelope checks, the named deferral vocabulary, what a VIOLATED verdict means), the NPSH/torsion closed forms, the critical-speed pack adapter, and the bare unit-cost adapter (WO-110, D232) |
| [26-reading-the-rigor-census.md](26-reading-the-rigor-census.md) | the D220 rigor doctrine: discharged vs accepted-deviation vs deferred, what the fleet census golden reports today, and what the health fleet leg actually gates on it |
| [27-authoring-for-discharge.md](27-authoring-for-discharge.md) | D224 corpus authoring: provenance rules (record / derivation / citation), the same-change waiver burn-down, and fixing the DESIGN on a real VIOLATED verdict -- worked from the real arm_a6 bearing and uav_talon spar stories |
| [28-growing-the-stdlib.md](28-growing-the-stdlib.md) | charter 39: the `std.` namespace taxonomy, the lithos-vs-feldspar boundary rule, citation/tier bar, generated batches, and where a new record/model/pack goes |
| [29-the-progress-channel.md](29-the-progress-channel.md) | the D228 progress-event wire shape (`python/regolith/progress.py`): in-process subscription vs subprocess stderr parsing, and the graphite/editor consumers |
| [30-hardware-bring-up.md](30-hardware-bring-up.md) | `--emit-profile debug` (WO-125) + the `harness/` bring-up pack (WO-126, charter 40): the tap model, `tap_map.json`/INV-32, `expected_signals.json`'s D224 provenance rule, `bringup.md`, and the sigrok-cli capture configs |
| [31-diagnostics-and-explain.md](31-diagnostics-and-explain.md) | the ONE code space (D247/WO-131): the families incl. E09xx/E10xx/E11xx, the code-stability rule, `regolith explain <code> [--json]`, the machine-checked completeness legs, and how a producer adds a new coded failure |
| [32-the-artifact-surface.md](32-the-artifact-surface.md) | WO-130 (D244/AD-41): the universal `artifact_index.json`, the closed viewer vocabulary + its one-home registry, the health consistency check, `regolith artifacts`, and the three edit models (boards/drawing sheets/assemblies) |

Numbering convention: 00 is getting started, 01-09 are per-track
guides in track order (hematite, cuprite, fluorite, calcite), 10+
are authoring/tooling guides.

Two ground rules for reading:

1. **These guides teach; the spec decides.** Every list here is a
   learning view of a normative document, and each section names its
   source (`docs/spec/hematite/`, `docs/spec/cuprite/`, `docs/spec/regolith/`). If a
   guide and the spec ever disagree, the spec wins and the guide has
   a bug -- please fix the guide.
2. **Status honesty.** The toolchain is under construction. What each
   guide shows is marked:
   - WORKING -- runs today (`regolith check`, `fmt`, `debug`,
     `build`, `ship`, `optimize`, `test`, the rule-pack engine, the
     geometry realizer, the closed-form harness).
   - DESIGNED -- specced and work-ordered, not yet runnable; each
     guide names the WO that will flip its section.

The corpus in `examples/` is the best companion to these guides:
dozens of single-file designs per track under `examples/tracks/`,
multi-file systems under `examples/systems/`, and the charter-31
flagship programs under `examples/flagships/` (led by the ten-file
Kestrel cubesat, `examples/flagships/cubesat/`) -- all in real
syntax, all compiled by CI, all built and shipped by the health
fleet leg.
