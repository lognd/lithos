# WO-131 -- One code space + `regolith explain <code>` (D247, extends AD-7; F147)

Status: open
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
