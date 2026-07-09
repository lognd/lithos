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
> run in `regolith-syntax::checks`. `../../spec/toolchain/grammar.ebnf` is authored at
> `docs/spec/toolchain/grammar.ebnf`.
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
>    (a comment-led machining body in `sheet_bracket.hema` that the
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
> USE-SITE GENERICS TYPED (this cycle, unblocks INV-11): call/value-site
> generic instantiations (`Foo<Bar>`, nested `PatternOf<TappedHole<M3>>`,
> `Decoder<3, 8>()`) now parse to typed `InstExpr`/`GenericArgs` nodes
> (mirroring decl-header `GenericParams`) instead of degrading to a
> comparison BinExpr + opaque tail. Disambiguation from the comparison
> operators `<`/`>`: the opener must be GLUED to the head name (no
> whitespace) AND the angle group must scan as balanced and
> type-argument-like (identifiers, numbers, commas, dots, colons, nested
> `<...>`), closing on the same logical line with an acceptable follower
> after `>` (`(`, `,`, `>`, `)`, `]`, line end). So whitespace-separated
> claim comparisons (`mass < 5kg`, `a < b and c > d`) stay `BinExpr`; a
> genuinely ambiguous `<...>` that fails the scan is left as a comparison
> chain, never mis-parsed. `../../spec/toolchain/grammar.ebnf` updated in lockstep; test
> `parser::tests::use_site_generic_instantiation_is_typed`. This is what
> `regolith-lower` monomorphization (INV-11) consumes.
>
> Cross-crate gap CLOSED (cycle 11, FE-7): `regolith-qty`'s seed unit
> table (WO-02) now defines `V`/`W`/`Hz` (plus `J`/`Pa`/`H`/`T`/`S`/`F`),
> so a literal `1V + 1A` surfaces as `INCOMPATIBLE_QUANTITIES` (E0101)
> specifically, the more precise diagnostic, rather than an unknown-unit
> condition.
> OWNERSHIP/REGION/SYMMETRY STATEMENTS TYPED (cycle 13, unblocks
> INV-04/05/23): the residual ownership/region/symmetry constructs are
> now typed single-line CST nodes -- `bind`/`modify` (`OwnershipStmt`),
> `region`/`keepout`/`route` (`RegionStmt`), and `pattern`/`break`/`any`/
> `symmetric`/`mirror`/`flip` (`SymmetryStmt`). Like the block words they
> are recognized CONTEXTUALLY at statement-start only and only with an
> argument follower (an `ident` for all verbs, plus `(` for the call-like
> mirror verbs), so a coincidental `region:` field, `route = x` ctor, or
> `boundary.orbit` path segment is never mis-promoted and path parsing is
> intact. The lowering pass (`regolith-lower/src/ownership.rs`) reads the
> leading verb + argument idents back off each node to populate
> `PredictedDelta.modifies`/`.regions_touched`, `EntityKind::Region`
> entities, and the `OrbitTable` -- the parsed input the previously
> caller-less `regolith-sem` `BorrowTable`/`OrbitTable` needed. The corpus
> `symmetric(...)`/`flip about X` lines are now typed (no longer opaque);
> only the gear_reducer CST insta golden changed and no obligation/
> resolution/diagnostic count moved on the corpus. `../../spec/toolchain/grammar.ebnf` updated
> in lockstep. Tests: `parser` unit coverage + `ownership::tests` +
> `tests/invariants/test_inv_{04,05,23}`.
>
> HINT ANNOTATION TYPED (cycle 15, unblocks INV-03): `@hint(...)`
> (regolith/12 rung 3) is now a typed single-line `HintStmt`. The `@`
> sigil is a new lexer token (`RawToken::At` -> `SyntaxKind::AtTok`),
> dispatched at statement-start and swallowed whole. It is verdict-inert
> BY CONSTRUCTION: no `regolith-lower` pass reads it, so it contributes no
> entity/obligation/snapshot/resolution and an obligation's content hash is
> byte-invariant under its presence -- the structural proof of hint
> droppability. `policy: prefer` (rung 3's soft half) was already the
> typed `PolicyBlock`/`PolicyRule`. The corpus declares no `@hint`, so no
> golden moved. `../../spec/toolchain/grammar.ebnf` gained `hint-stmt`. Tests:
> `parser::hint_annotation_is_a_typed_inert_node` +
> `tests/invariants/test_inv_03`.
Language: Rust (`regolith-syntax`) -- see `../../spec/toolchain/00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: regolith/08 (L0/L1); hematite/02, hematite/04 (canonical forms);
cuprite/07; examples/ (the concrete target corpus)

## Goal

Parse the shared surface into a typed AST with quantity/unit checking
and value-source parsing. This WO also AUTHORS the grammar EBNF (a
Phase A deliverable): write `docs/spec/toolchain/grammar.ebnf` as part
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
  `[i .. j]` per regolith/02 sec. 3.
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
  (regolith 12; regolith 08 sec. 4).

Parser technology: DECIDED, `../../spec/toolchain/00-architecture.md` AD-3 (supersedes the
old lark note): `logos` lexer + layout pass (INDENT/DEDENT) + rowan
lossless CST + hand-written event-based recursive-descent parser with
Pratt expressions and layout-anchored error recovery; typed AST as
generated views over the CST; cargo-fuzz targets are part of done.
../../spec/toolchain/grammar.ebnf remains the documentation/conformance deliverable. The
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
