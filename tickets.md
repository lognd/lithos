# Tickets

Central ledger managed by `frob ticket` -- one section per ticket.

<!-- ticket:T-0001 -->
```yaml
id: T-0001
title: Wire docs/workflow/work-orders/*.md into the docs link graph (DOC001)
state: done
kind: docs
origin: agent
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- docs/index.md
evidence:
- cmd:bash -c 'n=$(frob check --only gates 2>&1 | grep -c DOC001); echo DOC001=$n;
  test $n -eq 0' exit=0 sha256=9f1ad0aa2425
attachments: []
acceptance: []
threat: null
```
frob check --type python --only gates flags 769 DOC001 warnings (frob.toml legacy baseline). The bulk are docs/workflow/work-orders/WO-*.md and docs/workflow/design-log/*.md files that carry no frob:describes anchor, no frob:doc edge, and are unreachable by markdown link crawl from docs/index.md or README.md.

Design-log entries are explicitly frozen history (lithos CLAUDE.md: NEVER sweep or edit these) so those stay warn-only permanently via frob.toml's [gates.severity] DOC001=warn baseline. Work-order files are live and should be linked: add an index section in docs/index.md (or docs/workflow/README.md, then link that from docs/index.md) enumerating active/closed WOs so DOC001 clears for that subset without touching frozen design-log content.

Origin: frob enforcement adoption sweep (frob check --only gates dry run).

## Done report

Created `docs/index.md` as the doc-link root (linked from the
top-level `README.md`), plus new link-index READMEs for
`docs/workflow/work-orders/` (157 entries), `docs/workflow/design-log/`
(32 entries, index only -- verbatim file content untouched per
CLAUDE.md), `docs/workflow/research/` (4 entries), and
`docs/spec/toolchain/` (26 entries). Linkified the existing
per-track README tables (cuprite, hematite, fluorite, calcite,
regolith, guide) so their backtick-only `NN-name.md` mentions became
real markdown links reachable from the new root.

Verification: `frob check --only gates 2>&1 | grep -c DOC001` went
from 256 (baseline at ticket creation) to 0. No DOC002 (dangling
anchor) regressions introduced (`grep -c DOC002` on the same run:
0, unchanged). Total gate violation count dropped from 3476 to 3220,
matching the 256 DOC001 warnings removed exactly. Cargo build/clippy/
fmt/test and Python collection all still pass.

<!-- ticket:T-0002 -->
```yaml
id: T-0002
title: Close COV001/TEST001/TEST003 across crates/** (lane L2)
state: in-progress
kind: docs
origin: agent
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- crates/**
- docs/**
- fuzz/**
evidence: []
attachments: []
acceptance: []
threat: null
```
ORIGINAL SCOPE (regolith-oblig only) WIDENED 2026-07-18 by lane L2 to cover
the full crates/** surface: frob check --only gates reports ~854 COV001
(public symbols with no frob:doc edge), ~300 TEST001 (public fns with no
frob:tests binding) and 10 TEST003 (crates missing an integration test
binding) across crates/regolith-lower (251/148), regolith-syntax (185/57),
regolith-oblig (146/-), regolith-diag (115/-), regolith-qty (105/23),
regolith-sem (93/30), regolith-ir (64/17), regolith-ls (55/24),
regolith-api (32/-), regolith-util (5/-).

LANE L2b (2026-07-18) picked this back up: a re-run of `frob check --only
gates` shows the true current crates/** surface is much larger than the
snapshot above (COV001 4618 total: regolith-lower 502, regolith-syntax
370, regolith-oblig 292, regolith-diag 230, regolith-qty 210,
regolith-sem 186, regolith-ir 128, regolith-ls 110, regolith-api 64;
TEST001 1534 total with the same crate ranking; TEST003 still 1 per
crate, 9 crates outstanding under crates/**) -- the earlier numbers were
either stale or measured under a narrower check_type. Given the surface
size, L2b closed ONLY `crates/regolith-lower/src/lib.rs` this pass (the
crate's 6 top-level pipeline entry points: join_physical_lines,
parse_sources, lower, lower_with_lint_config, lower_and_discharge,
lower_and_discharge_with_lint_config) as a fully-real slice: new
docs/modules/regolith-lower.md (anchors per symbol, linked from
docs/modules/README.md), frob:doc edges on all 6, frob:tests bindings on
3 existing unit tests plus 2 new small unit tests written for the two
previously-untested lint-config wrapper functions, and a new
crates/regolith-lower/tests/integration.rs (TEST003). cargo fmt/clippy/
test all clean for regolith-lower after the change. The REST of
regolith-lower (38 more files, ~496 COV001/~440 TEST001 remaining in
that crate alone) and every crate after it in the stated order (syntax,
oblig, diag, qty, sem, ir, ls, api) are UNSTARTED -- this ticket stays
in-progress; do not close it. Per FROBLEMS.md, TEST001/TEST003 bindings
in this crate are correctly-scoped but cannot validate against the rust
test collector until the upstream frob fix lands; re-check counts after
any frob binary upgrade before assuming a binding is dead.

Add frob:doc edges backed by new docs/modules/<crate>.md module-contract
docs (linked from docs/index.md, keeping DOC001 at 0), and frob:tests
bindings on existing or new unit/integration tests, crate by crate, until
COV001/TEST001/TEST003 are 0 under crates/**. Re-run frob check --only
gates after each crate and confirm the crate's counts hit 0 with no new
rule ids introduced.

Origin: frob enforcement adoption sweep (frob check --only gates dry run);
scope widened by lane L2 of the crates/** frob-adoption campaign.

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
state: done
kind: docs
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- docs/**
- tickets.md
- TODO.md
evidence:
- cmd:bash -c 'frob ticket list >/dev/null && frob ticket doable >/dev/null' exit=0
  sha256=e3b0c44298fc
attachments: []
acceptance:
- frob ticket list parses clean; frob ticket doable shows correct set; frob check
  --only gates reports DOC001=0 and no ticket/queue errors
threat: null
```
## Done report

Part A: created T-0004..T-0030 (27 tickets) for every WO with
`Status: open` in `docs/workflow/work-orders/` plus the two
cycle-36 residual WOs still queued in TODO.md (WO-123, WO-124) and
two non-WO queue items (docs/README currency sweep, coordinator
visual acceptance), each with `scope:`/`blocked_by:`/`acceptance:`
mirroring the WO's own `Depends:` line and pointing at its doc
rather than duplicating it. Rewrote TODO.md's DISPATCH QUEUE section
to point at `tickets.md`/`frob ticket doable` instead of an inline
block (the old block had drifted across five closed cycles without
being pruned).

Part B: see T-0001's own Done report -- DOC001 256 -> 0 via
docs/index.md + four new index READMEs + linkifying six existing
per-track README tables.

Verification: `frob ticket list` parses all 31 tickets with no
errors; `frob ticket doable` returns exactly the unblocked set
(T-0001..T-0007, T-0012..T-0015, T-0017, T-0021, T-0023, T-0024,
T-0026, T-0029, T-0031 at time of check) -- power/traced-profile/
waveform/sim chains correctly excluded pending their blockers;
`frob check --only gates` shows 0 DOC001, 0 new DOC002, and no
ticket-ledger parse errors (COV003 or otherwise). `make check`-
equivalent gate run: cargo-check/clippy/fmt/test all still pass,
810 Rust tests green.

<!-- ticket:T-0032 -->
```yaml
id: T-0032
title: 'campaign: python+periphery annotation sweep (waves W2-W3)'
state: in-progress
kind: docs
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- python/regolith/**
- tools/**
- editors/vscode/**
- demos/*.py
- examples/**
- tests/**
- docs/modules/**
- pyproject.toml
- frob.toml
evidence: []
attachments: []
acceptance: []
threat: null
```

<!-- ticket:T-0033 -->
```yaml
id: T-0033
title: Convert INV-19 and INV-27 to checked invariants (enforcing-site analysis)
state: queued
kind: invariant
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- invariants/**
- crates/regolith-lower/**
- python/regolith/orchestrator/**
evidence: []
attachments: []
acceptance:
- 'INV-19: anchor the promises-not-actuals seam (harness_lower.rs / translate.py)
  after reading the escalation-edge wiring'
- 'INV-27: decide the anchor posture for an absence-proof invariant (owner input)
  or record anchor-less-by-design'
threat: null
```

<!-- ticket:T-0034 -->
```yaml
id: T-0034
title: 'design: lithos.strata system model + sys audit wiring'
state: in-progress
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- design/**
- docs/workflow/strata-system-model.md
- docs/index.md
evidence: []
attachments: []
acceptance: []
threat: null
```

## Done report

Landed `design/lithos.strata`: 10 nodes (rust_core, ffi_bridge,
regolith_py, stdlib_records, tooling, demos, vscode_ext, feldspar_pack,
kicad_cli, hdl_tools, operator), 14 flows, 9 claims, 4 assumes, 6
in-design waives, plus `docs/workflow/strata-system-model.md` (companion
doc: node rationale, the AD-4 flow-graph-vs-code-property distinction,
and a "known gaps, not gamed away" section) and one new link from
`docs/index.md`.

Divergences from the coordinator draft, each verified against real code:
- AD-4 CONFIRMED by direct grep (`grep -rn "_core" python/regolith
  --include=*.py`): `compiler.py:23` is the only non-comment `_core`
  import. The draft's `assert c_only_bridge_ffi noflow regolith_py ->
  rust_core` was REFUTED by `frob sys audit` on first run -- that path is
  the bridge's whole point, not a violation of it. Replaced with `assert
  c_reaches_rust_via_bridge reach regolith_py -> rust_core`; AD-4's real
  guarantee (no file but compiler.py imports `_core`) is a code-level
  property enforced by `make guard-core`'s grep gate, not something the
  flow graph can independently prove (the compiled `_core.abi3.so` sits
  outside `crates/**`, so tier-2 conformance can't see that import
  either).
- regolith_py kept as ONE node (draft's own suggestion, taken): verified
  backends/cli/harness/orchestrator/realizer/magnetite/docgen cross-import
  each other in both directions; a per-subpackage split would fight that
  real cycle and surface as SYS003 noise.
- ffi_bridge's code glob had to be the single file `compiler.py` rather
  than folded into `python/regolith/**`, and regolith_py's glob had to be
  enumerated one level deep (excluding compiler.py) -- tier-2 code
  binding requires exactly one node per file; the naive nested-glob
  version produced `AmbiguousCodeBinding`.
- Added a `hdl_tools` node (verilator/iverilog, distinct from `kicad_cli`)
  since the real call sites are disjoint (harness/models/hdl/*,
  backends/hdl.py vs. realizer/elec/*, backends/elec*.py).
- Added an `operator` node (`trust foreign`) purely so THREAT003's
  mitigation-chokepoint check has a real foreign-trust source for the
  four `weakness:CWE-78:<node>` assumes -- mirrors feldspar's
  `regolith_consumer`.
- Added two SYS003-driven flows not in the draft: `tooling ->
  stdlib_records` (tools/health/consistency.py, docs_agreement.py import
  `tools.stdlib.organization`) and `tooling -> demos`
  (tools/health/consistency.py, demos.py import `demos.run_all`).

Audit gaps closed (fix vs. waive):
- FIXED (real capability declared): `net` on regolith_py
  (magnetite/client.py's httpx RegistryClient, cli/app.py's file://
  transport); `fs`/`env`/`ffi` on rust_core (regolith-ls integration test
  fs write, REGOLITH_LS_LOG env read, regolith-py pyo3 crate); `env` on
  tooling (REGOLITH_UPDATE_GOLDEN); `exec`/`fs`/`env` on vscode_ext
  (cli-runner spawns, test-fixture fs, dev-script env).
- WAIVED (scanner false positive, `SYS100:eval`): ffi_bridge,
  stdlib_records, demos -- all three are the English word
  "eval"/"evaluated"/"evaluator" inside comments/docstrings/identifiers,
  verified by grep to have zero real `eval(` call sites.
- WAIVED (scanner blind spot, `SYS101:ffi`): ffi_bridge -- the ffi
  capability is real (compiler.py:23) but the scanner has no needle for
  a compiled-extension import; same posture as feldspar's core_api node.
- WAIVED (`LINT004`, no real kill-switch yet): regolith_py, demos,
  tooling, vscode_ext -- no REGOLITH_NO_EXEC/REGOLITH_OFFLINE flag exists
  today (existing REGOLITH_* vars are unrelated knobs, verified by grep).
  Filed **T-0035** as the follow-on ticket to add one, mirroring
  feldspar's FELDSPAR_CCX/FELDSPAR_NGSPICE precedent (T-0016 there).
- DISCHARGED (`THREAT003` CWE-78, assume+owner+review): regolith_py,
  demos, tooling, vscode_ext -- each `assume "weakness:CWE-78:<node>"
  noflow operator -> <node> owner logan review "2026-10-18"`. Verified
  (procio.py/toolenv.py): every spawn's argv is built from a
  toolenv-resolved binary path plus typed `ToolArgs.emit()` fragments,
  never a shell string, never operator-authored text concatenated into
  argv, always with a mandatory explicit timeout (WO-153, D264).

AD-4 finding: NONE -- confirmed clean by direct grep, no violation.

Bindings added in source: none needed (no `frob:channel`/`frob:boundary`/
`frob:secret` comments were required; every capability closed via the
strata model's own `may`/`waive` clauses).

FROBLEMS.md entries: none needed -- no gap required an out-of-band
FROBLEMS record; every finding closed via fix or in-design waive with a
named follow-on ticket (T-0035).

Verification: `frob sys audit` exits 0, "PROVED (4 waived) -- zero
UNWAIVED gaps" for both self-conformance and exhaustiveness views.
`frob check --only gates` after the change: 0 errors, 388 warnings, 299
waived (pre-change baseline: 0 errors, 387 warnings, 299 waived -- 1 net
new warning, outside `design/**`/`docs/workflow/strata-system-model.md`/
`docs/index.md`, same PERF/COV/TEST rule-id families as baseline). 0
SYS-family (SYS001-004) violations. DOC001/DOC002 both 0, unchanged.
cargo-check/clippy/fmt/test all pass (869 tests).

<!-- ticket:T-0035 -->
```yaml
id: T-0035
title: add REGOLITH_NO_EXEC/REGOLITH_OFFLINE kill-switch flags for procio/toolenv
  exec+net capabilities
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope: []
evidence: []
attachments: []
acceptance: []
threat: null
```
Follow-on from T-0034 (lithos.strata system model): frob sys audit's LINT004 flags regolith_py/demos/tooling/vscode_ext for holding exec (and regolith_py's net) capability with no declared kill-switch attr. No REGOLITH_NO_EXEC or REGOLITH_OFFLINE flag exists today (grep verified: only REGOLITH_LOG/REGOLITH_UPDATE_GOLDEN/REGOLITH_OPTIMIZE_BUDGET_EVALS/REGOLITH_DEBUG_TAPS exist, none of which disable subprocess spawning or network fetches). Add a real disable flag honored by procio.py's run_argv/run_tool and magnetite/client.py's RegistryClient, then update design/lithos.strata to name it and drop the in-design LINT004 waivers.
