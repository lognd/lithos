# stdlib/ -- the `std.` catalog (D135, WO-45)

Governance (regolith/11 sec. 8, D135):

- `std.` is a RESERVED namespace prefix in the magnetite registry: only
  the lithos project publishes under it.
- Nothing in the compiler special-cases `std` (grep `std.` in `crates/`
  stays clean of new logic), with the one documented exception that the
  unit tables (what `std.units` would be) live in `regolith-qty` because
  quantities are load-bearing at L1, before package resolution runs.
  `std.quantities` (below) is therefore a nominal package: it declares
  the namespace/claim-form surface the tracks already assume, so a
  project's `magnetite.toml` can depend on it like any other package,
  but it ships no records of its own -- the math lives in `regolith-qty`.
- **In-repo development home:** each `stdlib/<package>/` directory is a
  real magnetite package (its own `magnetite.toml` + record/model
  content). CI and the example corpus (`examples/`) consume these
  in-repo copies directly, via `regolith.magnetite.manifest.resolve_dependencies`
  pointed at `stdlib/` as a local search path -- no network, no separate
  "path source" concept invented (checked `magnetite/sources.py` first,
  per the WO note: `resolve_dependencies` already IS local-path
  resolution; `Sources`/`Registry` in `sources.py` is a distinct concern,
  URL-based routing for a future fetch step, not needed here).
  Publication to the public registry (out of scope, regolith/11 sec. 10)
  would be the same act as for any third-party package; the project
  signing key confers the tier (INV-14).
- **Tier honesty (D58):** every record here that transcribes a
  real-world datasheet/handbook value without an attached certified
  test report says `tier=community` in-file, and cites its source.
  Nothing here claims `tier=certified`.

## Packages (v1)

| package | kind(s) | content |
|---|---|---|
| `std.quantities` | quantities | namespace/claim-form declarations only (math in `regolith-qty`) |
| `std.materials` | materials | starter metal/polymer records, `tier=community` |
| `std.contact` | materials | dry/greased contact-pair friction records, `tier=community` |
| `std.mech` | interfaces, matings | mount/flange interface packs, process capability packs (cnc/forged/formed/cast/molding/sheet/tube/turned/weld/joining/gear/linear/spring/bearings/seals), bolted/press/bearing matings |
| `std.sheet_metal` | process | sheet-metal process capability records; the DFM RULE-PACK half is EXCLUDED (WO-28 engine remainder owns the rule format) -- this package is the record content + package home only |
| `std.elec` | interfaces, matings | port/family/protocol/bus packs (buffers, buses, digital, families, logic, power, protocols, sense) |
| `jlc_2l` | process | JLCPCB 2-layer fab + basic SMT assembly capability records (vendor-named, rides beside `std.elec`, NOT under the `std.` prefix) |
| `std.fluid` | materials | media property tables + fitting/loss/pipe-schedule records |
| `std.intents` | verbs | intent-verb schemas (`sense`, `actuate`) |
| `std.debug` | verbs | debug/probe/indicate verb schemas |
| `std.models` | models | registration manifest binding the EXISTING `python/regolith/harness/models/` code -- the code does not move, this package only names it |
| `std.mech.mechanisms` | matings, process | pattern library (D144/AD-28, WO-53): the `four_bar` Grashof linkage -- coupler-law `mating`, `advise:`-only recognition rule (`dfm:` block) |
| `std.elec.patterns` | interfaces, components, process | pattern library (D144/AD-28, WO-53): the `level_shifter` block + reference impl, `advise:`-only recognition rule (`erc:` block) |

`std.civil` is EXCLUDED here (WO-48, gated on the calcite front end).
`std.fluid.circuits` / `std.civil.assemblies` (D144 pattern libraries,
remaining catalog batches) are catalog GROWTH, not this WO's seed
(charter `docs/spec/toolchain/26-pattern-libraries.md` sec. 3
non-goal). `std.cost` (D147) is WO-54.

## Record format

Record BODIES that are ordinary language source (interface/mating/
process declarations consumed by a track's front end) are authored in
that track's own syntax, exactly like `examples/registry/*.cupr`. Data
records with no track-specific syntax yet (materials, contact pairs,
fluid media/pipe tables) are authored as plain TOML under each
package's `records/` directory and loaded by
`regolith.magnetite.stdlib_records.load_toml_records` into the ordinary
`regolith.magnetite.records.Record` model -- Python-side data
authoring only, no new Rust grammar (this WO is Python + records, no
Rust per its `Language:` header).
