# Front-end spec-conformance audit: regolith-qty + regolith-syntax

## Summary

Line-by-line conformance pass over `regolith-qty` (quantities, units,
dimensions, intervals, ranges, corners, value sources, resolutions,
monomorphization, counts, windows) and `regolith-syntax` (lexer, layout
pass, parser, L1 checks, formatter, extension registry, syntax-kind
table). The core numeric substrate is in good shape: dimension algebra
with rational exponents (AD-9) is correct, the interval outward-rounding
property for same-unit `add`/`sub`/`mul` is real and proptest-covered
(AD-6 / INV-9), the `==` ban is enforced structurally (`Qty` has no
`PartialEq`), the interval-vs-range type split is distinct and
non-interconvertible (INV-17), the extension registry is single-sourced
(ground rule 6), and the corner machinery keeps worseness a model
decision (INV-9). The largest gap is that the logarithmic-unit views of
substrate/02 sec. 5a -- which INV-17 names as an L1 requirement -- are
entirely absent while the crate docstring and AD-1 both claim the crate
contains "log views". Several smaller divergences and stale comments
follow.

### Coverage note

Spec sections actually read in full and checked against code:
substrate/02-quantity-core.md (sec. 1-7, incl. 5a log views);
substrate/08-lowering-architecture.md (L0/L1 placement, sec. 1-5);
substrate/13-invariants.md (INV-9, INV-16, INV-17, INV-21 in full, plus
INV-1/10/20/27 context); implementation/00-architecture.md AD-1, AD-3,
AD-6, AD-9, AD-12; WO-02 and WO-05 in full for recorded cuts.

Doc-path corrections from the task's suggested list:
- The value-source / resolution modules cite
  `docs/substrate/03-value-sources.md`, not `02`. I did not have `03`
  enumerated in the task, so value-source-cause-taxonomy findings are
  anchored on AD-6 rule 5 and INV-21 (both normative and explicit about
  the cause list) rather than on `03`; a follow-up should confirm `03`
  agrees (it is referenced by `value_source.rs:5`, `resolution.rs:4`,
  `monomorphize.rs:4`, `window.rs:4`).
- L0/L1 lexing rules: substrate/08 sec. 1-2 governs placement; the
  concrete ASCII/tabs rule lives in AD-3 and AD-12, cited accordingly.
- elec vocabulary: not separately needed; the vocabulary-relevant
  normative statements audited were all in substrate/02 + INV-17.

BUGS (undocumented divergences) are FE-1..FE-8; KNOWN CUTS (recorded in
a WO) are FE-9..FE-10.

---

## HIGH

### FE-1 (HIGH, BUG) -- Logarithmic-unit views and the L1 log-sum legality check are entirely unimplemented

- Spec: substrate/02-quantity-core.md sec. "5a. Logarithmic unit views"
  (SETTLED, closes SOPEN-5): "Sum legality = linear product legality: a
  sum of log terms is legal iff, after cancelling subtracted references
  against added ones, at most one referenced term remains ... `dBm +
  dBm` is a compile error." INV-17 (substrate/13) restates this as an
  L1 MUST: "the logarithmic-view reference algebra (a sum of log terms
  is legal iff at most one referenced term remains after cancellation;
  `dBm + dBm` dies at L1, substrate 02 sec. 5a)" with test family "one
  fixture per violation class, including the two-reference log sum; all
  must die at L1 with E01xx." AD-1 lists `regolith-qty` contents as
  "dimensions, units, intervals, **log views**, value-source types";
  AD-9 says "Log views per substrate 02 sec. 5a: stored linear, one L1
  reference-legality check."
- Code: `crates/regolith-qty/src/unit.rs:86` (UNIT_TABLE) contains no
  `dB`, `dBm`, `dBc`, `dBi`, `dBW`, `dBuV` entries and `Unit` carries no
  reference field; `crates/regolith-qty/src/lib.rs:1-2` docstring claims
  "log views" are part of the crate but no module implements them;
  `crates/regolith-syntax/src/checks.rs` implements E0101/E0102/E0103
  only -- no log-sum legality check exists anywhere.
- What the spec requires: a referenced/unreferenced log-unit notion, and
  an L1 check that rejects a log-term sum leaving more than one
  uncancelled reference (`dBm + dBm`), emitting an E01xx diagnostic.
- What the code does: `dBm` and friends are simply unknown unit symbols
  (`UnitError::UnknownSymbol`); a source expression `p1 + p2` in dBm is
  never dimension-checked as a log sum. The classic link-budget bug the
  spec says is "dead at L1" is not caught.
- This divergence is undocumented: WO-02's scope is "sec. 1-2" and
  WO-05's residual-opaque list (WO-05 lines 21-33) does not mention log
  units, so no WO records this as a cut, yet INV-17 (top of the
  normative order) lists it as a live L1 guarantee.
- Fix direction: this is a bounded feature, not "webhook infrastructure
  that doesn't exist." Smallest correct fix: (a) add a `reference:
  Option<Box<Unit>>` and a `log_kind` marker to `Unit` (or a dedicated
  `LogUnit` type) and seed `dB/dBc/dBi` (unreferenced) plus
  `dBm=ref(mW)`, `dBW=ref(W)`, `dBuV=ref(uV)`; (b) add an L1 check in
  `regolith-syntax::checks` that, for a `BinExpr` chain of `+`/`-` over
  log-unit operands, cancels subtracted vs added references and emits a
  new E01xx code when more than one referenced term survives. If even
  that is out of the current WO envelope, at minimum file an explicit
  cut in WO-02 and WO-05 and mark INV-17's log-sum test family
  `pending`, so the gap stops being silent.

---

## MEDIUM

### FE-2 (MEDIUM, BUG) -- `Cause` taxonomy is missing three of the spec's enumerated causes (extern, derived-intent, policy)

- Spec: 00-architecture.md AD-6 rule 5: "Resolutions are constructed
  only through a `Cause`-requiring API (INV-21 as a type: causeless
  resolved values are unrepresentable -- WO-04's contract, now in
  Rust)." INV-21 (substrate/13) enumerates the cause list explicitly:
  "the resolver API cannot construct a resolved value without a `Cause`
  (dfm/drc, obligation, budget, topology, planner, **extern**,
  **derived-intent**, **policy annotation**)."
- Code: `crates/regolith-qty/src/resolution.rs:19-32` -- `Cause` has
  exactly `Dfm`, `Drc`, `Obligation`, `Budget`, `Topology`, `Planner`.
  Missing: `Extern`, `DerivedIntent` (derived-intent), `Policy` (policy
  annotation).
- What the spec requires: eight cause kinds so every non-literal value
  source can name its resolving mechanism.
- What the code does: only six. A `derived` value source
  (`value_source.rs:91` `ValueSource::Derived`) has no matching cause
  variant, an `extern`-pinned resolution cannot be represented, and a
  `policy`-annotation-driven pin cannot be represented -- so INV-21's
  guarantee ("every number the designer did not write literally appears
  in the lockfile with its resolving cause") is unsatisfiable for those
  slots, forcing a future author to mislabel them under an existing
  variant.
- Failure scenario: a `derived(sf=1.5)` value reaches the resolver;
  there is no `Cause::DerivedIntent`, so lowering must either drop the
  provenance or file it under, e.g., `Obligation`, producing a lockfile
  row whose cause lies about why the number exists -- exactly the
  provenance corruption INV-21 forbids.
- Fix direction: add `Extern(String)`, `DerivedIntent(String)`,
  `Policy(String)` variants to `Cause`, extend `kind_and_ref` with
  `"extern"`/`"derived_intent"`/`"policy"`, and add round-trip tests.
  Cross-check spelling against substrate/03 sec. 2 when confirming.

### FE-3 (MEDIUM, BUG) -- Non-ASCII source is not rejected; the lexer does not ASCII-enforce

- Spec: AD-12 (00-architecture.md): "source files are UTF-8-checked,
  ASCII-enforced by the lexer per spec." AD-3 point 2: "Tabs are an
  E01xx error (ASCII-only source is already spec ...)." CLAUDE.md
  tripwire: "ASCII only in every file."
- Code: `crates/regolith-syntax/src/token.rs:106-124` -- any byte the
  DFA cannot classify becomes `RawToken::Error`; `lex` never emits a
  diagnostic. `layout.rs:88-99` emits a diagnostic only for `Tab`, not
  for general `Error` tokens. `parser.rs:451-459` / `747-777` sweep
  stray `Error`-kind tokens losslessly into an `OpaqueIsland` with no
  diagnostic; `parse_error_recovery` (`parser.rs:793`) fires only when
  an unclassifiable token appears at statement-start position (top
  level), not inside a value/body.
- What the spec requires: a non-ASCII character in source is an E01xx
  error.
- What the code does: a non-ASCII character in a value/body position
  lexes to an `Error` token, is swept into an `OpaqueIsland`, and
  produces zero diagnostics -- the file "parses clean." Only a leading
  non-ASCII byte at top level is reported (as UNEXPECTED_TOKEN, E0192,
  not a dedicated ASCII code).
- Failure scenario: `part p:` + newline + `    dia: 5` + a micro-sign
  byte + `m` compiles with no error; the non-ASCII byte is silently
  absorbed into an opaque island. ASCII-only, a stated spec guarantee,
  is not enforced.
- Fix direction: in `layout.rs`/`token.rs`, emit a dedicated `E01xx`
  non-ASCII diagnostic for every source byte >= 0x80 (or every
  `RawToken::Error` whose text is non-ASCII), analogous to the existing
  `TAB_INDENTATION` path, so the check is batch-emitted like the others.

### FE-4 (MEDIUM, BUG) -- Unit exponent suffixes (`m2`, `s2`) are unparseable, so spec units like `W/m2` cannot be expressed; the `parse_expr` docstring cites an example that does not work

- Spec: substrate/02-quantity-core.md sec. 1 quantity table includes
  `heat_flux: W/m2` and `2A/us`-style rates; WO-02 deliverables name
  `N/m`, `bit/s` unit expressions.
- Code: `crates/regolith-qty/src/unit.rs:202-222` (`parse_expr`) splits
  on a single `/` or `.` and calls `parse_atom` on each side;
  `parse_atom` (`unit.rs:167`) has no notion of a trailing integer
  exponent. The docstring at `unit.rs:203` gives `kg.m/s2` as a
  supported example, but `parse_atom("s2")` fails: `s2` is not a table
  entry, and prefix-stripping yields (`s`,`2`) which is not a valid
  prefix, so it returns `UnitError::UnknownSymbol("s2")`.
- What the code does: `Unit::parse_expr("W/m2")` and
  `Unit::parse_expr("kg.m/s2")` both error with `UnknownSymbol`. The
  heat-flux quantity's canonical unit from the spec table is
  inexpressible, and the module's own doc example is wrong.
- Failure scenario: a `.hem`/`.cupr` file (or a `QuantityDecl`) using
  `W/m2` surfaces an unknown-unit E01xx rather than resolving to a
  power-per-area dimension; conversely the docstring misleads a
  maintainer into believing `s2` works.
- Fix direction: either (a) support an integer exponent suffix on an
  atom in `parse_atom` (`m2` -> `m` with dimension `pow(2)`, using the
  existing `Dimension::pow`), which is the smallest correct fix and
  matches AD-9's rational-exponent machinery; or (b) if exponent syntax
  is deliberately deferred to WO-05's full unit grammar, remove the
  false `kg.m/s2` example from the docstring and record `W/m2` as an
  explicit WO-02 cut.

### FE-5 (MEDIUM, BUG) -- Offset units used as a tolerance/delta magnitude are converted as absolute temperatures, giving wrong interval bounds

- Spec: WO-02 acceptance: "offset units (`degC`/`K` deltas)"; the
  intended semantics is that a temperature *difference* in degC equals
  the same number in K (no 273.15 offset applied to a delta).
- Code: `crates/regolith-qty/src/interval.rs:60-73` (`plus_minus`)
  computes `tol_mag = convert(tol.magnitude(), tol.unit(),
  center.unit())`. `convert` (`quantity.rs:154-161`) always applies the
  additive offset: `si = magnitude * from_scale + from_offset`. For an
  offset `tol` unit this treats the tolerance as an absolute
  temperature, not a delta.
- What the code does: `Interval::plus_minus(center=300 K, tol=5 degC)`
  computes `tol_mag = (5*1 + 273.15 - 0)/1 = 278.15`, yielding the
  absurd interval `[300 - 278.15, 300 + 278.15] K` instead of
  `[295, 305] K`. (The multiplicative `Unit::mul`/`div` guard against
  offset units via `OffsetInAlgebra`, but `plus_minus`/`sub` call
  `convert` directly and bypass that guard.)
- Failure scenario: any tolerance or interval arithmetic whose magnitude
  is spelled in `degC` (or any future nonzero-offset unit) silently
  produces bounds off by the offset -- a wrong-result numeric bug that
  no diagnostic surfaces.
- Fix direction: model temperature *deltas* distinctly from absolute
  temperatures (a delta carries scale but zero offset), or have interval
  arithmetic reject offset-unit magnitudes in delta positions with a
  diagnostic, mirroring `UnitError::OffsetInAlgebra`. Add a test:
  `plus_minus(300 K, 5 degC)` must be `[295,305] K` or a typed error.

### FE-6 (MEDIUM, BUG) -- `Interval::new` and `contains` do not outward-round unit-converted bounds, weakening the AD-6/INV-9 soundness guarantee across units

- Spec: AD-6 point 2 / INV-9: "interval ops outward-round via
  `f64::next_up`/`next_down` on our own `Interval` type"; the interval
  module docstring (`interval.rs:1-9`) promises "Interval arithmetic
  rounds OUTWARD (AD-6) so a computed bound never excludes a physically
  reachable value."
- Code: `crates/regolith-qty/src/interval.rs:35-53` (`Interval::new`)
  stores `hi_in_lo_unit = convert(hi.magnitude(), hi.unit(),
  lo.unit())` with no `next_up`/`next_down`; `add`/`sub`
  (`interval.rs:132-158`) outward-round the final sum but apply
  `convert` to the other operand's bounds first with no outward rounding
  on the conversion itself; `contains` (`interval.rs:186`) converts the
  probe inward-nearest.
- What the code does: when bounds are constructed or combined across
  units (e.g. an interval built from a `lo` in `mm` and a `hi` in `m`,
  or `x.add(y)` where `y` is in different units), the `convert`
  round-to-nearest step can move a bound inward by up to half a ULP,
  which the subsequent single `next_up`/`next_down` on the *sum* does
  not necessarily cover (the conversion error is independent of the
  addition rounding). The proptests (`interval.rs:238-291`) only
  exercise same-unit `metres`, so this is untested.
- Failure scenario: a true corner value lying within half a ULP of a
  cross-unit-converted bound can be excluded from the computed interval
  -- exactly the INV-9 "computed bound never excludes a reachable value"
  property, violated in the cross-unit case.
- Fix direction: make `convert` (or an outward-rounding wrapper used by
  interval construction) round the lower bound toward -inf and the
  upper bound toward +inf, and have `Interval::new` apply
  `next_down`/`next_up` to the converted bound. Extend the corner
  proptests to mix units (e.g. `mm` and `m`).

### FE-7 (MEDIUM, BUG/stale-doc) -- `checks.rs` and the WO-05 header claim `V`/`W`/`Hz` are absent from the seed unit table, but the table now contains them

- Spec context: WO-05 lines 33-39 record a "Known cross-crate gap":
  "`regolith-qty`'s seed unit table (WO-02) has no `V`/`W`/`Hz` ... a
  literal `1V + 1A` therefore surfaces as an unknown-unit condition
  rather than `INCOMPATIBLE_QUANTITIES`."
- Code: `crates/regolith-qty/src/unit.rs:101-103` now defines `V`, `W`,
  `Hz` (plus `J`, `Pa`, `H`, `T`, `S`, `F`) with correct dimensions,
  and `unit.rs:374-388` tests that `1V + 1A` is a genuine dimension
  mismatch. But `crates/regolith-syntax/src/checks.rs:17-27` still
  states in its module docstring that the table "does not yet include
  `V` (volt), `W` (watt), or `Hz`" and that `1V + 1A` "resolves as an
  *unknown unit* rather than an *incompatible quantity*."
- What's wrong: the comment (and the WO-05 status text) now contradict
  the code -- the more specific `INCOMPATIBLE_QUANTITIES` code *can* now
  fire for `1V + 1A`. This is a desync between a load-bearing docstring
  and the implementation.
- Failure scenario: a maintainer reading `checks.rs` believes electrical
  units are still missing and either re-adds them (duplication, against
  the NO DUPLICATION rule) or leaves a real `1V + 1A` test mis-asserted
  against the wrong diagnostic code.
- Fix direction: delete the "Known gap" paragraph from
  `checks.rs:17-27`, and update WO-05's header note (lines 33-39) to
  mark the cross-crate gap closed. Confirm `checks.rs` actually emits
  `INCOMPATIBLE_QUANTITIES` for `1V + 1A` and add that as a test.

---

## LOW

### FE-8 (LOW, BUG) -- L1 `==` ban only fires when an operand is a unit-bearing literal; `a == b` between two continuous names escapes this pass

- Spec: INV-17: "no `==` on a continuous quantity ... survives L1."
  substrate/02 sec. 2: "`==` on continuous quantities is a compile
  error."
- Code: `crates/regolith-syntax/src/checks.rs:77-86` --
  `is_continuous_quantity` returns true only for a syntactic
  unit-bearing `QuantityLit` (after paren-stripping). `a == b` where
  both sides are bare names carries no unit token, so `check_bin_expr`
  (`checks.rs:139`) does not flag it.
- What the code does: `x: y == z` with `y`, `z` declared continuous
  quantities parses without an E0102 diagnostic at this pass.
- Why LOW: this check is deliberately syntactic (no name resolution
  available in `regolith-syntax`); the name-resolved case legitimately
  belongs to `regolith-sem`'s L1 completion. It is a finding only
  because INV-17 phrases the guarantee as absolute -- the fixer should
  verify `regolith-sem` does complete the ==-ban after resolution, and
  if it does not, that is where the HIGH fix belongs (outside this
  audit's two crates).
- Fix direction: confirm coverage in `regolith-sem`; if absent, add the
  resolved-operand ==-ban there. No change needed in `checks.rs` beyond
  a comment cross-referencing the sem-side completion.

### FE-9 (LOW, KNOWN CUT) -- the "canonical formatter" performs no canonicalization

- Spec: WO-05 acceptance: "A format-normalizer stub: parse -> print ->
  parse is a fixed point on the examples." AD-3 point 3 and formatter
  docstring reference mech/04 canonical forms.
- Code: `crates/regolith-syntax/src/formatter.rs:20-24` -- `format`
  returns `parse.syntax().text().to_string()`, i.e. the lossless
  reprint (identity on accepted input). The docstring (`formatter.rs:1`)
  calls it "The canonical formatter ... One normalizer" and cites
  mech/04, but it does no re-spacing, quote normalization, or any
  canonicalization.
- This is a RECORDED CUT: `formatter.rs:16-19` states "This bootstrap
  pass does not yet implement true canonicalization ... see the report
  note," and WO-05 acceptance asks only for the fixed-point stub, which
  is met. Flagged LOW so the fixer does not mistake the stub for a
  finished normalizer: the idempotence proptests
  (`formatter.rs:104-110`) are trivially satisfied by an identity
  function and prove nothing about canonicalization.
- Fix direction: none required for WO-05; when true formatting lands,
  replace the identity body and strengthen the idempotence tests to
  assert an actually-normalized output (e.g. `"x:1mm"` ->
  `"x: 1mm"`).

### FE-10 (LOW, KNOWN CUT) -- `within [lo, hi]` demanded windows are not parsed though the keyword, node kind, and `Window` value type all exist

- Spec: substrate/02 sec. 5 / value sources: `within [lo, hi]` is a
  two-sided demanded window (`value_source.rs:37` `Literal::Window`,
  `window.rs` `Window`); `SyntaxKind::WithinKw` and
  `SyntaxKind::WindowExpr` are both defined
  (`syntax_kind.rs:88`, `syntax_kind.rs:238`).
- Code: the parser (`crates/regolith-syntax/src/parser.rs`) never
  produces a `WindowExpr` and `parse_value` (`parser.rs:496`) has no
  `WithinKw` arm; a `within [ ... ]` in a value position degrades to an
  `OpaqueIsland`. `WindowExpr` and `CountExpr` are declared node kinds
  that are never constructed.
- This is consistent with WO-05's residual-opaque scope (WO-05 lines
  21-33: domain-specific bodies remain opaque), so it is a KNOWN CUT,
  not an undocumented divergence. Flagged LOW so the fixer knows the
  `WindowExpr`/`CountExpr` kinds are intentionally unwired, not dead
  code to delete.
- Fix direction: none for WO-05; wire `within`/`n x thing` when the
  value grammar is completed, and add typed-AST views for
  `WindowExpr`/`CountExpr` then.

---

## Notes (checked-correct, and boundaries)

Checked and found CORRECT (fixer need not re-verify):
- Dimension algebra with rational exponents (`dimension.rs`): `mul`/
  `div`/`pow` add/subtract/scale exponents correctly; `Ratio<i32>`
  round-trips through serde; `Eq` on `Dimension` is intentional and
  correct (the ban is on continuous quantities, not dimensions).
- The `==` ban as a structural property: `Qty` (`quantity.rs`),
  `Interval` (`interval.rs`), `Window` (`window.rs`) all deliberately
  omit `PartialEq`; `Count` (`count.rs`) correctly opts back in
  (discrete) -- matches substrate/02 sec. 2.
- Interval outward-rounding for SAME-unit `add`/`sub`/
  `mul_scalar_interval`/`plus_minus`/`scaled`: proptests
  (`interval.rs:238-315`) genuinely assert every true corner is
  contained; the AD-6 property holds in the same-unit case (cross-unit
  is FE-6).
- Interval-vs-range type distinction (INV-17): `Interval` and `Range`
  are separate types with no conversion; the parser distinguishes `[a,
  b]` (IntervalExpr) from `[i .. j]` (RangeExpr) on the separator token
  (`parser.rs:643-680`) and `checks.rs` flags mixed separators
  (E0103) and unit-bearing/fractional range endpoints.
- Extension registry single-sourcing (ground rule 6): `.hem`/`.cupr`
  live only in `extension.rs`; tests, formatter, and parser corpus
  walks all read `EXTENSIONS` rather than hard-coding strings; legacy
  `mill`/`loom` are negative-tested.
- Corner machinery (INV-9): `corner.rs` enumerates `2^n` corners in
  deterministic (IndexMap insertion) order and takes worseness direction
  from the model, never assuming one.
- Layout pass: tabs in indentation emit a diagnostic (`layout.rs`);
  blank/comment lines do not shift the indent stack; EOF closes open
  indents; INDENT/DEDENT are zero-width. Matches AD-3.
- Namespace/tensor-rank seeding (`decl.rs`): six namespaces
  (mech/elec/thermo/geom/info/mfg) match the AD-14/WO-02 seed set;
  `TensorRank` covers scalar/vector/tensor(n)/complex per substrate/02
  sec. 1.
- `si_prefix_exponent` is ASCII-only (`u` = micro, no Greek), exact
  rationals, no drift (AD-9); prefix stripping is longest-first (`da`
  before `d`).
- Monomorphization (`monomorphize.rs`): integer/enum domains expand in
  source order with a stable per-point identity string (INV-1 key
  input); `external`/variant flag is data-only per WO-04.
- `Resolution` is constructible only with a `Cause` (INV-21 as a type)
  -- the type-level guarantee is correct; only the cause *enumeration*
  is incomplete (FE-2).

Deliberately skipped / only skimmed (audit boundary):
- `cst.rs`, `debug.rs`, `walk.rs`, `ast.rs` in `regolith-syntax`: read
  for structure only (rowan plumbing / typed-view generation); no
  normative spec statements bind them beyond AD-3 mechanics, which the
  parser tests already exercise. Not line-audited.
- Numeric ULP-tightness of the outward-rounding proptests was reasoned
  about, not re-derived formally; FE-6 is the one place the same-unit
  proof does not extend.
- No cross-crate check into `regolith-sem`/`regolith-diag` beyond
  confirming the `codes::` constants referenced by `checks.rs` exist;
  FE-8's sem-side completion of the ==-ban is explicitly left for the
  fixer to confirm in `regolith-sem` (out of the two audited crates).
- substrate/03-value-sources.md was not in the enumerated read set, so
  cause-taxonomy (FE-2) and value-source-variant conformance are
  anchored on AD-6/INV-21 (normative and explicit) rather than on `03`;
  a `03` cross-check is the one residual verification for FE-2.
