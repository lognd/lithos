# WO-05: Lexer, parser, typed AST (L0 -> L1)

Status: done (statement grammar cycle 11; residual opaque constructs
promoted to typed CST nodes -- corpus parse diagnostics 18 -> 0)
Depends: WO-01..04, WO-06

> STATUS (cycle 11): the full statement grammar is implemented --
> `Field`/`CtorStmt` (`name: value` / `name = value`, dotted paths),
> `then`/`require`/`budget`/`waive`/`policy`/`locked` blocks, a Pratt
> expression grammar (comparisons, `+ - * /`, unary `-`, quantity
> literals, `[a, b]` intervals, `[i .. j]` ranges, `+- N%` tolerance,
> `default`/`derived`/`free`/`allocated` cause values, `in [...]`
> value sources, `during <expr>`, calls). L1 checks (E0101 incompatible
> quantities, E0102 `==` on continuous, E0103 interval/range confusion)
> run in `rockhead-syntax::checks`. `grammar.ebnf` is authored at
> `docs/implementation/grammar.ebnf`.
>
> RESIDUAL PROMOTION (this cycle): the residual opaque constructs are
> now TYPED CST nodes, and the whole `examples/` corpus parses with
> ZERO parse diagnostics (was 18). Two changes:
>
> 1. Bracket-aware layout (`layout.rs`): the off-side pass now does
>    Python-style implicit line joining inside `(`/`[` -- a multi-line
>    call / interval / import argument list is ONE logical line, so a
>    deeper continuation indent no longer emits spurious
>    INDENT/DEDENT that ejected the following siblings to the file
>    level (the true cause of all 18 residual diagnostics; they were
>    NOT domain-body payloads, contra the earlier TRIAGE note). This
>    alone took 18 -> 4.
> 2. Typed promotion (`parser.rs` + `syntax_kind.rs`): `stage`/`setup`
>    (`StageStmt`/`SetupStmt`), `impl ... for ... [as ...]`
>    (`ImplStmt`), `connect`/`parts`/`zones`/`boundary`/`flows`
>    (`*Block`), `policy` rule lines
>    (`prefer`/`forbid`/`minimize`/`maximize`/`use` -> `PolicyRule`),
>    decl-header generics `<...>` (`GenericParams`), and the WO-11
>    `walk` sub-grammar (`WalkBody`/`WalkStep` + nested `HoleBlock`,
>    `RegionsBlock`/`ConstraintsBlock`/`ExportsBlock`). The block
>    words are recognized CONTEXTUALLY at statement-start only (they
>    also appear as ordinary path segments in value position, so they
>    are NOT lexer keywords). Promoted blocks use the shared,
>    comment-led-body-aware `enter_body`, which fixed the remaining 4
>    (a comment-led machining body in `sheet_bracket.hem` that the
>    hand-rolled opaque-island indent check had ejected).
>
> Subject-attributed recovery (INV-20 unblock): a stray closing
> bracket at statement position now emits `E0193` MALFORMED_IN_BODY
> attributed to its enclosing declaration subject (a secondary span
> into the subject header + a `SubjectError` CST node), so downstream
> per-subject check gating can exclude exactly that subject.
>
> TRACKED CUTS (remaining opaque, honest residue, not silently
> dropped): value-expression tails the value grammar does not model
> (space-separated unit products like `1 N*m`, FE-4 territory);
> multi-line claim-expression continuations (a next line led by an
> operator -- swept as an opaque continuation); and Ident-led
> statements with no promoted shape (`override <record> by ...`,
> `plan: extern(...)`, `flip about X`, `parts` orbit `4 x Rail`
> count-expressions). `parts:` is a typed block but its per-line
> orbit constructors (`n x Thing`) are not further decomposed. See
> TODO.md section 2.
>
> Known cross-crate gap (escalated, not patched out-of-scope):
> `rockhead-qty`'s seed unit table (WO-02) has no `V`/`W`/`Hz` though
> substrate/02 sec. 1 lists `voltage: V`; a literal `1V + 1A` therefore
> surfaces as an unknown-unit condition rather than
> `INCOMPATIBLE_QUANTITIES` specifically (both are still E01xx). Fixing
> the table is WO-02/rockhead-qty's job, out of this WO's touch-scope
> (rockhead-syntax + rockhead-diag codes only); see the WO-05 report.
Language: Rust (`rockhead-syntax`) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/08 (L0/L1); mech/02, mech/04 (canonical forms);
elec/07; examples/ (the concrete target corpus)

## Goal

Parse the shared surface into a typed AST with quantity/unit checking
and value-source parsing. This WO also AUTHORS the grammar EBNF (a
Phase A deliverable): write `docs/implementation/grammar.ebnf` as part
of this work; where an example is ambiguous against the specs, STOP
and file a question in the design log rather than inventing.

## Scope

Indentation-based block syntax:
- file = `import` statements + top-level declarations (`part`,
  `profile`, `interface`, `mating`, `assembly`, `system`, `block`,
  `impl`, `component`, `protocol`, `computer`, `image`, `board`,
  `target`, `datum`, `event`).
- Common statement forms: `key: value` fields, `name = Ctor(args)`
  construction statements, `then [label] [on <region>]:` scopes,
  bare statements, `require <Group>:` claims, `budget`, queries as
  method chains, value sources in any numeric slot, `[a, b]` vs
  `[i .. j]` per substrate/02 sec. 3.
- Domain payloads (walk bodies, `on <event>:` bodies, continuous
  relations) parse to *opaque typed islands* in this WO -- structure
  recorded, semantics deferred (WO-11 does walks; behavioral semantics
  are settled as event-bounded hybrid, elec 03 sec. 1a, but full
  elaboration is out of this WO's scope).
- Cycle-3 additions in scope: `waive` blocks (target, `on` scope,
  `basis:`, evidence clause), `policy:` blocks (`prefer`/`forbid`/
  global `minimize`), free-standing `locked:` blocks,
  `extern(ref, format)` in impl-strategy / profile / `plan:` / image
  positions, `model=` on claims, `hosted_on`
  (substrate 12; substrate 08 sec. 4).

Parser technology: DECIDED, `00-architecture.md` AD-3 (supersedes the
old lark note): `logos` lexer + layout pass (INDENT/DEDENT) + rowan
lossless CST + hand-written event-based recursive-descent parser with
Pratt expressions and layout-anchored error recovery; typed AST as
generated views over the CST; cargo-fuzz targets are part of done.
grammar.ebnf remains the documentation/conformance deliverable. The
format-normalizer acceptance item below is the rowan-based formatter
(lossless CST makes parse -> print -> parse a fixed point by
construction for accepted input).

## Acceptance

- Every file under `examples/` parses to an AST (opaque islands
  allowed); goldens in `tests/golden/ast/`.
- Unit errors (`1V + 1A`), `==` on continuous quantities, and
  `[a, b]`/`[i .. j]` misuse are rejected with E01xx diagnostics
  (WO-06) carrying source spans.
- A format-normalizer stub: parse -> print -> parse is a fixed point
  on the examples.
