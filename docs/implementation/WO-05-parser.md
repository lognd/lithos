# WO-05: Lexer, parser, typed AST (L0 -> L1)

Status: done (statement grammar landed cycle 11; residual opaque list below)
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
> Residual opaque scope (recorded, not silently dropped -- see the
> WO-05 report for the full accounting): domain-specific statement
> bodies the spec defers to later WOs remain `OpaqueIsland` at
> statement granularity -- `stage`/`setup` machining plans, `walk:`
> bodies (WO-11), `zones`, `impl ... for ...` role bindings, `connect`,
> `boundary`, `parts` orbit constructors (`4 x Rail`), decl-header
> generic-parameter lists (`<screw: thread, n: int>`), and any nested
> indented block under a `Field`/`CtorStmt` (e.g. `constraints:`'s
> sub-lines are recorded as one opaque body, not further decomposed).
> Across the full `examples/` corpus this is 435 `OpaqueIsland` nodes
> vs 311 `Field` + 52 `CtorStmt` + 45 `RequireClaim` nodes -- the
> statement grammar structures a large minority of statements; the
> majority-opaque count reflects how domain-heavy (`.hem`/`.cupr`)
> the corpus genuinely is, matching the scope this WO's Scope section
> named as deferred.
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
