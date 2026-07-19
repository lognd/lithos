# regolith-py

The `regolith._core` PyO3 extension module: marshalling ONLY (AD-2/AD-4).
No logic lives here -- every function body is a thin call into
`regolith-api`; if a body here grows past marshalling, it belongs in a
lower crate. Only `python/regolith/compiler.py` may import this module
(AD-4, `make guard-core` enforces). Panic policy: every entry point is
`catch_unwind`-wrapped (the private `guard` helper) so a Rust panic
becomes a `regolith.CoreBug`, never an unguarded Python exception; an
infrastructure failure (unreadable file, corrupt cache) becomes
`regolith.CoreError`. A failing *build* is never an exception -- it is a
`BuildOutput` carrying error-severity diagnostics (AD-7).

## Build result

<a id="pybuildoutput"></a>
### `PyBuildOutput`

Opaque handle to a `regolith_api::BuildOutput`; every getter marshals
the underlying Rust value across the boundary.

<a id="pybuildoutput-rendered"></a>
#### `PyBuildOutput.rendered`

The diagnostics rendered to text through the one renderer (AD-7),
`ansi` selecting color escapes.

<a id="pybuildoutput-payload-json"></a>
#### `PyBuildOutput.payload_json`

The structured build payload as JSON bytes, parsed Python-side into the
pydantic `BuildPayload` model.

<a id="pybuildoutput-ok"></a>
#### `PyBuildOutput.ok`

`True` when the build produced no error-severity diagnostics.

<a id="pybuildoutput-diagnostic-count"></a>
#### `PyBuildOutput.diagnostic_count`

The total diagnostic count for the build (all severities).

## Compile session

<a id="pycoresession"></a>
### `PyCoreSession`

A compile session over a project root or explicit file set (AD-4).
Opening does no work; `check`/`compile` run the actual pipeline under
`Python::detach` so the GIL is released for the Rust-side compute.

<a id="pycoresession-new"></a>
#### `PyCoreSession.new`

Open a session over the given source paths (files or roots).

<a id="pycoresession-check"></a>
#### `PyCoreSession.check`

Run the static `check` pipeline. `realized_inputs` (WO-42 deliverable
3) is the caller-resolved realized-domain IR channel: a list of
`(digest, kind, subject, bytes)` tuples, empty for a build with no
realized-domain inputs. `lints` (WO-40 deliverable 4) is the resolved
`magnetite.toml [lints]` table as `(code, action)` pairs; an
unparseable action is silently dropped here (the manifest loader is
where an unknown value gets its own named warning).

<a id="pycoresession-compile"></a>
#### `PyCoreSession.compile`

Run the full `compile` pipeline. `registry_version` is the harness
model-registry version (Python-side, AD-1), folded into every
evidence-cache key (BE-1/INV-1) so a model upgrade forces
re-verification rather than reusing stale evidence. `realized_inputs`
and `lints` are the same coarse channels `check` takes.

## Module-level functions

<a id="core-version"></a>
### `core_version`

The compiler core version string -- the simplest possible proof the
Rust->Python crossing works at all.

<a id="schema-version"></a>
### `schema_version`

The serialized-schema version the boundary speaks (AD-5); every
cross-boundary payload folds this into its content address (AD-18).

<a id="format"></a>
### `format`

Format source text into its canonical spelling.

<a id="debug-dump"></a>
### `debug_dump`

Dump an intermediate pipeline stage of a source file as text
(`regolith debug dump`).

<a id="debug-ir"></a>
### `debug_ir`

Dump the `regolith debug ir` report for `paths` (WO-42 deliverable 3):
the compiler's own IR-stage summary plus the realized-domain IRs
supplied to the build (kind, digest, subject) -- the same coarse
`realized_inputs` channel `check`/`compile` take.

<a id="doc-extract"></a>
### `doc_extract`

Extract a source file's public-surface doc model as JSON (`regolith
doc`, WO-41): one entry per top-level declaration with its kind, name,
leading `#` doc comment (verbatim, D115), fields, `require` claim
groups, and `budget` statements.

<a id="extensions"></a>
### `extensions`

Every recognized `(extension, language)` pair, read from the ONE
registry so Python-side code (`magnetite new`) never hard-codes an
extension string (ground rule 6 / AD-14).

<a id="check-elec-single-driver"></a>
### `check_elec_single_driver`

Run the elec net discipline's single-driver check (AD-23 D4;
cuprite/06) over a `NetlistModel.nets`-shaped JSON array. Returns
`{"ok": true}` when every net is clean, or `{"ok": false, "net",
"drivers", "message"}` naming the first offending net (fail-fast,
byte-for-byte matching the retired Python implementation). A malformed
input is an infrastructure failure (`CoreError`), not a design error.

<a id="rules-test"></a>
### `rules_test`

Run every pack's `expect:` fixtures in `paths` (`regolith rules test`,
WO-28 deliverable 5). A failing fixture is data in the JSON report,
never an exception (AD-7).

<a id="rules-try"></a>
### `rules_try`

Run ONE pack against one design file (`regolith rules try`, WO-28
deliverable 5): forced attachment, every match/verdict/near-miss as a
JSON report string. No build.

<a id="on-events"></a>
### `on_events`

Every `on <event>:` trigger name declared per subject, across `paths`
(WO-37 close-out follow-up): `(declaration, event)` pairs, deduplicated
and sorted, so `regolith.realizer.firmware` builds its `EventDecl` list
from the real typed `OnBlock` CST (AD-22).

<a id="obligation-content-hashes"></a>
### `obligation_content_hashes`

The AD-18 canonical content hash of every obligation in the
`BuildPayload.obligations` array wire shape, in array order -- the ONE
encoder exposed so the Python release gate can match a
`WaiverRecord.matched` hash to its discharge result (WO-98).

<a id="resolve-extrusion-outline"></a>
### `resolve_extrusion_outline`

Resolve a custom extrusion section's radiused tangent-arc walk into its
closed outline + per-arc endpoints (F123/D231/WO116-F1): the
`saw_stock(extrusion(<profile>, l=<len>))` realizer path. Returns the
resolved-outline JSON string when fully determined, or `None` (an
honest skip) when missing, unpromotable, or not fully determined -- the
arc geometry stays single-sourced in Rust (D205).

<a id="reduce-unit-literal"></a>
### `reduce_unit_literal`

Reduce a magnitude in a given unit symbol to its SI base magnitude
(WO-122, F132.2: the bound-text truncation hazard) -- the ONE
unit-reduction crossing the Python orchestrator's bound-text resolver
uses. `None` when the symbol is not a known linear SI unit (log-ratio
spellings like `dB`/`dBc`/`dBm` honestly return `None`, never a guess).

<a id="init-logging"></a>
### `init_logging`

Install the `tracing`/`log` -> Python `logging` bridge (AD-8).
Idempotent: the underlying global logger may only be set once, so
repeat calls (e.g. re-import) are no-ops.

<a id="core"></a>
### `_core`

The PyO3 module initializer for `regolith._core`: registers every
function/class above onto the extension module object.
