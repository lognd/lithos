# py-magnetite

`python/regolith/magnetite` -- the package manager: manifest parsing,
immutable revisioned records, trait coherence, and the registry client
(AD-1). Normative sources are pointed at, not restated: `docs/spec/
regolith/11-magnetite.md` (all), `docs/spec/regolith/09-obligations.md`
sec. 5 (coherence), and the WO-145 citation-model work-order for the
structured-citation slice. See `AUDIT-2026-07-16.md` for this pass's
recon and the D256 hash-window follow-up in flight over the same area.

## Package root

<a id="magnetite-init"></a>
### `magnetite/__init__.py`

Owns the package layer (AD-1): manifest parsing and local resolution
(`manifest`), immutable revisioned records (`records`), trait coherence
(`coherence`), and the registry client (regolith/11 sec. 10): a sparse
index (`index`), manifest-declared sources (`sources`), a
content-addressed httpx client with hash-pinned fetch (`client`,
INV-22), signature-carried trust (`trust`, INV-14), and vendoring
(`vendor`). `stdlib/` starter packages (WO-45, D135) load through
`stdlib_records`.

## Manifest and resolution

<a id="magnetite-manifest"></a>
### `magnetite/manifest.py`

magnetite.toml manifest model and local path resolution (WO-16; regolith/11
all): a package declares its kind, what it provides, its dependencies
and halves, and evidence hashes. Resolution is local-path only here --
no network, no publishing. Two versions of one package in a resolution
is an error.

<a id="magnetite-sources"></a>
### `magnetite/sources.py`

Registry sources: the manifest `[sources]` table (regolith/11 sec.
10.2). Sources are declared in the manifest -- no ambient default
inside the languages (sec. 6's no-ambient-state rule); the toolchain
ships configured with the public registry, so the common case is zero
ceremony.

<a id="magnetite-lints"></a>
### `magnetite/lints.py`

`magnetite.toml [lints]` resolution (WO-40 deliverable 4;
`docs/spec/toolchain/24-developer-tooling.md` sec. 5). A manifest's
`[lints]` table (already flattened into `Manifest.lints`) is the code
-> action table `regolith.compiler` forwards to the Rust core, the ONE
place that promotes a `deny`'d code's severity to `Error`. No-manifest
projects resolve to pure defaults (every lint stays `Warning`).

<a id="magnetite-scaffold"></a>
### `magnetite/scaffold.py`

`magnetite new` -- scaffold a working project from a template (WO-41;
`docs/spec/toolchain/24-developer-tooling.md` sec. 6). Emits
`magnetite.toml`, one source file per track (an honest example claim
passing `regolith check` by construction), a house `.gitignore`, and a
CI snippet. Source-file extensions are read from the ONE registry
through the facade (`compiler.extensions()`, ground rule 6/AD-14) --
never hard-coded here or in template data, which is stored under
registry LANGUAGE names, not filenames carrying an extension.

<a id="magnetite-stdlib-resolve"></a>
### `magnetite/stdlib_resolve.py`

Resolves `std.*` record search paths for CLI builds. `build`/`ship`/
`test` need `cost_record_paths`/`frame_record_paths`/`plan_record_paths`
populated; `resolve_record_search_paths` reads the project's `[depends]`
table and, when at least one `std.*` package is declared, locates the
stdlib root by trying, in order: an explicit `records.stdlib_root`
config key, a vendored copy under `<project_root>/vendor/` (vendoring
pins win over silent fallback), then a development-fallback upward walk
for the `std.quantities` sentinel package. A project with no `std.*`
dependency, or one that resolves to no stdlib root, both return `()` --
not an error; the existing honest-deferral posture already names the
missing record at discharge time.

## Records and coherence

<a id="magnetite-records"></a>
### `magnetite/records.py`

Registry record store and schemas (WO-16; regolith/11, regolith/09 sec.
5). Records are addressed by `(package, key, revision)` with
append-only revisions and hash pinning; every record carries a
mandatory evidence clause (`by catalog/test/analysis` + trust tier).
Record shapes mirror the corpus (`examples/registry/`); concrete record
bodies are parsed by the Rust front-end like any source.

<a id="magnetite-records-payload"></a>
### `magnetite/records_payload.py`

Serializes loaded registry records for the Rust rule engine (WO-87,
D198). Magnetite is the ONE record loader -- the Rust side never reads
TOML. Walks the same `<package>/records/*.toml` files the stdlib
loaders read and serializes every `[[component]]` row's scalar fields
into the `kind: "registry.records"` realized-input payload
`regolith-lower`'s `registry` module deserializes, content-hashed like
every realized input (INV-22). Scoped to `component` rows deliberately
(D198: exactly the fields rule predicates dereference) -- materials,
cost rows, and section tables have their own typed loaders.

<a id="magnetite-stdlib-records"></a>
### `magnetite/stdlib_records.py`

Loads `stdlib/` data records (WO-45, D135) into `Record` values.
Package bodies that are ordinary language source live beside their
`magnetite.toml`; this module only loads the plain-TOML data records
this WO introduced for packages with no track-specific syntax yet
(materials, contact pairs, fluid media/pipe tables). Every row's
`content_hash` is a `sha256:` digest of its own canonical TOML row
(INV-22 has something real to bind to even though nothing here is
signed); `evidence` is read straight from the row's mandatory table
(D58: every stdlib record cites its tier honestly).

<a id="magnetite-coherence"></a>
### `magnetite/coherence.py`

Trait-coherence resolution (WO-16; regolith/09 sec. 5): the one
rulebook for all registry-like mechanisms -- canonical (unordered where
applicable) keys; resolution picks the unique most-specific record or
errors; `override <record> by <evidence>` shadows at the same key with
a mandatory evidence clause; `use { A, B }` / `use <impl>` pins
ambiguous resolution; every resolution is lockfile-provenanced.

<a id="magnetite-citation"></a>
### `magnetite/citation.py`

Structured per-value citations (WO-145, D257 ruling 2). The house
`evidence = { method, trust_tier, reference }` shape
(`records.Evidence`) is unchanged; this module decomposes the prose
`reference` string into structured, machine-checkable fields
(`document`, `revision`, `date`, `page`, `table`, `url`) for records
whose provenance is a specific manufacturer datasheet page and table
(the `xr_ratio_evidence` precedent, `stdlib/std.power/records/
transformer_dry_type.toml:75`). Type rule (D257 ruling 2): `Cited[T]`
and `CitedInterval` require a `Citation` at construction time, so
pydantic's own validation makes an uncited value a parse/type error,
never a lint finding a reviewer could miss.

## Registry client and trust

<a id="magnetite-index"></a>
### `magnetite/index.py`

The magnetite registry sparse index (regolith/11 sec. 10.1): maps
`(package, version)` to a manifest digest and an archive hash, append-
only and fetched sparsely (per-package paths, the cargo sparse-index
shape). Each package's index file is newline-delimited JSON, one
`IndexEntry` per line; a yank flips a flag rather than rewriting
history.

<a id="magnetite-client"></a>
### `magnetite/client.py`

The magnetite registry client over httpx (regolith/11 sec. 10; INV-22).
Fetches a package's sparse index and content-addressed archives, and
verifies every fetched archive against the hash the caller demands --
a poisoned mirror can only produce a loud hash-mismatch error, never a
silent substitution. The transport is injectable (an `httpx.Client`
passed in), so tests drive it with an in-memory `httpx.MockTransport`
and never touch the network. Trust is not decided here (sec. 10.4);
this layer delivers verified bytes, `trust` decides their tier.

<a id="magnetite-trust"></a>
### `magnetite/trust.py`

Trust tiers and signature verification (regolith/11 sec. 7 + 10;
INV-14). Trust is a property of signatures on a record, verified
locally against the consumer's key set -- never a property of where a
package was fetched from (sec. 10.4): a certified record is certified
from any mirror, no registry operator can mint certification by
hosting. The tiers form a total order (`certified > tested >
community`) so a claim group's trust floor compares totally; a
signature below the floor downgrades the usable tier rather than
erroring.

<a id="magnetite-vendor"></a>
### `magnetite/vendor.py`

`magnetite vendor`: copy pinned archives into the tree (regolith/11
sec. 10.3). Vendoring copies every lockfile-pinned archive into the
repo so builds run offline; the vendored bytes are content-addressed,
so the lockfile pin still decides acceptance and a tampered vendored
file fails the same INV-22 hash comparison a tampered mirror would.
Files land under `vendor/<digest>` -- content-addressed and
de-duplicated.
