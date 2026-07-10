# WO-68: forall-combo obligation emission + `in registry(...)` domains

Status: todo
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
