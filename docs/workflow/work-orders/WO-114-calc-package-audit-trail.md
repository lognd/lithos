# WO-114 -- Calc package + audit index (D221, the audit trail)

Status: done
Language: Python (backends/producers/renderers through the D208
  registry seam); no schema bump expected (D225).
Spec: D221 (the four rulings); charter 38 (registry seam, dist/
  layout, style packs, canonical digests); WO-98 (acceptance
  ledger -- cross-linked, not duplicated); AD-6/INV-10
  (determinism); AD-18 (one encoder).

## Goal

`regolith ship` emits an engineering calc book: per-discharged-
obligation calculation sheets plus one audit index that maps EVERY
obligation in the design to exactly one disposition (calc sheet |
acceptance row + memo | named deferral), all hash-chained, so an
external reviewer can audit the package with nothing but its own
contents.

## Deliverables

1. `calc/` producer (registry-registered, the seam's first
   post-charter family): one sheet per discharged obligation
   carrying claim source text + anchor, model id/version/citation,
   inputs with units + provenance pins (record ref | literal |
   derived), solver + tier + attestation, margin, verdict, and the
   evidence hash chain (sheet -> evidence -> payload -> source
   content addresses).
2. Audit index artifact: total obligation accounting with zero
   unexplained rows; cross-links acceptance_ledger.json rows and
   memo hashes for deviations; named deferral reasons for the rest;
   summary counts matching the census shape.
3. Renderers: canonical JSON (deterministic, hashed) + PDF sheets
   through the existing style-pack/PDF renderer (match the WO-100/
   101 sheet idiom); package index rows for every file.
4. Model citation surface: models expose their citation string
   (docstring-derived or explicit attribute) -- add the minimal
   accessor the sheets need; models without citations render an
   honest "uncited built-in" marker (WO-110 is landing citations in
   parallel; do not block on it).
5. Determinism: byte-identical across runs (golden-enrolled for at
   least two fleet projects, one mech-heavy + one civil/schedule).
6. Guide page (docs/guide/) documenting the calc package for users;
   charter 38 gains a short amendment section (coordinator reviews
   wording at integration).

## Acceptance

- Two enrolled fleet packages ship calc/ + audit index, goldens
  byte-stable; every obligation accounted (test asserts zero
  unexplained).
- Works TODAY at 45 discharges (small calc books are fine); scales
  with WO-113 without change.
- `make check` green.

## Escalation

If per-obligation input provenance is not reachable from the
payload/evidence surface for some model family, ledger it as a
named gap per family (placeholder F-number) rather than inventing
provenance; the coordinator folds it into the routing/model WOs.

## Close-out ledger (done)

Landed (all in `python/regolith/backends/calc.py`, wired into
`ship.py`; no schema bump -- D225 held):

1. `calc/` producer: `build_calc_book` emits one `CalcSheet` per
   DISCHARGED obligation (deferral-None, the census definition) --
   claim source text + subject anchor, model id/version/citation,
   every `given:` input with its provenance pin (materials ->
   `record_ref` w/ record hash; loads -> `declared_literal`; refs ->
   `derived`), solver + tier + attestation, computed value/margin,
   verdict, and an `EvidenceChain` (sheet -> evidence -> payload refs
   -> subject + record content addresses).
2. Audit index: `build_calc_book` maps EVERY obligation to exactly one
   `AuditRow` disposition (`calc_sheet` | `accepted_deviation` |
   `deferred` | `violated`), zero unexplained rows (row partition
   balances, `AuditSummary.balanced()`). Accepted rows cross-link the
   WO-98 `acceptance_ledger.json` waiver target + memo digest (never
   duplicated). `AuditSummary` carries BOTH the census-shape counts
   (`census_row()` reconciles field-for-field with
   `fleet_census.json`) and the per-obligation row partition, resolving
   the forall-duplicate-content-address ambiguity (accepted ROWS can
   exceed unique accepted addresses).
3. Renderers: canonical JSON (`calc_book.json` + `audit_index.json`,
   one sorted-key ASCII encoder, byte-deterministic) + one PDF per
   sheet through the EXISTING `DrawingModel` renderer (style-pack seam,
   `render_pdf`) + a `calc/` row in the package index (`FAMILY_DIRS`
   gains `calc`, so `index.md` lists it present/absent). Ships for
   EVERY project via `ship._calc_package_files` (an empty build still
   carries an honest zero-obligation audit index).
4. Model citation surface: `Model.citation` (default `None`) +
   `ModelRegistry.citations()`; a model without a citation renders the
   honest `uncited built-in` marker. Did NOT block on WO-110's parallel
   citation authoring.
5. Determinism: goldens enrolled for `cnc_router_r1` (mech-heavy) and
   `timber_pavilion` (civil/schedule) --
   `tests/golden/test_calc_corpus.py` freezes the canonical book +
   index bytes, asserts a two-build byte match, zero unexplained rows,
   and census reconciliation. Unit coverage in
   `tests/backends/test_calc.py`.
6. Guide: `docs/guide/24-calc-package.md` (+ README row).

Provenance-gap ledger (WO114-F1): the CAM/workload model families
(`cam_*_gcode_fanuc`, `workload_realization_identity`) carry their
inputs only as `given.loads` text expressions (`plan_ref:`,
`plan_dialect:`, `resolution_mm:`, `cause: derived(...)`), never as
typed record refs -- so their calc sheets pin those inputs as
`declared_literal`/`derived` (honest) but expose no `record_ref`
content pin. Not a defect: the source declares them as literals. When
the routing/model WOs promote these to record-backed inputs, the
provenance upgrades to `record_ref` with no calc-side change. No
model family produced a wholly-unreachable input surface (no
`unresolved` rows emitted), so no per-family placeholder gap was
needed beyond this note.

Census/family drift: adding `calc` to `FAMILY_DIRS` adds a `calc`
family to every fleet project's shipped set; `tests/golden/data/
fleet_census.json` `families` lists regenerated via the ordinary
`REGOLITH_UPDATE_GOLDEN=1 python -m tools.health.fleet` flow
(numbers unchanged -- only the family lists gained `calc`).

## Charter-38 amendment draft (for coordinator review)

Proposed new subsection under charter 38 sec. 1 (load-bearing design
decisions), for the coordinator to fold into the charter at
integration (WO agents do not edit the charter):

> 14. **The audit trail is a shipped family (D221).** Every `dist/`
>     package carries a `calc/` family produced through the producer
>     seam: one calc sheet per DISCHARGED obligation (claim source +
>     anchor, model id/version/citation, every `given:` input with its
>     provenance pin -- record ref / declared literal / derived --
>     solver/tier/attestation, margin, verdict, and a content-hash
>     chain sheet -> evidence -> payload -> sources), plus one audit
>     index mapping EVERY obligation to exactly one disposition (calc
>     sheet | accepted deviation cross-linking `acceptance_ledger.json`
>     | named deferral | violated) with zero unexplained rows. Forms:
>     canonical JSON + per-sheet PDF through the existing renderer, a
>     `calc/` row in the index. The index summary's census-shape
>     projection reconciles field-for-field with the WO-106 fleet
>     census. A sheet's own digest is a `local-blake3:`-tagged
>     producer-local hash (sec. 1.4); every address it cites is a
>     canonical toolchain address. Model citations are surfaced through
>     `Model.citation`; a model without one renders `uncited built-in`
>     (never a fabricated reference).
