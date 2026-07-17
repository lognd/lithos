---
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
---
frob check --type python --only gates reports 771 TEST001 warnings under python/regolith -- public functions/methods with no frob:tests unit edge -- the single largest concentration of TEST001 in the repo (second: crates/regolith-lower at 171). pyproject.toml already has a real, substantial pytest suite under tests/ and python/ (testpaths = ["tests", "python"]); most of these symbols likely already have a covering test that simply lacks the frob:tests <symref> directive binding it.

Sweep python/regolith's highest-symbol-count modules first (regolith.harness, regolith.orchestrator, regolith.realizer.* per the frob-exports tool-summary counts), add frob:tests directives above existing test functions that already exercise each symbol, and file follow-up tickets for genuinely untested public symbols rather than writing throwaway tests just to satisfy the gate. Re-run frob check --only gates and confirm the TEST001 count for python/regolith drops meaningfully.

Origin: frob enforcement adoption sweep (frob check --only gates dry run).