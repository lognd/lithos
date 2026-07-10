# Getting started

From zero to a checked design in about ten minutes. Everything on
this page is WORKING today.

## 1. Install

Prerequisites: Rust (pinned toolchain auto-selected via
`rust-toolchain.toml`), Python >= 3.12, `uv`.

```
git clone https://github.com/lognd/lithos
cd lithos
make install        # uv sync + maturin develop; one command, no manual steps
                    # (also links system KiCad's pcbnew into the venv when
                    # KiCad is installed -- optional, enables the real
                    # layout/DRC tier; without KiCad everything else works)
make check          # the full gate: fmt, lints, types, both test suites
```

`make install` gives you the `regolith` CLI inside the project venv
(`uv run regolith ...`, or activate the venv and call it bare).

## 2. The mental model (60 seconds)

You write WHAT must be true; the toolchain proves it or tells you
loudly that it cannot.

- **hematite** (`.hema`) describes mechanical artifacts: parts as
  process pipelines (cut, bend, machine), assemblies as contracts
  between parts.
- **cuprite** (`.cupr`) describes electrical/computer artifacts:
  blocks with behavioral specs, boards, systems of intents.
- Both share one **regolith**: the same quantity/unit core, the same
  five answers to "who decides this number?", the same claim system,
  the same build machinery.
- Claims (`require ...`) lower to **obligations**; models discharge
  obligations into **evidence** (discharged / violated /
  indeterminate). "I could not check this" is never a pass.

## 3. First part

Save as `bracket.hema`:

```
import std.mech.sheet (Blank, Pierce, Bend)

profile Flat:
    walk:
        from left_edge
        line right
        line up
        line left
        close
    constraints:
        a.length = 80mm
        b.length = 50mm

part Bracket:
    material: AISI_304

    stage cut: process=laser_cut(sheet=1.5mm)
        then:
            blank = Blank(Flat)

    stage formed: process=press_brake, from=cut
        flange = Bend(edge=cut.blank.top_edge, angle=90deg, radius=free)

    require Structural:
        sag: mech.deflection(formed.flange.tip,
                 under=interface_envelope(SensorPad)) < 0.2mm
```

Three things to notice:

1. The part is its **manufacturing pipeline** -- stages name real
   processes, and order matters.
2. `radius=free` -- you did not pick the bend radius. The process
   pack's DFM minimum decides, and the resolved value lands in the
   lockfile WITH its reason (`cause: dfm(min_bend_radius)`).
3. The `require` block is a **claim**, not a comment. It will be
   proven, refused, or honestly deferred -- never silently ignored.

## 4. Check it

```
uv run regolith check bracket.hema
```

`check` runs the full static pipeline: parse, entity/ownership
analysis, all L1/L2 checks, claim-to-obligation lowering. Failures
render as source-anchored diagnostics:

```
error[E0102]: `==` is not defined on continuous quantities
  --> bracket.hema:24:18
   |
24 |     gap: clearance == 0.2mm
   |                    ^^ use `within [lo, hi]`, a tolerance, or a comparator
```

Every diagnostic has a stable code. The exit code is nonzero iff
there are errors; `--json` gives the structured form for tooling.

Other commands available today:

```
uv run regolith fmt bracket.hema          # canonical formatting
uv run regolith debug tokens bracket.hema # inspect the pipeline:
uv run regolith debug cst bracket.hema    #   tokens|cst|ast|ir
uv run regolith doc .                     # render the public surface to markdown
uv run regolith version
```

## 4a. Build and ship (the two-command demo)

Once `check` is clean, `regolith build` runs the full staged pipeline
(realize -> re-lower to a fixed point, WO-42) and `--release` applies
the WO-21 release gate (INV-24: a green release means proven or
explicitly accepted, nothing between):

```
uv run regolith build bracket.hema --release --out .regolith/build
```

This writes `regolith.lock` + `build_report.json` under `--out` and
prints the ONE renderer's diagnostics (if any) plus a one-line summary
to stdout; exit code is 0 iff the build is clean AND (when `--release`
is given) the gate passed. `regolith ship` consumes that build's
outputs directly with `--build`, without re-running the pipeline:

```
uv run regolith ship bracket.hema --build .regolith/build --out ship/
```

That is the whole two-command corpus demo: `build --release` then
`ship --build DIR`, no Python-API knowledge required.

A project whose `[depends]` names a `std.*` package (`std.civil`,
`std.cost`, ...) has its record search path resolved automatically:
`regolith.magnetite.stdlib_resolve.resolve_record_search_paths` checks
an explicit `records.stdlib_root` config key, then a vendored copy
under the project, then walks up looking for a `stdlib/` tree -- so
`build`/`ship`/`test` discharge `std.*`-backed claims (section
records, cost rate tables) the same way from any CWD, not just from
the repo root. A `std.*` dependency that resolves to no known stdlib
root is not an error at this layer: the discharge path's own honest
deferrals (`frame_section_family_not_landed`, `cost_record_unresolved`)
still name the missing record.

## 4b. Starting a project from a template

Rather than hand-writing the first file, scaffold a project that
already passes `regolith check`:

```
uv run regolith magnetite new my_design --template mech   # or elec|fluid|system
```

That emits `magnetite.toml`, one source file per track (each with an
honest example claim), a house `.gitignore`, and a CI snippet. Then
`regolith check my_design` is green out of the box, and
`regolith doc my_design` renders its public surface -- interfaces,
parts/blocks/flownets, and claims (each claim shows its build status
and margin once you have built the project, or `(unbuilt)` before
then). Doc text is the leading `#` comment block above a declaration
(no new syntax) -- the same comments you already write.

## 5. Where numbers come from (the one grammar to internalize)

Every numeric slot in both languages takes exactly one of five value
sources (normative: `docs/spec/regolith/03-value-sources.md`):

| you write | meaning | who resolves it |
|---|---|---|
| `wall = 4mm` | you know it | nobody; asserted |
| `radius = in [2mm, 8mm] minimize` | bounded freedom | the optimizer |
| `radius = free` | cheapest legal value | DFM/DRC rules |
| `loads: radial: derived(sf=1.5)` | consequence of the system | the contract solver |
| `runout = allocated` | share of a budget | the budget allocator |

Every non-literal resolution is pinned in the lockfile with a cause.
When a number changes in review, the diff names WHY.

## 6. First board (a taste)

cuprite has the same shape -- contracts and claims, not netlists
first (full tour: `02-cuprite-guide.md`):

```
block Buck<v_out: voltage = 5.0V, i_max: current = 2A>:
    ports:
        vin: supply(in, [7V, 24V])
        out: supply(out, v_out +- 2%, i <= i_max)
        gnd: reference
    spec:
        forall i(out) in [0A, i_max], v(vin) in [7V, 24V]:
            v(out) = v_out +- 2%
    require Regulation:
        ripple: rms(v(out), band=[100kHz, 10MHz]) < 20mV
```

`regolith check` verifies this the same way -- same diagnostics, same
obligation machinery, one toolchain.

## 7. What happens after check (status: partly DESIGNED)

- WORKING: obligation discharge through the harness's closed-form
  models (beam bending, bolted joints, buck ripple, link budgets...)
  via the orchestrator; evidence caching; the release-gate logic.
- DESIGNED (work orders WO-20..28, `docs/workflow/work-orders/`): geometry
  realization to STEP, PCB layout via KiCad, `regolith ship`
  producing the manufacturing package (gerbers, BOM, STEP), external
  solver packs (FEA via the feldspar package), authorable DFM rule
  packs.

## 7a. Verifying a lowering visually (status: LANDED)

Beyond `regolith debug ir`'s text dump, some lowered structure reads
better as a picture -- interaction-surface/29 sec. 1.6, D165. These
diagrams are ordinary `DrawingModel` sheets (AD-27) through the SAME
SVG renderer every drawing uses; nothing here is a second rendering
path.

- WORKING: `diagram.elec_blocks` (WO-58 deliverable 1) -- a bdf-shaped
  block diagram from a declared `harness:` block's runs: one rectangle
  per component referenced by a run endpoint, one port-name annotation
  per distinct pin, one orthogonally-routed polyline per run. Wire it
  into a `regolith ship --spec` drawings block with
  `{"subject": "<harness name>", "track": "elec_blocks"}` (mirrors the
  mech/fluid/civil tracks exactly; reads `BackendInputs.harnesses`).
  NAMED SIMPLIFICATION: cuprite net membership (which schematic net a
  `component.port` belongs to) is not exposed to any existing seam
  today (WO-34's own escalation, `docs/workflow/work-orders/
  WO-34-routed-runs.md` sec. on `E0306`) -- this producer draws harness
  RUN connectivity, not resolved net membership, until that seam lands.
  Try it: `examples/tracks/cuprite/wiring_harness.cupr`'s `MainLoom`
  harness.
- WORKING: `diagram.contract_graph` (WO-61 D165/D167, the WO-58
  escalation above CLOSED): a node/edge L2 sheet from the new
  `BuildPayload.contract_graph` (`ContractGraphPayload`,
  SCHEMA_VERSION 22) -- one symbol per declared interface (named,
  promise-slot count annotated) or artifact/part, one orthogonally-
  routed polyline per mating with its declared-effects-derived kind
  label. Wire it with `{"subject": "<label>", "track":
  "contract_graph"}` (reads the single `BackendInputs.contract_graph`,
  not a per-subject map -- one graph per build).
- WORKING: `diagram.opt_trace` (WO-58 deliverable 4, landed once
  WO-55's `OptimizationTrace` merged): a candidate `tables` schedule
  plus a convergence polyline (objective vs evaluation index) and a
  winner annotation, every number citing the trace's own digest. Wire
  it with `{"subject": "<label>", "track": "opt_trace"}` (reads
  `BackendInputs.opt_traces`, keyed by subject -- caller-supplied only,
  since an `OptimizationTrace` is never part of `BuildPayload`).

## 8. Learn the languages properly

- `01-hematite-guide.md` -- parts, profiles, interfaces, assemblies,
  claims, with the complete vocabulary.
- `02-cuprite-guide.md` -- blocks, specs, impls, systems, computers.
- `10-writing-dfm-rules.md` -- encode manufacturing knowledge as
  checkable rules.
- `examples/` -- the corpus. Start with `mech/sheet_bracket.hema` and
  `elec/buck_converter.cupr`; graduate to `cubesat/`.
