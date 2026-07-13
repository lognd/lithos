# Proving your optimizations

Status: WORKING (WO-108, D218.1).

`11-optimization.md` teaches the search engine -- how `optimize`,
`by select(...)`, `in [lo, hi] minimize`, and the free-section family
produce a pinned winner with a `cause: optimize(...)` lockfile row. This
chapter is about the next question a reviewer always asks:

> Show me. Where can I *see* that this number is the one the optimizer
> chose, and that it is genuinely searched rather than hand-picked?

The answer is the **proof packs** under `demos/`. Each is a runnable
script that drives the REAL pipeline end to end and emits PHYSICAL
artifacts -- drawings (SVG + PDF), STEP solids, GLB + an offline viewer,
BOMs, and the pinned `regolith.lock` -- into a per-demo output tree with
a content-hashed manifest and a narrating `PROOF.md`.

## Running them

```
make demos          # run every LIVE proof pack (green when all live pass)
make demos-strict   # additionally FAIL if any surface is not yet live
```

`make demos` prints one status row per demo and writes each pack under
`demos/out/<demo>/`. The raw artifact bytes are gitignored (they are
regenerated on demand); what is committed as evidence-of-shape is each
demo's `manifest.json` and `PROOF.md`.

## What one pack contains

```
demos/out/demo1_select_ebi_decode/
    regolith.lock          # the pinned winner: cause: optimize(cost, trace=...)
    regolith.flip.lock     # the policy-flip: reversed cost -> different winner
    opt_trace.svg / .pdf   # the search trace: every candidate, the winner
    manifest.json          # every file above with its sha256 (committed)
    PROOF.md               # the narrative (committed)
```

Every `PROOF.md` names four things, so a human who never saw the design
can audit the claim:

1. the **optimized quantity** (cost, mass, mass_per_length, ...);
2. the **domain** searched (and the real source it was lowered from);
3. the **winner**;
4. the **`cause: optimize(...)` row**, verbatim from the lockfile, plus
   the artifact files (with content hashes) where the result is visible.

## The surfaces

| demo | surface | what it proves |
|------|---------|----------------|
| 1 | discrete `select` (ebi_decode) | the winner is genuinely searched -- a policy-flip variant reverses the cost order and the winner changes |
| 2 | continuous `in [lo,hi] minimize` (printer_k1) | before/after STEP + GLB of the realized part whose mass the search minimized |
| 3 | removal bounded slots (ribbed_panel) | the STEP solid carrying the pinned ribs, both `count` and `thickness` pinned from a mass search over real OCCT realizations |
| 4 | civil free-section search (footbridge) | the plan + member-schedule sheet and the search-trace sheets for the pinned `std.civil.w_shape` sections |
| 5 | bounded sketch slot (WingSpar) | probe-gated: honest gap until the WO-97/D209 structural-model coupling lands |
| 6 | full `regolith ship` package (small_office) | the complete `dist/` package whose own lockfile carries live `optimize(...)` section pins |

## The feature proof packs (WO-115, D222)

The same idiom generalizes past the optimizer: demos 7-16 give every
user-facing artifact/feature family its own runnable physical proof,
each driving the real pipeline over a real fleet design. Their
manifests set `cause_row: n/a` (no optimizer pin to cite); their
PROOF.md instead states the pipeline path exercised.

| demo | family | project(s) | what it proves |
|------|--------|------------|----------------|
| 7 | drawings | printer_k1 + small_office | shipped multi-view HLR sheet sets (mech) + the civil plan/section sheet, all five formats per subject |
| 8 | BOM + cost + schedule | cnc_router_r1 + timber_pavilion | derived BOM with real record-pinned masses; the member-schedule table; the WO-101 cost sheet over the build's own persisted estimate (WO115-F1 names the open `cost/` dist wiring) |
| 9 | assembly instructions | arm_a6 | mate-ordered steps citing typed mate edges + per-step projected views, through the real `ship --spec` assemblies channel |
| 10 | 3D | cnc_router_r1 | deterministic GLBs (glTF magic asserted) + viewer.html verified standalone (inline base64, zero external requests) |
| 11 | boards | mainboard_mx | real kicad-cli gerber/drill/pos set from the declared BoardOutline; fake-tier board pin labeled; real-tool timestamps labeled nondeterministic |
| 12 | firmware + HDL | espresso_machine + riscv_hart_rv1 | pinmux-solved WO-37 firmware tree with the honest no-ELF surface; the discharged verilator tier + named netlist absence (WO115-F2 names the FirmwareDesign lowering gap) |
| 13 | test runner | 4-language corpus net | cold run builds, warm run replays every scenario `from_cache` (WO115-F3's expectation-grammar fix landed with this pack) |
| 14 | preview | cnc_router_r1 | spec-less preview: 3D family byte-parity with ship, drawings differing by exactly the D197 stamp |
| 15 | calc book + audit | arm_a6 | every obligation walked to one disposition; every sheet's chain digest recomputed independently and matched |
| 16 | doctor/config | scratch project | the host toolenv report + the config precedence ladder (default -> project -> env), verbatim CLI output |

Demos run the real CLI/pipeline -- `regolith build`/`ship` and the real
orchestrator search -- never a bespoke scorer or a fixture-only
shortcut. Two runs of a deterministic demo are byte-identical; the
`tests/test_wo108_demos.py` gate enforces both manifest completeness and
that determinism.

## Honest gaps

A surface whose machinery is not yet merged does NOT fabricate an
artifact. Its script is wired behind an availability probe: it detects
whether the machinery is present on the installed core, and until it is,
writes a `PROOF.md` gap note naming exactly what it is blocked on and
exits nonzero from `make demos-strict`. The moment the machinery lands,
the probe flips and the real proof pack is produced with no further edit
(demo 5 is the current example, gated on the WO-97/D209 coupling).

This is the standing answer to "is every optimization still proven": the
`demos` leg of `make health` (D219) runs these packs and checks that
every manifest still matches.
