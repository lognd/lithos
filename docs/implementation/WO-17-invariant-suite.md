# WO-17: The invariant test suite

Status: in-progress (26 of 27 invariant families real+green; only INV-19
fully xfail, and INV-26 partially real -- 4 of its 6 enumerated defaults
have real end-to-end loud-failure fixtures, the other 2 are honest
tracked xfails with reopen criteria). Each xfail carries an accurate
blocker reason in its module. Flip to done only when every INV test is
real+green (no xfail, no stub).

Cycle 15 (candidate/discharge + hint droppability): INV-03 flipped to a
real fixture. `@hint(...)` is now a typed verdict-inert `HintStmt`
(regolith-syntax; `@`/`AtTok` lexed, statement-start dispatch, grammar.ebnf
`hint-stmt`), and the orchestrator translate pass now recovers the
comparator from a `require`-placeholder claim's `rhs` (`">= 6"`), which
was the true blocker behind `resolutions=0`: every obligation deferred
with `unsupported_op` because the core sets `op="require"` and carries the
comparator in the predicate. With that fixed the harness candidate loop
discharges real verdicts through `orchestrator.build`, so INV-03 discharges
a resolved beam design twice (with and without `@hint`/`policy: prefer`)
and diffs the verdict set -- identical, with the obligation content hash
byte-invariant. INV-26 now covers four reachable defaults (eager
candidate acceptance -> violated/indeterminate loud + release-gated;
canonical `any` -> E0502 loud; free-variable resolution -> the sheet-metal
DFM pack resolves a `free` bend radius to the manufacturable minimum, and a
tighter demanded window is violated + release-gated; local tolerance
allocation -> a `worst_case` stack-up model sums the locally-allocated
contributor bands and a chain that cannot close is violated + release-gated)
and honest-xfails the two still blocked on conformance discharge and
derived-workload lowering (WO-12). Each real default carries a negative
control proving it is not a blanket rejection.

Progress board (cycle 12+): GREEN end-to-end = INV-01 (evidence binding,
incl. mutation half), INV-09 (corner conservatism, harness-side worst
corner), INV-10 (reproducibility), INV-13 (conformance obligation
emitted AND discharge half: a spec contradicted by its hand-written impl
FAILS equivalence via the Python harness conformance-refinement model,
`harness.models.conformance`), INV-14 (trust totality), INV-17 (all four L1 classes:
E0101/E0102/E0103/E0104), INV-20 (per-subject check gating), INV-21
(resolution provenance), INV-22 (foreign-content pinning), INV-24
(release-gate totality), INV-25 (coverage honesty), INV-27 (file-layout
invariance). STILL xfail (16, blocker named in each module's reason):
INV-02/12 (no waiver/assume/accept ledger, sec. 8); INV-03/06/16
(hint/scope/converter bodies opaque, WO-05 + query/profile wiring);
INV-04/05/23 (predicted-delta symmetry/modifies/regions from opaque
domain bodies, WO-05 BE-7); INV-07/08/15/19 (contract IR / empty
SystemNodes, WO-12); INV-11 (generic use-site typing, WO-05; owned
separately); INV-18 (query resolution / E0301, WO-08); INV-26 (defaults meta:
2 of 6 sub-defaults -- implicit `by spec` + derived workloads -- still on
conformance discharge / derived-workload lowering, WO-12).
Depends: WO-06, then grows with every other WO
Language: both (placement per 00-architecture AD-11) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/13-invariants.md (normative)

## Goal

One executable test family per ledger invariant (INV-1..27), living in
`tests/invariants/`, named `test_inv_NN_*`. This suite is the
implementation's contract with the spec: **a spec change that alters a
proof argument must change this suite in the same commit**, and a WO
is not done while it reddens any invariant test it enables.

## Shape

- Each invariant gets a module docstring quoting its ledger statement
  and listing which WOs provide its mechanism.
- Tests land incrementally: when the mechanism does not exist yet, the
  test is written and marked `xfail(reason="WO-nn pending")` -- the
  suite doubles as an implementation progress board.
- Fixtures live beside the tests; deliberate-violation fixtures (the
  "test" column of each ledger entry) are the priority: mutate an
  obligation key component (INV-1), apply each ladder rung to a
  violated claim (INV-2), strip hints and diff verdicts (INV-3),
  symmetric-subject/asymmetric-givens extension refusal (INV-4),
  lying feature-class delta (INV-5), sibling-observation channels
  (INV-6), boundary widening (INV-7), base-perturbing target (INV-8),
  double-build identity diff (INV-10), per-point failure under
  monomorphization (INV-11), waiver match-set growth + expiry
  (INV-12), spec-contradicting extern (INV-13), under-tier deviation
  (INV-14), one leak per ledger (INV-15), converter loop fixtures
  (INV-16), L1 violation classes (INV-17), ambiguity classes (INV-18),
  internal-edit isolation (INV-19), gated-invocation counting
  (INV-20), lockfile totality over the examples corpus (INV-21),
  pin-drift halts (INV-22), region intrusion classes (INV-23),
  release-gate enumeration (INV-24), coverage-gap indeterminacy
  (INV-25), the enumerated-defaults loud-failure family (INV-26), and
  the file-split identity diff (INV-27: split a golden example across
  two files; verdicts, lockfile rows, and evidence keys identical).
- INV-9 (corner conservatism) is a *per-model* obligation: this suite
  provides the harness (corner sweep vs model's selection) that every
  model pack must pass; the pack CI runs it, not just ours.

## Acceptance

- Suite skeleton complete: 27 modules, each with its ledger quote and
  at least its primary deliberate-violation fixture (xfail where
  mechanisms are pending).
- CI wiring: `make check` runs the non-xfail subset; a report lists
  xfail counts per invariant (the progress board).
