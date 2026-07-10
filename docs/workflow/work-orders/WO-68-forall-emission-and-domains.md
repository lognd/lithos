# WO-68: forall-combo obligation emission + `in registry(...)` domains

Status: done (2026-07-10). SCHEMA_VERSION 25 landed; `make install` +
`make check` green. See design-log 2026-07-09-cycle-31 D181's "LANDED
(WO-68, 2026-07-10)" addendum for the root cause, the obligation-count
deltas per corpus design, and the deferral-reason accounting. WO-65
un-gated (its Status line updated in its own file).
Depends: WO-62 (SCHEMA_VERSION 24, landed). Owns the serialized
bump 24->25 (D181/D168 train rule): `FrameMember.section_domain`.
Gates: WO-65's reopen (the five-design verdict flip).
Language: Rust (`regolith-syntax` value-source grammar,
`regolith-lower` sweep emission, `regolith-oblig` FrameMember) +
Python (corpus goldens, `discrete_domains` wiring touch-up).
Spec: design-log 2026-07-09-cycle-31 D181 (NORMATIVE ruling -- read
it first), regolith/03 (value sources -- `in [lo, hi]` is the form
being generalized), regolith/13 INV-1 (the emission bug's severity
argument), calcite/03 secs. 4-5, WO-65's findings section +
WO-56's WO-65 dispatch record (the live verification recipe:
footbridge emits 4 obligations, zero strength).

## Goal

Two fixes, one bump: (a) every `forall <var> in <domain>:` nested
named claim lowers to per-axis obligations (the silent-no-obligation
bug class dies, with a corpus-wide regression net); (b) discrete
record domains are declarable -- `<slot>: in registry(<family-ref>)`
-- lowered into `FrameMember.section_domain`, giving the section
search its declared candidate family.

## Deliverables

1. **Emission fix** (`regolith-lower`): nested named claims inside
   `forall combo in ...:` blocks (the calcite strength form is the
   proven repro) emit one obligation per axis point, keyed per
   INV-1. Regression test: for EVERY corpus design, every source
   claim group produces >= 1 obligation OR is on an explicit,
   asserted exemption list with reasons (the test that would have
   caught this years-in-corpus bug).
2. **Grammar**: `in registry(<ref>)` as a value-source domain form
   (regolith/03 gains the row -- update the spec table in the same
   change); parse + CST + formatter canonical form; negative
   fixtures (empty ref; non-registry callee).
3. **Schema**: `FrameMember.section_domain: Option<String>` (the
   declared family ref), bump 24->25, `make schema`, goldens
   regenerated (digest churn + the new obligations from fix 1 --
   THIS one legitimately changes obligation counts in the five
   calcite goldens; account for every new obligation in the ledger).
4. **Lowering**: a calcite member `section: in registry(<family>)`
   lowers domain -> `section_domain`; `section: free` unchanged
   (D181: no reinterpretation).
5. **Corpus**: the five ratified designs' searchable members
   (footbridge G1/G2, bus_shelter G1, pole_barn T1, small_office
   G2_AB/GR_AB) updated to declare their families
   (`std.civil` w_shape/hss_square per each design's intent --
   match the section family class its FIXED siblings already use;
   record the choice per member); retaining_wall untouched.
6. **Python touch-up**: `frame_resolve`/`optimize` read
   `section_domain` where WO-65's code expected a family (keep the
   change minimal -- WO-65's reopen does the full flip).
7. **Docs**: regolith/03 table row + prose, D181 cross-refs, WO-65
   gating note updated, this WO's ledger.

## Acceptance criteria

- The live repro flips: footbridge `compiler.check` emits its
  strength obligations (count > 4 total; each combo axis point
  keyed distinctly); the corpus-wide no-silent-claims regression
  test is green and RED when the fix is reverted (prove once,
  note in ledger).
- `in registry(...)` parses/formats/round-trips; fixtures both
  ways; fuzzers green.
- SCHEMA_VERSION exactly 25; churn accounted (digests + the new
  obligations only); `make install` + `make check` green; Status
  flipped; WO-65's Status updated to un-gated.

## Ledger (2026-07-10, close-out)

- **Emission fix root cause**: `forall <var> in <domain>:` as a BLOCK
  claim (header line, no inline predicate, nested indented body of
  named claims) was unrecognized in every statement context outside a
  rule pack; the parser's generic dispatch classified it
  `StmtShape::Opaque`, and `parse_opaque_stmt` swallows an opaque
  statement's entire nested body into ONE `OpaqueIsland` -- so every
  named claim inside was invisible past the PARSER, not just to
  `regolith-lower`. Fixed with a new CST node,
  `SyntaxKind::ForallSweepClaim` (`crates/regolith-syntax`), recognized
  in `StmtCtx::Generic` (every `require`-group body's own context);
  `RequireClaim`/`RequireDecl::all_claims()` gives every
  `regolith-lower::claims` require-group lowering path (decl claims,
  calcite frame claims, fluid claims, top-level cost claims) one
  accessor covering both direct and swept claims, sweep-tagged.
- **Red-when-reverted**: proved once by temporarily removing the
  `StmtCtx::Generic` dispatch arm and re-running
  `forall_sweep_block_nested_named_claim_emits_an_obligation` /
  `forall_sweep_block_over_calcite_frame_claims_flips_the_live_repro`
  (`crates/regolith-lower/src/claims.rs`) -- both failed with exactly
  the live repro's shape (footbridge's `strength` obligation missing,
  4 total instead of 5); restored and re-verified green.
- **Obligation-count deltas** (every OTHER golden churned digests only,
  `obligation_count` unchanged -- checked file by file):
  - `calcite_footbridge`: 4 -> 5 (+1 `strength`)
  - `calcite_bus_shelter`: 3 -> 4 (+1 `strength`)
  - `calcite_pole_barn`: 3 -> 4 (+1 `strength`)
  - `small_office`: 18 -> 19 (+1 `strength`)
  - `calcite_retaining_wall`: 3 -> 3 (untouched, no `forall combo` in
    its require group, per spec)
  - `fluorite_dual_brake_circuit`: 1 -> 2 (+1 `margin`, the `forall
    circuit in {front_circuit, rear_circuit}:` sweep)
- **`in registry(<family-ref>)`**: needed NO grammar/parser change --
  verified with a zero-diagnostic parse of `section: in
  registry(std.civil.hss_square)` before writing any lowering code
  (the existing generic `in <expr>` value-source arm plus the ordinary
  `CallExpr` grammar already cover it). Real work: `FrameMember.
  section_domain: Option<String>` (schema) and
  `frame_lower::section_domain_ref` (lowering; `section` stays the
  `free` placeholder since the domain is declared, not resolved).
- **Corpus family choices** (per-member, matched to each design's
  FIXED siblings' material class): footbridge G1/G2, bus_shelter G1,
  small_office G2_AB/GR_AB -> `std.civil.w_shape` (steel, `astm_a992`,
  matching each design's steel columns/beams); pole_barn T1 ->
  `std.civil.timber_sawn` (timber, `spf_no1`, matching its posts and
  purlins -- `std.civil` has no dedicated truss family, and
  `timber_sawn` is the only catalog family its material class has).
- **Deferral reasons** (regenerated `deferral_*.json` goldens):
  `frame_section_domain_unsearched` (a declared-family free section,
  the new, more specific case WO-65 reopens against) and the
  pre-existing `frame_section_unresolved`/`frame_section_incomplete`
  (unrelated members whose section names no usable std.civil record) --
  zero blanket `unsupported_op`, confirmed by inspection of every
  changed `deferral_*.json` file, not assumed.
- **Cut, named, not silently dropped**: no new diagnostic code for a
  malformed `in registry(...)` (empty ref; a non-`registry` callee) --
  both degrade to `section_domain: None` honestly (covered by
  `frame_lower.rs` unit tests
  `section_in_registry_empty_ref_declares_no_domain` /
  `section_in_non_registry_callee_declares_no_domain`); no
  `examples/negative/` fixtures added for these two shapes since the
  negative-corpus driver (`tests/golden/test_negative_corpus.py`)
  requires a real diagnostic code in its header contract and inventing
  one was outside this WO's named deliverables (regolith/03's own
  prose now records the gap explicitly instead).
