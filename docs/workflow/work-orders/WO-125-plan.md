# WO-125 dispatch plan (working checklist, agent-authored)

Read: docs/workflow/README.md dispatch protocol, 00-architecture.md
(AD-1..31, esp AD-4/5/6/17/22/25), WO-125 body, charter 40 secs 1/2/5,
D237/D239 (cycle-36 design log).

## Leaf decomposition

Deliverable 1 (profile plumbing):
- [x] `ShipManifest.profile: Literal["release","debug"]="release"` field
      (manifest.py), threaded through `build_manifest`.
- [x] `ship()` gains `profile: Literal["release","debug"]="release"` kwarg;
      records on manifest.
- [x] CLI: `regolith ship --profile {release,debug}` (no collision --
      `ship` has no existing `--profile`).
- [x] CLI: `regolith build` already owns `--profile` for the WO-54 COST
      profile (different concept, same flag name) -- collision. Resolved
      by naming this WO's build-side flag `--emit-profile` (build's
      emission augmentation is a build-time concept too, per charter 40
      sec 1's `build --profile debug` wording, but the existing flag
      cannot be repurposed without breaking WO-54). Documented here, not
      escalated to coordinator: pure CLI-ergonomics naming call, no
      schema/architecture stakes.
- [x] `release_gate_refuses_debug_evidence()` helper (manifest.py or
      ship.py): a debug-profile manifest fails `verify_manifest`'s
      release-evidence check with a named `BackendError` kind
      (`debug_not_release_evidence`).
- [x] package index (package.py) records profile alongside gate/parity.
- [ ] CUT: full mainboard_mx + one more elec fleet-wide `--profile
      debug` run producing placed tap header + test points (needs
      deliverables 3/4 below).

Deliverable 2 (tap model + deriver) -- full leaf, pure + unit tested:
- [x] `regolith.backends.debug_taps` module: `Tap` (frozen pydantic:
      channel, kind, target_path, why, source: derived|explicit),
      `TapSet` (allocated + named `unallocated`).
- [x] `derive_taps(claims, explicit, capacity)`: rank by claim family
      (rails, clocks, buses, rest), dedup by target_path, explicit wins
      channels first, unknown explicit net path -> diagnostic (Result/
      Err, never silent), deterministic ordering (sorted target_path
      tiebreak), capacity-limited with `unallocated` rows for overflow.
- [x] unit tests on fixtures (tests/backends/test_debug_taps.py).

Deliverable 3 (tap header pinout record): CUT -- needs a new std.elec
pattern record (authoring + citation infra, AD-37 spirit). Escalate as
F-placeholder; too large for this pass without the record authoring
seam already in front of me. Recorded, not silently dropped.

Deliverable 4 (board augmentation): CUT -- depends on 3. Escalate.

Deliverable 5 (firmware augmentation: debug_taps.h): CUT -- depends on
2 being wired into a real per-project build call site (which subject's
claims feed the deriver is a per-project decision I don't have fixture
data for beyond the corpus scan this pass didn't have budget for).
Escalate; deriver itself (deliverable 2) is ready for a follow-up WO to
wire in.

Deliverable 6 (HDL augmentation): CUT -- same dependency as 5. Escalate.

Deliverable 7 (INV-32): CUT -- an invariant with proof argument must
land WITH its real enforcing check (house rule: nothing converts
violated->discharged, and CLAUDE.md forbids a placeholder proof). Since
3/4/5/6 are cut, there is no real tap-map/artifact pair to check yet.
Do NOT touch 13-invariants.md this pass. Escalate.

Deliverable 8 (docs): partial -- charter 40 already exists (this WO's
own spec); add a short cross-ref note in charter 40 pointing at the cut
items + a one-line guide stub. Feasible, low risk.

## Acceptance criteria coverage

- Fleet-wide `--profile debug` succeeds / census identical: PARTIAL --
  covered for the plumbing (manifest/CLI/gate refusal), NOT for real
  tap emission (cut). Census/verdict equality is untouched by this
  pass (no obligation/claim path is touched at all -- pure emission-
  layer addition), so D206 is safe by construction, not by a new test
  asserting fleet-wide census equality across profiles (that test
  needs a real debug emission path to be meaningful; a no-op profile
  flag trivially passes it, which would be a hollow acceptance test --
  cut alongside 4/5/6, escalated rather than faked).
- Release byte-identity: covered by regenerated goldens (manifest.json
  gains a `profile` field; individual artifact FILE bytes unchanged --
  confirmed by diffing golden artifact files other than manifest.json).
- mainboard_mx tap header/test points/firmware table/INV-32: CUT,
  escalated.
- Determinism per profile / `make check` green: covered for the
  landed subset.

## Escalation record (for coordinator, placeholder F-number)

F-WO125-1: WO-125 deliverables 3-7 (tap header pinout record, board/
firmware/HDL augmentation, INV-32) are CUT from this pass -- they form
one dependent chain (pinout record -> placement -> firmware/HDL ->
INV-32) too large for this dispatch's budget beyond the foundational
profile plumbing (deliverable 1) and the pure tap deriver (deliverable
2, fully done + unit tested, ready to be wired in). Recommend a
follow-up WO-125b scoped to exactly that chain, starting from the
landed `regolith.backends.debug_taps.derive_taps`.
