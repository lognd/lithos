# WO-121 -- Documentation refresh + guide expansion (D230)

Status: open
Language: docs (Markdown; Python only for the docs-agreement
  consistency checks); gates: after waves 1-3 merge (documents
  what IS); before WO-117 (the close verifies docs agree).
Spec: D230; house DOCUMENT-AS-YOU-GO rule (this WO is the
  coherence pass and gap-fill -- each feature WO still owns its
  own guide page); D219 (health consistency leg); charter 39 +
  feldspar spec 12 (the organization story the docs must tell).

## Goal

A newcomer can go from `git clone` to reading a shipped calc book,
authoring a claim with provenance, and adding a stdlib record or
feldspar solver, guided entirely by docs/ -- and every README
states current reality (no stale feature tables, dead names, or
superseded ranges).

## Deliverables

1. README refresh sweep: root README, docs/README, docs/guide/
   README (index), examples/README, stdlib/README (now pointing at
   charter 39 as the normative home, keeping its D135/D58 history
   note), apps/graphite/README, editors/vscode/README, plus any
   others a `find` survey turns up (fuzz/, examples/hdl/,
   examples/negative/). Current AD-1..37+/INV-1..30/WO ranges,
   real CLI verbs (health, optimize, test, preview...), the four
   languages + magnetite/regolith/feldspar naming table.
2. New guides (continue docs/guide/ numbering; match the existing
   voice -- worked examples over reference dumps):
   - Reading the calc book: calc sheets, the audit index, walking
     an obligation to its evidence chain, citing a package in a
     review (builds on WO-114's page if one landed -- extend,
     never duplicate).
   - The rigor census: discharged vs accepted vs deferred,
     per-class waiver accounting, what the health fleet leg
     enforces (D220).
   - Authoring for discharge (D224): declaring inputs with
     provenance (record | derivation | citation), the same-change
     waiver burn-down, fixing the DESIGN on VIOLATED.
   - Growing the stdlib (charter 39): where records/models/packs
     go, the boundary rule, citation + tier bar, generated
     batches; the feldspar half (spec 12) summarized with a
     pointer, including the calibration-first law.
   - Graphite progress UX (extend guide 12) and the VS Code
     workflow (tasks, hovers, go-to-artifact) -- only the halves
     that landed (WO-119/120); honest pointers otherwise.
3. Docs-agreement checks in the health consistency leg
   (standardized D219 rows): guide README index matches files
   present; README CLI-verb tables match `regolith --help` output;
   no dead names outside design-log history and negative tests
   (extend the existing sweep if one covers part of this).
4. Cross-reference integrity pass: every guide's spec/WO citations
   resolve; the guide README index carries one-line hooks per
   guide.

## Acceptance

- Survey table in the close-out: every README (found by sweep)
  with its refresh status; every new guide listed in the guide
  index.
- Docs-agreement checks live in `make health` and individually
  runnable; `make check` + health green.
- Zero content invented ahead of landed machinery: an unlanded
  half is a named pointer, never speculative documentation.

## Escalation

Feature behavior discovered undocumented AND surprising during
writing (a real UX bug, not a docs gap) is reported with a
placeholder label, not silently papered over in prose.
