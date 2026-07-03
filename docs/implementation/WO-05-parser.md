# WO-05: Lexer, parser, typed AST (L0 -> L1)

Status: todo
Depends: WO-01..04, WO-06
Language: Rust (`decl-syntax`) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
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
