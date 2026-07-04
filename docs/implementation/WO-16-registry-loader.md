# WO-16: Package manifest + registry loader (local-only)

Status: todo
Depends: WO-02, WO-06
Language: Python (`rockhead.quarry`; record parsing is the Rust front-end) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/11 (all); substrate/09 sec. 5

## Goal

Load quarry-style packages from local paths: manifests, registry
records, coherence resolution. No network, no publishing -- the data
spine `check` needs for capability tables, materials, components,
families, and intent verbs.

## Deliverables

- `quarry.toml` manifest model (package, kinds, provides, depends,
  halves, evidence hashes); local path resolution from a project root
  manifest; two-versions-of-one-package = error.
- Record store: `(package, key, revision)` addressing, append-only
  revisions, record hash pinning; evidence clause on every record
  (`by catalog/test/analysis` + trust tier).
- Trait-coherence resolution (substrate/09 sec. 5): canonical keys
  (unordered `contact{A, B}`), unique-most-specific-or-error,
  `use` pins, `override ... by <evidence>` (evidence mandatory).
- Record schemas for: `material` (f(T) interval properties),
  `contact`, `process` (capability table + rule-pack refs),
  `component` (limits, derating, resources, functions, packages/pin
  tables, straps -- shape per examples/registry/stm32g0.cupr),
  `family`, `protocol` (shape per examples/registry/i2c_protocol.cupr),
  intent-verb schemas.
- A minimal `std/` seed pack (in-repo): enough records for the
  examples corpus to resolve its references.

## Acceptance

- The examples' imports resolve against the seed pack; unresolvable
  refs and ambiguous records produce the documented diagnostics.
- Coherence tests: specificity resolution, `use` pinning, override
  with/without evidence.
- Lockfile rows (WO-14) carry (version, revision hash) for every
  record consumed.
