# regolith-lower

The pass-pipeline driver (AD-17, `docs/spec/toolchain/00-architecture.md`
sec. 17): parsed source -> entity DB snapshots -> semantic checks ->
contract IR -> content-addressed obligations -> (compile only) static
discharge. A PURE function of source text -- no IO, no rendering, and
it never returns `Err`; a failing build is diagnostics in the output
(AD-7). All IO (file discovery/read, evidence-cache load/store) stays
in `regolith-api::Session`; the ONE diagnostic renderer stays invoked
from `regolith-api`. Regolith reference:
`docs/spec/regolith/06-execution-model.md`,
`docs/spec/regolith/07-claims-and-evidence.md` sec. 2.

This doc currently covers the crate's top-level entry points
(`crates/regolith-lower/src/lib.rs`) only -- the per-pass submodules
(`entities`, `checks`, `claims`, `contracts`, `discharge`, ...) are
tracked as remaining `COV001` surface in `tickets.md` T-0002 and will
get their own sections as the sweep continues crate-by-crate.

## Pipeline entry points

<a id="join-physical-lines"></a>
### `join_physical_lines`

Rejoins a CST node's text into one line: each physical line has its
trailing `#` comment stripped, then all lines are joined with a single
space. Text-level scanners across this crate (net member tuples, rule
`demand:`/`advise:` values, stage `process=(...)` kwargs) read a
field/statement's spelled RHS off raw node text rather than a fully
structured value node (the grammar only partially structures
parenthesized argument lists, AD-3's lossless-degrade stance). Those
values can legally wrap across physical lines inside a balanced
`(`/`[`, so a naive `text.lines().next()` scanner silently drops every
continuation line with no diagnostic (this was F151, a false-pass
mechanism). ONE home for the join so every such scanner shares it
(NO DUPLICATION).

<a id="parse-sources"></a>
### `parse_sources`

Parses every `SourceFile` into a `ParsedFile`, preserving the caller's
order (`Session::discover_files` already sorts for determinism, AD-6;
this pass does not re-sort). The first stage both `lower` and
`lower_and_discharge` share.

<a id="lower"></a>
### `lower`

Runs passes 1-5 (`parse` through `lower.claims`): the `check()`
pipeline. Always materializes a full `LowerOutput`; never `Err`. Takes
the orchestrator-resolved `RealizedInputs` (WO-42 deliverable 3,
AD-25/D128) -- resolving a digest against the WO-30 store is the
caller's IO, done before this function is ever called (AD-17).

<a id="lower-with-lint-config"></a>
### `lower_with_lint_config`

Same as [`lower`](#lower), but promotes/silences `Lint`-family
diagnostics per a `regolith_diag::LintConfig` (WO-40 deliverable 4:
`magnetite.toml [lints]`, `deny` -> `Error`) at the very end of the
batch, in the ONE place (`regolith_diag::apply_lint_config`) severity
changes.

<a id="lower-and-discharge"></a>
### `lower_and_discharge`

Runs passes 1-6 (adds `lower.discharge`): the `compile()` pipeline.
Consults and updates an `EvidenceCache` for the statically
dischargeable toy subset (WO-13); a second call over the same sources
hits the cache. `registry_version` is the harness model-registry
version (Python-side, AD-1), folded into every evidence-cache key so a
model upgrade forces re-verification (BE-1/INV-1).

<a id="lower-and-discharge-with-lint-config"></a>
### `lower_and_discharge_with_lint_config`

Same as [`lower_and_discharge`](#lower-and-discharge), with the WO-40
`[lints]` promotion step (see
[`lower_with_lint_config`](#lower-with-lint-config)).
