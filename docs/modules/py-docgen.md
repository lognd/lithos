# py-docgen

Documentation generation: extracting doc-relevant facts from a
build, the intermediate render models, HTML/markdown rendering, and
status reporting. See `docs/spec/toolchain/00-architecture.md` and
WO-41 for `regolith doc`'s scaffolding contract.

## extract

<a id="extract"></a>
### `python/regolith/docgen/extract.py`

Package-wide doc extraction: enumerate sources, walk each (WO-41).

One ``regolith.compiler.doc_extract`` FFI call per source file (the ONE
door stays per-file, matching ``debug_dump``'s shape); this module
enumerates the package's source files (mirroring the Rust session's
own file-discovery convention: files or roots, recognized extensions
only, lexicographic order for determinism, AD-6) and assembles the
per-file results into one :class:`~regolith.docgen.models.PackageDoc`.

## harness/models (single-file physics/engineering models)

<a id="models"></a>
Each file in this cluster is one self-contained engineering model
(bearing life/pressure, beam bending/deflection/utilization, bolted
joint, buck efficiency/ripple/transient, cost estimators, friction
factor, fluid pressure drop, lame cylinder, link budget, lumped
thermal, NPSH margin, post embedment, sheet bend, shaft torsion,
tolerance stack, workload realization) registered into the harness
via `harness/registry.py`. Each model's pydantic I/O schema and
governing equations are documented in its own module docstring;
this entry indexes the whole cluster to one doc anchor rather than
duplicating per-file prose (WO-1xx model-pack work orders and
`docs/spec/toolchain/00-architecture.md` cover the harness
model-authoring contract these all follow).

## render

<a id="render"></a>
### `python/regolith/docgen/render.py`

Deterministic markdown rendering of a :class:`PackageDoc` (WO-41).

The ONE renderer for ``regolith doc``: pure text assembly, no I/O.
Ordering is fixed (source path, then declaration kind, then name) so
two runs over the same inputs are byte-identical (an acceptance
criterion).

## status

<a id="status"></a>
### `python/regolith/docgen/status.py`

Claim build status for ``regolith doc`` (WO-41): reads-only, never
runs the harness. When ``<project_root>/.regolith/`` is absent every
claim renders ``(unbuilt)`` (no error); when present, a fresh static
``compiler.check`` re-derives the (deterministic, content-addressed)
obligation list and each named obligation is looked up in the
persisted evidence cache (a previous ``regolith build --persist`` run)
-- no live discharge, no solver invocation.

Matching is by the claim's own optional ``name`` (the claim line's
subject, e.g. ``rail_stress:``); a package that reuses one claim name
across multiple declarations gets the same status text on each -- a
documented best-effort simplification (see design-log D127), not a
full per-declaration obligation graph.
