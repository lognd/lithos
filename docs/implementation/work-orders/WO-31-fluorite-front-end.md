# WO-31: Fluorite front end (.fluo grammar, CST, the AD-23 net core)

Status: in-progress (deliverable 1 DONE pre-existing; deliverable 2
NOW DONE this pass: the `(<a> -> <b>)` edge sense pair and the `{...}`
state-domain set are typed `SensePair`/`DomainSet` nodes -- parse-time
structuring of the existing token stream, no lexer change, AST
accessors added, cuprite/hematite goldens unaffected; `interface
FluidPort<...>` confirmed to need no grammar change (`through`/
`across` are ordinary bareword field values via existing machinery).
Deliverable 4 (AD-23 net core cross-language elec refit) NOW DONE on
branch wo31-d4netcore: `regolith-sem::net_core` (`NetDiscipline` trait,
`ElecDiscipline`, `FluidDiscipline`, `first_violation` traversal)
replaces the Python elec single-driver ledger
(`regolith.realizer.elec.netlist.check_single_driver` now marshals to
Rust via a new `regolith._core.check_elec_single_driver` FFI crossing,
reached only through `regolith.compiler`, AD-4). Elec/cuprite goldens
unchanged (proved). See the AD-23 CLARIFICATION in
`../00-architecture.md` sec. 23 for the exact scope of what moved.
Deliverables 3 (diagnostics), 5 (example corpus), 6 (docs) remain NOT
STARTED -- see the wo31-cont branch report for the handoff)
Depends: WO-05 (parser stack), WO-07/08 (entity DB + queries); the
WO-29 remainder is NOT a dependency (fluorite parses its own bodies
from day one -- no OpaqueIsland debt is being created here, that is
the point). GATES WO-32 (fluorite lowering).
Language: Rust (`regolith-syntax` grammar/CST/AST + extension
registry; `regolith-sem` generalized net core + disciplines;
`regolith-diag` new code family)
Spec: `docs/fluorite/` 01+02 (RATIFIED v1, D93 -- normative),
04 (FOPEN deferrals: reject, do not implement); cuprite/03 sec. 2
(the elec net discipline being refit); `../00-architecture.md` AD-3
(parser stack), AD-6 (determinism), AD-23 (one net core -- NORMATIVE
for deliverable 4); design-log 2026-07-07-cycle-20 D93/D100.

## Goal

fluorite becomes a parsed language: `.fluo` files lex/parse to CST +
typed AST, the flownet net discipline runs as compile checks on the
AD-23 generalized net core (with cuprite's existing checks refit onto
the same core), and every construct the ratified 02 defines is
grammar-covered with fixtures. Lowering to obligations is WO-32.

## Deliverables

1. **Extension registry.** `.fluo` joins `.hema`/`.cupr` in the ONE
   extension registry module in `regolith-syntax` (the tripwire:
   nowhere else, including tests -- fixtures obtain extensions from
   the registry).
2. **Grammar + CST + AST** for the ratified 02 surface:
   `medium <name>: <phase>` with `props: registry(...)`;
   `interface FluidPort<...>` reusing the existing interface
   machinery with `through`/`across` flow-role markers;
   component-class constructor calls with the parameter-source rules
   (`from=` geometry refs, `driven_by=` promise refs, record params,
   `free`/`allocated`/`derived` value sources -- all EXISTING value
   source machinery, WO-04); `flownet <name>(medium=<ref>):` with
   `reference:`, `nodes:`, `edges:` (edge = name, constructor,
   `(a -> b)` sense pair), `states:` (edge-parameter domains AND
   `state <name> in {...}` net-level declarations); `require` blocks
   whose claim expressions reuse the EXISTING claim grammar
   (`fluids.*` heads are ordinary qualified names -- no new claim
   syntax; `forall <var> in {<idents>}` already parses as a discrete
   domain). `../grammar.ebnf` updated in lockstep; fuzz targets inherit
   the new productions.
3. **Negative fixtures + diagnostics.** New `regolith-diag` code
   family for fluid net discipline (allocate the next free E-block
   in the diag registry; the design texts call it "the fluid
   discipline family"): unjoined terminal / not-`sealed`, reference
   unreachable, imposer-free subnet, mixed media in one subnet
   (FOPEN-1's compile error), undeclared state variable in a claim,
   `driven_by=` on a geometry-only parameter and vice versa. Each
   code gets a `tests/golden` negative fixture with exact rendering.
4. **AD-23 net core.** In `regolith-sem`: extract the net ledger
   machinery into `net_core` -- terminal ledger, reachability,
   imposer counting, per-subnet partition -- parameterized by a
   `NetDiscipline` (check predicates + diagnostic codes as DATA, not
   subclass logic where avoidable). Provide `elec` (single-driver,
   at-most-one voltage imposer, supply shorts, `discard`) and
   `fluid` (at-least-one pressure imposer counting `Imposer` edges,
   medium consistency, `sealed`) disciplines. REFIT cuprite's
   existing checks onto the core in this change: the elec check
   entry points keep their signatures and diagnostics byte-identical
   (goldens prove it), only their implementation moves. Two ledger
   implementations remaining after this WO is an acceptance FAILURE.
5. **Example corpus.** `examples/tracks/fluorite/` gains at least: a coolant
   loop (thermostat state domain), a feed system (regulator +
   check valve + orifice), and a brake-shaped circuit (Imposer with
   `driven_by=`, dual-circuit `state` variables, `forall` over state
   refs) -- each `regolith check`-clean except deliberate negative
   siblings. Port the shapes from
   `../feldspar/examples/lithos/dune_buggy/*.fluo` (post-rename)
   WITHOUT the cross-repo dependency: self-contained versions.
6. **Docs.** `docs/fluorite/` stays the normative home (fix any spec
   drift found while implementing VIA a design-log note, never
   silently); `docs/README.md` and root `CLAUDE.md` names table
   already updated (cycle 20); crate docstrings name their fluorite
   doc sections.

## Acceptance criteria

- `regolith debug tokens|cst|ast <file>.fluo` works on every corpus
  example; parse is lossless (CST round-trips byte-identically).
- Every 02 construct appears in at least one positive fixture; every
  deliverable-3 diagnostic in exactly one negative fixture with a
  golden rendering.
- The elec discipline refit changes ZERO existing goldens.
- An imposer-free flownet fails at compile with the singular-network
  diagnostic (02 sec. 4), not at solve time.
- `feature`/`refer`/query machinery is untouched (no regression in
  `regolith-lower` tests).
- Extension strings appear in exactly one module
  (`grep -rn '\.fluo' crates/ | grep -v registry` finds only the
  registry + generated/test fixtures that read from it).
- `make check` green; fuzz targets build.

## Non-goals

- Lowering, obligations, the flownet payload (WO-32).
- FOPEN-1 mixing / FOPEN-2 compressible solving (rejected at
  compile per 02/04).
- Any cuprite grammar change beyond the internal refit (deliverable
  4 moves implementation, not surface).
- Hematite `impl FluidPort` geometry EXTRACTION (WO-32; the impl
  syntax already parses via existing interface machinery).
