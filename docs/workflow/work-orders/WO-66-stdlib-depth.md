# WO-66: stdlib depth wave 1 (generation tooling + exhaustive families)

Status: todo
Depends: WO-45/53/60 conventions (landed). NO SCHEMA_VERSION bump
(WO-62 owns cycle-31's). Record-family shapes that need ratifying
(sec. below) are ratified by THIS WO's design-log addendum entry
before generation -- write the entry, then generate.
Language: Python (`tools/stdlib/` generation framework) + records;
no Rust.
Spec: docs/spec/toolchain/32-stdlib-depth.md (NORMATIVE -- the
taxonomy and sourcing law live there, follow them exactly),
00-architecture.md AD-34, design-log 2026-07-09-cycle-31 D174;
WO-60's ledger (the verification-note format precedent).

## Goal

The generation framework exists and the first exhaustive families
land: fasteners and section grids generated from standards tables,
E-series passives (shape ratified first), bearings/motion seeds
scaled, std.machines/std.tooling seeded for AD-35 -- all cited,
licensed, deterministic, loader-green.

## Deliverables

1. **`tools/stdlib/` framework**: source-table ingestion (committed
   input tables with citation headers, or polite cached fetchers
   for official sources), deterministic record rendering, license
   ledger (`tools/stdlib/SOURCES.md`: per family -- source,
   revision, license posture, fetch date, script). A `make
   stdlib-gen` target that regenerates and a drift check that
   generated records match committed ones (the schema-check
   pattern).
2. **std.fasteners** (NEW package): ISO 4762/4014/4032/7089 metric
   grids (M2-M24 x standard length series x property classes),
   GENERATED from the standards' dimension tables; record shape
   ratified in the design-log addendum first (head dims, thread,
   length, class, proof load where the standard states it).
3. **std.civil completion**: full AISC v16 W/HSS/C/L grids
   generated from the public shapes database (already the WO-60
   citation); existing 44 hand rows verified against and subsumed
   by the generated set WITHOUT changing existing record ids
   (zero corpus churn -- extend, never rename).
4. **std.elec E-series**: ratify the PARAMETRIC family shape
   (E24/E96 value grids x package x tolerance as generated
   families, not per-part records), then generate; widen
   connectors (JST-XH/PH, Molex KK, screw-terminal classes) from
   official drawings, hand-cited.
5. **std.bearings + std.motion** (NEW): 60xx/62xx/608 deep-groove
   grid + LM/MGN linear seeds; NEMA 17/23 steppers (rated points),
   Tr8 leadscrews, GT2 belts/pulleys -- manufacturer general
   catalogs, cited; sized to cover flagship-1's demand list
   (coordinate: WO-64 phase A's walls list may add members --
   check it at close).
6. **std.machines + std.tooling** (NEW, feeds WO-67): 3-axis mill
   class + FDM printer class + laser class machine records
   (travel/kinematics/spindle-or-nozzle); end-mill/drill grids
   from manufacturer catalogs.
7. **Tests/docs**: loaders + de-phantoming green over everything;
   stdlib README taxonomy table synced to the charter; WO ledger
   with per-family counts + omission notes.

## Acceptance criteria

- `make stdlib-gen` idempotent (regeneration = zero diff);
  SOURCES.md covers every generated family; no TOS-violating
  fetcher exists (fetchers only for sources SOURCES.md marks
  official/open).
- Family shape ratifications recorded BEFORE their generated
  records (log addendum committed first or same change, ordered).
- Zero existing-record renames; zero unrelated golden churn; every
  record loads; de-phantoming green.
- Spot-check honesty: any field the source does not state is
  absent with a note, repo-wide grep-verifiable convention.
- `make check` green; Status flipped with counts.
