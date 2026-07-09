# WO-45: The standard library v1 (`stdlib/`, D135)

Status: done
Depends: WO-16 (registry loader, done), WO-44 (plugin seam --
preferred but not blocking: model registration can land on the
WO-20 group and move with WO-44's migration if this runs first).
`std.civil` is EXCLUDED (WO-48). The `std.sheet_metal`/`jlc_2l`
RULE-PACK halves are EXCLUDED (WO-28's engine remainder owns the
rule format; this WO creates their package homes + record content
only).
Language: Python packaging + record/data authoring; no Rust.
Spec: regolith/11 sec. 8 (the D135 catalog -- NORMATIVE), sec. 3-7
(manifest, records, computed semver, namespacing, trust), design-log
2026-07-08-cycle-26 D135; D58 (tier honesty precedent); the
`examples/registry/*.cupr` records as the record-format lineage.

## Goal

The `std.` catalog stops being prose: `stdlib/` exists at the repo
root, each entry a real magnetite package with a manifest and
content, CI-consumed, corpus-cited (no phantom `process=`/import
refs anywhere in examples/), and loadable through the ordinary
registry/loader path (WO-16) from a local source.

## Deliverables

1. `stdlib/` layout: one directory per package, each with
   `magnetite.toml` (kinds declared per regolith/11 sec. 2) and
   sources. A top-level `stdlib/README.md` states the D135
   governance (reserved prefix, tier honesty, in-repo development).
2. Packages, v1 content (catalog per regolith/11 sec. 8):
   `std.quantities` (namespace + claim-form declarations -- the
   surface the tracks already assume); `std.materials` +
   `std.contact` (starter records, `tier=community`, sources cited);
   `std.mech` (mount/flange interface packs, bolted/press/bearing
   matings, weld features + records); `std.sheet_metal` (process
   capability records; rule-pack half deferred to WO-28 with a
   marker); `std.elec` (port kinds, family records, protocol packs,
   derating records; `jlc_2l` records beside it, vendor-named);
   `std.fluid` (media property tables, fitting/loss records);
   `std.intents` + `std.debug` (verb schemas); `std.models`
   (registration manifest binding the EXISTING
   `python/regolith/harness/models/` code -- code does not move).
3. Local-source resolution: the magnetite sources mechanism gains a
   `path` source form (manifest-declared directory source) IF one
   does not already exist -- check `magnetite/sources.py` first; if
   it exists, wire it, do not duplicate. CI and the corpus consume
   `stdlib/` through it.
4. Corpus de-phantoming: every `process=`, `import`, and record
   reference in `examples/` that names a std pack resolves against
   `stdlib/` in `make check` (a test enumerates them).
5. Tests: manifest validity for every package; record schema
   round-trips; the de-phantoming enumeration; a trust-tier test
   that every record's in-file tier claim matches its evidence
   clause shape.
6. Docs: regolith/11 sec. 8 flipped to "landed" per entry;
   examples/README notes the stdlib dependency.

## Acceptance criteria

- `make check` green with the corpus resolving std references from
  `stdlib/` (no network, INV-22 pinning respected).
- Every package's records carry provenance + honest tiers (D58).
- No compiler special-casing of `std` anywhere (grep `std.` in
  crates/ stays clean of new logic).

## Non-goals

- Publishing to a live registry (hosting is out of client scope,
  regolith/11 sec. 10 cut stands).
- `std.civil` (WO-48), rule-pack formats (WO-28), new harness model
  CODE (only packaging/registration here).
- Completeness: v1 content is the starter set the corpus needs;
  breadth grows by ordinary contribution, not by this WO.
