# WO-79: board-correctness rule packs, wave 1

Status: todo
Depends: WO-28 engine (in-language rules, landed), WO-40 lints,
AD-21/AD-34, charter 36 (NORMATIVE), D186/D187. Record-field gaps
(crystal CL, MCU strap tables, connector exposure class) are IN
scope as additive stdlib fields/records under the sourcing law.
NO schema bump; no crates/ (a rule-engine gap escalates).
Language: in-language rule packs + records + Python fixtures/tests.
Spec: docs/spec/toolchain/36-board-correctness.md, 21-rule-packs.md,
32-stdlib-depth.md sec. 1.

## Deliverables

1. The five wave-1 families (charter sec. 2) as `erc:`-family
   packs: >= 3 demand rules each, `per:` citations (vendor app
   notes/standards named with revision), expect pass/fail fixtures
   per the AD-21 mandatory-fixture law.
2. Supporting record fields/records (additive, cited): crystal
   records with CL; MCU family strap/reset-requirement fields where
   the datasheet states them; connector exposure classes.
3. The hazard fixture board (examples/negative or fixtures/): trips
   every family; the fixed twin passes.
4. Coverage visibility: whatever the landed audit surface already
   renders (rules run/fired/passed per subject) verified for these
   packs; a genuine surface gap is an escalation, not a new report.
5. Docs: guide section (the encoded checklist, how to declare N/A),
   charter cross-refs, WO ledger. `regolith rules test` green over
   every pack.

## Acceptance: charter 36 sec. 5 verbatim; make check green;
Status flipped.
