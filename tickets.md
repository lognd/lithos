# Tickets

Central ledger managed by `frob ticket` -- one section per ticket.

<!-- ticket:T-0001 -->
```yaml
id: T-0001
title: Wire docs/workflow/work-orders/*.md into the docs link graph (DOC001)
state: queued
kind: docs
origin: agent
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- docs/index.md
evidence: []
attachments: []
```
frob check --type python --only gates flags 769 DOC001 warnings (frob.toml legacy baseline). The bulk are docs/workflow/work-orders/WO-*.md and docs/workflow/design-log/*.md files that carry no frob:describes anchor, no frob:doc edge, and are unreachable by markdown link crawl from docs/index.md or README.md.

Design-log entries are explicitly frozen history (lithos CLAUDE.md: NEVER sweep or edit these) so those stay warn-only permanently via frob.toml's [gates.severity] DOC001=warn baseline. Work-order files are live and should be linked: add an index section in docs/index.md (or docs/workflow/README.md, then link that from docs/index.md) enumerating active/closed WOs so DOC001 clears for that subset without touching frozen design-log content.

Origin: frob enforcement adoption sweep (frob check --only gates dry run).

<!-- ticket:T-0002 -->
```yaml
id: T-0002
title: Annotate crates/regolith-oblig doc edges for COV001
state: queued
kind: docs
origin: agent
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- crates/regolith-oblig/src/**
evidence: []
attachments: []
```
frob check --type python --only gates reports 146 COV001 warnings under crates/regolith-oblig (e.g. flownet.rs::RecordRef, flownet.rs::ScalarInterval) -- public symbols with no frob:doc edge. This is the obligation-graph core crate (AD-1/AD-2 territory), the highest-value place to start closing COV001 given regolith-lower/regolith-syntax/regolith-oblig account for most of the 6900+ COV001 hits repo-wide.

Add frob:doc / frob:describes anchors (or doc comments the doclink/coverage gate already recognizes) for the public API surface of crates/regolith-oblig/src/, prioritizing flownet.rs and any other file with more than 10 undocumented public symbols. Re-run frob check --only gates and confirm the COV001 count for this crate drops to 0.

Origin: frob enforcement adoption sweep (frob check --only gates dry run).

<!-- ticket:T-0003 -->
```yaml
id: T-0003
title: Bind existing python/regolith tests via frob:tests (TEST001)
state: queued
kind: feature
origin: agent
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- python/regolith/**
evidence: []
attachments: []
```
frob check --type python --only gates reports 771 TEST001 warnings under python/regolith -- public functions/methods with no frob:tests unit edge -- the single largest concentration of TEST001 in the repo (second: crates/regolith-lower at 171). pyproject.toml already has a real, substantial pytest suite under tests/ and python/ (testpaths = ["tests", "python"]); most of these symbols likely already have a covering test that simply lacks the frob:tests <symref> directive binding it.

Sweep python/regolith's highest-symbol-count modules first (regolith.harness, regolith.orchestrator, regolith.realizer.* per the frob-exports tool-summary counts), add frob:tests directives above existing test functions that already exercise each symbol, and file follow-up tickets for genuinely untested public symbols rather than writing throwaway tests just to satisfy the gate. Re-run frob check --only gates and confirm the TEST001 count for python/regolith drops meaningfully.

Origin: frob enforcement adoption sweep (frob check --only gates dry run).
