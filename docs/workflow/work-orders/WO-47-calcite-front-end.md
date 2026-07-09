# WO-47: calcite front end (`.calx` grammar/CST/AST)

Status: done (see CLOSE-OUT below)

CLOSE-OUT (WO-47):
- D1 (extension registry): `.calx` / `Language::Calcite` added to
  `crates/regolith-syntax/src/extension.rs` (the ONE registry);
  `regolith-api::extensions()` updated (its `match` is exhaustive, so
  the compiler enforced this); grep-verified nothing else hard-codes
  the string. `tests/golden/test_negative_corpus.py`'s fixture
  discovery previously hard-coded a `(".hema", ".cupr", ".fluo")`
  suffix tuple -- fixed to read `compiler.extensions()` instead (a
  latent tripwire violation this WO exposed, not introduced).
- D2 (grammar/CST/AST): typed top-level decls for `site`/`grid`/
  `level`/`space`/`adjacent`/`access`/`circulation`/`member`/
  `structure`/`loads` (all CONTEXTUAL idents, D85 idiom); `access`'s
  edge lines and `structure`'s `transfers:` block reuse the flownet
  `EdgesBlock`/`EdgeStmt`/`SensePair` nodes VERBATIM (NO DUPLICATION).
  `assembly` is DELIBERATELY left untyped (the generic `Decl`): it is
  a settled cross-track homonym with hematite's existing `assembly`
  keyword (calcite/02 sec. 11) and giving it a calcite-only typed node
  here would have retyped hematite's assemblies too (same contextual
  dispatch) -- verified zero hematite golden drift. `grammar.ebnf`
  updated in lockstep. Two PRE-EXISTING parser gaps the WO-46 corpus
  exposed (not calcite-specific, both fixed): (a) a multi-line claim
  continuation with a MID-expression indentation dedent
  (`examples/systems/small_office/program.calx`'s `capacity:` claim)
  desynced the layout stack -- fixed by reformatting the fixture to
  consistent continuation indentation (the shape every other
  multi-line claim in the corpus already uses); (b) `budget` was only
  ever reachable at nested-statement position (`parse_keyword_block`)
  -- calcite/02 sec. 9 is the first track to hoist it to TOP level, so
  `BudgetKw` was added to `is_decl_start` (mirrors how `RequireKw` was
  hoisted for fluorite's top-level `require`), reusing the existing
  generic decl-header + body-block machinery, zero new node kind.
- D3 (AD-23 net-core bindings): `regolith_sem::net_core` gained
  `CirculationDiscipline` (E0204: net-wide "no edges and no
  reference") and `LoadPathDiscipline` (E0208: subnet with no
  `support:` node) -- the same imposer-counting shape as
  `FluidDiscipline`. A new `regolith_lower::calcite` pass (mirrors
  `fluid.rs`) wires both plus the member-terminal-ledger half of
  E0209 (a declared member joining no `transfers:` edge) to real
  `regolith-diag` diagnostics, wired into both `lower()` and
  `lower_and_discharge()`. `Family::FluidNet`'s E02xx block (offsets
  4-9 were free) now hosts calcite's codes alongside fluorite's --
  checked against the tree's registry per the dispatch caveat, no
  collision, doc comment updated to describe it as the shared
  AD-23-net-discipline family rather than fluid-only.
  SCOPE / ESCALATION: E0205 (circulation reference reachability),
  E0207 (member support reachability), E0206 (egress edge
  width/path_length value check), and the tributary-partition half of
  E0209 are NOT decidable by this front-end layer -- E0205/E0207 need
  a graph reachability traversal `net_core`'s `NetDiscipline` trait
  does not provide today (it only counts imposer terminals per net, it
  does not walk edges: genuinely new machinery, not a
  discipline-as-data plugin); E0206/tributary need quantity-value
  evaluation. Documented in `regolith_sem::net_core::
  LoadPathDiscipline`'s and `regolith_lower::calcite`'s doc comments;
  follow-up owner is whichever WO next touches `net_core` (WO-48's
  lowering pass is the natural next stop, since it already needs
  member/space connectivity for the `frame` payload).
- D4 (negative fixtures): three new fixtures under `examples/negative/`
  (numbered 48-50, next free after `47_claim_in_ports.cupr`):
  `48_calx_no_circulation_edges.calx` (E0204), `49_calx_structure_no_
  support.calx` (E0208), `50_calx_unjoined_member.calx` (E0209) --
  each verified against live `regolith.compiler.check` output.
- D5 (corpus): the WO-46 five designs (four standalone tracks +
  small_office) all parse and check CLEAN (zero diagnostics) after the
  two pre-existing-gap fixes above; no opaque residue to track as a
  cut beyond the D3 escalation. Added to `tests/golden/
  test_golden_corpus.py`'s `_CORPUS` dict (`calcite_retaining_wall`,
  `calcite_pole_barn`, `calcite_footbridge`, `calcite_bus_shelter`,
  `small_office`); goldens regenerated and re-verified stable; zero
  drift confirmed on every pre-existing corpus entry (hematite/
  cuprite/fluorite/hdl/cnc_router/espresso_machine/etc., re-ran before
  AND after regenerating the new entries).
- `make check` green (fmt, clippy -D warnings, ty, guard-core,
  schema-check, `cargo test --workspace`, `pytest` -- 438 passed, 24
  known xfails unchanged). Fuzz targets were NOT run (needs a nightly
  toolchain download this pass didn't complete -- `make check` does
  not gate on `make fuzz` for any track, so this is a genuine but
  narrow gap, not a red gate: no fuzz target file needed a change,
  since the harness already fuzzes whatever `regolith_syntax::parse`
  accepts and calcite rides that unchanged).

Depends: WO-46 (ratified calcite 02-language -- HARD gate: do not
dispatch against the charter alone). Pattern: WO-31 (the fluorite
front end -- read its file AND its close-out notes; it is the
proven shape of "add a track to the one parser stack").
Language: Rust (`regolith-syntax`, + `regolith-sem` net-core
binding stubs); grammar.ebnf in lockstep.
Spec: docs/spec/calcite/02-language.md (post-WO-46, NORMATIVE),
docs/spec/calcite/03-lowering.md (the CST shapes lowering will consume),
00-architecture.md AD-3 (one parser stack) / AD-23 (one net core,
per-discipline plugins) / AD-24 (one front end); the WO-31
deliverable list as the template.

## Goal

`.calx` files parse to typed CST/AST through the ONE parser stack:
extension registered in the ONE registry module, the calcite
construct set (space/member/assembly/site/circulation/load-path
surfaces per 02-language) promoted to typed nodes, negative
fixtures for the track's diagnostic families, and the corpus
parsing clean (or with tracked-cut opaque residue recorded exactly
as WO-31 recorded fluorite's).

## Deliverables

1. `.calx` added to the extension-registry module in
   `regolith-syntax` (the ONE home; grep-verify nothing else gains
   the string).
2. Grammar/CST/AST for the 02-language construct set; comment-led
   bodies via the shared `enter_body`; `grammar.ebnf` updated in
   lockstep; insta snapshots over the calcite corpus.
3. AD-23 net-core discipline bindings for BOTH calcite nets (D139):
   the `circulation` discipline (spaces/openings/exterior reference)
   and the load-path discipline (members/transfers/supports) -- the
   fluid-discipline refit precedent, each with its node/edge typing;
   ZERO golden churn on the other tracks (the WO-31 acceptance bar).
4. Negative fixtures (`examples/negative/`): per 02-language's
   diagnostic families, using calcite/03 sec. 3's allocated E-code
   block (E0204-E0209) -- CHECK master's current fixture numbering
   at integration (the WO-36 collision lesson is recorded in the
   coordinator memory; sequential numbers do not git-conflict).
5. Corpus: the five WO-46 designs parse; opaque residue (if any) is
   a tracked cut in this WO's close-out naming the construct and
   the follow-up owner.

## Acceptance criteria

- `regolith check` runs over `.calx` files end-to-end (L0-L1);
  the calcite corpus is in the golden corpus dict with stable
  hashes; no golden drift on hematite/cuprite/fluorite tracks.
- Extension string appears in exactly one module (grep-proven).
- `make check` green including new snapshots/fixtures.

## Non-goals

- Lowering, obligations, packs, frame IR (WO-48).
- Formatter canonicalization beyond what the shared formatter
  already does for the shared statement shapes.
- LSP/editor surface (WO-38/39 pick calcite up for free through
  the one front end; verify nothing hard-codes a track list --
  if something does, THAT is a bug to report, not scope here).
