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
acceptance: []
threat: null
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
acceptance: []
threat: null
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
acceptance: []
threat: null
```
frob check --type python --only gates reports 771 TEST001 warnings under python/regolith -- public functions/methods with no frob:tests unit edge -- the single largest concentration of TEST001 in the repo (second: crates/regolith-lower at 171). pyproject.toml already has a real, substantial pytest suite under tests/ and python/ (testpaths = ["tests", "python"]); most of these symbols likely already have a covering test that simply lacks the frob:tests <symref> directive binding it.

Sweep python/regolith's highest-symbol-count modules first (regolith.harness, regolith.orchestrator, regolith.realizer.* per the frob-exports tool-summary counts), add frob:tests directives above existing test functions that already exercise each symbol, and file follow-up tickets for genuinely untested public symbols rather than writing throwaway tests just to satisfy the gate. Re-run frob check --only gates and confirm the TEST001 count for python/regolith drops meaningfully.

Origin: frob enforcement adoption sweep (frob check --only gates dry run).

<!-- ticket:T-0004 -->
```yaml
id: T-0004
title: 'WO-111: feldspar model growth (WO-24 remainder + Class C solver half)'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- crates/regolith-lower/**
- python/regolith/**
- docs/spec/toolchain/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-111-feldspar-model-growth.md
threat: null
```

<!-- ticket:T-0005 -->
```yaml
id: T-0005
title: 'WO-123: artifact presentation v2 -- remaining wave-1 residual'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- python/regolith/emission/**
- docs/spec/toolchain/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-123-artifact-presentation-v2.md
threat: null
```

<!-- ticket:T-0006 -->
```yaml
id: T-0006
title: 'WO-124: complete board fab set -- remaining wave-1 residual'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- python/regolith/emission/**
- crates/regolith-lower/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-124-board-fab-completeness.md
threat: null
```

<!-- ticket:T-0007 -->
```yaml
id: T-0007
title: 'WO-132: power net discipline + cuprite power vocabulary'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- docs/spec/cuprite/**
- crates/regolith-syntax/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-132-power-front-end.md
threat: null
```

<!-- ticket:T-0008 -->
```yaml
id: T-0008
title: 'WO-133: power lowering + PowerNetPayload + claim routing'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0007
parent: null
scope:
- crates/regolith-lower/**
- python/regolith/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-133-power-lowering.md
threat: null
```

<!-- ticket:T-0009 -->
```yaml
id: T-0009
title: 'WO-135: power models -- closed-form built-ins + certified solvers'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0008
parent: null
scope:
- python/regolith/stdlib/**
- docs/spec/toolchain/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-135-power-models.md
threat: null
```

<!-- ticket:T-0010 -->
```yaml
id: T-0010
title: 'WO-136: sited equipment -- the cuprite-calcite tandem'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0009
parent: null
scope:
- docs/spec/cuprite/**
- docs/spec/calcite/**
- crates/regolith-lower/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-136-power-calcite-tandem.md
threat: null
```

<!-- ticket:T-0011 -->
```yaml
id: T-0011
title: 'WO-137: the factory flagship -- power + building together'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0010
parent: null
scope:
- examples/flagships/**
- docs/spec/toolchain/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-137-factory-flagship.md
threat: null
```

<!-- ticket:T-0012 -->
```yaml
id: T-0012
title: 'WO-140: minor losses -- Hooper/Darby/Borda-Carnot + component-dp chain'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- docs/spec/fluorite/**
- python/regolith/stdlib/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-140-minor-losses.md
threat: null
```

<!-- ticket:T-0013 -->
```yaml
id: T-0013
title: 'WO-141: feldspar fluids pack bridge, lithos half'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- python/regolith/**
- docs/spec/toolchain/20-solver-abstraction.md
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-141-fluids-pack-bridge.md
threat: null
```

<!-- ticket:T-0014 -->
```yaml
id: T-0014
title: 'WO-142: heat-transfer correlation growth'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- python/regolith/stdlib/**
- docs/spec/fluorite/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-142-heat-transfer-correlation-growth.md
threat: null
```

<!-- ticket:T-0015 -->
```yaml
id: T-0015
title: 'WO-143: Moody calc-sheet figure -- diagram.moody renderer'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- python/regolith/emission/**
- docs/spec/fluorite/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-143-moody-calc-sheet-figure.md
threat: null
```

<!-- ticket:T-0016 -->
```yaml
id: T-0016
title: 'WO-144: fluid demo close-out -- small_office waiver burn-down + demo pack'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0012
parent: null
scope:
- examples/**
- demos/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-144-fluid-demo-closeout.md
threat: null
```

<!-- ticket:T-0017 -->
```yaml
id: T-0017
title: 'WO-146: traced-profile format spec + .rgp ratification'
state: queued
kind: docs
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- docs/spec/hematite/**
- docs/spec/toolchain/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-146-traced-profile-spec.md
threat: null
```

<!-- ticket:T-0018 -->
```yaml
id: T-0018
title: 'WO-147: .rgp schema + extern-profile elaboration (SCHEMA_VERSION bump)'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0017
parent: null
scope:
- crates/regolith-syntax/**
- python/regolith/_schema/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-147-traced-profile-elaboration.md
threat: null
```

<!-- ticket:T-0019 -->
```yaml
id: T-0019
title: 'WO-148: traced-profile Python realizer + citation + artifact-index'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0018
parent: null
scope:
- python/regolith/realizer/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-148-traced-profile-realizer.md
threat: null
```

<!-- ticket:T-0020 -->
```yaml
id: T-0020
title: 'WO-149: native-walk fitting / promote-to-native-profile (v1.5, UNSCHEDULED)'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0019
parent: null
scope:
- python/regolith/realizer/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-149-native-walk-promotion.md (deferred, not scheduled
  this cycle)
threat: null
```

<!-- ticket:T-0021 -->
```yaml
id: T-0021
title: 'WO-151: waveform/mask record class + authored-posture refusal'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- docs/spec/cuprite/**
- python/regolith/stdlib/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-151-waveform-mask-record-class.md
threat: null
```

<!-- ticket:T-0022 -->
```yaml
id: T-0022
title: 'WO-152: waveform/mask records on sheets -- rendering + AUTHORED badge'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0021
parent: null
scope:
- python/regolith/emission/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-152-waveform-sheet-rendering.md
threat: null
```

<!-- ticket:T-0023 -->
```yaml
id: T-0023
title: 'WO-153: the in-house process-I/O seam regolith.procio'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- python/regolith/procio/**
- python/regolith/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-153-procio-seam.md
threat: null
```

<!-- ticket:T-0024 -->
```yaml
id: T-0024
title: 'WO-154: sim/timing gate spec deltas + INV ledger entry text'
state: queued
kind: docs
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- docs/spec/regolith/13-invariants.md
- docs/spec/cuprite/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-154-sim-gate-spec.md
threat: null
```

<!-- ticket:T-0025 -->
```yaml
id: T-0025
title: 'WO-155: cuprite functional simulation gate -- hdl.sim_assert'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0023
parent: null
scope:
- python/regolith/**
- crates/regolith-lower/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-155-cuprite-sim-gate.md
threat: null
```

<!-- ticket:T-0026 -->
```yaml
id: T-0026
title: 'WO-156: timing closure v1 -- grounding budget kind=timing'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- python/regolith/**
- docs/spec/cuprite/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-156-timing-closure-v1.md
threat: null
```

<!-- ticket:T-0027 -->
```yaml
id: T-0027
title: 'WO-157: sim/timing fleet adoption -- census flip + coverage sweep'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0025
parent: null
scope:
- examples/**
- python/regolith/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-157-sim-fleet-adoption.md
threat: null
```

<!-- ticket:T-0028 -->
```yaml
id: T-0028
title: 'WO-158: riscv_hart_rv1 sim demo -- expected_signals-vs-sim cross-check'
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by:
- T-0027
parent: null
scope:
- examples/flagships/**
- demos/**
evidence: []
attachments: []
acceptance:
- see docs/workflow/work-orders/WO-158-riscv-sim-demo.md
threat: null
```

<!-- ticket:T-0029 -->
```yaml
id: T-0029
title: 'Cycle-36: docs/README currency sweep -- charters 40/41, AD-38/39'
state: queued
kind: docs
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- docs/README.md
- docs/spec/toolchain/00-architecture.md
- docs/guide/**
evidence: []
attachments: []
acceptance:
- see TODO.md cycle-36 queue block, 'Docs/README currency sweep' line
threat: null
```

<!-- ticket:T-0030 -->
```yaml
id: T-0030
title: 'Cycle-36: coordinator VISUAL ACCEPTANCE record at WO-123+WO-124 integration'
state: queued
kind: docs
origin: agent
created: '2026-07-18'
blocked_by:
- ''
parent: null
scope:
- docs/workflow/design-log/**
evidence: []
attachments: []
acceptance:
- see TODO.md cycle-36 queue block, 'COORDINATOR VISUAL ACCEPTANCE record' line (D238.3)
threat: null
```

<!-- ticket:T-0031 -->
```yaml
id: T-0031
title: 'chore: frob adoption -- ticket conversion + docs link graph'
state: queued
kind: docs
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- docs/**
- tickets.md
- TODO.md
evidence: []
attachments: []
acceptance:
- frob ticket list parses clean; frob ticket doable shows correct set; frob check
  --only gates reports DOC001=0 and no ticket/queue errors
threat: null
```
