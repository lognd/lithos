# WO-114 -- Calc package + audit index (D221, the audit trail)

Status: open
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
