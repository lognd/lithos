# WO-17: The invariant test suite

Status: todo
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
