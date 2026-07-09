# WO-60: stdlib growth batch C (selection catalogs + recorded growth)

Status: todo
Depends: WO-45/WO-53 conventions (landed): catalog rows, TOML record
loaders, de-phantoming tests, two-halved pattern packs. Independent
of every other cycle-30 WO; feeds WO-56's ebi_decode demo (soft).
NO SCHEMA_VERSION bump; no Rust.
Language: records (TOML/`.cupr`/`.hema`/`.fluo`/`.calx` pack
content) + Python only for loader/test touch-ups.
Spec: docs/spec/toolchain/26-pattern-libraries.md (AD-28),
regolith/11 (packages/stdlib), design-log 2026-07-09-cycle-30 D166;
the cycle-28 MCU-registry verification precedent (INV-14: tier is
earned by signature, never by text cross-check -- everything here
stays community tier with in-file verification notes).

## Goal

The recorded WO-53/WO-45 growth lands, with the catalogs the
cycle-30 optimizer needs: an address-decode/glue-logic family (the
D161 demo candidates), wider civil section/material tables (a real
section-search domain), fluid component records, and the
mech-mechanisms remainder.

## Deliverables

1. **std.elec.patterns batch C -- glue-logic/address-decode
   family**: records + two-halved packs for at least: 74HC02 (quad
   NOR), 74HC138 (3-to-8 decoder), 74HC688 (8-bit comparator), one
   CPLD candidate (e.g. ATF1502ASL -- verify the real, current
   part), and an MCU chip-select pattern (EBI/FSMC-style, cited to
   a real MCU family reference manual). Each record: real datasheet
   citation WITH revision, key electrical facts (propagation delay,
   supply range, package options), cost-surface fields the landed
   costing records support.
2. **std.civil widening**: extend `sections.toml` (more W/HSS/pipe
   shapes across the depth range) and `materials.toml` per the
   landed schema; every row cites its source table (AISC shapes DB
   edition or equivalent public source) in-file. Enough shapes that
   the WO-56 section search is a real choice (>= 15 sections per
   family used by the corpus).
3. **std.fluid batch**: pump/valve/orifice/filter records per the
   landed fluid record shapes, real-catalog cited.
4. **std.mech.mechanisms remainder**: the batch-C members the WO-53
   ledger names as recorded growth.
5. **Research protocol**: facts verified against real, current
   datasheets/catalogs (web research in-dispatch); no invented
   numbers -- a fact that cannot be verified is OMITTED with a note,
   never guessed (feldspar's no-invented-physics discipline applied
   to records). Verification notes in-file per the MCU-registry
   precedent.
6. **Tests/wiring**: catalog rows, loader round-trips,
   de-phantoming (every referenced record exists; every record is
   referenced or listed), fixtures where WO-45/53 conventions add
   them.
7. **Docs**: stdlib README sections, WO-53/45 ledger cross-notes,
   WO ledger.

## Acceptance criteria

- Every new record loads through the landed loaders; de-phantoming
  green; catalog rows complete.
- Spot-check hooks: each record's citation names document + revision
  + the fields it sourced (reviewable without the datasheet).
- The glue-logic family is sufficient for WO-56's
  `by select(nor_glue, cpld, mcu_chip_selects)` demo (named refs
  documented in this WO's ledger for WO-56 to consume).
- std.civil growth changes NO existing corpus golden (additive
  rows only; if a golden churns, the row collides -- rename, never
  regenerate around it).
- ASCII only; `make check` green; Status flipped in this change.
