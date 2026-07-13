# WO-121 -- Documentation refresh + guide expansion (D230)

Status: done (2026-07-13; close-out ledger below; one named
  report-only baseline, WO121-F1)
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

## Close-out ledger (2026-07-13)

### README survey table (deliverable 1)

| README | status |
|---|---|
| `README.md` (root) | REFRESHED: apps/graphite + install-graphite dropped (D233), graphite section rewritten to the sibling-repo story, `make health` target added, AD range 35->37, cubesat path -> flagships/ |
| `docs/README.md` | REFRESHED: apps/ layout entry replaced with the extraction note, AD-1..37 / WO-01..122, stdlib entry points at charter 39, systems/flagships split corrected |
| `docs/guide/README.md` | REFRESHED: missing 23-health-gate.md row added, four new guide rows (26-29) with one-line hooks, guide-12 hook rewritten, corpus paragraph corrected to the tracks/systems/flagships taxonomy |
| `examples/README.md` | CURRENT already (D188 taxonomy); one cross-repo path normalized to `feldspar:examples/lithos/` |
| `stdlib/README.md` | REFRESHED: charter 39 named as the normative organization home (D227/AD-37), README repositioned as the working package index + D135/D58 history (both kept verbatim) |
| `fuzz/README.md` | CURRENT (surveyed, no stale names/ranges) |
| `editors/vscode/README.md` | CURRENT (surveyed; documents the WO-39 surface that exists -- WO-120 parity is not started and is not documented as shipped) |
| `examples/hdl/README.md` | CURRENT (surveyed) |
| `examples/negative/README.md` | CURRENT (surveyed) |
| `docs/workflow/README.md` | out of refresh scope (process doc, already current incl. the HEALTH-F4 status vocabulary); its one retired-name line documents the retirement itself |
| track/spec + per-project READMEs (`docs/spec/*/README.md`, `examples/{systems,flagships}/*/README.md`, `examples/tracks/{calcite,fluorite}/README.md`) | surveyed by the sweep; content is per-track/per-project and current; not this WO's to rewrite |

### New guides (deliverable 2)

- `docs/guide/26-reading-the-rigor-census.md` (D220/F133; names the
  WO-117 per-class census flip as pending, not shipped)
- `docs/guide/27-authoring-for-discharge.md` (D224; the real arm_a6
  j1_bearing provenance trail + the real uav_talon spar D224.3 fix)
- `docs/guide/28-growing-the-stdlib.md` (charter 39; feldspar spec 12
  summarized with a repo-qualified pointer + the calibration-first law)
- `docs/guide/29-the-progress-channel.md` (D228 wire shape v1 from
  `python/regolith/progress.py`; consumers named with honest status)
- `docs/guide/12-graphite.md` FULLY REFRESHED (D233/D234): sibling-repo
  story, what ships today (WO-G1..G4/G6 done per graphite's own
  ledgers), honest in-flight pointers (WO-G5/G7/G8 open). The VS Code
  half of D230's guide list is a named pointer only: WO-120 is not
  started, so no VS Code workflow guide exists yet (zero content ahead
  of landed machinery); `editors/vscode/README.md` covers what IS.
- Calc-book reading: guide 24 (WO-114) already covers it; extended by
  cross-links from guides 26/27 rather than duplicated.

### Docs-agreement checks (deliverable 3)

`tools/health/docs_agreement.py`, folded into the consistency leg
(`tools/health/consistency.py`, sweeps 6->7) and standalone runnable
(`python -m tools.health.docs_agreement [--check NAME]`), D219 row
shape, reusing `tools/stdlib/organization.py`'s `SubCheck` +
`is_excluded()` predicate (imported, never copied -- the wo118b
lesson):

- `guide_index` -- guide README index == guide files on disk (no
  phantom rows, no orphan files).
- `cli_verbs` -- root README CLI-section tokens name only real
  `regolith` verbs, introspected from the live typer app (never a
  second hard-coded verb list).
- `dead_names` -- retired names absent from the swept README/guide
  set outside design-log history + examples/negative/; machining
  "mill" contexts exempted; scope deliberately bounded to the docs
  this WO owns (a repo-wide purge of retired-name FOOTNOTES in
  normative specs is content work outside this charter).

Proof on a worktree-BEARING checkout: run read-only against the main
checkout (3 live worktrees under .claude/worktrees): cli_verbs PASS,
dead_names PASS (0 new / 18 baseline), zero worktree false positives;
guide_index correctly FAILED there by detecting main's real pre-fix
gap (23-health-gate.md missing from the index -- fixed on this
branch), i.e. honest detection, not a false positive.

### Cross-reference pass (deliverable 4)

Mechanical sweep over all 26 guides + the 8 swept READMEs: every
WO-nn citation resolves to a work-order file, every in-repo path
citation resolves on disk, ASCII-only -- 0 broken refs at close.
Fixed en route: stale `examples/systems/cubesat/` (3 files), bare
cross-repo paths normalized to `graphite:`/`feldspar:` citations.
Guide index carries a one-line hook for every guide.

### Escalations

- **WO121-F1** (report-only baseline, in-code at
  `tools/health/docs_agreement.py::_DEAD_NAME_FOOTNOTE_BASELINE`):
  7 files carry pre-existing one-line "retired names" footnotes
  (root README/TODO/docs README name tables, calcite/fluorite/cuprite
  spec notes). Reported as WARNING, never gating. Reopen: a file is
  edited for another reason in the same change as dropping its
  footnote entry, or the footnote moves to a design-log entry.
- No UX bugs found during writing (the escalation clause's trigger
  never fired); all gaps were docs gaps.

Verification: `make check` green FOREGROUND on this worktree
(fmt/clippy/ruff/ty/guard-core/schema-check, 26 Rust suites ok,
1794 Python tests passed, health-smoke all legs PASS with the new
consistency sub-check live).
