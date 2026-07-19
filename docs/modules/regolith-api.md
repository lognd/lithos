# regolith-api

The stable, coarse compile API (AD-4): `Session` and `BuildOutput`, plus
the handful of thin marshalling functions the PyO3 layer calls through
for one Rust<->Python crossing per verb. Regolith reference:
`docs/spec/regolith/06-execution-model.md`. A failing build is a
SUCCESSFUL call whose `BuildOutput` holds violated/indeterminate
results (claims-as-data, AD-7); only infrastructure failures are `Err`.
This doc is a symbol-level index into that contract, not a
restatement of it.

## Format and unit-literal reduction

<a id="format-and-unit-literal-reduction"></a>
### `format`, `reduce_unit_literal`

`format` (`crates/regolith-api/src/lib.rs`) is the boundary
`format(text) -> text` (AD-4): thin delegation to the one canonical
formatter in `regolith-syntax`. `reduce_unit_literal` reduces a
`(magnitude, unit_symbol)` pair to its SI base magnitude through
`regolith_qty::Unit::parse_expr` -- the SAME unit table L1 quantity
literals resolve through (AD-1's one-unit-engine rule), so a
Python-side bound-text resolver never grows a second unit table.
Returns `None` for a symbol the table does not know: log-ratio units
like dB/dBm are honestly not linear SI units, and rotational spellings
like `rpm`/`deg` are deliberately absent from the table too (their
radian equivalents carry irrational scale factors no exact
`Ratio<i64>` can represent, WO122-F1) -- both are an honest `None`,
never a silent approximation.

## Debug dump and debug IR

<a id="debug-dump-and-debug-ir"></a>
### `debug_dump`, `debug_ir`

`debug_dump` (`regolith debug tokens|cst|ast`, AD-13) thinly delegates
to `regolith_syntax::debug::dump`; an unknown stage name is a caller
(programmer) bug and panics rather than returning an error (crosses
the FFI as `CoreBug`, AD-4). `debug_ir` (`regolith debug ir`, WO-42
deliverable 3, AD-25) runs `Session::check` over given paths and
renders a summary of obligation/snapshot/feature-program/frame counts
plus every realized-domain IR supplied to the build (kind, digest,
subject), so a build with realized inputs is inspectable exactly like
every other pipeline stage; an empty `realized_inputs` renders an
explicit "(none supplied)" line (the D128 placeholder path).

## Event surface extraction

<a id="event-surface-extraction"></a>
### `on_events`

Every `on <event>:` trigger name declared per subject, across a set of
sources (WO-37 close-out follow-up): the firmware realizer's typed
event surface, backed by real `OnBlock` CST data via
`regolith_lower::converter::collect_on_events`. Thin parse-and-delegate,
matching `debug_dump`'s shape.

## Extrusion outline resolution

<a id="extrusion-outline-resolution"></a>
### `resolve_extrusion_outline`

Resolves a custom extrusion section's radiused tangent-arc walk into
its closed outline plus per-arc endpoints (F123/D231/WO116-F1), for
the `saw_stock(extrusion(<profile>, l=<len>))` realizer path. Promotes
the parsed profile walk and resolves it through the closed-form
`arc_chord` math in `regolith_ir::solve::sketch::resolve_outline`, so
arc geometry stays single-sourced in Rust (never recomputed in
Python, D205). Returns `Ok(None)` (an honest skip) when the profile is
missing, unpromotable, or not fully determined -- never a guess.

## Version and extension-registry accessors

<a id="version-and-extension-registry-accessors"></a>
### `core_version`, `schema_version`, `extensions`

`core_version` is the workspace package version, the truth
`regolith.core_version()`'s Python smoke test reads back.
`schema_version` is the serialized-schema version (AD-5) the facade
asserts against the generated pydantic models at import.  `extensions`
lists every recognized `(extension, language)` pair read from the ONE
registry (`regolith_syntax::EXTENSIONS`, ground rule 6 / AD-14), so
`magnetite new` and friends never hard-code an extension string
(WO-41's tripwire).

## Obligation content hashes

<a id="obligation-content-hashes"></a>
### `obligation_content_hashes`

The AD-18 canonical content hash of every obligation in a JSON array
(the `BuildPayload.obligations` wire shape), in the array's own order.
The ONE encoder exposed for the Python release gate: a `WaiveLedger`
entry records accepted obligations by content hash, and reproducing
the canonical CBOR address in Python would be a forbidden second
encoder (AD-18), so the address is computed here and marshalled
across. Returns `CoreError::CacheCorrupt` if the input is not a valid
`Vec<Obligation>` -- a boundary-contract violation, not a panic.

## Elec net-core marshalling

<a id="elec-net-core-marshalling"></a>
### `check_elec_single_driver`, `ElecViolation`

`crates/regolith-api/src/net_core.rs`: pure wire<->core translation
over `regolith_sem::net_core` for the elec discipline (AD-23 D4) -- no
net-ledger logic lives here. `check_elec_single_driver` parses a JSON
array of wire-format nets (matching
`regolith.realizer.elec.netlist.Net`/`Pin` field-for-field, including
`is_driver`) and runs the single-driver check (cuprite/06), returning
the first violation in net order, byte-identical to the retired Python
message text. `ElecViolation` is that result's wire shape: the
offending net, its driver terminals, and the rendered message.

## Rule-pack test and try verbs

<a id="rule-pack-test-and-try-verbs"></a>
### `rules_test`, `rules_try`

`crates/regolith-api/src/rules.rs`: the `regolith rules test|try` API
surface (WO-28 deliverable 5, AD-4), each a pure-Rust function
returning a deterministic JSON report string (stdout is data; the
golden suite freezes the JSON). `rules_test` runs every rule's
`expect:` fixtures across the given packs (a rule missing a pass or
fail case is a lint warning, not a hard error); a failing fixture is
DATA in the `ok: false` report, never an `Err` (AD-7). `rules_try` runs
ONE pack against one design with attachment forced (no build, no
`process=` edit needed) and reports every match's verdict, detail, and
near-miss margin (within `NEAR_MISS_MARGIN` of its bound) per
`docs/implementation/design/21-rule-packs.md` D-H.

## Public-surface doc extraction

<a id="public-surface-doc-extraction"></a>
### `doc_extract`

`crates/regolith-api/src/docextract.rs` (`regolith doc`, WO-41): walks
the typed CST over top-level declarations and collects kind/name,
leading `#` comment block (D115: attaches only when no blank line
separates it from the declaration), structured fields, `require` claim
groups, and `budget` statements, rendered as one JSON string
(`{"decls": [...]}`) so the Python `regolith doc` renderer never
re-implements the grammar.

## Session: opening and running a build

<a id="session-opening-and-running-a-build"></a>
### `Session`, `Session::open_root`, `Session::open_files`, `Session::check`, `Session::check_with_lints`, `Session::compile`, `Session::compile_with_lints`, `Session::roots`

`crates/regolith-api/src/session.rs`: a compile session over a project
root or an explicit file set (`docs/spec/regolith/06-execution-model.md`,
AD-4). Opening a session does no work; `check` runs the static
parse -> sem -> ir -> obligation-construction pipeline with no
discharge, while `compile` additionally runs static discharge against
a persisted evidence cache under `.regolith/` (so a second compile
over unchanged sources is a cache hit, WO-13). The `_with_lints`
variants apply `magnetite.toml [lints]` (WO-40 deliverable 4); the
plain variants delegate to them with an empty `LintConfig`.
`realized_inputs` (WO-42 deliverable 3, AD-25/D128) is the
caller-resolved realized-domain IR channel threaded through both
verbs -- `Session` does no store lookups itself. Both verbs return
`Err` only for infrastructure failures (unreadable file, corrupt
cache), never for a failing check/compile (AD-7). `roots` exposes the
source roots a session covers.

## Build output and payload

<a id="build-output-and-payload"></a>
### `BuildOutput`, `BuildOutput::new`, `BuildOutput::rendered`, `BuildOutput::payload_json`, `BuildOutput::ok`, `BuildOutput::diagnostic_count`, `BuildPayload`

The result of a build, handed across the FFI as one object:
pre-rendered diagnostics (plain and ANSI, the ONE renderer, AD-7), the
structured `BuildPayload` (mirrors the generated pydantic models,
AD-5), and scalar verdicts. `rendered` selects the ANSI or plain text;
`payload_json` serializes the payload to bytes the Python side parses
into pydantic; `ok` is true when there are no error-severity
diagnostics; `diagnostic_count` is the diagnostic tally. `BuildPayload`
carries every typed pipeline output field (obligations, snapshots,
evidence, waiver ledger, feature programs, flownets, harnesses,
frames, contract graph, choice points, tests, converter graphs) --
each field's own doc comment in `session.rs` names the work order that
grew it; this entry is the index, not a restatement of each field.

## Core error

<a id="core-error"></a>
### `CoreError`, `CoreError::path`

An infrastructure error at the API boundary (NOT a failing build):
`Io` (a source file or root could not be read) or `CacheCorrupt` (the
evidence cache was unreadable or malformed). Crosses the FFI as a
`regolith.CoreError` exception (AD-4). `path` returns the offending
path when the variant carries one.
