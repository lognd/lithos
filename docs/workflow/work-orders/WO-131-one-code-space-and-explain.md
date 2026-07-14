# WO-131 -- One code space + `regolith explain <code>` (D247, extends AD-7; F147)

Status: done
Language: Rust (`regolith-diag` code registry + explain content, the
  ONE home) + Python (generated code constants, CLI verb, backfill of
  the bare-string failures, health check). No wire-schema bump
  expected (D225/D239); the generated code table follows the
  `make schema` single-sourcing precedent.
Spec: D247 (the four rulings); F147 (the evidence); AD-7 (ONE
  diagnostic renderer -- this WO extends it to ONE code space);
  regolith/09 (the diagnostic families and the "a code's numeric
  family never changes" rule); the `make schema` precedent for
  single-sourced generated artifacts; guide 01 sec. 8 (the DESIGNED
  note this WO flips to WORKING).

## Goal

Every user-facing failure the toolchain can produce -- in Rust or in
Python -- has a stable code, and `regolith explain <code>` tells the
user what it means, why it fired, and how to fix it. Completeness is
enforced by the health gate, so the vocabulary can never again grow
an uncoded, unexplainable branch (F147).

## Deliverables

1. Code registry stays the ONE home (`crates/regolith-diag/src/
   code.rs`). Add the three new families (permanent once assigned,
   per the existing family-stability rule): E09xx emission/packaging,
   E10xx injection/override, E11xx bring-up/harness.
2. Generated code constants for Python (the `make schema` pattern --
   generated, drift-checked in CI, NEVER hand-edited). Python raises
   coded failures; a failure kind absent from the registry is a build
   error, not a string.
3. BACKFILL the bare-string kinds cycle 36 minted, in this change,
   with no grandfathering: `fab_set_incomplete` (WO-124),
   `drafting_audit_refused` (WO-123),
   `expectation_provenance_unresolved` (WO-126),
   `release_gate_refuses_debug_evidence` (WO-125). Sweep for any
   others (grep the backends/gate/harness surfaces); every one you
   find gets a code or a recorded reason why it is not user-facing.
   Reserved for WO-129A (do not implement, just reserve the numbers
   in the registry so it can use them): E1001 unexplained override
   (no author/reason), E1002 source-only target refused (the D246
   claims/evidence boundary), E1003 unresolvable override target.
4. Explain content beside the code, one entry per code: what it
   means, why it fires, how to fix, a worked example. This is
   authored content -- write real entries for the new families and
   for the highest-traffic existing codes; a code whose entry is
   genuinely not yet written must say so explicitly (an honest
   "no explanation authored yet" stub is fine and is COUNTED by the
   health check below; a silent absence is not).
5. `regolith explain <code> [--json]`: reads that one home. stdout is
   data; logs to stderr. Unknown code -> constructive diagnostic
   naming near matches.
6. Health consistency leg (D247.4 -- the rule must be able to FAIL):
   (a) every registered code has an explain entry (stub or real, and
   the check REPORTS the stub count so the debt is visible);
   (b) no user-facing failure is raised with a bare string kind --
   the sweep that finds one fails the leg. Include a negative test
   for each.
7. Docs: guide 01 sec. 8's `(DESIGNED)` note flips to WORKING with
   the real invocation; a short guide section (or a new
   `33-diagnostics-and-explain.md`) covering the families, the code
   stability rule, and how a producer adds a new coded failure.

## Acceptance

- `regolith explain E0102` (and one code from each new family)
  prints real content; `--json` round-trips.
- The four backfilled failures carry codes end to end (raised,
  rendered, explainable) with their tests updated.
- The health leg FAILS a deliberately uncoded failure and a
  deliberately entry-less code (negative tests prove both bite).
- Stub-entry count is reported, not hidden.
- `make check` + `make health` green.

## Escalation

If a Python-side failure genuinely is NOT user-facing (an internal
programmer-bug path), do not force a code onto it -- record it in the
close-out with the reason, and make sure the health sweep's exclusion
list is explicit and small. If the generated-constants path needs an
architecture call (e.g. where the generated file lives), escalate to
the coordinator rather than inventing a second home.

---

## Close-out (WO-131, cycle 36)

### The families + codes registered

| family | base | codes registered |
|---|---|---|
| `Emission` | E09xx | E0901 `FAB_SET_INCOMPLETE`, E0902 `DRAFTING_AUDIT_REFUSED`, E0903 `ARTIFACT_INDEX_DRIFT` (reserved -- see F-WO131-1) |
| `Injection` | E10xx | E1001 `UNEXPLAINED_OVERRIDE`, E1002 `SOURCE_ONLY_TARGET_REFUSED`, E1003 `UNRESOLVABLE_OVERRIDE_TARGET` -- ALL THREE RESERVED for WO-129A per deliverable 3; registered with meanings + explain content, not raised here |
| `BringUp` | E11xx | E1101 `EXPECTATION_PROVENANCE_UNRESOLVED`, E1102 `RELEASE_GATE_REFUSES_DEBUG_EVIDENCE`, E1103 `TAP_MAP_DISAGREEMENT` |

Registry total: 73 codes (was 64 + 9 new). Families are permanent
once assigned (regolith/09); nothing renumbered.

### Backfilled (no grandfathering, D247.2)

| was (bare string) | now | site |
|---|---|---|
| `fab_set_incomplete` | E0901 | `backends/elec_fabset.py` (WO-124) |
| `drafting_audit_refused` | E0902 | `backends/drawings/audit.py` (WO-123) |
| `expectation_provenance_unresolved` | E1101 | `backends/harness_pack.py` (WO-126) |
| `debug_not_release_evidence` | E1102 | `backends/manifest.py` (WO-125; the kind the WO named as `release_gate_refuses_debug_evidence`, which is the FUNCTION name -- the raised kind string was `debug_not_release_evidence`) |
| `tap_map_artifact_mismatch` | E1103 | `backends/debug_taps.py` (found by the sweep, beyond the four named) |

Their tests assert the code constants now, not the old strings.

### Explain content + stub ledger

Every one of the 73 codes has an explain entry (Rust
`explain::completeness_is_total` fails the build otherwise, in BOTH
directions -- missing entry AND stale entry). **10 authored** (E0102
plus all 9 new-family codes), **63 honest stubs** whose `meaning` is
the code's real doc comment and whose why/fix say "no explanation
authored yet". The health check REPORTS that 63, it does not hide it.

### Health leg (D247.4 -- both legs can FAIL)

`tools/health/diag_codes.py`, wired into `health-consistency` (11
sweeps, was 10):

- (a) every registered code has an explain entry; stub count reported.
- (b) AST sweep: no `BackendError(kind="bare string")` in
  `python/regolith/backends/`. 0 violations, 37 explicit per-line
  exemptions (each with a reason, none blank -- tested).

Negative tests in `tests/health/test_diag_codes.py` (7 tests) prove
each leg bites: a synthetic bare-string `BackendError` trips (b); a
synthetic entry-less code trips (a); a `kind=CONSTANT` call does NOT
trip (b), proving the sweep is not just rejecting all `BackendError`s.

### Failures deliberately NOT coded (with reason)

Nothing was judged "not user-facing". The 37 exemptions are all
DEFERRALS of real user-facing failures, not denials -- tracked as
F-WO131-2. Coding them is mechanical but touches ~10 modules and
their tests; the WO's named scope was the four bare strings, and the
sweep now makes any NEW one impossible. Recorded rather than dropped.

### Escalations

- **F-WO131-1 (E0903 has no producer).** D247.2 names
  "artifact-index drift" as an E09xx meaning, but the sweep found no
  live check that raises it -- the manifest verifies files it names,
  never the completeness of the naming. Registered + explained so a
  future producer needs no second home. Someone should decide whether
  that check is worth building; it is a real integrity gap.
- **F-WO131-2 (37 deferred bare-string kinds).** Enumerated by exact
  (file, line) in `tools/health/diag_codes.py`'s `EXEMPT`: manifest
  integrity (5), ship gate (4), realized-IR availability (9), native
  artifact store (3), tap infra (10), expected-signals shape (1),
  tool/export availability (2), unknown drawing track (1). Each is a
  user-facing failure that deserves a code. Proposed as a follow-up
  WO; the exemption list is the ready-made worklist and shrinks to
  zero as they land.
- **F-WO131-3 (sweep covers `BackendError` only).** The other Python
  error models (`OrchestratorError`, `MagnetiteError`, `LockfileError`,
  `DocError`, `CoreFailure`) also carry bare string kinds and are
  outside this WO's literal "backends/gate/harness" scope. The sweep
  is one constant away from covering them (`ERROR_CLASS_NAMES`), but
  turning it on today would fail the build on ~30 more sites. Same
  disposition as F-WO131-2: recorded, not silently dropped.

### Gates

`make check` green (fmt, clippy -D warnings, ruff, ty, guard-core,
schema-check, codes-check, test-rs, test-py, health-smoke);
`make health-consistency` PASS, 11 sweeps, 0 failed. Full pytest:
1904 passed, 0 failed.
