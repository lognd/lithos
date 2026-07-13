# The calc package and audit index (`calc/`)

STATUS: WORKING (WO-114). Every `regolith ship` release package now
carries a `calc/` family -- the calculation report an engineering firm
calls the *calc book* -- plus one *audit index* that accounts for every
obligation in the design. It ships for EVERY project, including designs
that discharge zero obligations (their audit index is still complete).

Source: design-log `2026-07-13-cycle-35.md` D221 (the four rulings),
charter `docs/spec/toolchain/38-emission-and-release.md` (the registry/
`dist/` seam), `00-architecture.md` AD-6/AD-18 (determinism, the one
encoder). Machinery: `python/regolith/backends/calc.py`, wired into
`python/regolith/backends/ship.py`.

## Why this exists

A release package already proves *what* a design claims and whether the
gate passed (`gate_summary.json`), and it lists every accepted deviation
(`acceptance_ledger.json`, the WO-98 ledger). The calc package closes the
last gap: it lets an external reviewer audit the design with nothing but
the package's own bytes -- no access to the toolchain, the source tree,
or the author. Two artifacts do this:

1. a **calc sheet** for every DISCHARGED obligation -- the worked
   calculation, with its inputs, model, margin, verdict, and a content-
   hash chain a reviewer can re-verify;
2. an **audit index** that maps EVERY obligation to exactly one
   disposition, so nothing is silently unaccounted for.

## What ships

```
dist/<project>/
  calc/
    calc_book.json        every calc sheet, canonical JSON
    audit_index.json      the total obligation accounting
    <claim>__<subject>.pdf one rendered sheet per discharged obligation
```

Every file is content-addressed in `manifest.json` and re-verified by
`regolith ship --verify` exactly like any other artifact.

### A calc sheet

One discharged obligation's sheet carries:

- **claim** -- the source text (`stress < limit`) and its subject anchor
  (the declaration the obligation is rooted at);
- **model** -- the discharge model id, its version, and its citation. A
  model with no citation renders the honest marker `uncited built-in`
  rather than a fabricated reference;
- **inputs** -- every value the obligation's `given:` context pinned,
  each tagged with its provenance:
  - `record_ref` -- a hash-pinned std.*/registry record (the content
    hash is the pin);
  - `declared_literal` -- a value written directly in the design source;
  - `derived` -- a value resolved from other declared design data;
- **solver / tier / attestation** -- how it was discharged;
- **value, margin, verdict** -- the computed result;
- **chain** -- the content-hash chain `sheet -> evidence -> payload ->
  sources`. The sheet's own digest is a producer-local `local-blake3:`
  hash (it has no upstream address of its own); everything it CITES
  (the evidence hash, the subject content address, the pinned record
  hashes) is a canonical toolchain address.

If per-obligation input provenance is not reachable from the payload for
some model family, the inputs list is honestly empty for that sheet --
the toolchain never invents an input to fill the sheet.

### The audit index

The index's `rows` list every obligation exactly once, each with one
`disposition`:

- `calc_sheet` -- discharged; `detail` names the sheet;
- `accepted_deviation` -- an accepted waiver covers it; `detail` cross-
  links the `acceptance_ledger.json` waiver target and its memo digest
  (the index never duplicates the ledger);
- `deferred` -- honestly indeterminate; `detail` is the named reason;
- `violated` -- a failed verdict; `detail` is the reason.

The `summary` reports two reconcilable views:

- the **census-shape** counts (`obligations`, `discharged`,
  `accepted_deviation`, `violated`) -- these match the fleet census
  (`tests/golden/data/fleet_census.json`) field for field, so the audit
  index and the census can never silently disagree;
- the **row partition** -- `discharged + accepted_rows + deferred +
  violated == obligations`. `accepted_rows` can exceed
  `accepted_deviation` because `forall`-expanded obligation instances
  legitimately share one content address; both numbers are reported so
  the accounting is never ambiguous.

"Zero unexplained rows" is the guarantee: there is exactly one row per
obligation, and the partition always balances.

## Determinism

The calc book is byte-identical across runs and checkout paths (AD-6/
INV-10): canonical JSON through one sorted-key encoder, no wall-clock, no
absolute paths, and PDFs through the existing deterministic `DrawingModel`
renderer. Two ships of the same design produce the same `calc/` bytes.

## Regenerating the goldens

Two fleet projects are golden-enrolled (`tests/golden/test_calc_corpus.py`):
`cnc_router_r1` (mech-heavy) and `timber_pavilion` (civil/schedule). To
regenerate after an intended change:

```
REGOLITH_UPDATE_GOLDEN=1 pytest tests/golden/test_calc_corpus.py
```

and diff-review the change like any other generated artifact.
