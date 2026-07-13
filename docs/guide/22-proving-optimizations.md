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
