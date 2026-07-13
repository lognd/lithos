# WO-106 -- The repo health gate: make health (fleet + demos + consistency)

Status: done (2026-07-13: `make health` composes the four legs
  cheapest-first; fleet 15/15 release-green + hash-clean ship on the
  census golden; demos + consistency green; `make check`+`make health`
  green. Close-out ledger at foot.)
Language: Python (tests + scripts/ + Makefile)
Spec: D219 (the health-gate ruling -- read first); charter 38
  sec. 4 (the fleet acceptance shape); D210 (fleet definition);
  D218.1/WO-108 (demo proof manifests); AD-11 (golden corpus
  tradeoff -- fleet census joins it).

## Goal

ONE command (`make health`) proves the owner's bar and keeps it
proven, composing four legs cheapest-first, each independently
runnable, each reporting one standardized typed summary row (leg,
ok, counts, evidence pointer): `check` (existing code gates),
`fleet` (every D210 project --release green + verify-clean
package, census golden), `demos` (every live WO-108 proof manifest
matches), `consistency` (D/F-number uniqueness, WO-Status-vs-TODO
agreement, extension single-sourcing, golden byte-drift, memo/
waiver ledger integrity incl. every `by doc(...)` resolving and
zero stale waivers, stale-worktree detection). Refactor existing
scattered checks INTO the legs rather than duplicating them.

## Deliverables

1. `make fleet` + `tests/fleet/test_release_fleet.py`:
   discovers D210 fleet projects (by magnetite.toml presence,
   minus explicit exemptions), runs `build --release` + `ship`
   per project, asserts rc/release_ok/manifest-schema-valid/
   `ship --verify` clean/index present/every family
   present-or-named-absent.
2. Determinism leg: ship twice for one mech-heavy + one
   elec-heavy project; byte-compare every deterministic artifact
   (GLB, SVG, DXF, PDF, fake-tier kicad_pcb, index, ledgers).
3. Tracks leg: every `examples/tracks/**` non-advice file builds
   `--release` green; negative corpus still fails exactly as
   encoded (reuse the existing negative-corpus runner).
4. Census golden: `tests/golden/data/fleet_census.json` --
   per-project {obligations, discharged, accepted_deviation,
   violated, below_floor, families_shipped}; regeneration is the
   ordinary golden flow with the cycle-33 diff-review rule.
5. Wiring: `make check` gains a cheap fleet-smoke (one project);
   full `make fleet` is its own target (runtime documented);
   CI note in 10-test-infra-and-ci.md.
6. Docs: guide "shipping your project" chapter gains the fleet
   example; TODO/START-HERE one-liner update.

## Acceptance criteria

- `make fleet` green on final cycle-34 master, twice in a row,
  from a clean checkout.
- Census golden enrolled; a synthetic new bare waiver in a
  fixture project flips the census (proven by test) -- acceptance
  creep cannot land silently.
- `make check` green.

## Close-out ledger (WO-106 execution, 2026-07-13)

Delivered the D219 shape: `make health` composes four legs cheapest-
first, each runnable alone (`health-check` aliases `check`;
`health-fleet`/`health-demos`/`health-consistency`), each emitting ONE
standardized `LegSummary` row (leg, ok, counts, evidence) and together a
machine-readable `.regolith/health/health_report.json`. Scripts live in
`tools/health/` (the repo's existing `tools/` convention). The refactor
rule held: legs CALL existing gates (`make check`, the WO-108 runner +
`tests/test_wo108_demos.py`, the golden byte-drift check) rather than
duplicating them.

### Legs
- **check** (`tools/health/check.py`): runs `make check`.
- **fleet** (`tools/health/fleet.py` + `tests/health/test_health.py`):
  discovers the 15 D210 projects (magnetite.toml, no exemptions), runs
  `build --release --json` + `ship --build [--spec]` per project, asserts
  release_ok + hash-clean package + zero stale waivers + families
  recorded, and compares the per-project census
  {obligations, discharged, accepted_deviation, violated, families} to
  the new golden `tests/golden/data/fleet_census.json` (regen via
  `REGOLITH_UPDATE_GOLDEN=1 make health-fleet`, diff-reviewed). The
  census reproduces WO-105's FINAL table exactly. Determinism sub-leg
  ships dune_buggy twice byte-identical AND asserts design_hash is stable
  across checkout paths.
- **demos** (`tools/health/demos.py`): the WO-108 runner + completeness
  test, unchanged.
- **consistency** (`tools/health/consistency.py`): D/F-number
  uniqueness (addenda `-a`/"addendum" allowed), WO-status-vs-TODO
  false-done, extension single-sourcing (core FFI is authoritative; no
  competing Python registry), golden byte-drift, `by doc(...)` + stale-
  waiver ledger integrity (reads the fleet cache), stale-worktree
  (report-only).

`make check` gains a cheap `health-smoke` (timber_pavilion + one demo
probe + the build-free sweeps). Full `make health` runtime ~15-25 min
(fleet dominates). Guide 23-health-gate.md + CI note (own scheduled
health job) + TODO one-liner landed.

### Findings (placeholder labels; no design-log numbers self-assigned)

- [HEALTH-F1] design_hash was checkout-path-sensitive. `ship._design_hash`
  hashed ABSOLUTE source-path strings, so a byte-identical design shipped
  a different design_hash from each worktree, drifting committed manifests
  (demo6 confirmed pre-existing on clean master). FIXED here (coordinator-
  directed, part of the determinism leg): hash project-relative POSIX
  paths, order-preserving, content-sensitive; demo6 manifest/PROOF
  regenerated stable. Cross-directory stability is now asserted by the
  determinism sub-leg + `tests/health` unit tests. This alters shipped
  design_hash values (expected, reviewed) -- no test pinned a real one
  (test_manifest uses fakes; 23 ship/manifest tests still green).
- [HEALTH-F2] the fake-KiCad tier did not create its output parent dir,
  so a fresh-checkout elec ship failed with FileNotFoundError before
  writing `.regolith/board/board.kicad_pcb`. FIXED (small non-verdict
  machinery fix, the WO-105 ship-fix precedent); mainboard_mx now ships
  its boards+drawings families, the last project to reach a clean gate.
- [HEALTH-F3] WO-57's Status line was never flipped: DONE in the cycle-30
  TODO queue, its file still `todo`. The consistency sweep caught it;
  flipped to done in the same change (the gate's first real catch).
- [HEALTH-F4] the repo deliberately keeps a worked WO's Status prose
  conservative (`in-progress`/`honest-partial`/`partial`/`phase ...`)
  after queue integration to name its residual, so a naive WO-status-vs-
  TODO equality is red on master for legitimate reasons. The gating
  check is therefore narrowed to the dangerous lie only (queue marks
  done a WO whose file is `todo`); the softer residual desyncs are
  reported non-gating. A future normalization of Status vocabulary
  would let this tighten.
