# regolith-diag

Diagnostic model and the single diagnostic renderer (AD-7). Regolith
reference: `docs/spec/regolith/09-build-and-lockfile.md` sec. 4
(batch-emitted, cross-referenced diagnostics) and `docs/spec/regolith/
05-ownership-and-queries.md` sec. 6 (matched entities + concrete
fixes). There is exactly one renderer in the whole toolchain and it
lives here (annotate-snippets); the Python side prints returned strings
verbatim, never re-renders. User-facing failures are diagnostics
(data), not `Err` (AD-7): checks return `Result<T, Vec<Diagnostic>>`;
collection and batching are the sink's job, never per-check effort.

## code

The diagnostic code registry: stable regolith-wide code families
(`docs/spec/regolith/09-build-and-lockfile.md` sec. 4). Codes are DATA,
defined once here, never inline literals anywhere else. Families are
shared across both languages; only the human message is domain-
specific. A `Family` is the hundreds digit of the numeric code (e.g.
`E03xx` -> `Family::References`); `codes::ALL` is the closed registry
`explain.rs`'s completeness check walks.

## diagnostic

The `Diagnostic` model: a constructive, cross-referenced error or
warning stated in the user's vocabulary (`docs/spec/regolith/
09-build-and-lockfile.md` sec. 4 and `05-ownership-and-queries.md` sec.
6). Shows the query, the matched entities with origin and measures,
and 2-3 concrete fixes, with cross-references to related diagnostics.
Carries a `DiagCode`, primary/secondary `LabeledSpan`s, and a
`Severity` that `lints.rs` can promote at emission time.

## explain

Explain content beside the code (D247.3): `regolith explain <code>`
reads this one home. Every code in `code::codes::ALL` must have a
matching entry here -- the completeness rule D247.4 machine-checks
(`completeness_is_total`) so a code with no entry at all is a build
error, never a silent gap. An entry may legitimately be an honest stub
(`authored: false`, the WO-131 deliverable 4 allowance) -- the health
check counts stubs and reports the count, it never hides it. Each
entry states what a code means, why it fires, how to fix it, and (when
authored) a worked example.

## lib

Crate root: re-exports the diagnostic model and the one renderer
(`docs/spec/regolith/09-build-and-lockfile.md` sec. 4,
`05-ownership-and-queries.md` sec. 6). Declares the module map (`code`,
`diagnostic`, `explain`, `lints`, `render`, `sink`, `span`) and the
crate-level `Severity` type every diagnostic carries. User-facing
failures are diagnostics (data), not `Err` (AD-7).

## lints

`[lints]` configuration (WO-40): `magnetite.toml`'s `code ->
allow|warn|deny` table, and the one place `deny` promotes a
`Diagnostic`'s `Severity` to `Error` at emission time (charter sec. 5,
D112: lints are configuration, not an engineering deviation -- the
`waive` ladder never touches this table). Reference:
`docs/spec/toolchain/24-developer-tooling.md` sec. 5. Keyed by
`code::Family` and individual code, so a whole family can be silenced
or promoted at once.

## render

The one diagnostic renderer (AD-7): rustc-style constructive output
via `annotate-snippets` (`docs/spec/regolith/09-build-and-lockfile.md`
sec. 4). No second renderer exists anywhere; the Python side prints
these strings verbatim. Rendering shows the message, the primary and
secondary spans as source snippets, the matched-entity table, the 2-3
fixes, and the related cross-references -- the "edit blast radius at
once" -- using `anstyle` for terminal color and `camino::Utf8PathBuf`
for Windows-safe paths.

## sink

`DiagnosticSink`: batch collection with dedup and deterministic
ordering. Never-first-error-stops is a property of the sink, not of
per-check discipline (WO-06 goal). Ordering is deterministic (AD-6): by
primary span (file, then offset), ties broken by code number, so the
same source always renders the same blast radius regardless of which
check happened to run first.

## span

Source spans: a byte range in a named source file, optionally
labelled, used to anchor diagnostics to source (AD-7 renderer).
`Span` is a half-open byte range `[start, end)` within a source file;
`LabeledSpan` pairs a span with the label text the renderer shows next
to it. Paths are `Utf8PathBuf` (AD-12 -- Windows-safe, UTF-8-checked).
Byte offsets are the fidelity currency; the renderer turns them into
line/column snippets.
